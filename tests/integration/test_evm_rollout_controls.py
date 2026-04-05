from __future__ import annotations

import hmac
import json
import os
import re
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
from app.services import anchoring as anchoring_service
from app.services.anchor_adapter.base import (
    AnchorAdapter,
    AnchorAdapterError,
    AnchorReceiptData,
    AnchorSubmission,
)


class _InspectableSafeAdapter(AnchorAdapter):
    def __init__(self, *, network: str = "safe-mock") -> None:
        self.network = network
        self.anchor_calls = 0
        self._hash_by_tx: dict[str, str] = {}

    def anchor_event(
        self,
        *,
        event_id: int,
        canonical_hash: str,
        payload: dict[str, Any],
    ) -> AnchorSubmission:
        del payload
        self.anchor_calls += 1
        tx_hash = f"0xsafe{event_id:060x}"[-66:]
        self._hash_by_tx[tx_hash] = canonical_hash
        return AnchorSubmission(
            transaction_hash=tx_hash,
            network=self.network,
            metadata={"adapter": "safe", "event_id": event_id},
        )

    def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
        canonical_hash = self._hash_by_tx.get(transaction_hash)
        if canonical_hash is None:
            raise AnchorAdapterError("unknown safe transaction hash")
        return AnchorReceiptData(
            transaction_hash=transaction_hash,
            network=self.network,
            anchored_at=datetime.now(UTC),
            receipt_payload={
                "status": "safe_success",
                "transaction_hash": transaction_hash,
                "canonical_hash": canonical_hash,
            },
        )

    def verify_anchor(
        self, *, canonical_hash: str, receipt: AnchorReceiptData | None
    ) -> bool:
        if receipt is None:
            return False
        return str(receipt.receipt_payload.get("canonical_hash")) == canonical_hash


class _InspectableEvmAdapter(AnchorAdapter):
    def __init__(
        self, *, network: str = "evm-test", fail_submission: bool = False
    ) -> None:
        self.network = network
        self.fail_submission = fail_submission
        self.anchor_calls = 0
        self._hash_by_tx: dict[str, str] = {}

    def supports_durable_submissions(self) -> bool:
        return True

    def anchor_event(
        self,
        *,
        event_id: int,
        canonical_hash: str,
        payload: dict[str, Any],
    ) -> AnchorSubmission:
        del payload
        self.anchor_calls += 1
        if self.fail_submission:
            raise AnchorAdapterError("forced evm submission failure")
        tx_hash = f"0xevm{event_id:060x}"[-66:]
        self._hash_by_tx[tx_hash] = canonical_hash
        return AnchorSubmission(
            transaction_hash=tx_hash,
            network=self.network,
            metadata={"adapter": "evm", "event_id": event_id},
        )

    def get_receipt(self, transaction_hash: str) -> AnchorReceiptData:
        canonical_hash = self._hash_by_tx.get(transaction_hash)
        if canonical_hash is None:
            raise AnchorAdapterError("unknown evm transaction hash")
        return AnchorReceiptData(
            transaction_hash=transaction_hash,
            network=self.network,
            anchored_at=datetime.now(UTC),
            receipt_payload={
                "status": "success",
                "transaction_hash": transaction_hash,
                "canonical_hash": canonical_hash,
            },
        )

    def verify_anchor(
        self, *, canonical_hash: str, receipt: AnchorReceiptData | None
    ) -> bool:
        if receipt is None:
            return False
        return str(receipt.receipt_payload.get("canonical_hash")) == canonical_hash


def _configure_runtime(
    db_path: Path,
    *,
    rollout_mode: str,
    canary_percent: int,
    max_retries: int,
    abort_after_seconds: int,
    window_seconds: int,
    force_rollback_safe: bool = False,
) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})
    os.environ["ANCHOR_ADAPTER"] = "evm_contract"
    os.environ["ANCHOR_MOCK_MODE"] = "success"
    os.environ["ANCHOR_MAX_RETRIES"] = str(max_retries)
    os.environ["ANCHOR_EVM_ROLLOUT_MODE"] = rollout_mode
    os.environ["ANCHOR_EVM_CANARY_PERCENT"] = str(canary_percent)
    os.environ["ANCHOR_EVM_CANARY_MIN_SUCCESS_RATE"] = "0.99"
    os.environ["ANCHOR_EVM_CANARY_MAX_DEAD_LETTER_RATE"] = "0.005"
    os.environ["ANCHOR_EVM_CANARY_MAX_P95_CONFIRMATION_SECONDS"] = "120"
    os.environ["ANCHOR_EVM_CANARY_ABORT_AFTER_SECONDS"] = str(abort_after_seconds)
    os.environ["ANCHOR_EVM_CANARY_WINDOW_SECONDS"] = str(window_seconds)
    os.environ["ANCHOR_EVM_FORCE_ROLLBACK_SAFE"] = "1" if force_rollback_safe else "0"


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


