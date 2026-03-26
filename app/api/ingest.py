from __future__ import annotations

import logging
from time import perf_counter

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.domain.contracts.trace_event import TraceEvent
from app.observability.logging import correlation_extra, get_request_trace_id, set_request_event_id
from app.observability.metrics import observe_ingest_request
from app.services.audit import append_audit_row
from app.services.idempotency import IdempotencyConflictError, ingest_trace_event
from app.services.signature_verification import verify_trace_event_signature_with_reason

router = APIRouter(prefix="/v1", tags=["ingest"])
ingest_logger = logging.getLogger("app.request.ingest")


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


@router.post("/events", status_code=202, response_model=None)
async def ingest_event(
    request: Request,
    payload: TraceEvent,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    signature_algorithm: str | None = Header(default=None, alias="X-Signature-Algorithm"),
) -> object:
    started_at = perf_counter()
    trace_id = get_request_trace_id(request)
    verification = verify_trace_event_signature_with_reason(
        payload, algorithm_override=signature_algorithm
    )
    if not verification.is_valid:
        signature_reason = verification.reason or "signature_verification_failed"
        append_audit_row(
            actor="ingest",
            action="ingest.signature.verify",
            target=f"device:{payload.device_id}",
            result="failure",
            metadata={
                "device_id": payload.device_id,
                "key_id": payload.signature_envelope.key_id,
                "algorithm": payload.signature_envelope.algorithm,
                "reason": signature_reason,
            },
        )
        observe_ingest_request(
            outcome="rejected_signature", latency_seconds=perf_counter() - started_at
        )
        ingest_logger.warning(
            f"ingest_rejected reason={signature_reason}",
            extra=correlation_extra(trace_id=trace_id),
        )
        return _problem(
            request,
            status=401,
            title="Unauthorized",
            detail="Signature verification failed for the supplied trace event.",
            type_path="signature-mismatch",
        )

    try:
        result = ingest_trace_event(payload, idempotency_key=idempotency_key)
    except IdempotencyConflictError:
        observe_ingest_request(
            outcome="idempotency_conflict", latency_seconds=perf_counter() - started_at
        )
        ingest_logger.warning(
            "ingest_rejected reason=idempotency_conflict",
            extra=correlation_extra(trace_id=trace_id),
        )
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail="Idempotency-Key was reused with a different payload.",
            type_path="idempotency-conflict",
        )

    set_request_event_id(request, result.event_id)
    observe_ingest_request(outcome="accepted", latency_seconds=perf_counter() - started_at)
    ingest_logger.info(
        "ingest_accepted",
        extra=correlation_extra(trace_id=trace_id, event_id=result.event_id),
    )

    return {
        "event_id": result.event_id,
        "ingest_status": result.ingest_status,
    }
