from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{key}="{_escape_label_value(labels[key])}"' for key in sorted(labels)]
    return "{" + ",".join(parts) + "}"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.12g}"


@dataclass
class _HistogramSample:
    count: int
    value_sum: float
    bucket_counts: list[int]


class CounterVec:
    def __init__(
        self, name: str, documentation: str, *, label_names: tuple[str, ...]
    ) -> None:
        self.name = name
        self.documentation = documentation
        self.label_names = label_names
        self._samples: dict[tuple[str, ...], float] = {}
        self._lock = Lock()

    def inc(self, labels: dict[str, str], amount: float = 1.0) -> None:
        key = tuple(labels[label] for label in self.label_names)
        with self._lock:
            self._samples[key] = self._samples.get(key, 0.0) + amount

    def collect(self) -> list[str]:
        with self._lock:
            snapshot = dict(self._samples)
        lines = [
            f"# HELP {self.name} {self.documentation}",
            f"# TYPE {self.name} counter",
        ]
        for key in sorted(snapshot):
            labels = {
                label_name: key[index]
                for index, label_name in enumerate(self.label_names)
            }
            lines.append(
                f"{self.name}{_format_labels(labels)} {_format_number(snapshot[key])}"
            )
        return lines


class Histogram:
    def __init__(
        self,
        name: str,
        documentation: str,
        *,
        buckets: tuple[float, ...],
        label_names: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.documentation = documentation
        self.label_names = label_names
        self.buckets = tuple(sorted(buckets))
        self._samples: dict[tuple[str, ...], _HistogramSample] = {}
        self._lock = Lock()

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        safe_labels = labels or {}
        key = tuple(safe_labels.get(label, "") for label in self.label_names)
        with self._lock:
            sample = self._samples.get(key)
            if sample is None:
                sample = _HistogramSample(
                    count=0,
                    value_sum=0.0,
                    bucket_counts=[0 for _ in range(len(self.buckets) + 1)],
                )
                self._samples[key] = sample

            sample.count += 1
            sample.value_sum += value
            for index, bound in enumerate(self.buckets):
                if value <= bound:
                    sample.bucket_counts[index] += 1
            sample.bucket_counts[-1] += 1

    def collect(self) -> list[str]:
        with self._lock:
            snapshot = {
                key: _HistogramSample(
                    count=sample.count,
                    value_sum=sample.value_sum,
                    bucket_counts=list(sample.bucket_counts),
                )
                for key, sample in self._samples.items()
            }

        lines = [
            f"# HELP {self.name} {self.documentation}",
            f"# TYPE {self.name} histogram",
        ]
        for key in sorted(snapshot):
            sample = snapshot[key]
            series_labels = {
                label_name: key[index]
                for index, label_name in enumerate(self.label_names)
                if key[index] != ""
            }
            for index, bound in enumerate(self.buckets):
                bucket_labels = dict(series_labels)
                bucket_labels["le"] = _format_number(bound)
                lines.append(
                    f"{self.name}_bucket{_format_labels(bucket_labels)} {sample.bucket_counts[index]}"
                )
            inf_labels = dict(series_labels)
            inf_labels["le"] = "+Inf"
            lines.append(
                f"{self.name}_bucket{_format_labels(inf_labels)} {sample.bucket_counts[-1]}"
            )
            lines.append(
                f"{self.name}_sum{_format_labels(series_labels)} {_format_number(sample.value_sum)}"
            )
            lines.append(
                f"{self.name}_count{_format_labels(series_labels)} {sample.count}"
            )
        return lines


INGEST_REQUESTS_TOTAL = CounterVec(
    "traceability_ingest_requests_total",
    "Total ingest requests by outcome.",
    label_names=("outcome",),
)

ANCHORING_RUNS_TOTAL = CounterVec(
    "traceability_anchoring_runs_total",
    "Total anchoring attempts by outcome.",
    label_names=("outcome",),
)

ANCHORING_OUTCOMES_TOTAL = CounterVec(
    "traceability_anchoring_outcomes_total",
    "Anchoring canary gate outcomes (success/retry/dead_letter).",
    label_names=("outcome",),
)

ANCHORING_ROLLOUT_DECISIONS_TOTAL = CounterVec(
    "traceability_anchoring_rollout_decisions_total",
    "Anchoring rollout routing decisions by mode and path.",
    label_names=("mode", "path"),
)

ANCHORING_ROLLOUT_TRANSITIONS_TOTAL = CounterVec(
    "traceability_anchoring_rollout_transitions_total",
    "Anchoring rollout state transitions.",
    label_names=("to_state",),
)

ANCHORING_ROLLOUT_CANARY_OUTCOMES_TOTAL = CounterVec(
    "traceability_anchoring_rollout_canary_outcomes_total",
    "Canary cohort outcomes for rollout SLO checks.",
    label_names=("outcome",),
)

COMPAT_REQUESTS_TOTAL = CounterVec(
    "traceability_compat_requests_total",
    "Compatibility endpoint requests by endpoint/method/status.",
    label_names=("endpoint", "method", "status"),
)

ANCHORING_ROLLOUT_CANARY_CONFIRMATION_SECONDS = Histogram(
    "traceability_anchoring_rollout_canary_confirmation_seconds",
    "Canary cohort confirmation latency in seconds.",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 180.0, 300.0, 600.0),
)

