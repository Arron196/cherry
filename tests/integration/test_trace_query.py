from __future__ import annotations

import hmac
import json
import os
import sqlite3
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
    return hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), sha256
    ).hexdigest()


def _event_payload(
    *, batch_id: str, timestamp: str, temperature_c: float
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": "device-trace-001",
        "batch_id": batch_id,
        "timestamp": timestamp,
        "sensor_payload": {
            "temperature_c": temperature_c,
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


def _insert_quality_result(
    db_path: Path,
    event_id: int,
    grade: str,
    *,
    score: float = 4.0,
    evaluated_at: str | None = None,
) -> None:
    with sqlite3.connect(db_path) as connection:
        if evaluated_at is None:
            connection.execute(
                "INSERT INTO quality_results (event_id, check_name, status, score, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    event_id,
                    "quality.grade",
                    "PASS",
                    score,
                    json.dumps({"grade": grade}),
                ),
            )
        else:
            connection.execute(
                "INSERT INTO quality_results (event_id, check_name, status, score, details, evaluated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    "quality.grade",
                    "PASS",
                    score,
                    json.dumps({"grade": grade}),
                    evaluated_at,
                ),
            )
        connection.commit()


def _insert_anchor_receipt(db_path: Path, event_id: int, transaction_hash: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO anchor_receipts (event_id, network, transaction_hash, receipt_payload, anchored_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event_id,
                "active_mock",
                transaction_hash,
                json.dumps({"status": "ok"}),
                "2026-02-10 07:00:00",
            ),
        )
        connection.commit()


def _insert_alerts(db_path: Path, event_id: int) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO alerts (event_id, alert_type, severity, message, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, "temperature_spike", "high", "temp exceeded threshold", "open"),
        )
        connection.execute(
            "INSERT INTO alerts (event_id, alert_type, severity, message, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, "humidity_warning", "low", "humidity warning", "resolved"),
        )
        connection.execute(
            "INSERT INTO alerts (event_id, alert_type, severity, message, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, "chain_unstable", "critical", "critical chain alert", "open"),
        )
        connection.commit()


@pytest.mark.asyncio
async def test_trace_query_returns_ordered_public_timeline_with_mvp_fields(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "trace-query-success.db"
    _configure_runtime(db_path)

    newer_event = _event_payload(
        batch_id="batch-trace-001",
        timestamp="2026-02-10T06:00:00Z",
        temperature_c=6.0,
    )
    older_event = _event_payload(
        batch_id="batch-trace-001",
        timestamp="2026-02-10T04:00:00Z",
        temperature_c=4.5,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        newer_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "trace-key-new"},
            json=newer_event,
        )
        older_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "trace-key-old"},
            json=older_event,
        )

        assert newer_response.status_code == 202
        assert older_response.status_code == 202

        assert run_anchor_worker_once() == 2

        older_event_id = int(older_response.json()["event_id"])
        _insert_quality_result(db_path, older_event_id, "B")
        _insert_alerts(db_path, older_event_id)

        trace_response = await client.get("/v1/trace/batch-trace-001")

    assert trace_response.status_code == 200
    payload = trace_response.json()
    assert payload["batch_id"] == "batch-trace-001"
    assert payload["timeline_order"] == "oldest_first"
    assert len(payload["timeline"]) == 2

    timeline = payload["timeline"]
    assert [entry["timestamp"] for entry in timeline] == [
        "2026-02-10T04:00:00Z",
        "2026-02-10T06:00:00Z",
    ]

    sensitive_keys = {
        "sensor_payload",
        "signature_envelope",
        "canonical_hash",
        "payload_hash",
        "last_error",
        "receipt_payload",
    }

    older_entry = timeline[0]
    assert set(older_entry) >= {
        "event_id",
        "timestamp",
        "ingest_status",
        "anchor",
        "quality_grade",
        "alert_snapshot",
    }
    assert older_entry["ingest_status"] == "ANCHORED"
    assert older_entry["anchor"]["status"] == "ANCHORED"
    assert isinstance(older_entry["anchor"]["transaction_hash"], str)
    assert older_entry["quality_grade"] == "B"
    assert older_entry["alert_snapshot"] == {
        "total": 3,
        "open": 2,
        "high_open": 2,
    }
    assert sensitive_keys.isdisjoint(older_entry)

    newer_entry = timeline[1]
    assert newer_entry["ingest_status"] == "ANCHORED"
    assert newer_entry["anchor"]["status"] == "ANCHORED"
    assert isinstance(newer_entry["anchor"]["transaction_hash"], str)
    assert newer_entry["quality_grade"] is None
    assert newer_entry["alert_snapshot"] == {
        "total": 0,
        "open": 0,
        "high_open": 0,
    }
    assert sensitive_keys.isdisjoint(newer_entry)


@pytest.mark.asyncio
async def test_trace_query_returns_rfc9457_for_unknown_batch(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-query-not-found.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/trace/batch-not-found")

    assert response.status_code == 404
    payload = response.json()
    assert set(payload) == {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 404
    assert payload["instance"] == "/v1/trace/batch-not-found"


@pytest.mark.asyncio
async def test_trace_query_prefers_latest_anchor_and_quality_records(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "trace-query-latest-records.db"
    _configure_runtime(db_path)

    event_payload = _event_payload(
        batch_id="batch-trace-latest",
        timestamp="2026-02-10T04:00:00Z",
        temperature_c=5.0,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "trace-key-latest"},
            json=event_payload,
        )

        assert response.status_code == 202
        assert run_anchor_worker_once() == 1

        event_id = int(response.json()["event_id"])
        _insert_anchor_receipt(db_path, event_id, "0xtx-hash-latest")
        _insert_quality_result(
            db_path,
            event_id,
            "B",
            score=80.0,
            evaluated_at="2026-02-10 05:00:00",
        )
        _insert_quality_result(
            db_path,
            event_id,
            "A",
            score=98.0,
            evaluated_at="2026-02-10 06:00:00",
        )

        trace_response = await client.get("/v1/trace/batch-trace-latest")

    assert trace_response.status_code == 200
    payload = trace_response.json()
    assert len(payload["timeline"]) == 1

    entry = payload["timeline"][0]
    assert entry["anchor"]["transaction_hash"] == "0xtx-hash-latest"
    assert entry["quality_grade"] == "A"


@pytest.mark.asyncio
async def test_trace_query_breaks_quality_ties_by_higher_id_when_timestamps_match(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "trace-query-quality-tie.db"
    _configure_runtime(db_path)

    event_payload = _event_payload(
        batch_id="batch-trace-quality-tie",
        timestamp="2026-02-10T04:00:00Z",
        temperature_c=5.0,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "trace-key-quality-tie"},
            json=event_payload,
        )

        assert response.status_code == 202

        event_id = int(response.json()["event_id"])
        _insert_quality_result(
            db_path,
            event_id,
            "B",
            score=80.0,
            evaluated_at="2026-02-10 06:00:00",
        )
        _insert_quality_result(
            db_path,
            event_id,
            "A",
            score=98.0,
            evaluated_at="2026-02-10 06:00:00",
        )

        trace_response = await client.get("/v1/trace/batch-trace-quality-tie")

    assert trace_response.status_code == 200
    payload = trace_response.json()
    assert len(payload["timeline"]) == 1
    assert payload["timeline"][0]["quality_grade"] == "A"
