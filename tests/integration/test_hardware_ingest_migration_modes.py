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
from app.main import app
from simulator.stm32_device import STM32Device


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})
    os.environ["COMPAT_TELEMETRY_SIGNATURE_MODE"] = "observe"


def _compat_telemetry_enabled() -> bool:
    paths = app.openapi().get("paths", {})
    return isinstance(paths, dict) and "/api/cherry/telemetry" in paths


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


def _canonical_payload(*, sequence: int) -> dict[str, Any]:
    payload = {
        "version": "1.0.0",
        "device_id": "stm32-mode-test-device",
        "batch_id": "stm32-mode-test-batch",
        "timestamp": "2026-02-10T02:00:00Z",
        "sensor_payload": {
            "temperature_c": 4.2,
            "humidity_pct": 73.0,
            "seq": sequence,
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": "factory-key-1",
        },
        "co2_ppm": 420.0,
        "vibration_g": 0.1,
        "supply_chain_stage": "transport",
    }
    payload["signature_envelope"]["signature"] = _sign_payload(payload, "super-secret")
    return payload


def _compat_payload(*, sequence: int) -> dict[str, Any]:
    return {
        "seq": sequence,
        "ts": 1770688800,
        "temp_c": 4.2,
        "hum_rh": 73.0,
        "co2": 420.0,
        "vibration": True,
        "vibration_g": 0.1,
        "digest": "a1" * 32,
        "signature": "b2" * 64,
        "device_id": "stm32-mode-test-device",
        "batch_id": "stm32-mode-test-batch",
        "stage": "transport",
        "key_id": "factory-key-1",
    }


def _event_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert row is not None
    return int(row[0])


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


def test_simulator_mode_switch_uses_compat_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHERRY_INGEST_MODE", "compat")
    captured: dict[str, Any] = {}

    def _fake_post(
        url: str, json: Any, headers: dict[str, str], timeout: float
    ) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(202, {"event_id": 11, "ingest_status": "RECEIVED"})

    monkeypatch.setattr("simulator.stm32_device.httpx.post", _fake_post)
    device = STM32Device(
        device_id="sim-mode-compat",
        device_type="storage",
        gateway_url="http://test.local",
        signing_key_id="factory-key-1",
        signing_secret="super-secret",
    )

    result = device.sign_and_send(
        {
            "temperature_c": 4.2,
            "humidity_pct": 73.0,
            "co2_ppm": 420.0,
            "vibration_g": 0.1,
        },
        sequence=7,
    )

    assert result is not None
    assert captured["url"].endswith("/api/cherry/telemetry")
    assert captured["headers"]["Idempotency-Key"] == (
        f"hw:compat:{device.device_id}:{device.batch_id}:7"
    )
    assert device.mode_counters["compat"]["success"] == 1


def test_simulator_mode_switch_uses_canonical_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHERRY_INGEST_MODE", "canonical")
    captured: dict[str, Any] = {}

    def _fake_post(
        url: str, json: Any, headers: dict[str, str], timeout: float
    ) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(202, {"event_id": 12, "ingest_status": "RECEIVED"})

    monkeypatch.setattr("simulator.stm32_device.httpx.post", _fake_post)
    device = STM32Device(
        device_id="sim-mode-canonical",
        device_type="transport",
        gateway_url="http://test.local",
        signing_key_id="factory-key-1",
        signing_secret="super-secret",
    )

    result = device.sign_and_send(
        {
            "temperature_c": 3.9,
            "humidity_pct": 70.5,
            "co2_ppm": 415.0,
            "vibration_g": 0.2,
        },
        sequence=9,
    )

    assert result is not None
    assert captured["url"].endswith("/v1/events")
    assert captured["headers"]["Idempotency-Key"] == (
        f"hw:canonical:{device.device_id}:{device.batch_id}:9"
    )
    assert device.mode_counters["canonical"]["success"] == 1


def test_simulator_defaults_to_canonical_mode_when_not_overridden() -> None:
    device = STM32Device(
        device_id="sim-default-mode",
        device_type="transport",
        gateway_url="http://test.local",
        signing_key_id="factory-key-1",
        signing_secret="super-secret",
    )

    assert device.ingest_mode == "canonical"


@pytest.mark.asyncio
async def test_canonical_mode_ingest_success_and_replay_idempotency(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "canonical-mode-idempotency.db"
    _configure_runtime(db_path)
    payload = _canonical_payload(sequence=101)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-canonical-101"},
            json=payload,
        )
        second = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-canonical-101"},
            json=payload,
        )

    assert first.status_code == 202
    assert second.status_code == 202
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["ingest_status"] == "RECEIVED"
    assert second_payload["ingest_status"] == "RECEIVED"
    assert first_payload["event_id"] == second_payload["event_id"]
    assert _event_count(db_path) == 1


@pytest.mark.asyncio
async def test_compat_mode_ingest_success_and_replay_idempotency(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compat-mode-idempotency.db"
    _configure_runtime(db_path)
    payload = _compat_payload(sequence=202)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/cherry/telemetry",
            headers={"Idempotency-Key": "idem-compat-202"},
            json=payload,
        )
        second = await client.post(
            "/api/cherry/telemetry",
            headers={"Idempotency-Key": "idem-compat-202"},
            json=payload,
        )

    if _compat_telemetry_enabled():
        assert first.status_code == 202
        assert second.status_code == 202
        first_payload = first.json()
        second_payload = second.json()
        assert first_payload["accepted"] is True
        assert second_payload["accepted"] is True
        assert first_payload["ingest_status"] == "RECEIVED"
        assert second_payload["ingest_status"] == "RECEIVED"
        assert first_payload["event_id"] == second_payload["event_id"]
        assert _event_count(db_path) == 1
    else:
        assert first.status_code == 404
        assert second.status_code == 404
        assert first.json() == {"detail": "Not Found"}
        assert second.json() == {"detail": "Not Found"}
