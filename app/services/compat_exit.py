from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

COMPAT_EXIT_HISTORY_DEFAULT_PATH = Path("data/compat_traffic_history.json")


@dataclass(frozen=True)
class CompatExitCriteriaConfig:
    required_releases: int
    required_consecutive_days: int
    max_compat_ratio: float


@dataclass(frozen=True)
class CompatTrafficSample:
    day: date
    compat_requests: int
    total_requests: int
    compat_ratio: float


@dataclass(frozen=True)
class CompatExitEvaluation:
    criteria_passed: bool
    releases_observed: int
    trailing_streak_days: int
    trailing_streak_dates: tuple[str, ...]
    required_releases: int
    required_consecutive_days: int
    max_compat_ratio: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CompatClosureDecision:
    closure_requested: bool
    include_compat_router: bool
    evaluation: CompatExitEvaluation | None


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _optional_int_env(name: str) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def compat_closure_requested() -> bool:
    return _bool_env("COMPAT_CLOSURE_ENABLED", False)


def load_exit_criteria_config_from_env() -> CompatExitCriteriaConfig:
    required_releases = max(1, _int_env("COMPAT_EXIT_REQUIRED_RELEASES", 2))
    required_consecutive_days = max(
        1, _int_env("COMPAT_EXIT_REQUIRED_CONSECUTIVE_DAYS", 14)
    )
    max_ratio_percent = _float_env("COMPAT_EXIT_MAX_RATIO_PERCENT", 1.0)
    max_compat_ratio = max(0.0, min(100.0, max_ratio_percent)) / 100.0
    return CompatExitCriteriaConfig(
        required_releases=required_releases,
        required_consecutive_days=required_consecutive_days,
        max_compat_ratio=max_compat_ratio,
    )


def _parse_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("traffic day requires a string `date` field")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid date '{value}'") from exc


