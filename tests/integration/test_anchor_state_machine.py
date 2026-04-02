from __future__ import annotations

import hmac
import json
import os
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.jobs.anchor_worker import run_anchor_worker_once
from app.main import app
from app.services.anchor_adapter.base import AnchorReceiptData, AnchorSubmission


def _configure_runtime(
    db_path: Path,
    *,
    anchor_mode: str,
    max_retries: int,
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
        "device_id": "device-anchor-001",
        "batch_id": "batch-anchor-2026-02-10",
        "timestamp": "2026-02-10T03:00:00Z",
        "sensor_payload": {
            "temperature_c": 4.5,
            "humidity_pct": 72.0,
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


def _fetch_ingest_state(
    db_path: Path, idempotency_key: str
) -> tuple[str, int, str | None, int]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT ingest_status, retry_count, last_error, event_id "
            "FROM ingest_requests WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    assert row is not None
    return (
        str(row[0]),
        int(row[1]),
        str(row[2]) if row[2] is not None else None,
        int(row[3]),
    )


def _anchor_receipts_for_event(db_path: Path, event_id: int) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT transaction_hash, receipt_payload FROM anchor_receipts WHERE event_id = ?",
            (event_id,),
        ).fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


@pytest.mark.asyncio
async def test_anchor_worker_transitions_received_to_anchored_and_persists_receipt(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "anchor-success.db"
    _configure_runtime(db_path, anchor_mode="success", max_retries=2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-success-key"},
            json=_event_payload(),
        )

    assert response.status_code == 202
    assert response.json()["ingest_status"] == "RECEIVED"
    state_before, retries_before, _, event_id = _fetch_ingest_state(
        db_path, "anchor-success-key"
    )
    assert state_before == "RECEIVED"
    assert retries_before == 0
    assert _anchor_receipts_for_event(db_path, event_id) == []

    processed = run_anchor_worker_once()
    assert processed == 1

    state_after, retries_after, last_error_after, event_id_after = _fetch_ingest_state(
        db_path, "anchor-success-key"
    )
    assert state_after == "ANCHORED"
    assert retries_after == 0
    assert last_error_after is None

    receipts = _anchor_receipts_for_event(db_path, event_id_after)
    assert len(receipts) == 1
    tx_hash, receipt_payload_raw = receipts[0]
    assert tx_hash.startswith("0x")
    receipt_payload = json.loads(receipt_payload_raw)
    assert receipt_payload["anchored_hash"]
    assert receipt_payload["transaction_hash"] == tx_hash


@pytest.mark.asyncio
async def test_anchor_worker_marks_retryable_failure_and_increments_retry_count(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "anchor-retry.db"
    _configure_runtime(db_path, anchor_mode="timeout", max_retries=3)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-timeout-key"},
            json=_event_payload(),
        )

    assert response.status_code == 202
    assert run_anchor_worker_once() == 1

    state, retries, last_error, event_id = _fetch_ingest_state(
        db_path, "anchor-timeout-key"
    )
    assert state == "FAILED_RETRYING"
    assert retries == 1
    assert last_error is not None and "timeout" in last_error.lower()
    assert _anchor_receipts_for_event(db_path, event_id) == []


@pytest.mark.asyncio
async def test_anchor_worker_transitions_to_dead_letter_after_retry_exhaustion(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "anchor-dead-letter.db"
    _configure_runtime(db_path, anchor_mode="failure", max_retries=2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-dead-key"},
            json=_event_payload(),
        )

    assert response.status_code == 202
    assert run_anchor_worker_once() == 1
    state_after_first, retries_after_first, _, _ = _fetch_ingest_state(
        db_path, "anchor-dead-key"
    )
    assert state_after_first == "FAILED_RETRYING"
    assert retries_after_first == 1

    assert run_anchor_worker_once() == 1
    state_after_second, retries_after_second, last_error, event_id = (
        _fetch_ingest_state(db_path, "anchor-dead-key")
    )
    assert state_after_second == "DEAD_LETTER"
    assert retries_after_second == 2
    assert last_error is not None
    assert _anchor_receipts_for_event(db_path, event_id) == []

    assert run_anchor_worker_once() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_status", ["RECEIVED", "ANCHORING"])
async def test_anchor_worker_recovers_from_persisted_submission_without_resubmitting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial_status: str,
) -> None:
    db_path = tmp_path / "anchor-recovery.db"
    _configure_runtime(db_path, anchor_mode="success", max_retries=2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-recovery-key"},
            json=_event_payload(),
        )
    assert response.status_code == 202

    with sqlite3.connect(db_path) as connection:
        ingest_row = connection.execute(
            "SELECT event_id FROM ingest_requests WHERE idempotency_key = ?",
            ("anchor-recovery-key",),
        ).fetchone()
        assert ingest_row is not None
        event_id = int(ingest_row[0])
        canonical_row = connection.execute(
            "SELECT canonical_hash FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        assert canonical_row is not None
        canonical_hash = str(canonical_row[0])

        connection.execute(
            "UPDATE ingest_requests SET ingest_status = ? WHERE idempotency_key = ?",
            (initial_status, "anchor-recovery-key"),
        )
        connection.execute(
            "INSERT INTO anchor_submissions "
            "(event_id, network, transaction_hash, canonical_hash, status, metadata) "
            "VALUES (?, ?, ?, ?, 'PENDING', ?)",
            (
                event_id,
                "evm-recovery",
                "0x" + ("11" * 32),
                canonical_hash,
                json.dumps({"source": "test"}),
            ),
        )
        connection.commit()

    class _RecoverableAdapter:
        def __init__(self) -> None:
            self.anchor_calls = 0
            self.receipt_calls = 0

        def supports_durable_submissions(self) -> bool:
            return True

        def anchor_event(
            self,
            *,
            event_id: int,
            canonical_hash: str,
            payload: dict[str, Any],
        ) -> AnchorSubmission:
            del event_id, canonical_hash, payload
            self.anchor_calls += 1
            return AnchorSubmission(
                transaction_hash="0x" + ("22" * 32),
                network="evm-recovery",
                metadata={},
            )

        def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
            self.receipt_calls += 1
            return AnchorReceiptData(
                transaction_hash=transaction_hash,
                network="evm-recovery",
                anchored_at=datetime.now(UTC),
                receipt_payload={
                    "status": "success",
                    "canonical_hash": canonical_hash,
                    "transaction_hash": transaction_hash,
                },
            )

        def verify_anchor(
            self, *, canonical_hash: str, receipt: AnchorReceiptData | None
        ) -> bool:
            if receipt is None:
                return False
            payload_hash = str(receipt.receipt_payload.get("canonical_hash", ""))
            return (
                payload_hash == canonical_hash
                and receipt.receipt_payload.get("status") == "success"
            )

    adapter = _RecoverableAdapter()
    monkeypatch.setattr("app.services.anchoring._build_active_adapter", lambda: adapter)

    processed = run_anchor_worker_once()
    assert processed == 1
    assert adapter.anchor_calls == 0
    assert adapter.receipt_calls == 1

    state, retries, last_error, event_id = _fetch_ingest_state(
        db_path, "anchor-recovery-key"
    )
    assert state == "ANCHORED"
    assert retries == 0
    assert last_error is None

    receipts = _anchor_receipts_for_event(db_path, event_id)
    assert len(receipts) == 1
    assert receipts[0][0] == "0x" + ("11" * 32)
