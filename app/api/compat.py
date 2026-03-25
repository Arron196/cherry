from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.public_trace import (
    PUBLIC_TRACE_PROBLEM_RESPONSES,
    PublicTraceResponse,
    get_public_trace,
)
from app.domain.contracts.trace_event import (
    SensorPayload,
    SignatureEnvelope,
    SupplyChainStage,
    TraceEvent,
)
from app.services.audit import append_audit_row
from app.services.idempotency import IdempotencyConflictError, ingest_trace_event
from app.services.query_service import query_recent_events
from app.services.signature_verification import (
    normalize_signature_algorithm,
    verify_trace_event_signature_with_reason,
)
from app.observability.metrics import observe_compat_request

router = APIRouter(tags=["compat"])
compat_logger = logging.getLogger("app.request.compat")

_COMPAT_DEPRECATION_SUNSET = "Wed, 30 Sep 2026 00:00:00 GMT"
_COMPAT_DEPRECATION_LINK = '<https://example.com/runbooks/compatibility-closure>; rel="deprecation"; type="text/markdown"'

_COMPAT_ENDPOINT_REPLACEMENTS = {
    "/v1/events/recent": "GET /v1/events",
    "/v1/trace/{batch_id}/public": "GET /v1/public/trace/{batch_id}",
    "/api/cherry/telemetry": "POST /v1/events",
}


def _compat_signature_mode() -> str:
    mode = os.getenv("COMPAT_TELEMETRY_SIGNATURE_MODE", "observe").strip().lower()
    if mode in {"observe", "enforce"}:
        return mode
    return "observe"


