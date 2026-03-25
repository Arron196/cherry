from __future__ import annotations

from fastapi import APIRouter

from app.domain.contracts.hash_canonicalization import canonical_hash
from app.domain.contracts.trace_event import TraceEvent

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("/trace-events/validate")
async def validate_trace_event(payload: TraceEvent) -> dict[str, str]:
    return {
        "status": "valid",
        "canonical_hash": canonical_hash(payload.canonical_payload()),
    }