def _event_payload(*, batch_id: str, timestamp: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": "device-rollout-001",
        "batch_id": batch_id,
        "timestamp": timestamp,
        "sensor_payload": {
            "temperature_c": 4.9,
            "humidity_pct": 72.1,
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


def _fetch_ingest_status(db_path: Path, idempotency_key: str) -> str:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT ingest_status FROM ingest_requests WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    assert row is not None
    return str(row[0])


def _metric_value(metrics_text: str, metric_name: str, labels: dict[str, str]) -> float:
    escaped = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    pattern = re.compile(
        rf"^{re.escape(metric_name)}\{{{re.escape(escaped)}\}}\s+([0-9]+(?:\.[0-9]+)?)$",
        re.MULTILINE,
    )
    match = pattern.search(metrics_text)
    if match is None:
        return 0.0
    return float(match.group(1))


def _reset_rollout_runtime() -> None:
    with anchoring_service._ROLLOUT_LOCK:
        anchoring_service._ROLLOUT_RUNTIME.signature = None
        anchoring_service._ROLLOUT_RUNTIME.auto_aborted = False
        anchoring_service._ROLLOUT_RUNTIME.violation_started_at_seconds = None
        anchoring_service._ROLLOUT_RUNTIME.samples.clear()


@pytest.mark.asyncio
async def test_canary_success_path_records_evm_canary_slo_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_rollout_runtime()
    db_path = tmp_path / "rollout-canary-success.db"
    _configure_runtime(
        db_path,
        rollout_mode="canary",
        canary_percent=100,
        max_retries=2,
        abort_after_seconds=600,
        window_seconds=611,
    )

    safe_adapter = _InspectableSafeAdapter()
    evm_adapter = _InspectableEvmAdapter()
    monkeypatch.setattr(anchoring_service, "_build_safe_adapter", lambda: safe_adapter)
    monkeypatch.setattr(anchoring_service, "_build_evm_adapter", lambda: evm_adapter)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-canary-success-key"},
            json=_event_payload(
                batch_id="batch-rollout-canary-success",
                timestamp="2026-02-12T10:00:00Z",
            ),
        )
        assert ingest_response.status_code == 202
        assert run_anchor_worker_once() == 1
        metrics_response = await client.get("/metrics")

    assert _fetch_ingest_status(db_path, "rollout-canary-success-key") == "ANCHORED"
    assert safe_adapter.anchor_calls == 0
    assert evm_adapter.anchor_calls == 1
    assert metrics_response.status_code == 200
    assert (
        _metric_value(
            metrics_response.text,
            "traceability_anchoring_rollout_canary_outcomes_total",
            {"outcome": "success"},
        )
        >= 1
    )
    assert (
        _metric_value(
            metrics_response.text,
            "traceability_anchoring_rollout_decisions_total",
            {"mode": "canary", "path": "evm"},
        )
        >= 1
    )


@pytest.mark.asyncio
async def test_canary_threshold_breach_auto_aborts_and_rolls_back_to_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_rollout_runtime()
    db_path = tmp_path / "rollout-canary-abort.db"
    _configure_runtime(
        db_path,
        rollout_mode="canary",
        canary_percent=100,
        max_retries=1,
        abort_after_seconds=600,
        window_seconds=607,
    )

    safe_adapter = _InspectableSafeAdapter()
    evm_adapter = _InspectableEvmAdapter(fail_submission=True)
    monkeypatch.setattr(anchoring_service, "_build_safe_adapter", lambda: safe_adapter)
    monkeypatch.setattr(anchoring_service, "_build_evm_adapter", lambda: evm_adapter)

    clock = {"value": 0.0}
    monkeypatch.setattr(
        anchoring_service, "_rollout_now_seconds", lambda: clock["value"]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response_first = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-canary-abort-key-1"},
            json=_event_payload(
                batch_id="batch-rollout-canary-abort-1",
                timestamp="2026-02-12T11:00:00Z",
            ),
        )
        assert response_first.status_code == 202
        assert run_anchor_worker_once() == 1
        assert (
            _fetch_ingest_status(db_path, "rollout-canary-abort-key-1") == "DEAD_LETTER"
        )

        clock["value"] = 601.0
        response_second = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-canary-abort-key-2"},
            json=_event_payload(
                batch_id="batch-rollout-canary-abort-2",
                timestamp="2026-02-12T11:01:00Z",
            ),
        )
        assert response_second.status_code == 202
        assert run_anchor_worker_once() == 1
        assert (
            _fetch_ingest_status(db_path, "rollout-canary-abort-key-2") == "DEAD_LETTER"
        )

        clock["value"] = 602.0
        response_third = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-canary-abort-key-3"},
            json=_event_payload(
                batch_id="batch-rollout-canary-abort-3",
                timestamp="2026-02-12T11:02:00Z",
            ),
        )
        assert response_third.status_code == 202
        assert run_anchor_worker_once() == 1
        metrics_response = await client.get("/metrics")

    assert _fetch_ingest_status(db_path, "rollout-canary-abort-key-3") == "ANCHORED"
    assert evm_adapter.anchor_calls == 2
    assert safe_adapter.anchor_calls == 1
    assert metrics_response.status_code == 200
    assert (
        _metric_value(
            metrics_response.text,
            "traceability_anchoring_rollout_transitions_total",
            {"to_state": "rollback_safe"},
        )
        >= 1
    )
    assert (
        _metric_value(
            metrics_response.text,
            "traceability_anchoring_rollout_decisions_total",
            {"mode": "rollback_safe", "path": "safe"},
        )
        >= 1
    )


