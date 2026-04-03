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


def _build_valid_event_payload() -> dict:
    payload = {
        "version": "1.0.0",
        "device_id": "device-001",
        "batch_id": "batch-2026-02-10",
        "timestamp": "2026-02-10T02:00:00Z",
        "sensor_payload": {
            "temperature_c": 4.2,
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
async def test_ingest_accepts_valid_signed_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest-signed.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-signed-ok"},
            json=_build_valid_event_payload(),
        )

    assert response.status_code == 202
    payload = response.json()
    assert set(payload) == {"event_id", "ingest_status"}
    assert isinstance(payload["event_id"], int)
    assert payload["ingest_status"] == "RECEIVED"
    assert _event_count(db_path) == 1


@pytest.mark.asyncio
async def test_ingest_rejects_signature_mismatch_with_rfc9457(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest-signature-mismatch.db"
    _configure_runtime(db_path)
    event_payload = _build_valid_event_payload()
    event_payload["signature_envelope"]["signature"] = "not-a-valid-signature"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-signature-mismatch"},
            json=event_payload,
        )

    assert response.status_code == 401
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 401
    assert payload["instance"] == "/v1/events"


@pytest.mark.asyncio
async def test_ingest_rejects_missing_idempotency_key_header(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest-missing-idempotency.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            json=_build_valid_event_payload(),
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/v1/events"
    assert "errors" in payload
