from __future__ import annotations

import hmac
import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.jobs.anchor_worker import run_anchor_worker_once
from app.main import app


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})
    os.environ["ANCHOR_ADAPTER"] = "active_mock"
    os.environ["ANCHOR_MOCK_MODE"] = "success"


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
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), sha256).hexdigest()


def _event_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": "device-correlation-001",
        "batch_id": "batch-correlation-2026-02-10",
        "timestamp": "2026-02-10T05:00:00Z",
        "sensor_payload": {
            "temperature_c": 6.0,
            "humidity_pct": 70.0,
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


@pytest.mark.asyncio
async def test_request_and_worker_logs_include_correlation_ids(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "correlation-ids.db"
    _configure_runtime(db_path)

    caplog.set_level("INFO", logger="app")
    trace_id = "trace-correlation-integration"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={
                "Idempotency-Key": "obs-correlation-key",
                "X-Trace-Id": trace_id,
            },
            json=_event_payload(),
        )

    assert response.status_code == 202
    event_id = response.json()["event_id"]

    processed = run_anchor_worker_once()
    assert processed == 1

    request_records = [
        record
        for record in caplog.records
        if record.name.startswith("app.request") and getattr(record, "event_id", "-") != "-"
    ]
    assert request_records
    assert any(getattr(record, "trace_id", "") == trace_id for record in request_records)
    assert any(str(getattr(record, "event_id", "")) == str(event_id) for record in request_records)

    worker_records = [record for record in caplog.records if record.name.startswith("app.worker")]
    assert worker_records
    assert any(getattr(record, "trace_id", "") not in {"", "-"} for record in worker_records)
    assert any(str(getattr(record, "event_id", "")) == str(event_id) for record in worker_records)
    assert any(str(getattr(record, "tx_hash", "")).startswith("0x") for record in worker_records)
