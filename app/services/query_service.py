from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Optional

from sqlalchemy import Engine, func, inspect, literal, select
from sqlalchemy.orm import Session

from app.domain.persistence.models import (
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

DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200
SIMULATION_BATCH_LIKE = "batch-sim-%"
SIMULATION_DEVICE_LIKE = "dev-sim-%"

_TABLE_COLUMNS_CACHE: dict[tuple[str, str], frozenset[str]] = {}
_TABLE_COLUMNS_LOCK = Lock()


@dataclass(frozen=True)
class BatchRecord:
    batch_id: str
    device_id: str
    event_count: int
    start_time: str
    end_time: str


@dataclass(frozen=True)
class BatchPage:
    total: int
    limit: int
    offset: int
    items: list[BatchRecord]


@dataclass(frozen=True)
class EventRecord:
    id: int
    batch_id: str
    device_id: str
    timestamp: str
    ingest_status: str
    supply_chain_stage: Optional[str] = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    co2_ppm: float | None = None
    vibration_g: float | None = None
    quality_grade: str | None = None
    anchor_transaction_hash: str | None = None


@dataclass(frozen=True)
class EventPage:
    total: int
    limit: int
    offset: int
    items: list[EventRecord]


@dataclass(frozen=True)
class SensorPointRecord:
    timestamp: str
    temperature_c: float
    humidity_pct: float
    co2_ppm: float | None = None
    vibration_g: float | None = None
    supply_chain_stage: str | None = None


def _table_columns(url: str, table_name: str) -> frozenset[str]:
    cache_key = (url, table_name)
    columns = _TABLE_COLUMNS_CACHE.get(cache_key)
    if columns is not None:
        return columns

    with _TABLE_COLUMNS_LOCK:
        cached = _TABLE_COLUMNS_CACHE.get(cache_key)
        if cached is not None:
            return cached

        inspector = inspect(_get_engine(url))
        resolved = frozenset(
            column["name"] for column in inspector.get_columns(table_name)
        )
        _TABLE_COLUMNS_CACHE[cache_key] = resolved
        return resolved


def _event_optional_expressions(engine: Engine) -> tuple[Any, Any, Any, bool]:
    columns = _table_columns(str(engine.url), "events")
    has_supply_chain_stage = "supply_chain_stage" in columns
    has_co2_ppm = "co2_ppm" in columns
    has_vibration_g = "vibration_g" in columns

    supply_chain_stage_expr = (
        Event.supply_chain_stage if has_supply_chain_stage else literal(None)
    )
    co2_ppm_expr = Event.co2_ppm if has_co2_ppm else literal(None)
    vibration_g_expr = Event.vibration_g if has_vibration_g else literal(None)

    return (
        supply_chain_stage_expr,
        co2_ppm_expr,
        vibration_g_expr,
        has_supply_chain_stage,
    )


def _engine_from_session(session: Session, *, fallback_url: str) -> Engine:
    bind = session.get_bind()
    if isinstance(bind, Engine):
        return bind
    if bind is not None and hasattr(bind, "engine"):
        candidate = bind.engine
        if isinstance(candidate, Engine):
            return candidate
    return _get_engine(fallback_url)


def _to_iso8601_z(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _to_optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _scoped_event_filters(*, include_simulation: bool) -> list[Any]:
    if include_simulation:
        return []
    return [
        ~Event.batch_id.like(SIMULATION_BATCH_LIKE),
        ~Event.device_id.like(SIMULATION_DEVICE_LIKE),
    ]


def _sensor_value(payload: Any, key: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    return _to_optional_float(payload.get(key))


def _extract_quality_grade(
    *, quality_status: str | None, quality_details: Any
) -> str | None:
    if isinstance(quality_details, dict):
        grade = quality_details.get("grade")
        if isinstance(grade, str):
            return grade
    if quality_status in {"A", "B", "C"}:
        return quality_status
    return None


def query_batches(
    *,
    limit: int = DEFAULT_QUERY_LIMIT,
    offset: int = 0,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    include_simulation: bool = True,
) -> BatchPage:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    grouped = select(
        Event.batch_id.label("batch_id"),
        Event.device_id.label("device_id"),
        func.count(Event.id).label("event_count"),
        func.min(Event.timestamp).label("start_time"),
        func.max(Event.timestamp).label("end_time"),
    ).group_by(Event.batch_id, Event.device_id)

    grouped = grouped.where(
        *_scoped_event_filters(include_simulation=include_simulation)
    )
    if device_id is not None:
        grouped = grouped.where(Event.device_id == device_id)
    if start_time is not None:
        grouped = grouped.where(Event.timestamp >= start_time)
    if end_time is not None:
        grouped = grouped.where(Event.timestamp <= end_time)

    grouped_subquery = grouped.subquery()

    with Session(engine) as session:
        total = int(
            session.scalar(select(func.count()).select_from(grouped_subquery)) or 0
        )
        rows = session.execute(
            select(grouped_subquery)
            .order_by(
                grouped_subquery.c.end_time.desc(),
                grouped_subquery.c.batch_id.asc(),
                grouped_subquery.c.device_id.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

    return BatchPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            BatchRecord(
                batch_id=str(row.batch_id),
                device_id=str(row.device_id),
                event_count=int(row.event_count),
                start_time=_to_iso8601_z(row.start_time),
                end_time=_to_iso8601_z(row.end_time),
            )
            for row in rows
        ],
    )


def query_events(
    *,
    limit: int = DEFAULT_QUERY_LIMIT,
    offset: int = 0,
    batch_id: str | None = None,
    device_id: str | None = None,
    ingest_status: str | None = None,
    supply_chain_stage: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    include_simulation: bool = True,
) -> EventPage:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    (
        supply_chain_stage_expr,
        co2_ppm_expr,
        vibration_g_expr,
        has_supply_chain_stage,
    ) = _event_optional_expressions(engine)

    latest_ingest_id_subquery = (
        select(
            IngestRequest.event_id.label("event_id"),
            func.max(IngestRequest.id).label("latest_ingest_id"),
        )
        .group_by(IngestRequest.event_id)
        .subquery()
    )

    latest_ingest_subquery = (
        select(
            IngestRequest.event_id.label("event_id"),
            IngestRequest.ingest_status.label("ingest_status"),
        )
        .join(
            latest_ingest_id_subquery,
            IngestRequest.id == latest_ingest_id_subquery.c.latest_ingest_id,
        )
        .subquery()
    )

    resolved_ingest_status = func.coalesce(
        latest_ingest_subquery.c.ingest_status, "UNKNOWN"
    )
    base = (
        select(
            Event.id.label("id"),
            Event.batch_id.label("batch_id"),
            Event.device_id.label("device_id"),
            Event.timestamp.label("timestamp"),
            resolved_ingest_status.label("ingest_status"),
            supply_chain_stage_expr.label("supply_chain_stage"),
        )
        .select_from(Event)
        .outerjoin(
            latest_ingest_subquery, latest_ingest_subquery.c.event_id == Event.id
        )
        .where(*_scoped_event_filters(include_simulation=include_simulation))
    )

    if batch_id is not None:
        base = base.where(Event.batch_id == batch_id)
    if device_id is not None:
        base = base.where(Event.device_id == device_id)
    if ingest_status is not None:
        base = base.where(resolved_ingest_status == ingest_status)
    if supply_chain_stage is not None:
        if not has_supply_chain_stage:
            return EventPage(total=0, limit=limit, offset=offset, items=[])
        base = base.where(Event.supply_chain_stage == supply_chain_stage)
    if start_time is not None:
        base = base.where(Event.timestamp >= start_time)
    if end_time is not None:
        base = base.where(Event.timestamp <= end_time)

    filtered_subquery = base.subquery()

    with Session(engine) as session:
        total = int(
            session.scalar(select(func.count()).select_from(filtered_subquery)) or 0
        )
        rows = session.execute(
            select(filtered_subquery)
            .order_by(
                filtered_subquery.c.timestamp.desc(), filtered_subquery.c.id.desc()
            )
            .offset(offset)
            .limit(limit)
        ).all()

    return EventPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            EventRecord(
                id=int(row.id),
                batch_id=str(row.batch_id),
                device_id=str(row.device_id),
                timestamp=_to_iso8601_z(row.timestamp),
                ingest_status=str(row.ingest_status),
                supply_chain_stage=row.supply_chain_stage,
            )
            for row in rows
        ],
    )


def query_recent_events(
    *, limit: int = 10, include_simulation: bool = True
) -> list[EventRecord]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        return query_recent_events_in_session(
            session,
            database_url=database_url,
            limit=limit,
            include_simulation=include_simulation,
        )


def query_recent_events_in_session(
    session: Session,
    *,
    database_url: str,
    limit: int = 10,
    include_simulation: bool = True,
) -> list[EventRecord]:
    engine = _engine_from_session(session, fallback_url=database_url)
    supply_chain_stage_expr, co2_ppm_expr, vibration_g_expr, _ = (
        _event_optional_expressions(engine)
    )
    event_filters = _scoped_event_filters(include_simulation=include_simulation)

    latest_ingest_id_subquery = (
        select(
            IngestRequest.event_id.label("event_id"),
            func.max(IngestRequest.id).label("latest_ingest_id"),
        )
        .group_by(IngestRequest.event_id)
        .subquery()
    )

    latest_ingest_subquery = (
        select(
            IngestRequest.event_id.label("event_id"),
            IngestRequest.ingest_status.label("ingest_status"),
        )
        .join(
            latest_ingest_id_subquery,
            IngestRequest.id == latest_ingest_id_subquery.c.latest_ingest_id,
        )
        .subquery()
    )

    latest_quality_id_subquery = (
        select(
            QualityResult.event_id.label("event_id"),
            func.max(QualityResult.id).label("latest_quality_id"),
        )
        .group_by(QualityResult.event_id)
        .subquery()
    )

    latest_quality_subquery = (
        select(
            QualityResult.event_id.label("event_id"),
            QualityResult.status.label("quality_status"),
            QualityResult.details.label("quality_details"),
        )
        .join(
            latest_quality_id_subquery,
            QualityResult.id == latest_quality_id_subquery.c.latest_quality_id,
        )
        .subquery()
    )

    latest_anchor_id_subquery = (
        select(
            AnchorReceipt.event_id.label("event_id"),
            func.max(AnchorReceipt.id).label("latest_anchor_id"),
        )
        .group_by(AnchorReceipt.event_id)
        .subquery()
    )

    latest_anchor_subquery = (
        select(
            AnchorReceipt.event_id.label("event_id"),
            AnchorReceipt.transaction_hash.label("anchor_transaction_hash"),
        )
        .join(
            latest_anchor_id_subquery,
            AnchorReceipt.id == latest_anchor_id_subquery.c.latest_anchor_id,
        )
        .subquery()
    )

    resolved_ingest_status = func.coalesce(
        latest_ingest_subquery.c.ingest_status, "UNKNOWN"
    )

    rows = session.execute(
        select(
            Event.id.label("id"),
            Event.batch_id.label("batch_id"),
            Event.device_id.label("device_id"),
            Event.timestamp.label("timestamp"),
            resolved_ingest_status.label("ingest_status"),
            supply_chain_stage_expr.label("supply_chain_stage"),
            Event.sensor_payload.label("sensor_payload"),
            co2_ppm_expr.label("co2_ppm"),
            vibration_g_expr.label("vibration_g"),
            latest_quality_subquery.c.quality_status.label("quality_status"),
            latest_quality_subquery.c.quality_details.label("quality_details"),
            latest_anchor_subquery.c.anchor_transaction_hash.label(
                "anchor_transaction_hash"
            ),
        )
        .select_from(Event)
        .outerjoin(
            latest_ingest_subquery, latest_ingest_subquery.c.event_id == Event.id
        )
        .outerjoin(
            latest_quality_subquery, latest_quality_subquery.c.event_id == Event.id
        )
        .outerjoin(
            latest_anchor_subquery, latest_anchor_subquery.c.event_id == Event.id
        )
        .where(*event_filters)
        .order_by(Event.timestamp.desc(), Event.id.desc())
        .limit(limit)
    ).all()

    return [
        EventRecord(
            id=int(row.id),
            batch_id=str(row.batch_id),
            device_id=str(row.device_id),
            timestamp=_to_iso8601_z(row.timestamp),
            ingest_status=str(row.ingest_status),
            supply_chain_stage=row.supply_chain_stage,
            temperature_c=_sensor_value(row.sensor_payload, "temperature_c"),
            humidity_pct=_sensor_value(row.sensor_payload, "humidity_pct"),
            co2_ppm=_to_optional_float(row.co2_ppm),
            vibration_g=_to_optional_float(row.vibration_g),
            quality_grade=_extract_quality_grade(
                quality_status=row.quality_status,
                quality_details=row.quality_details,
            ),
            anchor_transaction_hash=row.anchor_transaction_hash,
        )
        for row in rows
    ]


def query_batch_stages(*, batch_id: str) -> list[dict[str, Any]]:
    """Query events for a batch grouped by supply chain stage."""
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    supply_chain_stage_expr, co2_ppm_expr, vibration_g_expr, _ = (
        _event_optional_expressions(engine)
    )

    with Session(engine) as session:
        events = session.execute(
            select(
                Event.id.label("id"),
                Event.device_id.label("device_id"),
                Event.timestamp.label("timestamp"),
                Event.sensor_payload.label("sensor_payload"),
                supply_chain_stage_expr.label("supply_chain_stage"),
                co2_ppm_expr.label("co2_ppm"),
                vibration_g_expr.label("vibration_g"),
            )
            .where(Event.batch_id == batch_id)
            .order_by(Event.timestamp.asc(), Event.id.asc())
        ).all()

    if not events:
        return []

    stage_order = ["harvest", "storage", "transport", "retail"]
    stages_map: dict[str, list[Any]] = {}
    for event in events:
        stage = event.supply_chain_stage or "unknown"
        stages_map.setdefault(stage, []).append(event)

    result: list[dict[str, Any]] = []
    # Ordered stages first, then any unknown
    for stage in stage_order + ["unknown"]:
        if stage not in stages_map:
            continue
        stage_events = stages_map[stage]
        sensor_events = []
        for e in stage_events:
            payload = e.sensor_payload if isinstance(e.sensor_payload, dict) else {}
            sensor_events.append(
                {
                    "event_id": e.id,
                    "timestamp": _to_iso8601_z(e.timestamp),
                    "device_id": e.device_id,
                    "temperature_c": payload.get("temperature_c"),
                    "humidity_pct": payload.get("humidity_pct"),
                    "co2_ppm": e.co2_ppm,
                    "vibration_g": e.vibration_g,
                }
            )
        result.append(
            {
                "stage": stage,
                "event_count": len(stage_events),
                "start_time": _to_iso8601_z(stage_events[0].timestamp),
                "end_time": _to_iso8601_z(stage_events[-1].timestamp),
                "events": sensor_events,
            }
        )

    return result


def query_batch_sensors(*, batch_id: str) -> list[SensorPointRecord] | None:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    supply_chain_stage_expr, co2_ppm_expr, vibration_g_expr, _ = (
        _event_optional_expressions(engine)
    )

    with Session(engine) as session:
        events = session.execute(
            select(
                Event.timestamp.label("timestamp"),
                Event.sensor_payload.label("sensor_payload"),
                supply_chain_stage_expr.label("supply_chain_stage"),
                co2_ppm_expr.label("co2_ppm"),
                vibration_g_expr.label("vibration_g"),
            )
            .where(Event.batch_id == batch_id)
            .order_by(Event.timestamp.asc(), Event.id.asc())
        ).all()

    if not events:
        return None

    points: list[SensorPointRecord] = []
    for event in events:
        payload = event.sensor_payload if isinstance(event.sensor_payload, dict) else {}
        temperature = payload.get("temperature_c")
        humidity = payload.get("humidity_pct")

        try:
            if temperature is None or humidity is None:
                continue
            temperature_value = float(temperature)
            humidity_value = float(humidity)
        except (TypeError, ValueError):
            continue

        points.append(
            SensorPointRecord(
                timestamp=_to_iso8601_z(event.timestamp),
                temperature_c=temperature_value,
                humidity_pct=humidity_value,
                co2_ppm=float(event.co2_ppm) if event.co2_ppm is not None else None,
                vibration_g=float(event.vibration_g)
                if event.vibration_g is not None
                else None,
                supply_chain_stage=event.supply_chain_stage,
            )
        )

    return points