def _problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    type_path: str,
    endpoint: str,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status,
        content={
            "type": f"https://example.com/problems/{type_path}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )
    _apply_compat_headers(response, endpoint=endpoint)
    observe_compat_request(endpoint=endpoint, method=request.method, status=status)
    return response


def _compat_headers(endpoint: str) -> dict[str, str]:
    replacement = _COMPAT_ENDPOINT_REPLACEMENTS.get(endpoint, "canonical /v1 routes")
    return {
        "Deprecation": "true",
        "Sunset": _COMPAT_DEPRECATION_SUNSET,
        "Link": _COMPAT_DEPRECATION_LINK,
        "X-Compat-Deprecated": "true",
        "X-Compat-Replacement": replacement,
        "X-Compat-Exit-Criteria": "2-releases,14-consecutive-days,<1%-traffic",
    }


def _apply_compat_headers(response: Response, *, endpoint: str) -> None:
    for header_name, header_value in _compat_headers(endpoint).items():
        response.headers[header_name] = header_value


class RecentEventView(BaseModel):
    id: int
    batch_id: str
    device_id: str
    timestamp: str
    ingest_status: str
    temperature_c: float | None = None
    humidity_pct: float | None = None
    co2_ppm: float | None = None
    vibration_g: float | None = None
    supply_chain_stage: str | None = None
    quality_grade: str | None = None
    anchor_transaction_hash: str | None = None


class CherryTelemetryPayload(BaseModel):
    seq: int = Field(ge=0)
    ts: int | None = Field(default=None, ge=0)
    temp_c: float
    hum_rh: float
    co2: float | None = None
    vibration: bool | None = None
    vibration_g: float | None = None
    digest: str | None = None
    signature: str | None = None
    device_id: str = "stm32-cherry-node"
    batch_id: str = "compat-batch"
    stage: str | None = None
    key_id: str = "compat-gateway-key"


class CherryTelemetryResponse(BaseModel):
    accepted: bool
    event_id: int
    ingest_status: str


@router.get("/v1/events/recent", response_model=list[RecentEventView])
async def get_recent_events(
    response: Response,
    limit: int = Query(default=10, ge=1, le=100),
    include_simulation: bool = Query(default=True),
) -> list[RecentEventView]:
    endpoint = "/v1/events/recent"
    _apply_compat_headers(response, endpoint=endpoint)
    observe_compat_request(endpoint=endpoint, method="GET", status=200)
    recent_events = query_recent_events(
        limit=limit, include_simulation=include_simulation
    )
    return [
        RecentEventView(
            id=item.id,
            batch_id=item.batch_id,
            device_id=item.device_id,
            timestamp=item.timestamp,
            ingest_status=item.ingest_status,
            temperature_c=item.temperature_c,
            humidity_pct=item.humidity_pct,
            co2_ppm=item.co2_ppm,
            vibration_g=item.vibration_g,
            supply_chain_stage=item.supply_chain_stage,
            quality_grade=item.quality_grade,
            anchor_transaction_hash=item.anchor_transaction_hash,
        )
        for item in recent_events
    ]


@router.get(
    "/v1/trace/{batch_id}/public",
    response_model=PublicTraceResponse,
    responses=PUBLIC_TRACE_PROBLEM_RESPONSES,
)
async def get_public_trace_alias(
    request: Request,
    batch_id: str,
    response: Response,
) -> Any:
    endpoint = "/v1/trace/{batch_id}/public"
    result = await get_public_trace(request, batch_id)
    if isinstance(result, JSONResponse):
        _apply_compat_headers(result, endpoint=endpoint)
        observe_compat_request(
            endpoint=endpoint,
            method=request.method,
            status=result.status_code,
        )
    else:
        _apply_compat_headers(response, endpoint=endpoint)
        observe_compat_request(endpoint=endpoint, method=request.method, status=200)
    return result


@router.post(
    "/api/cherry/telemetry", response_model=CherryTelemetryResponse, status_code=202
)
async def ingest_cherry_telemetry(
    payload: CherryTelemetryPayload,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CherryTelemetryResponse | JSONResponse:
    endpoint = "/api/cherry/telemetry"
    timestamp = datetime.now(UTC)
    if payload.ts is not None:
        try:
            timestamp = datetime.fromtimestamp(payload.ts, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return _problem(
                request,
                status=400,
                title="Bad Request",
                detail="Invalid unix timestamp in field 'ts'.",
                type_path="telemetry-invalid-timestamp",
                endpoint=endpoint,
            )

    sensor_payload = {
        "temperature_c": payload.temp_c,
        "humidity_pct": payload.hum_rh,
        "seq": payload.seq,
    }
    if payload.co2 is not None:
        sensor_payload["co2_ppm"] = payload.co2
    if payload.vibration is not None:
        sensor_payload["vibration"] = payload.vibration
    if payload.digest is not None:
        sensor_payload["digest"] = payload.digest

    signature = (
        payload.signature if payload.signature is not None else "compat-signature"
    )
    algorithm_alias = "ECDSA"
    normalized_algorithm = normalize_signature_algorithm(algorithm_alias)
    stage: SupplyChainStage = cast(
        SupplyChainStage,
        payload.stage
        if payload.stage in {"harvest", "storage", "transport", "retail"}
        else "transport",
    )

    event = TraceEvent(
        version="1.0.0",
        device_id=payload.device_id,
        batch_id=payload.batch_id,
        timestamp=timestamp,
        sensor_payload=SensorPayload.model_validate(sensor_payload),
        signature_envelope=SignatureEnvelope(
            algorithm=normalized_algorithm,
            signature=signature,
            key_id=payload.key_id,
        ),
        co2_ppm=payload.co2,
        vibration_g=payload.vibration_g
        if payload.vibration_g is not None
        else (1.0 if payload.vibration else 0.0),
        supply_chain_stage=stage,
    )

    verification = verify_trace_event_signature_with_reason(event)
    signature_mode = _compat_signature_mode()
    if not verification.is_valid:
        signature_reason = verification.reason or "signature_verification_failed"
        append_audit_row(
            actor="ingest",
            action="ingest.signature.verify",
            target=f"device:{payload.device_id}",
            result="failure" if signature_mode == "enforce" else "observed",
            metadata={
                "device_id": payload.device_id,
                "key_id": payload.key_id,
                "algorithm": normalized_algorithm,
                "source_algorithm": algorithm_alias,
                "mode": signature_mode,
                "reason": signature_reason,
                "route": "/api/cherry/telemetry",
            },
        )
        compat_logger.warning(
            "compat_ingest_signature_check_failed mode=%s reason=%s",
            signature_mode,
            signature_reason,
        )
        if signature_mode == "enforce":
            return _problem(
                request,
                status=401,
                title="Unauthorized",
                detail="Signature verification failed for the supplied trace event.",
                type_path="signature-mismatch",
                endpoint=endpoint,
            )

    dedupe_key = idempotency_key or f"hw:{payload.device_id}:{payload.seq}"
    try:
        result = ingest_trace_event(event=event, idempotency_key=dedupe_key)
    except IdempotencyConflictError as exc:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail=str(exc),
            type_path="idempotency-conflict",
            endpoint=endpoint,
        )

    _apply_compat_headers(response, endpoint=endpoint)
    observe_compat_request(endpoint=endpoint, method=request.method, status=202)
    return CherryTelemetryResponse(
        accepted=True,
        event_id=result.event_id,
        ingest_status=result.ingest_status,
    )
