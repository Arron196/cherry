import logging
import os
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.admin import v1_router as admin_v1_router
from app.api.auth import router as auth_router
from app.api.anchoring_admin import router as anchoring_admin_router
from app.api.alerts import router as alerts_router
from app.api.contracts import router as contracts_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.metrics import router as metrics_router
from app.api.compat import router as compat_router
from app.api.query import router as query_router
from app.api.quality import router as quality_router
from app.api.simulation import router as simulation_router
from app.api.trace import router as trace_router
from app.api.stats import router as stats_router
from app.api.public_trace import router as public_trace_router
from app.observability.logging import (
    TRACE_ID_HEADER,
    configure_logging,
    correlation_extra,
    get_request_event_id,
    new_trace_id,
    set_request_trace_id,
)
from app.services.compat_exit import evaluate_compat_closure_decision
from app.security.auth import AuthProblem, auth_problem_response

configure_logging()

_DEFAULT_CORS_ALLOW_ORIGINS = [
    "*",
]


def _cors_allow_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS")
    if raw_origins is None:
        return _DEFAULT_CORS_ALLOW_ORIGINS.copy()

    parsed_origins = [
        origin.strip() for origin in raw_origins.split(",") if origin.strip()
    ]
    if not parsed_origins:
        return _DEFAULT_CORS_ALLOW_ORIGINS.copy()
    return parsed_origins


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(contracts_router)
app.include_router(ingest_router)
app.include_router(quality_router)
app.include_router(simulation_router)
app.include_router(trace_router)
app.include_router(admin_router)
app.include_router(admin_v1_router)
app.include_router(anchoring_admin_router)
app.include_router(alerts_router)
app.include_router(metrics_router)
compat_closure_decision = evaluate_compat_closure_decision()
if compat_closure_decision.include_compat_router:
    app.include_router(compat_router)
app.include_router(query_router)
app.include_router(stats_router)
app.include_router(public_trace_router)

compat_gate_logger = logging.getLogger("app.compat.gate")
if compat_closure_decision.closure_requested:
    evaluation = compat_closure_decision.evaluation
    if evaluation is not None and evaluation.criteria_passed:
        compat_gate_logger.info(
            "compatibility_router_disabled releases=%s trailing_days=%s threshold=%.6f",
            evaluation.releases_observed,
            evaluation.trailing_streak_days,
            evaluation.max_compat_ratio,
        )
    elif evaluation is not None:
        compat_gate_logger.warning(
            "compatibility_router_kept_enabled closure_requested=true reasons=%s",
            ";".join(evaluation.reasons),
        )

request_logger = logging.getLogger("app.request.http")


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    trace_id = request.headers.get(TRACE_ID_HEADER) or new_trace_id(prefix="req")
    set_request_trace_id(request, trace_id)
    start = perf_counter()
    request_logger.info(
        "request_started method=%s path=%s",
        request.method,
        request.url.path,
        extra=correlation_extra(trace_id=trace_id),
    )
    try:
        response = await call_next(request)
    except Exception:
        request_logger.exception(
            "request_failed method=%s path=%s",
            request.method,
            request.url.path,
            extra=correlation_extra(
                trace_id=trace_id, event_id=get_request_event_id(request)
            ),
        )
        raise

    response.headers[TRACE_ID_HEADER] = trace_id
    duration_seconds = perf_counter() - start
    request_logger.info(
        "request_completed method=%s path=%s status=%s latency=%.6f",
        request.method,
        request.url.path,
        response.status_code,
        duration_seconds,
        extra=correlation_extra(
            trace_id=trace_id, event_id=get_request_event_id(request)
        ),
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = exc.errors()

    return JSONResponse(
        status_code=422,
        content={
            "type": "https://example.com/problems/validation-error",
            "title": "Unprocessable Entity",
            "status": 422,
            "detail": "Request validation failed.",
            "errors": details,
            "instance": request.url.path,
        },
    )


@app.exception_handler(AuthProblem)
async def auth_exception_handler(request: Request, exc: AuthProblem) -> JSONResponse:
    return auth_problem_response(request, exc)
