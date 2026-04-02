from __future__ import annotations

import base64
import hashlib
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


def _configure_runtime(db_path: Path, ingest_signing_keys: dict[str, str] | None = None) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-device-tests"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps(ingest_signing_keys or {})


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_jwt(*, subject: str, roles: list[str], issuer: str, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "iss": issuer, "roles": roles}
    encoded_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


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


def _build_event_payload(*, device_id: str, key_id: str, secret: str) -> dict:
    payload = {
        "version": "1.0.0",
        "device_id": device_id,
        "batch_id": "batch-2026-02-10-managed",
        "timestamp": "2026-02-10T02:00:00Z",
        "sensor_payload": {
            "temperature_c": 4.2,
            "humidity_pct": 73.0,
            "status": "stable",
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": key_id,
        },
    }
    payload["signature_envelope"]["signature"] = _sign_payload(payload, secret)
    return payload


def _fetch_latest_signature_audit(db_path: Path, *, device_id: str) -> tuple[str, str, str, str] | None:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT action,
                   json_extract(metadata, '$.reason') AS reason,
                   json_extract(metadata, '$.key_id') AS key_id,
                   json_extract(metadata, '$.algorithm') AS algorithm
            FROM audits
            WHERE target = ? AND action = 'ingest.signature.verify'
            ORDER BY id DESC
            LIMIT 1
            """,
            (f"device:{device_id}",),
        ).fetchone()
    if row is None:
        return None
    return (str(row[0]), str(row[1]), str(row[2]), str(row[3]))


@pytest.mark.asyncio
async def test_ingest_accepts_signature_verified_by_managed_device_key(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest-managed-key-success.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-managed-key",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "managed-device-001", "display_name": "managed"},
        )
        rotate = await client.post(
            "/admin/devices/managed-device-001/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "managed-key-001",
                "algorithm": "HMAC_SHA256",
                "public_key": "managed-secret-001",
            },
        )

        ingest = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-managed-key-success"},
            json=_build_event_payload(
                device_id="managed-device-001",
                key_id="managed-key-001",
                secret="managed-secret-001",
            ),
        )

    assert register.status_code == 201
    assert rotate.status_code == 201
    assert ingest.status_code == 202
    assert ingest.json()["ingest_status"] == "RECEIVED"


@pytest.mark.asyncio
async def test_ingest_rejects_when_device_and_key_do_not_match_even_if_fallback_exists(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ingest-managed-key-device-mismatch.db"
    _configure_runtime(db_path, ingest_signing_keys={"managed-key-002": "managed-secret-002"})
    token = _mint_jwt(
        subject="admin-managed-key",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "managed-device-002", "display_name": "managed"},
        )
        rotate = await client.post(
            "/admin/devices/managed-device-002/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "managed-key-002",
                "algorithm": "HMAC_SHA256",
                "public_key": "managed-secret-002",
            },
        )

        ingest = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-managed-key-device-mismatch"},
            json=_build_event_payload(
                device_id="managed-device-other",
                key_id="managed-key-002",
                secret="managed-secret-002",
            ),
        )

    assert register.status_code == 201
    assert rotate.status_code == 201
    assert ingest.status_code == 401
    assert ingest.json()["instance"] == "/v1/events"

    latest_audit = _fetch_latest_signature_audit(
        db_path,
        device_id="managed-device-other",
    )
    assert latest_audit is not None
    assert latest_audit[0] == "ingest.signature.verify"
    assert latest_audit[1] == "managed_key_device_mismatch"
    assert latest_audit[2] == "managed-key-002"
    assert latest_audit[3] == "HMAC_SHA256"


@pytest.mark.asyncio
async def test_ingest_rejects_when_managed_device_is_disabled_even_if_fallback_exists(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ingest-managed-key-device-disabled.db"
    _configure_runtime(db_path, ingest_signing_keys={"managed-key-003": "managed-secret-003"})
    token = _mint_jwt(
        subject="admin-managed-key",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "managed-device-003", "display_name": "managed"},
        )
        rotate = await client.post(
            "/admin/devices/managed-device-003/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "managed-key-003",
                "algorithm": "HMAC_SHA256",
                "public_key": "managed-secret-003",
            },
        )
        disable = await client.post(
            "/admin/devices/managed-device-003/disable",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "retired"},
        )

        ingest = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-managed-key-device-disabled"},
            json=_build_event_payload(
                device_id="managed-device-003",
                key_id="managed-key-003",
                secret="managed-secret-003",
            ),
        )

    assert register.status_code == 201
    assert rotate.status_code == 201
    assert disable.status_code == 200
    assert ingest.status_code == 401
    assert ingest.json()["instance"] == "/v1/events"


@pytest.mark.asyncio
async def test_ingest_falls_back_to_env_signing_keys_when_managed_key_not_found(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ingest-managed-key-fallback-env.db"
    _configure_runtime(db_path, ingest_signing_keys={"factory-key-fallback": "fallback-secret"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ingest = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "idem-managed-key-fallback"},
            json=_build_event_payload(
                device_id="legacy-device-001",
                key_id="factory-key-fallback",
                secret="fallback-secret",
            ),
        )

    assert ingest.status_code == 202
    assert ingest.json()["ingest_status"] == "RECEIVED"


@pytest.mark.asyncio
async def test_list_device_keys_requires_admin_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "device-keys-list-auth.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/devices/device-keys-001/keys")

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == 401
    assert payload["instance"] == "/admin/devices/device-keys-001/keys"


@pytest.mark.asyncio
async def test_list_device_keys_returns_expected_structure(tmp_path: Path) -> None:
    db_path = tmp_path / "device-keys-list-structure.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-managed-key",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-keys-002", "display_name": "keys"},
        )
        rotate_first = await client.post(
            "/admin/devices/device-keys-002/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-keys-002-v1",
                "algorithm": "HMAC_SHA256",
                "public_key": "keys-secret-v1",
            },
        )
        rotate_second = await client.post(
            "/admin/devices/device-keys-002/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-keys-002-v2",
                "algorithm": "HMAC_SHA256",
                "public_key": "keys-secret-v2",
            },
        )

        key_list = await client.get(
            "/admin/devices/device-keys-002/keys",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert register.status_code == 201
    assert rotate_first.status_code == 201
    assert rotate_second.status_code == 201
    assert key_list.status_code == 200

    payload = key_list.json()
    assert payload["device_id"] == "device-keys-002"
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) == 2

    first_item = payload["items"][0]
    second_item = payload["items"][1]

    assert set(first_item) >= {"key_id", "algorithm", "status", "activated_at", "retired_at"}
    assert set(second_item) >= {"key_id", "algorithm", "status", "activated_at", "retired_at"}

    assert first_item["key_id"] == "device-keys-002-v2"
    assert first_item["algorithm"] == "HMAC_SHA256"
    assert first_item["status"] == "active"
    assert first_item["retired_at"] is None
    assert isinstance(first_item["activated_at"], str) and first_item["activated_at"]

    assert second_item["key_id"] == "device-keys-002-v1"
    assert second_item["algorithm"] == "HMAC_SHA256"
    assert second_item["status"] == "retired"
    assert isinstance(second_item["activated_at"], str) and second_item["activated_at"]
    assert isinstance(second_item["retired_at"], str) and second_item["retired_at"]
