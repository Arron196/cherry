from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.domain.persistence.models import (
    Alert,
    AnchorReceipt,
    Event,
    IngestRequest,
    QualityResult,
)
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)


class TraceBatchNotFoundError(Exception):
    """Raised when no trace events exist for the requested batch id."""


@dataclass(frozen=True)
class TraceTimelineEntry:
    event_id: int
    timestamp: str
    ingest_status: str
    anchor_status: str
    anchor_transaction_hash: str | None
    quality_grade: str | None
    alert_snapshot: dict[str, int]


TERMINAL_INGEST_STATES = {"ANCHORED", "DEAD_LETTER"}


def _to_iso8601_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _quality_grade(result: Any) -> str | None:
    if result is None:
        return None
    details = result.details if isinstance(result.details, dict) else None
    if details is not None:
        grade = details.get("grade")
        if isinstance(grade, str):
            return grade
    if result.status in {"A", "B", "C"}:
        return result.status
    return None


def _alert_snapshot(rows: list[Alert]) -> dict[str, int]:
    open_count = sum(1 for row in rows if row.status.lower() == "open")
    high_open_count = sum(
        1
        for row in rows
        if row.status.lower() == "open" and row.severity.lower() in {"high", "critical"}
    )
    return {
        "total": len(rows),
        "open": open_count,
        "high_open": high_open_count,
    }


@dataclass(frozen=True)
class _LatestQualityRow:
    status: str
    details: Any


@dataclass(frozen=True)
class _AlertSnapshotRow:
    total: int
    open: int
    high_open: int


def _latest_ingest_status_by_event(
    session: Session, *, event_ids: list[int]
) -> dict[int, str]:
    latest_ingest_id_subquery = (
        select(
            IngestRequest.event_id.label("event_id"),
            func.max(IngestRequest.id).label("latest_ingest_id"),
        )
        .where(IngestRequest.event_id.in_(event_ids))
        .group_by(IngestRequest.event_id)
        .subquery()
    )

    rows = session.execute(
        select(
            IngestRequest.event_id.label("event_id"),
            IngestRequest.ingest_status.label("ingest_status"),
        ).join(
            latest_ingest_id_subquery,
            IngestRequest.id == latest_ingest_id_subquery.c.latest_ingest_id,
        )
    ).all()
    return {int(row.event_id): str(row.ingest_status) for row in rows}


def _latest_anchor_by_event(
    session: Session, *, event_ids: list[int]
) -> dict[int, AnchorReceipt]:
    latest_anchor_id_subquery = (
        select(
            AnchorReceipt.event_id.label("event_id"),
            func.max(AnchorReceipt.id).label("latest_anchor_id"),
        )
        .where(AnchorReceipt.event_id.in_(event_ids))
        .group_by(AnchorReceipt.event_id)
        .subquery()
    )

    rows = session.scalars(
        select(AnchorReceipt).join(
            latest_anchor_id_subquery,
            AnchorReceipt.id == latest_anchor_id_subquery.c.latest_anchor_id,
        )
    )
    return {int(row.event_id): row for row in rows}


def _latest_quality_by_event(
    session: Session, *, event_ids: list[int]
) -> dict[int, _LatestQualityRow]:
    latest_quality_time_subquery = (
        select(
            QualityResult.event_id.label("event_id"),
            func.max(QualityResult.evaluated_at).label("latest_evaluated_at"),
        )
        .where(QualityResult.event_id.in_(event_ids))
        .group_by(QualityResult.event_id)
        .subquery()
    )

    latest_quality_id_subquery = (
        select(
            QualityResult.event_id.label("event_id"),
            func.max(QualityResult.id).label("latest_quality_id"),
        )
        .join(
            latest_quality_time_subquery,
            and_(
                QualityResult.event_id == latest_quality_time_subquery.c.event_id,
                QualityResult.evaluated_at
                == latest_quality_time_subquery.c.latest_evaluated_at,
            ),
        )
        .group_by(QualityResult.event_id)
        .subquery()
    )

    rows = session.execute(
        select(
            QualityResult.event_id.label("event_id"),
            QualityResult.status.label("status"),
            QualityResult.details.label("details"),
        ).join(
            latest_quality_id_subquery,
            QualityResult.id == latest_quality_id_subquery.c.latest_quality_id,
        )
    ).all()
    return {
        int(row.event_id): _LatestQualityRow(
            status=str(row.status),
            details=row.details,
        )
        for row in rows
    }


def _alert_snapshots_by_event(
    session: Session, *, event_ids: list[int]
) -> dict[int, _AlertSnapshotRow]:
    is_open = func.lower(Alert.status) == "open"
    is_high_open = and_(is_open, func.lower(Alert.severity).in_(["high", "critical"]))

    rows = session.execute(
        select(
            Alert.event_id.label("event_id"),
            func.count(Alert.id).label("total_count"),
            func.sum(case((is_open, 1), else_=0)).label("open_count"),
            func.sum(case((is_high_open, 1), else_=0)).label("high_open_count"),
        )
        .where(Alert.event_id.in_(event_ids))
        .group_by(Alert.event_id)
    ).all()
    return {
        int(row.event_id): _AlertSnapshotRow(
            total=int(row.total_count),
            open=int(row.open_count or 0),
            high_open=int(row.high_open_count or 0),
        )
        for row in rows
        if row.event_id is not None
    }


def query_trace_timeline(batch_id: str) -> list[TraceTimelineEntry]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        events = session.execute(
            select(
                Event.id.label("id"),
                Event.timestamp.label("timestamp"),
            )
            .where(Event.batch_id == batch_id)
            .order_by(Event.timestamp.asc(), Event.id.asc())
        ).all()
        if not events:
            raise TraceBatchNotFoundError

        event_ids = [int(event.id) for event in events]

        latest_ingest_status_by_event = _latest_ingest_status_by_event(
            session, event_ids=event_ids
        )
        latest_anchor_by_event = _latest_anchor_by_event(session, event_ids=event_ids)
        latest_quality_by_event = _latest_quality_by_event(session, event_ids=event_ids)
        alert_snapshots_by_event = _alert_snapshots_by_event(
            session, event_ids=event_ids
        )

        timeline: list[TraceTimelineEntry] = []
        for event in events:
            ingest_status = latest_ingest_status_by_event.get(event.id, "UNKNOWN")
            anchor = latest_anchor_by_event.get(event.id)
            quality = latest_quality_by_event.get(event.id)
            alert_snapshot = alert_snapshots_by_event.get(
                event.id, _AlertSnapshotRow(total=0, open=0, high_open=0)
            )
            timeline.append(
                TraceTimelineEntry(
                    event_id=event.id,
                    timestamp=_to_iso8601_z(event.timestamp),
                    ingest_status=ingest_status,
                    anchor_status=(
                        "ANCHORED"
                        if anchor is not None
                        else (
                            ingest_status
                            if ingest_status not in {"UNKNOWN", *TERMINAL_INGEST_STATES}
                            else "NOT_ANCHORED"
                        )
                    ),
                    anchor_transaction_hash=(
                        anchor.transaction_hash if anchor is not None else None
                    ),
                    quality_grade=_quality_grade(quality),
                    alert_snapshot={
                        "total": alert_snapshot.total,
                        "open": alert_snapshot.open,
                        "high_open": alert_snapshot.high_open,
                    },
                )
            )

        return timeline
