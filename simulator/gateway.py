"""Simulated edge gateway -- verifies device signatures and forwards to backend."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
import time
from typing import Literal, cast

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey

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


class EdgeGateway:
    """Simulate an edge gateway that sits between STM32 devices and the cloud backend.

    Responsibilities:
    - Maintain a registry of device public keys
    - Verify ECDSA signatures from devices
    - Forward verified events to the backend API
    - Retry on transient failures
    """

    def __init__(
        self,
        api_url: str = "http://localhost:18941",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        ingest_mode: str | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.ingest_mode: IngestMode = _resolve_ingest_mode(
            ingest_mode,
            default="canonical",
        )
        self.registered_devices: dict[str, str] = {}  # device_id -> public_key_pem
        self.mode_counters: dict[IngestMode, dict[str, int]] = {
            "compat": {"attempts": 0, "success": 0, "failure": 0},
            "canonical": {"attempts": 0, "success": 0, "failure": 0},
        }

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def register_device(self, device_id: str, public_key_pem: str) -> None:
        """Register a device's public key for future ECDSA verification."""
        self.registered_devices[device_id] = public_key_pem
        print(f"[Gateway] Registered device {device_id}")

    def is_registered(self, device_id: str) -> bool:
        return device_id in self.registered_devices

    # ------------------------------------------------------------------
    # Verification helpers
    # ------------------------------------------------------------------

    def verify_ecdsa(self, device_id: str, data: bytes, signature_b64: str) -> bool:
        """Verify an ECDSA-P256-SHA256 signature using the registered public key."""
        pem = self.registered_devices.get(device_id)
        if pem is None:
            print(f"[Gateway] Unknown device {device_id} -- not registered")
            return False
        loaded_public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
        if not isinstance(loaded_public_key, EllipticCurvePublicKey):
            print(f"[Gateway] Invalid public key type for {device_id}")
            return False
        try:
            loaded_public_key.verify(
                base64.b64decode(signature_b64),
                data,
                ec.ECDSA(hashes.SHA256()),
            )
            return True
        except Exception:
            print(f"[Gateway] ECDSA verification failed for {device_id}")
            return False

    # ------------------------------------------------------------------
    # Forwarding
    # ------------------------------------------------------------------

    def verify_and_forward(
        self, device_id: str, data: dict, signature: str
    ) -> dict | None:
        """Verify a device's ECDSA signature, then forward the event to the backend."""
        payload_bytes = json.dumps(data, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        if not self.verify_ecdsa(device_id, payload_bytes, signature):
            return None
        return self.forward_to_backend(data)

    def _canonical_to_compat_payload(self, event: dict) -> dict:
        sensor_payload = event.get("sensor_payload", {})
        timestamp_value = event.get("timestamp")
        ts_unix: int | None = None
        if isinstance(timestamp_value, str):
            try:
                ts_unix = int(
                    datetime.fromisoformat(
                        timestamp_value.replace("Z", "+00:00")
                    ).timestamp()
                )
            except ValueError:
                ts_unix = None

        vibration_g = event.get("vibration_g")
        return {
            "seq": int(sensor_payload.get("seq", 0)),
            "ts": ts_unix,
            "temp_c": float(sensor_payload.get("temperature_c", 0.0)),
            "hum_rh": float(sensor_payload.get("humidity_pct", 0.0)),
            "co2": event.get("co2_ppm"),
            "vibration": bool(vibration_g and float(vibration_g) > 0.0),
            "vibration_g": vibration_g,
            "digest": sensor_payload.get("digest"),
            "signature": event.get("signature_envelope", {}).get("signature"),
            "device_id": event.get("device_id", "stm32-cherry-node"),
            "batch_id": event.get("batch_id", "compat-batch"),
            "stage": event.get("supply_chain_stage", "transport"),
            "key_id": event.get("signature_envelope", {}).get(
                "key_id", "compat-gateway-key"
            ),
        }

    def _idempotency_key(self, *, mode: IngestMode, event: dict) -> str:
        sensor_payload = (
            event.get("sensor_payload", {}) if isinstance(event, dict) else {}
        )
        sequence = sensor_payload.get("seq")
        if sequence is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            sequence = f"ts-{timestamp}"
        return f"gw:{mode}:{event.get('device_id', 'unknown')}:{event.get('batch_id', 'unknown')}:{sequence}"

    def _record_mode_result(self, *, mode: IngestMode, success: bool) -> None:
        self.mode_counters[mode]["attempts"] += 1
        if success:
            self.mode_counters[mode]["success"] += 1
        else:
            self.mode_counters[mode]["failure"] += 1

    def forward_to_backend(
        self, event: dict, *, ingest_mode: str | None = None
    ) -> dict | None:
        """POST a fully-formed TraceEvent to the backend ``/v1/events`` endpoint.

        Retries up to ``max_retries`` times on connection / 5xx errors.
        """
        mode = _resolve_ingest_mode(ingest_mode, default=self.ingest_mode)
        idempotency_key = self._idempotency_key(mode=mode, event=event)
        target_path = (
            _CANONICAL_INGEST_PATH if mode == "canonical" else _COMPAT_INGEST_PATH
        )
        payload = (
            event if mode == "canonical" else self._canonical_to_compat_payload(event)
        )
        url = f"{self.api_url}{target_path}"
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
                if resp.status_code in (200, 202):
                    result = resp.json()
                    self._record_mode_result(mode=mode, success=True)
                    print(
                        f"[Gateway] mode={mode} forwarded OK: event_id={result.get('event_id')}"
                    )
                    return result
                elif resp.status_code >= 500:
                    self._record_mode_result(mode=mode, success=False)
                    print(
                        f"[Gateway] mode={mode} server error "
                        f"(attempt {attempt}/{self.max_retries}): "
                        f"HTTP {resp.status_code}"
                    )
                    last_error = RuntimeError(f"HTTP {resp.status_code}")
                else:
                    # 4xx -- do not retry
                    self._record_mode_result(mode=mode, success=False)
                    print(
                        f"[Gateway] mode={mode} client error: HTTP {resp.status_code} "
                        f"{resp.text[:200]}"
                    )
                    return None
            except httpx.RequestError as exc:
                self._record_mode_result(mode=mode, success=False)
                print(
                    f"[Gateway] mode={mode} connection error "
                    f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                last_error = exc

            if attempt < self.max_retries:
                time.sleep(self.retry_delay * attempt)

        print(
            f"[Gateway] mode={mode} all {self.max_retries} attempts failed: {last_error}"
        )
        return None
