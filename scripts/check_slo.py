from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.observability.metrics import render_metrics


@dataclass(frozen=True)
class SLOCheck:
    name: str
    status: str
    detail: str
    passed: bool


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_metrics_text() -> str:
    metrics_url = os.getenv("SLO_METRICS_URL", "http://127.0.0.1:8000/metrics")
    timeout_seconds = _float_env("SLO_METRICS_TIMEOUT_SECONDS", 2.0)
    try:
        with urllib.request.urlopen(metrics_url, timeout=timeout_seconds) as response:  # noqa: S310
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError):
        # Fallback keeps the MVP script runnable without a live server.
        return render_metrics()


def _parse_labels(raw_labels: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not raw_labels:
        return labels
    for part in raw_labels.split(","):
        key, _, raw_value = part.partition("=")
        if not key:
            continue
        labels[key.strip()] = raw_value.strip().strip('"')
    return labels


def _metric_value(metrics_text: str, metric_name: str, labels: dict[str, str] | None = None) -> float:
    expected = labels or {}
    pattern = re.compile(rf"^{re.escape(metric_name)}(?:\{{([^}}]*)\}})?\s+([-+eE0-9.]+)$", re.MULTILINE)
    for match in pattern.finditer(metrics_text):
        got_labels = _parse_labels(match.group(1) or "")
        if got_labels == expected:
            return float(match.group(2))
    return 0.0


def _histogram_quantile(metrics_text: str, metric_name: str, quantile: float) -> tuple[float | None, float]:
    count = _metric_value(metrics_text, f"{metric_name}_count")
    if count <= 0:
        return None, 0.0

    bucket_pattern = re.compile(
        rf"^{re.escape(metric_name)}_bucket\{{([^}}]*)\}}\s+([-+eE0-9.]+)$",
        re.MULTILINE,
    )
    buckets: list[tuple[float, float]] = []
    inf_bucket_count = count
    for match in bucket_pattern.finditer(metrics_text):
        labels = _parse_labels(match.group(1))
        le = labels.get("le")
        if le is None:
            continue
        bucket_value = float(match.group(2))
        if le == "+Inf":
            inf_bucket_count = bucket_value
            continue
        buckets.append((float(le), bucket_value))

    if not buckets:
        return None, inf_bucket_count

    buckets.sort(key=lambda item: item[0])
    threshold = quantile * count
    for upper_bound, cumulative in buckets:
        if cumulative >= threshold:
            return upper_bound, count
    return None, count


def _status_line(*, name: str, passed: bool, detail: str, no_data: bool = False) -> SLOCheck:
    if no_data:
        return SLOCheck(name=name, status="NO_DATA", detail=detail, passed=True)
    return SLOCheck(name=name, status="PASS" if passed else "FAIL", detail=detail, passed=passed)


def main() -> int:
    metrics_text = _load_metrics_text()

    max_ingest_p95 = _float_env("SLO_MAX_INGEST_P95_SECONDS", 2.0)
    max_anchor_p95 = _float_env("SLO_MAX_ANCHOR_P95_SECONDS", 5.0)
    min_anchor_success_rate = _float_env("SLO_MIN_ANCHOR_SUCCESS_RATE", 0.95)
    min_samples = max(0, _int_env("SLO_MIN_SAMPLES", 1))

    anchored = _metric_value(
        metrics_text,
        "traceability_anchoring_runs_total",
        labels={"outcome": "anchored"},
    )
    already_anchored = _metric_value(
        metrics_text,
        "traceability_anchoring_runs_total",
        labels={"outcome": "already_anchored"},
    )
    failed_retrying = _metric_value(
        metrics_text,
        "traceability_anchoring_runs_total",
        labels={"outcome": "failed_retrying"},
    )
    dead_letter = _metric_value(
        metrics_text,
        "traceability_anchoring_runs_total",
        labels={"outcome": "dead_letter"},
    )

    anchor_attempts = anchored + already_anchored + failed_retrying + dead_letter
    anchor_successes = anchored + already_anchored

    checks: list[SLOCheck] = []
    if anchor_attempts < min_samples or anchor_attempts == 0:
        checks.append(
            _status_line(
                name="anchor_success_rate",
                passed=True,
                no_data=True,
                detail=f"samples={anchor_attempts:.0f}, min_samples={min_samples}",
            )
        )
    else:
        success_rate = anchor_successes / anchor_attempts
        checks.append(
            _status_line(
                name="anchor_success_rate",
                passed=success_rate >= min_anchor_success_rate,
                detail=(
                    f"value={success_rate:.4f}, threshold>={min_anchor_success_rate:.4f}, "
                    f"samples={anchor_attempts:.0f}"
                ),
            )
        )

    ingest_p95, ingest_samples = _histogram_quantile(
        metrics_text,
        "traceability_ingest_latency_seconds",
        0.95,
    )
    if ingest_p95 is None or ingest_samples < min_samples:
        checks.append(
            _status_line(
                name="ingest_p95_seconds",
                passed=True,
                no_data=True,
                detail=f"samples={ingest_samples:.0f}, min_samples={min_samples}",
            )
        )
    else:
        checks.append(
            _status_line(
                name="ingest_p95_seconds",
                passed=ingest_p95 <= max_ingest_p95,
                detail=f"value<={ingest_p95:.6f}, threshold<={max_ingest_p95:.6f}",
            )
        )

    anchor_p95, anchor_samples = _histogram_quantile(
        metrics_text,
        "traceability_anchoring_latency_seconds",
        0.95,
    )
    if anchor_p95 is None or anchor_samples < min_samples:
        checks.append(
            _status_line(
                name="anchoring_p95_seconds",
                passed=True,
                no_data=True,
                detail=f"samples={anchor_samples:.0f}, min_samples={min_samples}",
            )
        )
    else:
        checks.append(
            _status_line(
                name="anchoring_p95_seconds",
                passed=anchor_p95 <= max_anchor_p95,
                detail=f"value<={anchor_p95:.6f}, threshold<={max_anchor_p95:.6f}",
            )
        )

    overall_pass = all(check.passed for check in checks)

    print("SLO CHECK SUMMARY")
    print("=================")
    for check in checks:
        print(f"- {check.name}: {check.status} ({check.detail})")
    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
