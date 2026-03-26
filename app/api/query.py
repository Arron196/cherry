from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.query_service import (
    DEFAULT_QUERY_LIMIT,
    MAX_QUERY_LIMIT,
    query_batches,
    query_events,
    query_batch_stages,
    query_batch_sensors,
)
from app.services.simulation import ensure_simulation_batch, is_simulation_batch_id

router = APIRouter(prefix="/v1", tags=["query"])


class BatchItemView(BaseModel):
    batch_id: str
    device_id: str
    event_count: int
    start_time: str
    end_time: str


class EventItemView(BaseModel):
    id: int
    batch_id: str
    device_id: str
    timestamp: str
    ingest_status: str
    supply_chain_stage: Optional[str] = None


IngestStatusFilter = Literal[
    "RECEIVED",
    "ANCHORING",
    "ANCHORED",
    "FAILED_RETRYING",
    "DEAD_LETTER",
    "UNKNOWN",
]

SupplyChainStageFilter = Literal["harvest", "storage", "transport", "retail"]


class BatchQueryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[BatchItemView]


class EventQueryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EventItemView]


class StageEventView(BaseModel):
    event_id: int
    timestamp: str
    device_id: str
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    co2_ppm: Optional[float] = None
    vibration_g: Optional[float] = None


class StageInfoView(BaseModel):
    stage: str
    event_count: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    events: list[StageEventView]


class BatchStagesResponse(BaseModel):
    batch_id: str
    stages: list[StageInfoView]


class SensorPointView(BaseModel):
    timestamp: str
    temperature_c: float
    humidity_pct: float
    co2_ppm: Optional[float] = None
    vibration_g: Optional[float] = None
    supply_chain_stage: Optional[str] = None


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


def _invalid_time_range_problem(
    request: Request, start_time: datetime, end_time: datetime
) -> JSONResponse | None:
    if start_time > end_time:
        return _problem(
            request,
            status=422,
            title="Unprocessable Entity",
            detail="'start_time' must be less than or equal to 'end_time'.",
            type_path="invalid-query-parameter",
        )
    return None


@router.get("/batches", response_model=BatchQueryResponse)
async def get_batches(
    request: Request,
    limit: int = Query(default=DEFAULT_QUERY_LIMIT, ge=1, le=MAX_QUERY_LIMIT),
    offset: int = Query(default=0, ge=0),
    device_id: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    include_simulation: bool = Query(default=True),
) -> object:
    if start_time is not None and end_time is not None:
        invalid_range = _invalid_time_range_problem(request, start_time, end_time)
        if invalid_range is not None:
            return invalid_range

    page = query_batches(
        limit=limit,
        offset=offset,
        device_id=device_id,
        start_time=start_time,
        end_time=end_time,
        include_simulation=include_simulation,
    )
    return BatchQueryResponse(
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        items=[BatchItemView(**item.__dict__) for item in page.items],
    )


@router.get(
    "/events", response_model=EventQueryResponse, response_model_exclude_none=True
)
async def get_events(
    request: Request,
    limit: int = Query(default=DEFAULT_QUERY_LIMIT, ge=1, le=MAX_QUERY_LIMIT),
    offset: int = Query(default=0, ge=0),
    batch_id: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    ingest_status: IngestStatusFilter | None = Query(default=None),
    supply_chain_stage: SupplyChainStageFilter | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    include_simulation: bool = Query(default=True),
) -> object:
    if include_simulation and batch_id is not None and is_simulation_batch_id(batch_id):
        ensure_simulation_batch(batch_id)

    if start_time is not None and end_time is not None:
        invalid_range = _invalid_time_range_problem(request, start_time, end_time)
        if invalid_range is not None:
            return invalid_range

    page = query_events(
        limit=limit,
        offset=offset,
        batch_id=batch_id,
        device_id=device_id,
        ingest_status=ingest_status,
        supply_chain_stage=supply_chain_stage,
        start_time=start_time,
        end_time=end_time,
        include_simulation=include_simulation,
    )
    return EventQueryResponse(
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        items=[EventItemView(**item.__dict__) for item in page.items],
    )


@router.get("/batches/{batch_id}/stages", response_model=BatchStagesResponse)
async def get_batch_stages(
    request: Request,
    batch_id: str,
) -> object:
    if is_simulation_batch_id(batch_id):
        ensure_simulation_batch(batch_id)

    stages_data = query_batch_stages(batch_id=batch_id)
    if not stages_data:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail=f"No events found for batch_id '{batch_id}'.",
            type_path="batch-not-found",
        )

    stages = []
    for stage_record in stages_data:
        stages.append(
            StageInfoView(
                stage=stage_record["stage"],
                event_count=stage_record["event_count"],
                start_time=stage_record["start_time"],
                end_time=stage_record["end_time"],
                events=[StageEventView(**e) for e in stage_record["events"]],
            )
        )

    return BatchStagesResponse(batch_id=batch_id, stages=stages)


@router.get(
    "/batches/{batch_id}/sensors",
    response_model=list[SensorPointView],
    response_model_exclude_none=True,
)
async def get_batch_sensors(request: Request, batch_id: str) -> object:
    if is_simulation_batch_id(batch_id):
        ensure_simulation_batch(batch_id)

    sensor_points = query_batch_sensors(batch_id=batch_id)
    if sensor_points is None:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail=f"No events found for batch_id '{batch_id}'.",
            type_path="batch-not-found",
        )

    return [SensorPointView(**point.__dict__) for point in sensor_points]
