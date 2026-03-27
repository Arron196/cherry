from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import Engine, Integer, and_, cast, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.domain.persistence.models import (
    Alert,
    Event,
    ManagedDevice,
    QualityResult,
)
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)
from app.services.event_schema import event_has_column
from app.services.query_service import EventRecord, query_recent_events_in_session

router = APIRouter(prefix="/v1/stats", tags=["stats"])

SIMULATION_BATCH_LIKE = "batch-sim-%"
SIMULATION_DEVICE_LIKE = "dev-sim-%"
MAX_TEMPERATURE_TREND_POINTS = 96
TEMPERATURE_TREND_WINDOW_SECONDS = 24 * 60 * 60


def _to_iso8601_z(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _sqlite_temperature_value_expressions() -> tuple[Any, Any]:
    return (
        func.json_type(Event.sensor_payload, "$.temperature_c"),
        func.json_extract(Event.sensor_payload, "$.temperature_c"),
    )


def _temperature_trend_bucket_seconds(max_points: int) -> int:
    normalized_max_points = max(1, max_points)
    return max(
        1,
        (TEMPERATURE_TREND_WINDOW_SECONDS + normalized_max_points - 1)
        // normalized_max_points,
    )


class GradeDistribution(BaseModel):
    A: int = 0
    B: int = 0
    C: int = 0


class OverviewResponse(BaseModel):
    total_batches: int
    total_events: int
    active_devices: int
    avg_quality_score: float
    grade_distribution: GradeDistribution
    open_alerts: int


class TemperatureTrendPoint(BaseModel):
    timestamp: str
    avg_temperature: float
    min_temperature: float
    max_temperature: float


class QualityDistributionItem(BaseModel):
    grade: str
    count: int
    percentage: float


class StageDistributionItem(BaseModel):
    stage: str
    count: int


class DashboardStatsResponse(BaseModel):
    overview: OverviewResponse
    temperature_trend: list[TemperatureTrendPoint]
    quality_distribution: list[QualityDistributionItem]
    stage_distribution: list[StageDistributionItem]
    recent_events: list[EventRecord]


def _scoped_event_filters(*, include_simulation: bool) -> list[Any]:
    if include_simulation:
        return []
    return [
        ~Event.batch_id.like(SIMULATION_BATCH_LIKE),
        ~Event.device_id.like(SIMULATION_DEVICE_LIKE),
    ]


def _get_overview_response(
    session: Session, *, include_simulation: bool
) -> OverviewResponse:
    event_filters = _scoped_event_filters(include_simulation=include_simulation)
    total_events_query = select(func.count()).select_from(Event).where(*event_filters)
    total_events = int(session.scalar(total_events_query) or 0)
    total_batches = int(
        session.scalar(
            select(func.count(distinct(Event.batch_id)))
            .select_from(Event)
            .where(*event_filters)
        )
        or 0
    )
    active_devices_query = (
        select(func.count())
        .select_from(ManagedDevice)
        .where(ManagedDevice.status == "active")
    )
    if not include_simulation:
        active_devices_query = active_devices_query.where(
            ~ManagedDevice.device_id.like(SIMULATION_DEVICE_LIKE)
        )
    active_devices = int(
        session.scalar(active_devices_query) or 0
    )
    open_alerts_query = (
        select(func.count()).select_from(Alert).where(Alert.status == "open")
    )
    if not include_simulation:
        open_alerts_query = (
            open_alerts_query.outerjoin(Event, Alert.event_id == Event.id).where(
                or_(
                    Alert.event_id.is_(None),
                    and_(*_scoped_event_filters(include_simulation=False)),
                )
            )
        )
    open_alerts = int(
        session.scalar(open_alerts_query) or 0
    )

    grade_dist = {"A": 0, "B": 0, "C": 0}
    quality_filters = [QualityResult.score.isnot(None)]
    if not include_simulation:
        quality_filters.extend(_scoped_event_filters(include_simulation=False))
    avg_score_query = (
        select(func.avg(QualityResult.score))
        .select_from(QualityResult)
        .where(*quality_filters)
    )
    if not include_simulation:
        avg_score_query = avg_score_query.join(
            Event, QualityResult.event_id == Event.id
        )
    avg_score = round(
        float(session.scalar(avg_score_query) or 0.0),
        1,
    )
    grade_expression = QualityResult.details["grade"].as_string()
    grade_query = (
        select(grade_expression.label("grade"), func.count().label("grade_count"))
        .select_from(QualityResult)
        .where(grade_expression.is_not(None))
        .group_by(grade_expression)
    )
    if not include_simulation:
        grade_query = grade_query.join(Event, QualityResult.event_id == Event.id).where(
            *_scoped_event_filters(include_simulation=False)
        )
    grade_rows = session.execute(grade_query).all()
    for row in grade_rows:
        grade = row[0]
        grade_count = row[1]
        if grade in grade_dist:
            grade_dist[str(grade)] = int(grade_count)

    return OverviewResponse(
        total_batches=total_batches,
        total_events=total_events,
        active_devices=active_devices,
        avg_quality_score=avg_score,
        grade_distribution=GradeDistribution(**grade_dist),
        open_alerts=open_alerts,
    )


def _get_temperature_trend_response(
    session: Session,
    *,
    cutoff: datetime,
    include_simulation: bool,
    max_points: int = MAX_TEMPERATURE_TREND_POINTS,
) -> list[TemperatureTrendPoint]:
    event_filters = _scoped_event_filters(include_simulation=include_simulation)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        temperature_type_expression, temperature_value_expression = (
            _sqlite_temperature_value_expressions()
        )
        query_filters = [
            Event.timestamp >= cutoff,
            temperature_type_expression.in_(["integer", "real"]),
            *event_filters,
        ]
        raw_point_count = int(
            session.scalar(
                select(func.count()).select_from(Event).where(*query_filters)
            )
            or 0
        )

        if raw_point_count <= max_points:
            rows = session.execute(
                select(
                    Event.timestamp.label("timestamp"),
                    temperature_value_expression.label("temperature_c"),
                )
                .where(*query_filters)
                .order_by(Event.timestamp.asc(), Event.id.asc())
            ).all()
            return [
                TemperatureTrendPoint(
                    timestamp=_to_iso8601_z(row.timestamp),
                    avg_temperature=float(row.temperature_c),
                    min_temperature=float(row.temperature_c),
                    max_temperature=float(row.temperature_c),
                )
                for row in rows
                if row.temperature_c is not None
            ]

        bucket_seconds = _temperature_trend_bucket_seconds(max_points)
        event_epoch_expression = cast(func.strftime("%s", Event.timestamp), Integer)
        bucket_index_expression = cast(event_epoch_expression / bucket_seconds, Integer)
        rows = session.execute(
            select(
                bucket_index_expression.label("bucket_index"),
                func.avg(temperature_value_expression).label("avg_temperature"),
                func.min(temperature_value_expression).label("min_temperature"),
                func.max(temperature_value_expression).label("max_temperature"),
            )
            .where(*query_filters)
            .group_by(bucket_index_expression)
            .order_by(bucket_index_expression.asc())
        ).all()
        return [
            TemperatureTrendPoint(
                timestamp=_to_iso8601_z(
                    datetime.fromtimestamp(
                        int(row.bucket_index) * bucket_seconds,
                        UTC,
                    )
                ),
                avg_temperature=float(row.avg_temperature),
                min_temperature=float(row.min_temperature),
                max_temperature=float(row.max_temperature),
            )
            for row in rows
            if row.bucket_index is not None
        ]

    events = session.execute(
        select(
            Event.timestamp.label("timestamp"),
            Event.sensor_payload.label("sensor_payload"),
        )
        .where(Event.timestamp >= cutoff)
        .where(*event_filters)
        .order_by(Event.timestamp.asc(), Event.id.asc())
    ).all()

    points: list[TemperatureTrendPoint] = []
    for event in events:
        payload = event.sensor_payload if isinstance(event.sensor_payload, dict) else {}
        temp = payload.get("temperature_c")
        if not isinstance(temp, (int, float)) or isinstance(temp, bool):
            continue
        temperature_value = float(temp)
        points.append(
            TemperatureTrendPoint(
                timestamp=_to_iso8601_z(event.timestamp),
                avg_temperature=temperature_value,
                min_temperature=temperature_value,
                max_temperature=temperature_value,
            )
        )
    if len(points) <= max_points:
        return points

    bucket_seconds = _temperature_trend_bucket_seconds(max_points)
    buckets: dict[int, dict[str, float]] = {}
    for point in points:
        timestamp = datetime.fromisoformat(point.timestamp.replace("Z", "+00:00"))
        bucket_index = int(timestamp.timestamp()) // bucket_seconds
        bucket = buckets.setdefault(
            bucket_index,
            {
                "count": 0.0,
                "sum": 0.0,
                "min": point.avg_temperature,
                "max": point.avg_temperature,
            },
        )
        bucket["count"] += 1
        bucket["sum"] += point.avg_temperature
        bucket["min"] = min(bucket["min"], point.avg_temperature)
        bucket["max"] = max(bucket["max"], point.avg_temperature)

    return [
        TemperatureTrendPoint(
            timestamp=_to_iso8601_z(
                datetime.fromtimestamp(bucket_index * bucket_seconds, UTC)
            ),
            avg_temperature=bucket["sum"] / bucket["count"],
            min_temperature=bucket["min"],
            max_temperature=bucket["max"],
        )
        for bucket_index, bucket in sorted(buckets.items())
    ]


def _get_quality_distribution_response(
    session: Session,
    *,
    include_simulation: bool,
) -> list[QualityDistributionItem]:
    grade_expression = QualityResult.details["grade"].as_string()
    query = (
        select(grade_expression.label("grade"), func.count().label("grade_count"))
        .select_from(QualityResult)
        .where(grade_expression.is_not(None))
        .group_by(grade_expression)
    )
    if not include_simulation:
        query = query.join(Event, QualityResult.event_id == Event.id).where(
            *_scoped_event_filters(include_simulation=False)
        )
    rows = session.execute(query).all()

    grade_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    for row in rows:
        grade = row[0]
        grade_count = row[1]
        if grade in grade_counts:
            grade_counts[str(grade)] = int(grade_count)

    total = sum(grade_counts.values())
    if total == 0:
        return []

    distribution: list[QualityDistributionItem] = []
    for grade in ("A", "B", "C"):
        count = grade_counts[grade]
        if count == 0:
            continue
        distribution.append(
            QualityDistributionItem(
                grade=grade,
                count=count,
                percentage=round(count / total * 100, 1),
            )
        )

    return distribution


def _get_stage_distribution_response(
    session: Session, *, engine: Engine, include_simulation: bool
) -> list[StageDistributionItem]:
    event_filters = _scoped_event_filters(include_simulation=include_simulation)
    distribution_rows: list[tuple[str, int]]
    if event_has_column(engine, "supply_chain_stage"):
        stage_expression = func.coalesce(Event.supply_chain_stage, "unknown")
        query = (
            select(
                stage_expression.label("stage"),
                func.count(Event.id).label("count"),
            )
            .where(*event_filters)
            .group_by(stage_expression)
            .order_by(stage_expression.asc())
        )
        rows = list(session.execute(query).all())
        distribution_rows = [(str(row[0]), int(row[1])) for row in rows]
    else:
        total = int(
            session.scalar(
                select(func.count()).select_from(Event).where(*event_filters)
            )
            or 0
        )
        distribution_rows = [] if total == 0 else [("unknown", total)]

    return [
        StageDistributionItem(stage=str(stage_value), count=int(stage_count))
        for stage_value, stage_count in distribution_rows
    ]


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    include_simulation: bool = Query(default=True),
) -> OverviewResponse:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        return _get_overview_response(
            session, include_simulation=include_simulation
        )


