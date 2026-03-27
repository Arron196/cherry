from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.security.auth import Principal
from app.security.rbac import require_roles
from app.services.simulation import (
    DEFAULT_SIMULATION_EVENT_COUNT,
    DEFAULT_GENERATOR_BATCHES_PER_TICK,
    DEFAULT_GENERATOR_INTERVAL_SECONDS,
    SimulationGeneratorStatus,
    SimulationTickResult,
    SimulationBatchNotSupportedError,
    ensure_simulation_batch,
    get_simulation_generator_status,
    run_simulation_tick,
    start_simulation_generator,
    stop_simulation_generator,
)

router = APIRouter(prefix="/v1/simulation", tags=["simulation"])


class SimulationBatchResponse(BaseModel):
    batch_id: str
    total_events: int
    created_events: int
    existing_events: int
    anchored_events: int
    processed_anchoring: int


class SimulationGeneratorRequest(BaseModel):
    interval_seconds: float = DEFAULT_GENERATOR_INTERVAL_SECONDS
    batches_per_tick: int = DEFAULT_GENERATOR_BATCHES_PER_TICK


class SimulationGeneratorStatusResponse(BaseModel):
    running: bool
    interval_seconds: float
    batches_per_tick: int
    generated_events: int
    generated_alerts: int
    active_batches: list[str]
    started_at: str | None
    last_tick_at: str | None
    last_error: str | None


class SimulationTickResponse(BaseModel):
    generated_events: int
    processed_anchoring: int
    alerts_created: int
    active_batches: list[str]


def _status_response(status: SimulationGeneratorStatus) -> SimulationGeneratorStatusResponse:
    return SimulationGeneratorStatusResponse(**status.__dict__)


def _tick_response(result: SimulationTickResult) -> SimulationTickResponse:
    return SimulationTickResponse(**result.__dict__)


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


@router.post("/batches/{batch_id}", response_model=SimulationBatchResponse)
async def seed_simulation_batch(
    batch_id: str,
    request: Request,
    event_count: int = Query(
        default=DEFAULT_SIMULATION_EVENT_COUNT,
        ge=1,
        le=50,
    ),
    _principal: Principal = Depends(require_roles("admin", "regulator")),
) -> SimulationBatchResponse | JSONResponse:
    try:
        result = ensure_simulation_batch(batch_id, event_count=event_count)
    except SimulationBatchNotSupportedError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Only batch ids in the 'batch-sim-*' namespace can be generated.",
            type_path="simulation-batch-not-supported",
        )

    return SimulationBatchResponse(**result.__dict__)


@router.get("/generator", response_model=SimulationGeneratorStatusResponse)
async def get_generator_status(
    _principal: Principal = Depends(require_roles("admin", "regulator")),
) -> SimulationGeneratorStatusResponse:
    return _status_response(get_simulation_generator_status())


@router.post("/generator/start", response_model=SimulationGeneratorStatusResponse)
async def start_generator(
    payload: SimulationGeneratorRequest | None = None,
    _principal: Principal = Depends(require_roles("admin", "regulator")),
) -> SimulationGeneratorStatusResponse:
    config = payload or SimulationGeneratorRequest()
    return _status_response(
        start_simulation_generator(
            interval_seconds=config.interval_seconds,
            batches_per_tick=config.batches_per_tick,
        )
    )


@router.post("/generator/stop", response_model=SimulationGeneratorStatusResponse)
async def stop_generator(
    _principal: Principal = Depends(require_roles("admin", "regulator")),
) -> SimulationGeneratorStatusResponse:
    return _status_response(stop_simulation_generator())


@router.post("/generator/tick", response_model=SimulationTickResponse)
async def tick_generator(
    payload: SimulationGeneratorRequest | None = None,
    _principal: Principal = Depends(require_roles("admin", "regulator")),
) -> SimulationTickResponse:
    config = payload or SimulationGeneratorRequest()
    return _tick_response(run_simulation_tick(batches_per_tick=config.batches_per_tick))