@pytest.mark.asyncio
async def test_ingest_stays_available_while_rollout_mode_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_rollout_runtime()
    db_path = tmp_path / "rollout-mode-change-availability.db"
    _configure_runtime(
        db_path,
        rollout_mode="shadow",
        canary_percent=100,
        max_retries=2,
        abort_after_seconds=600,
        window_seconds=613,
    )

    safe_adapter = _InspectableSafeAdapter()
    evm_adapter = _InspectableEvmAdapter()
    monkeypatch.setattr(anchoring_service, "_build_safe_adapter", lambda: safe_adapter)
    monkeypatch.setattr(anchoring_service, "_build_evm_adapter", lambda: evm_adapter)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-mode-switch-key-1"},
            json=_event_payload(
                batch_id="batch-rollout-mode-switch-1",
                timestamp="2026-02-12T12:00:00Z",
            ),
        )
        assert first.status_code == 202
        assert run_anchor_worker_once() == 1

        os.environ["ANCHOR_EVM_ROLLOUT_MODE"] = "rollback-safe"
        second = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-mode-switch-key-2"},
            json=_event_payload(
                batch_id="batch-rollout-mode-switch-2",
                timestamp="2026-02-12T12:01:00Z",
            ),
        )
        assert second.status_code == 202
        assert run_anchor_worker_once() == 1

        os.environ["ANCHOR_EVM_ROLLOUT_MODE"] = "full"
        third = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "rollout-mode-switch-key-3"},
            json=_event_payload(
                batch_id="batch-rollout-mode-switch-3",
                timestamp="2026-02-12T12:02:00Z",
            ),
        )
        assert third.status_code == 202
        assert run_anchor_worker_once() == 1

    assert _fetch_ingest_status(db_path, "rollout-mode-switch-key-1") == "ANCHORED"
    assert _fetch_ingest_status(db_path, "rollout-mode-switch-key-2") == "ANCHORED"
    assert _fetch_ingest_status(db_path, "rollout-mode-switch-key-3") == "ANCHORED"
    assert safe_adapter.anchor_calls >= 2
    assert evm_adapter.anchor_calls >= 2
