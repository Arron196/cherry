from __future__ import annotations

import hmac
import json
import os
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.main import app


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})


def _sign_payload(payload: dict, secret: str) -> str:
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


def _event_payload(temperature_c: float) -> dict:
    payload = {
        "version": "1.0.0",
        "device_id": "device-001",
        "batch_id": "batch-2026-02-10",
        "timestamp": "2026-02-10T02:00:00Z",
        "sensor_payload": {
            "temperature_c": temperature_c,
            "humidity_pct": 73.0,
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


def _event_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.asyncio
async def test_ingest_replays_same_idempotency_key_for_same_body(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest-idempotency-replay.db"
    _configure_runtime(db_path)
    payload = _event_payload(temperature_c=4.2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-replay-1"},
            json=payload,
        )
        second_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-replay-1"},
            json=payload,
        )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert first_payload["event_id"] == second_payload["event_id"]
    assert first_payload["ingest_status"] == "RECEIVED"
    assert second_payload["ingest_status"] == "RECEIVED"
    assert _event_count(db_path) == 1


@pytest.mark.asyncio
async def test_ingest_returns_409_for_same_idempotency_key_with_different_body(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ingest-idempotency-conflict.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-conflict-1"},
            json=_event_payload(temperature_c=4.2),
        )
        conflict_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-conflict-1"},
            json=_event_payload(temperature_c=9.9),
        )

    assert first_response.status_code == 202
    assert conflict_response.status_code == 409
    payload = conflict_response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 409
    assert payload["instance"] == "/v1/events"
    assert _event_count(db_path) == 1