@router.get("/temperature-trend", response_model=list[TemperatureTrendPoint])
async def get_temperature_trend(
    include_simulation: bool = Query(default=True),
) -> list[TemperatureTrendPoint]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    with Session(engine) as session:
        return _get_temperature_trend_response(
            session, cutoff=cutoff, include_simulation=include_simulation
        )


@router.get("/quality-distribution", response_model=list[QualityDistributionItem])
async def get_quality_distribution(
    include_simulation: bool = Query(default=True),
) -> list[QualityDistributionItem]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        return _get_quality_distribution_response(
            session, include_simulation=include_simulation
        )


@router.get("/stage-distribution", response_model=list[StageDistributionItem])
async def get_stage_distribution(
    include_simulation: bool = Query(default=True),
) -> list[StageDistributionItem]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        return _get_stage_distribution_response(
            session, engine=engine, include_simulation=include_simulation
        )


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    include_simulation: bool = Query(default=True),
) -> DashboardStatsResponse:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    with Session(engine) as session:
        overview = _get_overview_response(
            session, include_simulation=include_simulation
        )
        temperature_trend = _get_temperature_trend_response(
            session,
            cutoff=cutoff,
            include_simulation=include_simulation,
            max_points=MAX_TEMPERATURE_TREND_POINTS,
        )
        quality_distribution = _get_quality_distribution_response(
            session, include_simulation=include_simulation
        )
        stage_distribution = _get_stage_distribution_response(
            session, engine=engine, include_simulation=include_simulation
        )
        recent_events = query_recent_events_in_session(
            session,
            database_url=database_url,
            limit=10,
            include_simulation=include_simulation,
        )

    return DashboardStatsResponse(
        overview=overview,
        temperature_trend=temperature_trend,
        quality_distribution=quality_distribution,
        stage_distribution=stage_distribution,
        recent_events=recent_events,
    )
