from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.domain.quality.grading import grade_quality

router = APIRouter(prefix="/v1", tags=["quality"])


class QualityGradeRequest(BaseModel):
    temperature_c: float = Field(ge=-50, le=120)
    humidity_pct: float = Field(ge=0, le=100)
    co2_ppm: Optional[float] = Field(default=None, ge=0)
    vibration_g: Optional[float] = Field(default=None, ge=0)


class QualityGradeResponse(BaseModel):
    grade: Literal["A", "B", "C"]
    score: int
    max_score: int
    reasons: list[str]
    threshold_context: dict[str, Any]


@router.post("/quality/grade", response_model=QualityGradeResponse)
async def grade_quality_endpoint(payload: QualityGradeRequest) -> QualityGradeResponse:
    result = grade_quality(
        temperature_c=payload.temperature_c,
        humidity_pct=payload.humidity_pct,
        co2_ppm=payload.co2_ppm,
        vibration_g=payload.vibration_g,
    )
    return QualityGradeResponse(
        grade=result.grade,
        score=result.score,
        max_score=result.max_score,
        reasons=result.reasons,
        threshold_context=result.threshold_context,
    )
