from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
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
from app.services.event_schema import optional_event_expressions
from app.services.simulation import ensure_simulation_batch, is_simulation_batch_id

router = APIRouter(prefix="/v1/public", tags=["public"])


def _to_iso8601_z(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


class SensorDataView(BaseModel):
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    co2_ppm: Optional[float] = None
    vibration_g: Optional[float] = None


class TimelineEventView(BaseModel):
    event_id: int
    timestamp: str
    device_id: str
    supply_chain_stage: Optional[str] = None
    sensor_data: SensorDataView


class StageEnvironmentView(BaseModel):
    stage: str
    event_count: int
    avg_temperature_c: Optional[float] = None
    avg_humidity_pct: Optional[float] = None
    avg_co2_ppm: Optional[float] = None
    avg_vibration_g: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class QualityView(BaseModel):
    grade: Optional[str] = None
    score: Optional[float] = None
    max_score: int = 100


class BlockchainAnchorView(BaseModel):
    is_anchored: bool
    anchored_count: int
    total_events: int
    latest_transaction_hash: Optional[str] = None


class BatchInfoView(BaseModel):
    batch_id: str
    total_events: int
    first_event_at: Optional[str] = None
    last_event_at: Optional[str] = None


class PublicTraceResponse(BaseModel):
    batch_info: BatchInfoView
    timeline: list[TimelineEventView]
    stage_environments: list[StageEnvironmentView]
    quality: QualityView
    blockchain_anchor: BlockchainAnchorView


@dataclass
class _StageAggregate:
    event_count: int = 0
    temperature_total: float = 0.0
    temperature_count: int = 0
    humidity_total: float = 0.0
    humidity_count: int = 0
    co2_total: float = 0.0
    co2_count: int = 0
    vibration_total: float = 0.0
    vibration_count: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None


PUBLIC_TRACE_PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {
        "description": "RFC9457 problem response when no trace data exists for the requested batch.",
    }
}


def _problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    type_path: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "type": f"https://example.com/problems/{type_path}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )


