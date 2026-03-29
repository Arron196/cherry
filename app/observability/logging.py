from __future__ import annotations

import logging
import uuid
from threading import Lock
from typing import Any

from fastapi import Request

TRACE_ID_HEADER = "X-Trace-Id"
_LOGGING_CONFIGURED = False
_LOGGING_LOCK = Lock()


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    with _LOGGING_LOCK:
        if _LOGGING_CONFIGURED:
            return
        logger = logging.getLogger("app")
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)
        _LOGGING_CONFIGURED = True


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def set_request_trace_id(request: Request, trace_id: str) -> None:
    request.state.trace_id = trace_id


def get_request_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    header_value = request.headers.get(TRACE_ID_HEADER)
    if header_value:
        return header_value
    return new_trace_id(prefix="req")


def set_request_event_id(request: Request, event_id: int | str) -> None:
    request.state.event_id = str(event_id)


def get_request_event_id(request: Request) -> str:
    event_id = getattr(request.state, "event_id", None)
    if event_id is None or event_id == "":
        return "-"
    return str(event_id)


def correlation_extra(
    *,
    trace_id: str | None = None,
    event_id: int | str | None = None,
    tx_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id or "-",
        "event_id": "-" if event_id is None else str(event_id),
        "tx_hash": tx_hash or "-",
    }
