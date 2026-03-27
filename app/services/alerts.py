from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.domain.persistence.models import Alert, Event
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)
from app.services.audit import append_audit_row

ALERT_TYPE_ANCHOR_RETRY_FAILURE = "ANCHOR_RETRY_FAILURE"
ALERT_TYPE_ANCHOR_DEAD_LETTER = "ANCHOR_DEAD_LETTER"

DEFAULT_ALERT_LIMIT = 50
MAX_ALERT_LIMIT = 200
SIMULATION_BATCH_LIKE = "batch-sim-%"
SIMULATION_DEVICE_LIKE = "dev-sim-%"

ALERT_STATUS_OPEN = "open"
ALERT_STATUS_ACKNOWLEDGED = "acknowledged"
ALERT_STATUS_RESOLVED = "resolved"

_ESCALATION_ORDER = ("low", "medium", "high", "critical")


class AlertActionError(Exception):
    """Base class for alert action workflow errors."""


class AlertNotFoundError(AlertActionError):
    pass


class AlertActionConflictError(AlertActionError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class AlertRecord:
    id: int
    event_id: int | None
    alert_type: str
    severity: str
    status: str
    message: str
    raised_at: str
    resolved_at: str | None


@dataclass(frozen=True)
class AlertPage:
    total: int
    limit: int
    offset: int
    alerts: list[AlertRecord]


@dataclass(frozen=True)
class AlertActionResult:
    id: int
    status: str
    severity: str
    resolved_at: str | None
    audit_id: int


def _suppression_window_seconds() -> int:
    raw_value = os.getenv("ANCHOR_ALERT_SUPPRESSION_SECONDS", "300")
    try:
        parsed = int(raw_value)
    except ValueError:
        return 300
    return parsed if parsed >= 0 else 0


def _to_iso8601_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _normalize_limit(value: int) -> int:
    if value < 1:
        return 1
    if value > MAX_ALERT_LIMIT:
        return MAX_ALERT_LIMIT
    return value


def _normalize_offset(value: int) -> int:
    return value if value >= 0 else 0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _build_alert_record(row: Alert) -> AlertRecord:
    return AlertRecord(
        id=row.id,
        event_id=row.event_id,
        alert_type=row.alert_type,
        severity=row.severity,
        status=row.status,
        message=row.message,
        raised_at=_to_iso8601_z(row.raised_at) or "",
        resolved_at=_to_iso8601_z(row.resolved_at),
    )


def _scoped_alert_filters(*, include_simulation: bool) -> list:
    if include_simulation:
        return []
    return [
        or_(
            Alert.event_id.is_(None),
            and_(
                ~Event.batch_id.like(SIMULATION_BATCH_LIKE),
                ~Event.device_id.like(SIMULATION_DEVICE_LIKE),
            ),
        )
    ]


def _build_action_result(*, row: Alert, audit_id: int) -> AlertActionResult:
    return AlertActionResult(
        id=row.id,
        status=row.status,
        severity=row.severity,
        resolved_at=_to_iso8601_z(row.resolved_at),
        audit_id=audit_id,
    )


def _next_escalated_severity(current: str) -> str:
    lowered = current.lower()
    if lowered not in _ESCALATION_ORDER:
        raise AlertActionConflictError(
            f"Alert severity '{current}' is not eligible for deterministic escalation."
        )
    index = _ESCALATION_ORDER.index(lowered)
    if index >= len(_ESCALATION_ORDER) - 1:
        raise AlertActionConflictError(
            f"Alert severity '{current}' is already at the highest escalation level."
        )
    return _ESCALATION_ORDER[index + 1]


def create_alert(
    session: Session,
    *,
    event_id: int | None,
    alert_type: str,
    severity: str,
    message: str,
    status: str = "open",
    suppression_window_seconds: int | None = None,
) -> int | None:
    dedup_seconds = (
        _suppression_window_seconds()
        if suppression_window_seconds is None
        else max(0, suppression_window_seconds)
    )
    if dedup_seconds > 0:
        cutoff = datetime.now(UTC) - timedelta(seconds=dedup_seconds)
        dedup_query = select(Alert).where(
            Alert.alert_type == alert_type,
            Alert.severity == severity,
            Alert.message == message,
            Alert.status == status,
            Alert.raised_at >= cutoff,
        )
        if event_id is None:
            dedup_query = dedup_query.where(Alert.event_id.is_(None))
        else:
            dedup_query = dedup_query.where(Alert.event_id == event_id)

        existing = session.scalar(dedup_query.order_by(Alert.id.desc()))
        if existing is not None:
            return None

    alert = Alert(
        event_id=event_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        status=status,
    )
    session.add(alert)
    session.flush()
    return alert.id


def acknowledge_alert(*, actor: str, alert_id: int) -> AlertActionResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise AlertNotFoundError

        if alert.status != ALERT_STATUS_OPEN:
            raise AlertActionConflictError(
                "Alert can only be acknowledged from status 'open'."
            )

        alert.status = ALERT_STATUS_ACKNOWLEDGED
        alert.resolved_at = None
        session.commit()
        session.refresh(alert)

    audit_id = append_audit_row(
        actor=actor,
        action="alert.acknowledge",
        target=f"alert:{alert_id}",
        result="success",
        metadata={
            "from_status": ALERT_STATUS_OPEN,
            "to_status": ALERT_STATUS_ACKNOWLEDGED,
        },
    )
    return _build_action_result(row=alert, audit_id=audit_id)


def resolve_alert(*, actor: str, alert_id: int) -> AlertActionResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise AlertNotFoundError

        if alert.status not in {ALERT_STATUS_OPEN, ALERT_STATUS_ACKNOWLEDGED}:
            raise AlertActionConflictError(
                "Alert can only be resolved from status 'open' or 'acknowledged'."
            )

        from_status = alert.status
        alert.status = ALERT_STATUS_RESOLVED
        alert.resolved_at = _utcnow()
        session.commit()
        session.refresh(alert)

    audit_id = append_audit_row(
        actor=actor,
        action="alert.resolve",
        target=f"alert:{alert_id}",
        result="success",
        metadata={
            "from_status": from_status,
            "to_status": ALERT_STATUS_RESOLVED,
            "resolved_at": _to_iso8601_z(alert.resolved_at),
        },
    )
    return _build_action_result(row=alert, audit_id=audit_id)


def escalate_alert(*, actor: str, alert_id: int) -> AlertActionResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise AlertNotFoundError

        if alert.status not in {ALERT_STATUS_OPEN, ALERT_STATUS_ACKNOWLEDGED}:
            raise AlertActionConflictError(
                "Alert can only be escalated while status is 'open' or 'acknowledged'."
            )

        from_severity = alert.severity
        alert.severity = _next_escalated_severity(alert.severity)
        session.commit()
        session.refresh(alert)

    audit_id = append_audit_row(
        actor=actor,
        action="alert.escalate",
        target=f"alert:{alert_id}",
        result="success",
        metadata={
            "status": alert.status,
            "from_severity": from_severity,
            "to_severity": alert.severity,
        },
    )
    return _build_action_result(row=alert, audit_id=audit_id)


def query_recent_alerts(
    *,
    limit: int = DEFAULT_ALERT_LIMIT,
    offset: int = 0,
    include_simulation: bool = True,
) -> AlertPage:
    normalized_limit = _normalize_limit(limit)
    normalized_offset = _normalize_offset(offset)

    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    alert_filters = _scoped_alert_filters(include_simulation=include_simulation)

    with Session(engine) as session:
        count_query = select(func.count()).select_from(Alert)
        rows_query = select(Alert)
        if alert_filters:
            count_query = count_query.outerjoin(Event, Alert.event_id == Event.id).where(
                *alert_filters
            )
            rows_query = rows_query.outerjoin(Event, Alert.event_id == Event.id).where(
                *alert_filters
            )

        total = int(session.scalar(count_query) or 0)
        rows = list(
            session.scalars(
                rows_query
                .order_by(Alert.raised_at.desc(), Alert.id.desc())
                .offset(normalized_offset)
                .limit(normalized_limit)
            )
        )
        return AlertPage(
            total=total,
            limit=normalized_limit,
            offset=normalized_offset,
            alerts=[_build_alert_record(row) for row in rows],
        )