def _parse_non_negative_int(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


def _compat_requests_from_day(day: dict[str, Any]) -> int | None:
    direct_value = day.get("compat_requests")
    if direct_value is not None:
        return _parse_non_negative_int(direct_value, field_name="compat_requests")

    by_endpoint = day.get("compat_requests_by_endpoint")
    if by_endpoint is None:
        return None
    if not isinstance(by_endpoint, dict):
        raise ValueError("compat_requests_by_endpoint must be an object")

    total = 0
    for endpoint, value in by_endpoint.items():
        if not isinstance(endpoint, str):
            raise ValueError("compat_requests_by_endpoint keys must be strings")
        total += _parse_non_negative_int(
            value, field_name=f"compat_requests_by_endpoint['{endpoint}']"
        )
    return total


def _ratio_from_day(
    day: dict[str, Any], *, compat_requests: int, total_requests: int
) -> float:
    raw_ratio = day.get("compat_ratio")
    if raw_ratio is not None:
        if not isinstance(raw_ratio, (int, float)):
            raise ValueError("compat_ratio must be numeric")
        ratio = float(raw_ratio)
        if ratio < 0.0 or ratio > 1.0:
            raise ValueError("compat_ratio must be between 0.0 and 1.0")
        return ratio

    if total_requests == 0:
        return 0.0
    return compat_requests / float(total_requests)


def parse_compat_traffic_history(
    payload: dict[str, Any],
    *,
    releases_observed_override: int | None = None,
) -> tuple[int, list[CompatTrafficSample]]:
    if releases_observed_override is not None:
        releases_observed = max(0, releases_observed_override)
    else:
        releases_observed = _parse_non_negative_int(
            payload.get("releases_observed", 0),
            field_name="releases_observed",
        )

    raw_days = payload.get("daily")
    if not isinstance(raw_days, list):
        raise ValueError("history payload requires a `daily` list")

    samples: list[CompatTrafficSample] = []
    seen_dates: set[date] = set()
    for index, raw_day in enumerate(raw_days):
        if not isinstance(raw_day, dict):
            raise ValueError(f"daily[{index}] must be an object")
        day_value = _parse_date(raw_day.get("date"))
        if day_value in seen_dates:
            raise ValueError(f"duplicate daily sample for date {day_value.isoformat()}")
        seen_dates.add(day_value)

        total_requests = _parse_non_negative_int(
            raw_day.get("total_requests", 0),
            field_name=f"daily[{index}].total_requests",
        )
        compat_requests = _compat_requests_from_day(raw_day)
        if compat_requests is None:
            compat_requests = 0
        ratio = _ratio_from_day(
            raw_day,
            compat_requests=compat_requests,
            total_requests=total_requests,
        )

        samples.append(
            CompatTrafficSample(
                day=day_value,
                compat_requests=compat_requests,
                total_requests=total_requests,
                compat_ratio=ratio,
            )
        )

    samples.sort(key=lambda sample: sample.day)
    return releases_observed, samples


def load_compat_traffic_history(
    history_path: Path,
    *,
    releases_observed_override: int | None = None,
) -> tuple[int, list[CompatTrafficSample]]:
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("history file must contain a JSON object")
    return parse_compat_traffic_history(
        payload,
        releases_observed_override=releases_observed_override,
    )


def evaluate_compat_exit_criteria(
    *,
    releases_observed: int,
    samples: list[CompatTrafficSample],
    config: CompatExitCriteriaConfig,
) -> CompatExitEvaluation:
    reasons: list[str] = []

    if releases_observed < config.required_releases:
        reasons.append(
            "releases_below_threshold:"
            f" observed={releases_observed} required>={config.required_releases}"
        )

    trailing_streak: list[CompatTrafficSample] = []
    previous_day: date | None = None
    for sample in reversed(samples):
        under_threshold = sample.compat_ratio < config.max_compat_ratio
        if not under_threshold:
            break
        if previous_day is not None and (previous_day - sample.day).days != 1:
            break
        trailing_streak.append(sample)
        previous_day = sample.day

    trailing_streak_days = len(trailing_streak)
    if trailing_streak_days < config.required_consecutive_days:
        reasons.append(
            "traffic_streak_below_threshold:"
            f" trailing_days={trailing_streak_days}"
            f" required>={config.required_consecutive_days}"
            f" ratio<{config.max_compat_ratio:.6f}"
        )

    trailing_streak_dates = tuple(
        sample.day.isoformat() for sample in reversed(trailing_streak)
    )
    return CompatExitEvaluation(
        criteria_passed=not reasons,
        releases_observed=releases_observed,
        trailing_streak_days=trailing_streak_days,
        trailing_streak_dates=trailing_streak_dates,
        required_releases=config.required_releases,
        required_consecutive_days=config.required_consecutive_days,
        max_compat_ratio=config.max_compat_ratio,
        reasons=tuple(reasons),
    )


def evaluate_compat_closure_decision() -> CompatClosureDecision:
    closure_requested = compat_closure_requested()
    if not closure_requested:
        return CompatClosureDecision(
            closure_requested=False,
            include_compat_router=True,
            evaluation=None,
        )

    config = load_exit_criteria_config_from_env()
    history_path = Path(
        os.getenv("COMPAT_EXIT_HISTORY_PATH", str(COMPAT_EXIT_HISTORY_DEFAULT_PATH))
    )
    releases_observed_override = _optional_int_env("COMPAT_EXIT_RELEASES_OBSERVED")

    try:
        releases_observed, samples = load_compat_traffic_history(
            history_path,
            releases_observed_override=releases_observed_override,
        )
        evaluation = evaluate_compat_exit_criteria(
            releases_observed=releases_observed,
            samples=samples,
            config=config,
        )
    except Exception as exc:  # noqa: BLE001 - startup must stay safe.
        evaluation = CompatExitEvaluation(
            criteria_passed=False,
            releases_observed=max(0, releases_observed_override or 0),
            trailing_streak_days=0,
            trailing_streak_dates=(),
            required_releases=config.required_releases,
            required_consecutive_days=config.required_consecutive_days,
            max_compat_ratio=config.max_compat_ratio,
            reasons=(f"invalid_exit_criteria_input:{exc}",),
        )

    return CompatClosureDecision(
        closure_requested=True,
        include_compat_router=not evaluation.criteria_passed,
        evaluation=evaluation,
    )
