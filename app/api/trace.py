from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.trace_query import TraceBatchNotFoundError, query_trace_timeline
from app.services.simulation import ensure_simulation_batch, is_simulation_batch_id

router = APIRouter(prefix="/v1", tags=["trace"])


class AnchorView(BaseModel):
    status: str
    transaction_hash: str | None


class AlertSnapshotView(BaseModel):
    total: int
    open: int
    high_open: int


class TimelineEntryView(BaseModel):
    event_id: int
    timestamp: str
    ingest_status: str
    anchor: AnchorView
    quality_grade: str | None
    alert_snapshot: AlertSnapshotView


class TraceQueryResponse(BaseModel):
    batch_id: str
    timeline_order: Literal["oldest_first"]
    timeline: list[TimelineEntryView]


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


@router.get("/trace/{batch_id}", response_model=TraceQueryResponse)
async def get_trace_timeline(request: Request, batch_id: str) -> object:
    if is_simulation_batch_id(batch_id):
        ensure_simulation_batch(batch_id)

    try:
        timeline_entries = query_trace_timeline(batch_id)
    except TraceBatchNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail=f"No trace timeline found for batch_id '{batch_id}'.",
            type_path="trace-batch-not-found",
        )

    return TraceQueryResponse(
        batch_id=batch_id,
        timeline_order="oldest_first",
        timeline=[
            TimelineEntryView(
                event_id=entry.event_id,
                timestamp=entry.timestamp,
                ingest_status=entry.ingest_status,
                anchor=AnchorView(
                    status=entry.anchor_status,
                    transaction_hash=entry.anchor_transaction_hash,
                ),
                quality_grade=entry.quality_grade,
                alert_snapshot=AlertSnapshotView(**entry.alert_snapshot),
            )
            for entry in timeline_entries
        ],
    )
