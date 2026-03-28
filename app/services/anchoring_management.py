from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.persistence.models import Audit, Event, IngestRequest
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)
from app.services.anchoring import (
    ANCHOR_STATE_DEAD_LETTER,
    ANCHOR_STATE_FAILED_RETRYING,
    ANCHOR_STATE_RECEIVED,
    run_anchor_state_machine,
)

DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200


class AnchoringManagementError(Exception):
    """Base class for anchoring management workflow errors."""


class AnchoringTaskNotFoundError(AnchoringManagementError):
    pass


class AnchoringTaskRequeueConflictError(AnchoringManagementError):
    def __init__(self, current_status: str) -> None:
        super().__init__(
            f"ingest request is not requeueable from status={current_status}"
        )
        self.current_status = current_status


@dataclass(frozen=True)
class AnchoringTaskRecord:
    ingest_request_id: int
    event_id: int
    batch_id: str
    device_id: str
    status: str
    retry_count: int
    last_error: str | None
    created_at: str


@dataclass(frozen=True)
class AnchoringTaskPage:
    total: int
    limit: int
    offset: int
    items: list[AnchoringTaskRecord]


@dataclass(frozen=True)
class RequeueAnchoringTaskResult:
    ingest_request_id: int
    status: str
    retry_count: int
    audit_id: int


@dataclass(frozen=True)
class RunAnchoringOnceResult:
    processed: int
    limit: int
    audit_id: int


def _to_iso8601_z(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _append_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    target: str,
    metadata: dict | None = None,
) -> int:
    details = {"result": "success"}
    if metadata:
        details.update(metadata)
    audit = Audit(actor=actor, action=action, target=target, metadata_=details)
    session.add(audit)
    session.flush()
    return audit.id


def list_anchoring_tasks(
    *,
    status: str,
    limit: int = DEFAULT_QUERY_LIMIT,
    offset: int = 0,
    batch_id: str | None = None,
    device_id: str | None = None,
) -> AnchoringTaskPage:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    base = (
        select(
            IngestRequest.id.label("ingest_request_id"),
            IngestRequest.event_id.label("event_id"),
            Event.batch_id.label("batch_id"),
            Event.device_id.label("device_id"),
            IngestRequest.ingest_status.label("status"),
            IngestRequest.retry_count.label("retry_count"),
            IngestRequest.last_error.label("last_error"),
            IngestRequest.created_at.label("created_at"),
        )
        .join(Event, Event.id == IngestRequest.event_id)
        .where(IngestRequest.ingest_status == status)
    )

    if batch_id is not None:
        base = base.where(Event.batch_id == batch_id)
    if device_id is not None:
        base = base.where(Event.device_id == device_id)

    filtered = base.subquery()

    with Session(engine) as session:
        total = int(session.scalar(select(func.count()).select_from(filtered)) or 0)
        rows = session.execute(
            select(filtered)
            .order_by(filtered.c.ingest_request_id.desc())
            .offset(offset)
            .limit(limit)
        ).all()

    return AnchoringTaskPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            AnchoringTaskRecord(
                ingest_request_id=int(row.ingest_request_id),
                event_id=int(row.event_id),
                batch_id=str(row.batch_id),
                device_id=str(row.device_id),
                status=str(row.status),
                retry_count=int(row.retry_count),
                last_error=str(row.last_error) if row.last_error is not None else None,
                created_at=_to_iso8601_z(row.created_at),
            )
            for row in rows
        ],
    )


def requeue_anchoring_task(
    *, actor: str, ingest_request_id: int
) -> RequeueAnchoringTaskResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        request = session.get(IngestRequest, ingest_request_id)
        if request is None:
            raise AnchoringTaskNotFoundError

        if request.ingest_status not in {
            ANCHOR_STATE_FAILED_RETRYING,
            ANCHOR_STATE_DEAD_LETTER,
        }:
            raise AnchoringTaskRequeueConflictError(request.ingest_status)

        from_status = request.ingest_status
        request.ingest_status = ANCHOR_STATE_RECEIVED
        request.retry_count = 0
        request.last_error = None

        audit_id = _append_audit(
            session,
            actor=actor,
            action="admin.anchoring.task.requeue",
            target=f"ingest_request:{ingest_request_id}",
            metadata={
                "from_status": from_status,
                "to_status": ANCHOR_STATE_RECEIVED,
                "retry_count": 0,
            },
        )
        session.commit()

    return RequeueAnchoringTaskResult(
        ingest_request_id=ingest_request_id,
        status=ANCHOR_STATE_RECEIVED,
        retry_count=0,
        audit_id=audit_id,
    )


def run_anchoring_once(
    *, actor: str, limit: int | None = None
) -> RunAnchoringOnceResult:
    resolved_limit = limit if limit is not None and limit > 0 else 100
    processed = run_anchor_state_machine(limit=resolved_limit)

    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    with Session(engine) as session:
        audit_id = _append_audit(
            session,
            actor=actor,
            action="admin.anchoring.run_once",
            target="anchoring_worker",
            metadata={"processed": processed, "limit": resolved_limit},
        )
        session.commit()

    return RunAnchoringOnceResult(
        processed=processed, limit=resolved_limit, audit_id=audit_id
    )
