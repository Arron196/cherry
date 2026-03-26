from __future__ import annotations

import hmac
import json
import os
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.domain.contracts.trace_event import TraceEvent
from app.domain.persistence.models import ManagedDevice, ManagedDeviceKey
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)

ECDSA_CANONICAL_ALGORITHM = "ECDSA_P256_SHA256"
_ECDSA_ALGORITHM_ALIASES = {"ECDSA"}
_HEX_SIGNATURE_PATTERN = re.compile(r"^[0-9a-fA-F]+$")
SUPPORTED_ALGORITHMS = {
    "HMAC_SHA256",
    ECDSA_CANONICAL_ALGORITHM,
    *_ECDSA_ALGORITHM_ALIASES,
}


@dataclass(frozen=True)
class SignatureVerificationResult:
    is_valid: bool
    reason: str | None


def normalize_signature_algorithm(algorithm: str) -> str:
    normalized = algorithm.strip()
    if normalized in _ECDSA_ALGORITHM_ALIASES:
        return ECDSA_CANONICAL_ALGORITHM
    return normalized


def _is_ecdsa_algorithm(algorithm: str) -> bool:
    return normalize_signature_algorithm(algorithm) == ECDSA_CANONICAL_ALGORITHM


def _load_signing_keys() -> dict[str, str]:
    raw = os.getenv("INGEST_SIGNING_KEYS", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _signature_payload(payload: dict[str, Any]) -> dict[str, Any]:
    envelope = payload["signature_envelope"]
    return {
        "version": payload["version"],
        "device_id": payload["device_id"],
        "batch_id": payload["batch_id"],
        "timestamp": payload["timestamp"],
        "sensor_payload": payload["sensor_payload"],
        "signature_envelope": {
            "algorithm": envelope["algorithm"],
            "key_id": envelope["key_id"],
        },
    }


def _verify_hmac_signature(*, event: TraceEvent, secret: str) -> bool:
    event_payload = event.model_dump(mode="json")
    canonical_payload = canonicalize_payload(_signature_payload(event_payload))
    expected_signature = hmac.new(
        secret.encode("utf-8"), canonical_payload.encode("utf-8"), sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, event.signature_envelope.signature)


def _verify_ecdsa_signature(*, event: TraceEvent, public_key_pem: str) -> bool:
    """Verify ECDSA (secp256r1/P-256) signature using the cryptography library."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import (
            decode_dss_signature,
            encode_dss_signature,
        )
    except ImportError:
        return False

    event_payload = event.model_dump(mode="json")
    canonical_payload = canonicalize_payload(_signature_payload(event_payload))
    message_bytes = canonical_payload.encode("utf-8")

    signature_hex = event.signature_envelope.signature.strip()
    if (
        len(signature_hex) % 2 != 0
        or _HEX_SIGNATURE_PATTERN.fullmatch(signature_hex) is None
    ):
        return False
    try:
        signature_bytes = bytes.fromhex(signature_hex)
    except ValueError:
        return False

    der_signature = signature_bytes
    if len(signature_bytes) == 64:
        r = int.from_bytes(signature_bytes[:32], byteorder="big")
        s = int.from_bytes(signature_bytes[32:], byteorder="big")
        der_signature = encode_dss_signature(r, s)
    else:
        try:
            decode_dss_signature(signature_bytes)
        except ValueError:
            return False

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            return False
        public_key.verify(der_signature, message_bytes, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False


def _lookup_managed_device_secret(
    *,
    device_id: str,
    key_id: str,
    algorithm: str,
) -> tuple[str | None, str | None, bool]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        row = session.execute(
            select(
                ManagedDevice.device_id.label("device_id"),
                ManagedDevice.status.label("device_status"),
                ManagedDeviceKey.algorithm.label("algorithm"),
                ManagedDeviceKey.status.label("key_status"),
                ManagedDeviceKey.public_key.label("secret"),
            )
            .select_from(ManagedDeviceKey)
            .join(ManagedDevice, ManagedDevice.id == ManagedDeviceKey.device_id)
            .where(ManagedDeviceKey.key_id == key_id)
        ).one_or_none()

    if row is None:
        return None, "managed_key_not_found", True
    if str(row.device_id) != device_id:
        return None, "managed_key_device_mismatch", False
    if str(row.device_status) != "active":
        return None, "managed_device_disabled", False
    if str(row.key_status) != "active":
        return None, "managed_key_inactive", False
    row_algorithm = normalize_signature_algorithm(str(row.algorithm))
    if row_algorithm != algorithm:
        return None, "managed_key_algorithm_mismatch", False
    return str(row.secret), None, False


def verify_trace_event_signature_with_reason(
    event: TraceEvent,
    *,
    algorithm_override: str | None = None,
) -> SignatureVerificationResult:
    envelope = event.signature_envelope
    algorithm = normalize_signature_algorithm(algorithm_override or envelope.algorithm)

    if algorithm not in SUPPORTED_ALGORITHMS:
        return SignatureVerificationResult(
            is_valid=False, reason="unsupported_algorithm"
        )

    managed_secret, managed_lookup_reason, fallback_allowed = (
        _lookup_managed_device_secret(
            device_id=event.device_id,
            key_id=envelope.key_id,
            algorithm=algorithm,
        )
    )
    if managed_secret is not None:
        if _is_ecdsa_algorithm(algorithm):
            valid = _verify_ecdsa_signature(event=event, public_key_pem=managed_secret)
        else:
            valid = _verify_hmac_signature(event=event, secret=managed_secret)
        if valid:
            return SignatureVerificationResult(is_valid=True, reason=None)
        return SignatureVerificationResult(is_valid=False, reason="signature_mismatch")
    if not fallback_allowed:
        return SignatureVerificationResult(is_valid=False, reason=managed_lookup_reason)

    # ECDSA does not support fallback to env-based keys (only HMAC does)
    if _is_ecdsa_algorithm(algorithm):
        return SignatureVerificationResult(is_valid=False, reason="ecdsa_key_not_found")

    fallback_secret = _load_signing_keys().get(envelope.key_id)
    if fallback_secret is None:
        return SignatureVerificationResult(
            is_valid=False, reason="fallback_key_not_found"
        )

    if _verify_hmac_signature(event=event, secret=fallback_secret):
        return SignatureVerificationResult(is_valid=True, reason=None)
    return SignatureVerificationResult(is_valid=False, reason="signature_mismatch")


def verify_trace_event_signature(event: TraceEvent) -> bool:
    return verify_trace_event_signature_with_reason(event).is_valid
