from __future__ import annotations

import hmac
import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.jobs.anchor_worker import run_anchor_worker_once
from app.main import app


def _configure_runtime(
    db_path: Path,
    *,
    anchor_mode: str = "success",
    max_retries: int = 3,
) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})
    os.environ["ANCHOR_ADAPTER"] = "active_mock"
    os.environ["ANCHOR_MOCK_MODE"] = anchor_mode
    os.environ["ANCHOR_MAX_RETRIES"] = str(max_retries)


def _sign_payload(payload: dict[str, Any], secret: str) -> str:
    signing_payload = {
        "version": payload["version"],
        "device_id": payload["device_id"],
        "batch_id": payload["batch_id"],
        "timestamp": payload["timestamp"],
        "sensor_payload": payload["sensor_payload"],
        "signature_envelope": {
            "algorithm": payload["signature_envelope"]["algorithm"],
            "key_id": payload["signature_envelope"]["key_id"],
        },
    }
    canonical = canonicalize_payload(signing_payload)
    return hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), sha256
    ).hexdigest()


def _event_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": "device-observability-001",
        "batch_id": "batch-observability-2026-02-10",
        "timestamp": "2026-02-10T04:30:00Z",
        "sensor_payload": {
            "temperature_c": 5.1,
            "humidity_pct": 71.3,
            "status": "stable",
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": "factory-key-1",
        },
    }
    payload["signature_envelope"]["signature"] = _sign_payload(payload, "super-secret")
    return payload


def _extract_metric_value(
    metrics_text: str, metric_name: str, *, outcome: str
) -> float:
    pattern = re.compile(
        rf'^{re.escape(metric_name)}\{{outcome="{re.escape(outcome)}"\}}\s+([0-9]+(?:\.[0-9]+)?)$',
        re.MULTILINE,
    )
    match = pattern.search(metrics_text)
    if match is None:
        return 0.0
    return float(match.group(1))


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_ingest_anchoring_counters_and_latency_histograms(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "metrics-endpoint.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        baseline_response = await client.get("/metrics")
        assert baseline_response.status_code == 200
        ingest_before = _extract_metric_value(
            baseline_response.text,
            "traceability_ingest_requests_total",
            outcome="accepted",
        )
        anchor_before = _extract_metric_value(
            baseline_response.text,
            "traceability_anchoring_runs_total",
            outcome="anchored",
        )
        gate_success_before = _extract_metric_value(
            baseline_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="success",
        )
        gate_dead_letter_before = _extract_metric_value(
            baseline_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="dead_letter",
        )

        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "obs-metrics-key"},
            json=_event_payload(),
        )
        assert ingest_response.status_code == 202
        assert run_anchor_worker_once() == 1

        metrics_response = await client.get("/metrics")

    assert metrics_response.status_code == 200
    assert (
        _extract_metric_value(
            metrics_response.text,
            "traceability_ingest_requests_total",
            outcome="accepted",
        )
        >= ingest_before + 1
    )
    assert (
        _extract_metric_value(
            metrics_response.text,
            "traceability_anchoring_runs_total",
            outcome="anchored",
        )
        >= anchor_before + 1
    )
    assert (
        _extract_metric_value(
            metrics_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="success",
        )
        >= gate_success_before + 1
    )
    assert (
        _extract_metric_value(
            metrics_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="dead_letter",
        )
        == gate_dead_letter_before
    )
    assert "traceability_anchoring_outcomes_total" in metrics_response.text
    assert "traceability_ingest_latency_seconds_bucket" in metrics_response.text
    assert "traceability_ingest_latency_seconds_count" in metrics_response.text
    assert "traceability_anchoring_latency_seconds_bucket" in metrics_response.text
    assert "traceability_anchoring_latency_seconds_count" in metrics_response.text


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_retry_then_dead_letter_gate_outcomes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "metrics-anchor-failure.db"
    _configure_runtime(db_path, anchor_mode="failure", max_retries=2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        baseline_response = await client.get("/metrics")
        assert baseline_response.status_code == 200
        retry_before = _extract_metric_value(
            baseline_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="retry",
        )
        dead_letter_before = _extract_metric_value(
            baseline_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="dead_letter",
        )

        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "obs-metrics-failure-key"},
            json=_event_payload(),
        )
        assert ingest_response.status_code == 202

        assert run_anchor_worker_once() == 1
        assert run_anchor_worker_once() == 1

        metrics_response = await client.get("/metrics")

    assert metrics_response.status_code == 200
    assert (
        _extract_metric_value(
            metrics_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="retry",
        )
        >= retry_before + 1
    )
    assert (
        _extract_metric_value(
            metrics_response.text,
            "traceability_anchoring_outcomes_total",
            outcome="dead_letter",
        )
        >= dead_letter_before + 1
    )
