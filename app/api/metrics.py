from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.observability.metrics import render_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(
        content=render_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
