"""Simulated STM32H743 device for cherry cold-chain monitoring."""

from __future__ import annotations

import hmac
import json
import os
import random
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal, cast

import httpx

from .crypto_utils import ATECC608ASimulator
from .sensors import AccelerometerSimulator, MHZ19BSimulator, SHT31Simulator

IngestMode = Literal["compat", "canonical"]

_CANONICAL_INGEST_PATH = "/v1/events"
_COMPAT_INGEST_PATH = "/api/cherry/telemetry"


def _resolve_ingest_mode(raw_mode: str | None, *, default: IngestMode) -> IngestMode:
    candidate = (raw_mode or "").strip().lower()
    if not candidate:
        candidate = os.getenv("CHERRY_INGEST_MODE", default).strip().lower()
    if candidate in {"compat", "canonical"}:
        return cast(IngestMode, candidate)
    return default


# ---------------------------------------------------------------------------
# Canonicalization -- mirrors app/domain/contracts/hash_canonicalization.py
# ---------------------------------------------------------------------------


def _normalize_datetime(value: str) -> str:
    try:
        if "T" not in value:
            return value
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z")


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        return _normalize_datetime(stripped)
    return value


def canonicalize_payload(payload: Any) -> str:
    normalized = _normalize(payload)
    return json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


# ---------------------------------------------------------------------------
# STM32 Device
# ---------------------------------------------------------------------------