@router.get(
    "/trace/{batch_id}",
    response_model=PublicTraceResponse,
    responses=PUBLIC_TRACE_PROBLEM_RESPONSES,
)
async def get_public_trace(
    request: Request, batch_id: str
) -> PublicTraceResponse | JSONResponse:
    if is_simulation_batch_id(batch_id):
        ensure_simulation_batch(batch_id)

    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    supply_chain_stage_expr, co2_ppm_expr, vibration_g_expr, _ = (
        optional_event_expressions(engine)
    )

    with Session(engine) as session:
        events = session.execute(
            select(
                Event.id.label("id"),
                Event.timestamp.label("timestamp"),
                Event.device_id.label("device_id"),
                Event.sensor_payload.label("sensor_payload"),
                supply_chain_stage_expr.label("supply_chain_stage"),
                co2_ppm_expr.label("co2_ppm"),
                vibration_g_expr.label("vibration_g"),
            )
            .where(Event.batch_id == batch_id)
            .order_by(Event.timestamp.asc(), Event.id.asc())
        ).all()

        if not events:
            return _problem(
                request,
                status=404,
                title="Not Found",
                detail=f"No trace data found for batch '{batch_id}'.",
                type_path="public-trace-not-found",
            )

        event_ids = [e.id for e in events]

        anchored_count = int(
            session.scalar(
                select(func.count(func.distinct(AnchorReceipt.event_id))).where(
                    AnchorReceipt.event_id.in_(event_ids)
                )
            )
            or 0
        )
        latest_tx_hash = session.scalar(
            select(AnchorReceipt.transaction_hash)
            .where(AnchorReceipt.event_id.in_(event_ids))
            .order_by(AnchorReceipt.id.desc())
            .limit(1)
        )
        quality_grade_expression = QualityResult.details["grade"].as_string()
        latest_quality_result = session.execute(
            select(
                QualityResult.score.label("score"),
                quality_grade_expression.label("grade"),
            )
            .where(
                QualityResult.event_id.in_(event_ids),
                quality_grade_expression.is_not(None),
            )
            .order_by(QualityResult.evaluated_at.desc(), QualityResult.id.desc())
            .limit(1)
        ).first()

    timeline: list[TimelineEventView] = []
    stage_order = ["harvest", "storage", "transport", "retail", "unknown"]
    stage_aggregates: dict[str, _StageAggregate] = {}

    for event in events:
        payload = event.sensor_payload if isinstance(event.sensor_payload, dict) else {}
        temperature_c = payload.get("temperature_c")
        humidity_pct = payload.get("humidity_pct")
        stage = event.supply_chain_stage or "unknown"

        aggregate = stage_aggregates.setdefault(stage, _StageAggregate())
        aggregate.event_count += 1
        if aggregate.start_time is None:
            aggregate.start_time = event.timestamp
        aggregate.end_time = event.timestamp

        if temperature_c is not None:
            aggregate.temperature_total += float(temperature_c)
            aggregate.temperature_count += 1

        if humidity_pct is not None:
            aggregate.humidity_total += float(humidity_pct)
            aggregate.humidity_count += 1

        if event.co2_ppm is not None:
            aggregate.co2_total += float(event.co2_ppm)
            aggregate.co2_count += 1

        if event.vibration_g is not None:
            aggregate.vibration_total += float(event.vibration_g)
            aggregate.vibration_count += 1

        timeline.append(
            TimelineEventView(
                event_id=event.id,
                timestamp=_to_iso8601_z(event.timestamp),
                device_id=event.device_id,
                supply_chain_stage=event.supply_chain_stage,
                sensor_data=SensorDataView(
                    temperature_c=temperature_c,
                    humidity_pct=humidity_pct,
                    co2_ppm=event.co2_ppm,
                    vibration_g=event.vibration_g,
                ),
            )
        )

    stage_environments: list[StageEnvironmentView] = []
    for stage in stage_order:
        aggregate = stage_aggregates.get(stage)
        if aggregate is None:
            continue

        stage_environments.append(
            StageEnvironmentView(
                stage=stage,
                event_count=aggregate.event_count,
                avg_temperature_c=round(
                    aggregate.temperature_total / aggregate.temperature_count, 2
                )
                if aggregate.temperature_count
                else None,
                avg_humidity_pct=round(
                    aggregate.humidity_total / aggregate.humidity_count, 2
                )
                if aggregate.humidity_count
                else None,
                avg_co2_ppm=round(aggregate.co2_total / aggregate.co2_count, 2)
                if aggregate.co2_count
                else None,
                avg_vibration_g=round(
                    aggregate.vibration_total / aggregate.vibration_count, 4
                )
                if aggregate.vibration_count
                else None,
                start_time=_to_iso8601_z(aggregate.start_time),
                end_time=_to_iso8601_z(aggregate.end_time),
            )
        )

    quality_grade: str | None = None
    quality_score: float | None = None
    if latest_quality_result is not None:
        if isinstance(latest_quality_result.grade, str):
            quality_grade = latest_quality_result.grade
            quality_score = latest_quality_result.score

    batch_info = BatchInfoView(
        batch_id=batch_id,
        total_events=len(events),
        first_event_at=_to_iso8601_z(events[0].timestamp) if events else None,
        last_event_at=_to_iso8601_z(events[-1].timestamp) if events else None,
    )

    return PublicTraceResponse(
        batch_info=batch_info,
        timeline=timeline,
        stage_environments=stage_environments,
        quality=QualityView(
            grade=quality_grade,
            score=quality_score,
            max_score=100,
        ),
        blockchain_anchor=BlockchainAnchorView(
            is_anchored=anchored_count > 0,
            anchored_count=anchored_count,
            total_events=len(events),
            latest_transaction_hash=latest_tx_hash,
        ),
    )
