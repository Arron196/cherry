from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.security.auth import Principal
from app.security.rbac import require_roles
from app.services.anchoring_management import (
    DEFAULT_QUERY_LIMIT,
    MAX_QUERY_LIMIT,
    AnchoringTaskNotFoundError,
    AnchoringTaskRequeueConflictError,
    list_anchoring_tasks,
    requeue_anchoring_task,
    run_anchoring_once,
)

router = APIRouter(prefix="/admin/anchoring", tags=["admin"])

AnchoringTaskStatus = Literal[
    "RECEIVED",
    "ANCHORING",
    "ANCHORED",
    "FAILED_RETRYING",
    "DEAD_LETTER",
]


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


class AnchoringTaskItemView(BaseModel):
    ingest_request_id: int
    event_id: int
    batch_id: str
    device_id: str
    status: str
    retry_count: int
    last_error: str | None
    created_at: str


class AnchoringTaskListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AnchoringTaskItemView]


class RequeueAnchoringTaskResponse(BaseModel):
    ingest_request_id: int
    status: str
    retry_count: int
    audit_id: int


class RunAnchoringOnceRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=1000)


class RunAnchoringOnceResponse(BaseModel):
    processed: int
    limit: int
    audit_id: int


@router.get("/tasks", response_model=AnchoringTaskListResponse)
async def get_anchoring_tasks(
    status: AnchoringTaskStatus,
    limit: int = Query(default=DEFAULT_QUERY_LIMIT, ge=1, le=MAX_QUERY_LIMIT),
    offset: int = Query(default=0, ge=0),
    batch_id: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    _principal: Principal = Depends(require_roles("admin")),
) -> AnchoringTaskListResponse:
    page = list_anchoring_tasks(
        status=status,
        limit=limit,
        offset=offset,
        batch_id=batch_id,
        device_id=device_id,
    )
    return AnchoringTaskListResponse(
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        items=[AnchoringTaskItemView(**item.__dict__) for item in page.items],
    )


@router.post("/tasks/{ingest_request_id}/requeue", response_model=RequeueAnchoringTaskResponse)
async def requeue_anchoring(
    ingest_request_id: int,
    request: Request,
    principal: Principal = Depends(require_roles("admin")),
) -> RequeueAnchoringTaskResponse | JSONResponse:
    try:
        result = requeue_anchoring_task(actor=principal.subject, ingest_request_id=ingest_request_id)
    except AnchoringTaskNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Anchoring ingest request was not found.",
            type_path="anchoring-task-not-found",
        )
    except AnchoringTaskRequeueConflictError as exc:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail=(
                "Anchoring ingest request cannot be requeued from current status "
                f"'{exc.current_status}'."
            ),
            type_path="anchoring-task-not-requeueable",
        )

    return RequeueAnchoringTaskResponse(
        ingest_request_id=result.ingest_request_id,
        status=result.status,
        retry_count=result.retry_count,
        audit_id=result.audit_id,
    )


@router.post("/run-once", response_model=RunAnchoringOnceResponse)
async def run_anchoring_worker_once(
    payload: RunAnchoringOnceRequest | None = None,
    principal: Principal = Depends(require_roles("admin")),
) -> RunAnchoringOnceResponse:
    result = run_anchoring_once(actor=principal.subject, limit=payload.limit if payload else None)
    return RunAnchoringOnceResponse(
        processed=result.processed,
        limit=result.limit,
        audit_id=result.audit_id,
    )