class STM32Device:
    """Simulate an STM32H743 micro-controller with attached sensors.

    This is the base class.  Use :class:`StorageDevice` or
    :class:`TransportDevice` (in their own modules) for pre-configured
    cold-chain scenarios, or instantiate this directly for custom setups.
    """

    # Class-level sequence counter per device_type for batch IDs
    _batch_seq: dict[str, int] = {}

    def __init__(
        self,
        device_id: str,
        device_type: str,
        gateway_url: str,
        signing_key_id: str | None = None,
        signing_secret: str | None = None,
        ingest_mode: str | None = None,
    ) -> None:
        self.device_id = device_id
        self.device_type = device_type  # "storage" or "transport"
        self.gateway_url = gateway_url.rstrip("/")
        self.crypto = ATECC608ASimulator()
        self.signing_key_id = signing_key_id
        self.signing_secret = signing_secret
        self.ingest_mode: IngestMode = _resolve_ingest_mode(
            ingest_mode,
            default="canonical",
        )
        self.sensors = self._init_sensors()
        self.batch_id = self._generate_batch_id()
        self.use_ecdsa = False  # default to HMAC (backend currently supports HMAC)
        self.collected_events: list[dict] = []
        self._next_sequence = 1
        self.mode_counters: dict[IngestMode, dict[str, int]] = {
            "compat": {"attempts": 0, "success": 0, "failure": 0},
            "canonical": {"attempts": 0, "success": 0, "failure": 0},
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_batch_id(self) -> str:
        """Generate batch ID: ``STORAGE-20260214-001`` or ``TRANSPORT-20260214-001``."""
        prefix = self.device_type.upper()
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        seq_key = f"{prefix}-{date_str}"
        seq = STM32Device._batch_seq.get(seq_key, 0) + 1
        STM32Device._batch_seq[seq_key] = seq
        return f"{prefix}-{date_str}-{seq:03d}"

    def _init_sensors(self) -> dict:
        if self.device_type == "storage":
            return {
                "sht31": SHT31Simulator(base_temp=2.0, base_humidity=92.0),
                "mhz19b": MHZ19BSimulator(base_co2=120000),
                "accel": AccelerometerSimulator(
                    base_vibration=0.05, is_transport=False
                ),
            }
        else:  # transport
            return {
                "sht31": SHT31Simulator(base_temp=4.0, base_humidity=88.0),
                "mhz19b": MHZ19BSimulator(base_co2=100000),
                "accel": AccelerometerSimulator(base_vibration=0.3, is_transport=True),
            }

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def collect_data(self) -> dict:
        """Read every attached sensor and assemble a sensor payload dict."""
        sht31 = self.sensors["sht31"].read()
        mhz19b = self.sensors["mhz19b"].read()
        accel = self.sensors["accel"].read()
        return {
            "temperature_c": sht31["temperature_c"],
            "humidity_pct": sht31["humidity_pct"],
            "co2_ppm": mhz19b["co2_ppm"],
            "vibration_g": accel["vibration_g"],
        }

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _build_trace_event(self, sensor_data: dict, *, sequence: int) -> dict:
        """Build a TraceEvent-compatible dict (without the final signature)."""
        now = datetime.now(timezone.utc)
        event = {
            "version": "1.0",
            "device_id": self.device_id,
            "batch_id": self.batch_id,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "sensor_payload": {
                "temperature_c": sensor_data["temperature_c"],
                "humidity_pct": sensor_data["humidity_pct"],
                "seq": sequence,
            },
            "signature_envelope": {
                "algorithm": "HMAC_SHA256",
                "key_id": self.signing_key_id or "factory-key-1",
                "signature": "",  # placeholder -- filled below
            },
            "co2_ppm": sensor_data.get("co2_ppm"),
            "vibration_g": sensor_data.get("vibration_g"),
            "supply_chain_stage": self.device_type,  # "storage" or "transport"
        }
        return event

    def _trace_event_to_compat_payload(self, event: dict) -> dict:
        """Explicitly map canonical TraceEvent to compat telemetry payload."""
        sensor_payload = event["sensor_payload"]
        timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        vibration_g = event.get("vibration_g")
        return {
            "seq": int(sensor_payload.get("seq", 0)),
            "ts": int(timestamp.timestamp()),
            "temp_c": float(sensor_payload["temperature_c"]),
            "hum_rh": float(sensor_payload["humidity_pct"]),
            "co2": event.get("co2_ppm"),
            "vibration": bool(vibration_g and float(vibration_g) > 0.0),
            "vibration_g": vibration_g,
            "digest": sha256(
                canonicalize_payload(sensor_payload).encode("utf-8")
            ).hexdigest(),
            "signature": event["signature_envelope"]["signature"],
            "device_id": event["device_id"],
            "batch_id": event["batch_id"],
            "stage": event.get("supply_chain_stage") or "transport",
            "key_id": event["signature_envelope"]["key_id"],
        }

    def _idempotency_key(self, *, mode: IngestMode, sequence: int) -> str:
        return f"hw:{mode}:{self.device_id}:{self.batch_id}:{sequence}"

    def _next_sequence_value(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def _record_mode_result(self, *, mode: IngestMode, success: bool) -> None:
        self.mode_counters[mode]["attempts"] += 1
        if success:
            self.mode_counters[mode]["success"] += 1
        else:
            self.mode_counters[mode]["failure"] += 1

    def _hmac_sign(self, event: dict) -> str:
        """Compute the HMAC-SHA256 signature matching the backend verifier."""
        envelope = event["signature_envelope"]
        sig_payload = {
            "version": event["version"],
            "device_id": event["device_id"],
            "batch_id": event["batch_id"],
            "timestamp": event["timestamp"],
            "sensor_payload": event["sensor_payload"],
            "signature_envelope": {
                "algorithm": envelope["algorithm"],
                "key_id": envelope["key_id"],
            },
        }
        canonical = canonicalize_payload(sig_payload)
        secret = self.signing_secret or "super-secret"
        return hmac.new(
            secret.encode("utf-8"), canonical.encode("utf-8"), sha256
        ).hexdigest()

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def sign_and_send(
        self,
        sensor_data: dict,
        *,
        sequence: int | None = None,
        ingest_mode: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict | None:
        """Sign a reading and POST it through canonical or compat ingest path."""
        mode = _resolve_ingest_mode(ingest_mode, default=self.ingest_mode)
        seq = sequence if sequence is not None else self._next_sequence_value()
        event = self._build_trace_event(sensor_data, sequence=seq)
        event["signature_envelope"]["signature"] = self._hmac_sign(event)

        target_path = (
            _CANONICAL_INGEST_PATH if mode == "canonical" else _COMPAT_INGEST_PATH
        )
        payload = (
            event if mode == "canonical" else self._trace_event_to_compat_payload(event)
        )
        dedupe_key = idempotency_key or self._idempotency_key(mode=mode, sequence=seq)
        url = f"{self.gateway_url}{target_path}"
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": dedupe_key,
        }

        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            if resp.status_code in (200, 202):
                result = resp.json()
                self._record_mode_result(mode=mode, success=True)
                print(
                    f"  [OK] mode={mode} event_id={result.get('event_id', 'n/a')} "
                    f"status={result.get('ingest_status', 'n/a')}"
                )
                return result
            else:
                self._record_mode_result(mode=mode, success=False)
                print(
                    f"  [FAIL] mode={mode} HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None
        except httpx.RequestError as exc:
            self._record_mode_result(mode=mode, success=False)
            print(f"  [ERR] mode={mode} {exc}")
            return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, interval_seconds: float = 5, count: int = 10) -> list[dict]:
        """Run *count* collection-sign-send cycles, sleeping *interval_seconds* between them."""
        print(f"\n{'=' * 60}")
        print(f"STM32 Device: {self.device_id}  type={self.device_type}")
        print(f"Batch: {self.batch_id}")
        print(f"Target: {self.gateway_url}")
        print(f"{'=' * 60}")

        results: list[dict] = []
        for i in range(1, count + 1):
            sensor_data = self.collect_data()
            print(
                f"\n[{i}/{count}] temp={sensor_data['temperature_c']}C  "
                f"hum={sensor_data['humidity_pct']}%  "
                f"co2={sensor_data['co2_ppm']}ppm  "
                f"vib={sensor_data['vibration_g']}g"
            )
            result = self.sign_and_send(sensor_data)
            if result:
                results.append(result)
            if i < count:
                time.sleep(interval_seconds)

        print(f"\nDevice {self.device_id}: {len(results)}/{count} events accepted.\n")
        self.collected_events = results
        return results