INGEST_LATENCY_SECONDS = Histogram(
    "traceability_ingest_latency_seconds",
    "Ingest request latency in seconds.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

ANCHORING_LATENCY_SECONDS = Histogram(
    "traceability_anchoring_latency_seconds",
    "Anchoring processing latency in seconds.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)


def observe_ingest_request(*, outcome: str, latency_seconds: float) -> None:
    INGEST_REQUESTS_TOTAL.inc({"outcome": outcome})
    INGEST_LATENCY_SECONDS.observe(max(0.0, latency_seconds))


def observe_anchoring_run(*, outcome: str, latency_seconds: float) -> None:
    ANCHORING_RUNS_TOTAL.inc({"outcome": outcome})
    ANCHORING_LATENCY_SECONDS.observe(max(0.0, latency_seconds))


def observe_anchoring_outcome(*, outcome: str) -> None:
    ANCHORING_OUTCOMES_TOTAL.inc({"outcome": outcome})


def observe_anchoring_rollout_decision(*, mode: str, path: str) -> None:
    ANCHORING_ROLLOUT_DECISIONS_TOTAL.inc({"mode": mode, "path": path})


def observe_anchoring_rollout_transition(*, to_state: str) -> None:
    ANCHORING_ROLLOUT_TRANSITIONS_TOTAL.inc({"to_state": to_state})


def observe_anchoring_rollout_canary_outcome(
    *, outcome: str, confirmation_seconds: float | None = None
) -> None:
    ANCHORING_ROLLOUT_CANARY_OUTCOMES_TOTAL.inc({"outcome": outcome})
    if confirmation_seconds is not None:
        ANCHORING_ROLLOUT_CANARY_CONFIRMATION_SECONDS.observe(
            max(0.0, confirmation_seconds)
        )


def observe_compat_request(*, endpoint: str, method: str, status: int) -> None:
    COMPAT_REQUESTS_TOTAL.inc(
        {
            "endpoint": endpoint,
            "method": method.upper(),
            "status": str(status),
        }
    )


def render_metrics() -> str:
    lines: list[str] = []
    lines.extend(INGEST_REQUESTS_TOTAL.collect())
    lines.extend(ANCHORING_RUNS_TOTAL.collect())
    lines.extend(ANCHORING_OUTCOMES_TOTAL.collect())
    lines.extend(ANCHORING_ROLLOUT_DECISIONS_TOTAL.collect())
    lines.extend(ANCHORING_ROLLOUT_TRANSITIONS_TOTAL.collect())
    lines.extend(ANCHORING_ROLLOUT_CANARY_OUTCOMES_TOTAL.collect())
    lines.extend(COMPAT_REQUESTS_TOTAL.collect())
    lines.extend(ANCHORING_ROLLOUT_CANARY_CONFIRMATION_SECONDS.collect())
    lines.extend(INGEST_LATENCY_SECONDS.collect())
    lines.extend(ANCHORING_LATENCY_SECONDS.collect())
    return "\n".join(lines) + "\n"


for _outcome in ("accepted", "rejected_signature", "idempotency_conflict"):
    INGEST_REQUESTS_TOTAL.inc({"outcome": _outcome}, amount=0.0)

for _outcome in ("anchored", "failed_retrying", "dead_letter", "already_anchored"):
    ANCHORING_RUNS_TOTAL.inc({"outcome": _outcome}, amount=0.0)

for _outcome in ("success", "retry", "dead_letter"):
    ANCHORING_OUTCOMES_TOTAL.inc({"outcome": _outcome}, amount=0.0)

for _mode in ("shadow", "canary", "full", "rollback_safe"):
    for _path in ("safe", "evm"):
        ANCHORING_ROLLOUT_DECISIONS_TOTAL.inc(
            {"mode": _mode, "path": _path}, amount=0.0
        )

for _state in ("rollback_safe", "canary", "full", "shadow"):
    ANCHORING_ROLLOUT_TRANSITIONS_TOTAL.inc({"to_state": _state}, amount=0.0)

for _outcome in ("success", "retry", "dead_letter"):
    ANCHORING_ROLLOUT_CANARY_OUTCOMES_TOTAL.inc({"outcome": _outcome}, amount=0.0)

for _endpoint, _method in (
    ("/v1/events/recent", "GET"),
    ("/v1/trace/{batch_id}/public", "GET"),
    ("/api/cherry/telemetry", "POST"),
):
    for _status in ("200", "202", "400", "401", "409"):
        COMPAT_REQUESTS_TOTAL.inc(
            {
                "endpoint": _endpoint,
                "method": _method,
                "status": _status,
            },
            amount=0.0,
        )
