from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

GradeBand = Literal["ideal", "warning", "outside"]
GradeLetter = Literal["A", "B", "C"]

# Score per band: ideal=100, warning=50, outside=0
BAND_SCORES: dict[GradeBand, int] = {"ideal": 100, "warning": 50, "outside": 0}

# Default weights when only temperature and humidity are provided (backward compat)
_LEGACY_WEIGHTS = {"temperature_c": 0.5, "humidity_pct": 0.5}
_LEGACY_BAND_POINTS: dict[GradeBand, int] = {"ideal": 2, "warning": 1, "outside": 0}


@dataclass(frozen=True)
class QualityGradeResult:
    grade: GradeLetter
    score: int
    max_score: int
    reasons: list[str]
    threshold_context: dict[str, Any]


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, Any]:
    rules_path = Path(__file__).with_name("rules.yml")
    return json.loads(rules_path.read_text(encoding="utf-8"))


def _evaluate_metric(
    metric_name: str, value: float, metric_rules: dict[str, Any]
) -> tuple[GradeBand, int, str]:
    ideal = metric_rules["ideal"]
    warning = metric_rules["warning"]

    if ideal["min"] <= value <= ideal["max"]:
        return (
            "ideal",
            BAND_SCORES["ideal"],
            f"{metric_name} is within ideal range [{ideal['min']}, {ideal['max']}].",
        )
    if warning["min"] <= value <= warning["max"]:
        return (
            "warning",
            BAND_SCORES["warning"],
            (
                f"{metric_name} is within warning range [{warning['min']}, {warning['max']}] "
                f"but outside ideal range [{ideal['min']}, {ideal['max']}]."
            ),
        )
    return (
        "outside",
        BAND_SCORES["outside"],
        f"{metric_name} is outside warning range [{warning['min']}, {warning['max']}].",
    )


def _to_grade(score: int, thresholds: dict[str, int]) -> GradeLetter:
    if score >= thresholds["A"]:
        return "A"
    if score >= thresholds["B"]:
        return "B"
    return "C"


def grade_quality(
    *,
    temperature_c: float,
    humidity_pct: float,
    co2_ppm: Optional[float] = None,
    vibration_g: Optional[float] = None,
) -> QualityGradeResult:
    rules = _load_rules()

    evaluations: dict[str, tuple[GradeBand, int, str]] = {
        "temperature_c": _evaluate_metric(
            "temperature_c", temperature_c, rules["temperature_c"]
        ),
        "humidity_pct": _evaluate_metric(
            "humidity_pct", humidity_pct, rules["humidity_pct"]
        ),
    }

    if co2_ppm is not None:
        evaluations["co2_ppm"] = _evaluate_metric("co2_ppm", co2_ppm, rules["co2_ppm"])
    if vibration_g is not None:
        evaluations["vibration_g"] = _evaluate_metric(
            "vibration_g", vibration_g, rules["vibration_g"]
        )

    # Determine weights: use configured weights if all 4 metrics are present,
    # otherwise distribute evenly among available metrics
    has_all_metrics = co2_ppm is not None and vibration_g is not None
    if has_all_metrics:
        weights = {k: rules[k].get("weight", 0.25) for k in evaluations}
    else:
        equal_weight = 1.0 / len(evaluations)
        weights = {k: equal_weight for k in evaluations}

    if not has_all_metrics:
        legacy_score = sum(
            _LEGACY_BAND_POINTS[evaluations[k][0]]
            for k in ("temperature_c", "humidity_pct")
        )
        score = int(legacy_score)
        max_score = 4
        score_percent = round((score / max_score) * 100)
        grade = _to_grade(score_percent, rules["grade_thresholds"])
    else:
        weighted_score = sum(evaluations[k][1] * weights[k] for k in evaluations)
        score = round(weighted_score)
        max_score = 100
        grade = _to_grade(score, rules["grade_thresholds"])
    reasons = [item[2] for item in evaluations.values()]

    threshold_context: dict[str, Any] = {}
    for metric in evaluations:
        threshold_context[metric] = rules[metric]
    threshold_context["grade_thresholds"] = rules["grade_thresholds"]
    threshold_context["bands"] = {
        metric: item[0] for metric, item in evaluations.items()
    }
    threshold_context["weights"] = weights

    return QualityGradeResult(
        grade=grade,
        score=score,
        max_score=max_score,
        reasons=reasons,
        threshold_context=threshold_context,
    )
