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


def _configure_runtime(
    db_path: Path,
    *,
    anchor_mode: str,
    max_retries: int,
    suppression_seconds: int,
) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})
    os.environ["ANCHOR_ADAPTER"] = "active_mock"
    os.environ["ANCHOR_MOCK_MODE"] = anchor_mode
    os.environ["ANCHOR_MAX_RETRIES"] = str(max_retries)
    os.environ["ANCHOR_ALERT_SUPPRESSION_SECONDS"] = str(suppression_seconds)


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
        "device_id": "device-alert-001",
        "batch_id": "batch-alert-2026-02-10",
        "timestamp": "2026-02-10T08:00:00Z",
        "sensor_payload": {
            "temperature_c": 5.2,
            "humidity_pct": 71.0,
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


def _fetch_ingest_state(db_path: Path, idempotency_key: str) -> tuple[str, int, int]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT ingest_status, retry_count, event_id "
            "FROM ingest_requests WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    assert row is not None
    return str(row[0]), int(row[1]), int(row[2])


def _fetch_alert_rows(db_path: Path, event_id: int) -> list[tuple[str, str, str, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT alert_type, severity, status, message "
            "FROM alerts WHERE event_id = ? ORDER BY id ASC",
            (event_id,),
        ).fetchall()
    return [(str(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows]


@pytest.mark.asyncio
async def test_anchor_repeated_failures_are_deduped_and_dead_letter_raises_persistent_alert(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "alert-retry-dead-letter.db"
    _configure_runtime(
        db_path,
        anchor_mode="failure",
        max_retries=3,
        suppression_seconds=3600,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "alert-dead-letter-key"},
            json=_event_payload(),
        )

    assert ingest_response.status_code == 202

    assert run_anchor_worker_once() == 1
    state_after_first, retries_after_first, event_id = _fetch_ingest_state(
        db_path, "alert-dead-letter-key"
    )
    assert state_after_first == "FAILED_RETRYING"
    assert retries_after_first == 1
    first_alerts = _fetch_alert_rows(db_path, event_id)
    assert len(first_alerts) == 1
    assert first_alerts[0][0] == "ANCHOR_RETRY_FAILURE"

    assert run_anchor_worker_once() == 1
    state_after_second, retries_after_second, same_event_id = _fetch_ingest_state(
        db_path, "alert-dead-letter-key"
    )
    assert same_event_id == event_id
    assert state_after_second == "FAILED_RETRYING"
    assert retries_after_second == 2
    second_alerts = _fetch_alert_rows(db_path, event_id)
    assert len(second_alerts) == 1

    assert run_anchor_worker_once() == 1
    state_after_third, retries_after_third, _ = _fetch_ingest_state(db_path, "alert-dead-letter-key")
    assert state_after_third == "DEAD_LETTER"
    assert retries_after_third == 3

    final_alerts = _fetch_alert_rows(db_path, event_id)
    assert len(final_alerts) == 2
    assert final_alerts[1][0] == "ANCHOR_DEAD_LETTER"
    assert final_alerts[1][2] == "open"
    assert "dead letter" in final_alerts[1][3].lower()

    assert run_anchor_worker_once() == 0
