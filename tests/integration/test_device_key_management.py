from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-device-tests"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"


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


def _fetch_devices(db_path: Path) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT device_id, status, disabled_reason FROM managed_devices ORDER BY id"
        ).fetchall()
    return [(str(row[0]), str(row[1]), row[2]) for row in rows]


def _fetch_keys(db_path: Path) -> list[tuple[str, str, str, int]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT key_id, algorithm, status, device_id FROM managed_device_keys ORDER BY id"
        ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2]), int(row[3])) for row in rows]


def _fetch_audits(db_path: Path) -> list[tuple[str, str, str, Any]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT actor, action, target, metadata FROM audits ORDER BY id"
        ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2]), row[3]) for row in rows]


def _insert_signature_failure_audits(
    db_path: Path,
    *,
    device_id: str,
    key_id: str,
    algorithm: str,
    reasons: list[str],
) -> None:
    now = datetime.now(UTC)
    with sqlite3.connect(db_path) as connection:
        for index, reason in enumerate(reasons):
            created_at = (now - timedelta(hours=index + 1)).isoformat().replace("+00:00", "Z")
            metadata = json.dumps(
                {
                    "result": "failure",
                    "device_id": device_id,
                    "key_id": key_id,
                    "algorithm": algorithm,
                    "reason": reason,
                }
            )
            connection.execute(
                """
                INSERT INTO audits (event_id, actor, action, target, metadata, created_at)
                VALUES (NULL, ?, ?, ?, ?, ?)
                """,
                (
                    "ingest",
                    "ingest.signature.verify",
                    f"device:{device_id}",
                    metadata,
                    created_at,
                ),
            )

        stale_created_at = (now - timedelta(hours=30)).isoformat().replace("+00:00", "Z")
        stale_metadata = json.dumps(
            {
                "result": "failure",
                "device_id": device_id,
                "key_id": key_id,
                "algorithm": algorithm,
                "reason": "stale_failure",
            }
        )
        connection.execute(
            """
            INSERT INTO audits (event_id, actor, action, target, metadata, created_at)
            VALUES (NULL, ?, ?, ?, ?, ?)
            """,
            (
                "ingest",
                "ingest.signature.verify",
                f"device:{device_id}",
                stale_metadata,
                stale_created_at,
            ),
        )

        success_metadata = json.dumps(
            {
                "result": "success",
                "device_id": device_id,
                "key_id": key_id,
                "algorithm": algorithm,
            }
        )
        connection.execute(
            """
            INSERT INTO audits (event_id, actor, action, target, metadata, created_at)
            VALUES (NULL, ?, ?, ?, ?, ?)
            """,
            (
                "ingest",
                "ingest.signature.verify",
                f"device:{device_id}",
                success_metadata,
                now.isoformat().replace("+00:00", "Z"),
            ),
        )
        connection.commit()


@pytest.mark.asyncio
async def test_device_registration_requires_admin_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "device-auth.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/devices",
            json={"device_id": "device-100", "display_name": "Warehouse Sensor"},
        )

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == 401
    assert payload["instance"] == "/admin/devices"


@pytest.mark.asyncio
async def test_device_list_requires_admin_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "device-list-auth.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/devices")

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == 401
    assert payload["instance"] == "/v1/devices"


@pytest.mark.asyncio
async def test_device_list_returns_registered_devices_and_supports_status_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "device-list.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-list-001", "display_name": "List Sensor A"},
        )
        second_register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-list-002", "display_name": "List Sensor B"},
        )
        disable_response = await client.post(
            "/admin/devices/device-list-002/disable",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "retired"},
        )

        all_devices = await client.get(
            "/v1/devices",
            headers={"Authorization": f"Bearer {token}"},
        )
        active_devices = await client.get(
            "/v1/devices?status=active",
            headers={"Authorization": f"Bearer {token}"},
        )
        disabled_devices = await client.get(
            "/v1/devices?status=disabled",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert first_register.status_code == 201
    assert second_register.status_code == 201
    assert disable_response.status_code == 200

    assert all_devices.status_code == 200
    all_payload = all_devices.json()
    assert all_payload["total"] == 2
    assert all_payload["limit"] == 50
    assert all_payload["offset"] == 0

    items = all_payload["items"]
    assert len(items) == 2
    for item in items:
        assert set(item) == {"device_id", "name", "status", "last_seen_at", "created_at"}
        assert item["created_at"]

    by_device_id = {item["device_id"]: item for item in items}
    assert by_device_id["device-list-001"]["name"] == "List Sensor A"
    assert by_device_id["device-list-001"]["status"] == "active"
    assert by_device_id["device-list-001"]["last_seen_at"] is None
    assert by_device_id["device-list-002"]["name"] == "List Sensor B"
    assert by_device_id["device-list-002"]["status"] == "disabled"
    assert by_device_id["device-list-002"]["last_seen_at"] is None

    assert active_devices.status_code == 200
    active_payload = active_devices.json()
    assert active_payload["total"] == 1
    assert [item["device_id"] for item in active_payload["items"]] == ["device-list-001"]
    assert [item["status"] for item in active_payload["items"]] == ["active"]

    assert disabled_devices.status_code == 200
    disabled_payload = disabled_devices.json()
    assert disabled_payload["total"] == 1
    assert [item["device_id"] for item in disabled_payload["items"]] == ["device-list-002"]
    assert [item["status"] for item in disabled_payload["items"]] == ["disabled"]


@pytest.mark.asyncio
async def test_device_list_can_exclude_simulation_namespace(tmp_path: Path) -> None:
    db_path = tmp_path / "device-list-real-mode.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-list-real-001", "display_name": "Real Sensor"},
        )
        simulation_detail_response = await client.get(
            "/admin/devices/dev-sim-2",
            headers={"Authorization": f"Bearer {token}"},
        )
        default_response = await client.get(
            "/v1/devices",
            headers={"Authorization": f"Bearer {token}"},
        )
        real_mode_response = await client.get(
            "/v1/devices?include_simulation=false",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert register_response.status_code == 201
    assert simulation_detail_response.status_code == 200
    assert default_response.status_code == 200
    assert default_response.json()["total"] == 4
    assert real_mode_response.status_code == 200
    real_mode_payload = real_mode_response.json()
    assert real_mode_payload["total"] == 1
    assert [item["device_id"] for item in real_mode_payload["items"]] == [
        "device-list-real-001"
    ]


@pytest.mark.asyncio
async def test_device_lifecycle_register_rotate_disable_persists_state(tmp_path: Path) -> None:
    db_path = tmp_path / "device-lifecycle.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-001", "display_name": "Line 1 Sensor"},
        )
        first_key_response = await client.post(
            "/admin/devices/device-001/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-001-key-v1",
                "algorithm": "ED25519",
                "public_key": "ed25519-public-key-v1",
            },
        )
        rotated_key_response = await client.post(
            "/admin/devices/device-001/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-001-key-v2",
                "algorithm": "ED25519",
                "public_key": "ed25519-public-key-v2",
            },
        )
        disable_response = await client.post(
            "/admin/devices/device-001/disable",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "device decommissioned"},
        )

    assert register_response.status_code == 201
    assert register_response.json()["status"] == "active"

    assert first_key_response.status_code == 201
    first_key_payload = first_key_response.json()
    assert first_key_payload["device_id"] == "device-001"
    assert first_key_payload["key_id"] == "device-001-key-v1"
    assert first_key_payload["retired_key_ids"] == []

    assert rotated_key_response.status_code == 201
    rotated_key_payload = rotated_key_response.json()
    assert rotated_key_payload["key_id"] == "device-001-key-v2"
    assert rotated_key_payload["retired_key_ids"] == ["device-001-key-v1"]

    assert disable_response.status_code == 200
    disable_payload = disable_response.json()
    assert disable_payload["status"] == "disabled"
    assert disable_payload["retired_key_ids"] == ["device-001-key-v2"]

    device_rows = _fetch_devices(db_path)
    assert device_rows == [("device-001", "disabled", "device decommissioned")]

    key_rows = _fetch_keys(db_path)
    assert [item[:3] for item in key_rows] == [
        ("device-001-key-v1", "ED25519", "retired"),
        ("device-001-key-v2", "ED25519", "retired"),
    ]

    audits = _fetch_audits(db_path)
    assert [entry[1] for entry in audits] == [
        "admin.device.register",
        "admin.device.key.rotate",
        "admin.device.key.rotate",
        "admin.device.disable",
    ]


@pytest.mark.asyncio
async def test_get_managed_device_detail_returns_device_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "device-detail.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-detail-001", "display_name": "Detail Sensor"},
        )
        rotate_response = await client.post(
            "/admin/devices/device-detail-001/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-detail-001-key-v1",
                "algorithm": "HMAC_SHA256",
                "public_key": "detail-secret",
            },
        )
        detail_response = await client.get(
            "/admin/devices/device-detail-001",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert register_response.status_code == 201
    assert rotate_response.status_code == 201
    assert detail_response.status_code == 200

    payload = detail_response.json()
    assert payload["device_id"] == "device-detail-001"
    assert payload["name"] == "Detail Sensor"
    assert payload["status"] == "active"
    assert payload["created_at"]
    assert payload["last_seen_at"] is None
    assert payload["key_count"] == 1
    assert payload["active_key"]["key_id"] == "device-detail-001-key-v1"
    assert payload["active_key"]["algorithm"] == "HMAC_SHA256"
    assert payload["active_key"]["status"] == "active"
    assert payload["active_key"]["activated_at"]
    assert payload["signature_failures_last_24h"] == 0
    assert payload["latest_signature_failure_reason"] is None
    assert payload["online_status_explanation"] == "Offline: device has not reported any events yet."


@pytest.mark.asyncio
async def test_get_managed_device_detail_includes_signature_failure_stats_and_offline_reason(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "device-detail-observability.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-detail-obs-001", "display_name": "Obs Sensor"},
        )
        rotate_response = await client.post(
            "/admin/devices/device-detail-obs-001/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-detail-obs-001-key-v1",
                "algorithm": "HMAC_SHA256",
                "public_key": "obs-secret",
            },
        )

    assert register_response.status_code == 201
    assert rotate_response.status_code == 201

    _insert_signature_failure_audits(
        db_path,
        device_id="device-detail-obs-001",
        key_id="device-detail-obs-001-key-v1",
        algorithm="HMAC_SHA256",
        reasons=["signature_mismatch", "managed_key_device_mismatch"],
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail_response = await client.get(
            "/admin/devices/device-detail-obs-001",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["device_id"] == "device-detail-obs-001"
    assert payload["signature_failures_last_24h"] == 2
    assert payload["latest_signature_failure_reason"] == "signature_mismatch"
    assert payload["online_status_explanation"] == "Offline: device has not reported any events yet."


@pytest.mark.asyncio
async def test_get_managed_device_detail_returns_not_found_for_missing_device(tmp_path: Path) -> None:
    db_path = tmp_path / "device-detail-missing.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/devices/device-not-found",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == 404
    assert payload["instance"] == "/admin/devices/device-not-found"


@pytest.mark.asyncio
async def test_get_managed_device_audits_returns_device_operations(tmp_path: Path) -> None:
    db_path = tmp_path / "device-audits.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-audit-001", "display_name": "Audit Sensor"},
        )
        rotate_response = await client.post(
            "/admin/devices/device-audit-001/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-audit-001-key-v1",
                "algorithm": "HMAC_SHA256",
                "public_key": "audit-secret-v1",
            },
        )
        disable_response = await client.post(
            "/admin/devices/device-audit-001/disable",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "audit-test-disable"},
        )
        audits_response = await client.get(
            "/admin/devices/device-audit-001/audits",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert register_response.status_code == 201
    assert rotate_response.status_code == 201
    assert disable_response.status_code == 200
    assert audits_response.status_code == 200

    payload = audits_response.json()
    assert payload["device_id"] == "device-audit-001"
    assert len(payload["items"]) == 3

    actions = [item["action"] for item in payload["items"]]
    assert actions == [
        "admin.device.disable",
        "admin.device.key.rotate",
        "admin.device.register",
    ]
    assert all(item["target"] == "device:device-audit-001" for item in payload["items"])
    assert all(item["created_at"] for item in payload["items"])


@pytest.mark.asyncio
async def test_get_managed_device_audits_returns_not_found_for_missing_device(tmp_path: Path) -> None:
    db_path = tmp_path / "device-audits-missing.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/devices/device-audit-not-found/audits",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == 404
    assert payload["instance"] == "/admin/devices/device-audit-not-found/audits"


@pytest.mark.asyncio
async def test_register_device_with_initial_key_creates_active_key(tmp_path: Path) -> None:
    db_path = tmp_path / "device-register-with-initial-key.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        register_response = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": "device-init-key-001",
                "display_name": "Init Key Sensor",
                "initial_key": {
                    "key_id": "device-init-key-001-v1",
                    "algorithm": "HMAC_SHA256",
                    "secret": "init-secret-v1",
                },
            },
        )
        key_list_response = await client.get(
            "/admin/devices/device-init-key-001/keys",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert register_response.status_code == 201
    register_payload = register_response.json()
    assert register_payload["device_id"] == "device-init-key-001"
    assert register_payload["status"] == "active"
    assert register_payload["initial_key"] == {
        "key_id": "device-init-key-001-v1",
        "algorithm": "HMAC_SHA256",
        "status": "active",
    }

    assert key_list_response.status_code == 200
    key_items = key_list_response.json()["items"]
    assert len(key_items) == 1
    assert key_items[0]["key_id"] == "device-init-key-001-v1"
    assert key_items[0]["algorithm"] == "HMAC_SHA256"
    assert key_items[0]["status"] == "active"


@pytest.mark.asyncio
async def test_register_device_with_duplicate_initial_key_returns_conflict(tmp_path: Path) -> None:
    db_path = tmp_path / "device-register-initial-key-conflict.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": "device-init-key-a",
                "display_name": "A",
                "initial_key": {
                    "key_id": "shared-initial-key",
                    "algorithm": "HMAC_SHA256",
                    "secret": "shared-secret-a",
                },
            },
        )
        second_register = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": "device-init-key-b",
                "display_name": "B",
                "initial_key": {
                    "key_id": "shared-initial-key",
                    "algorithm": "HMAC_SHA256",
                    "secret": "shared-secret-b",
                },
            },
        )

    assert first_register.status_code == 201
    assert second_register.status_code == 409
    payload = second_register.json()
    assert payload["status"] == 409
    assert payload["instance"] == "/admin/devices"


@pytest.mark.asyncio
async def test_cannot_add_key_to_disabled_device(tmp_path: Path) -> None:
    db_path = tmp_path / "device-disabled-key.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-200", "display_name": "Disabled Sensor"},
        )
        await client.post(
            "/admin/devices/device-200/disable",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "retired"},
        )
        key_response = await client.post(
            "/admin/devices/device-200/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-200-key-v1",
                "algorithm": "ED25519",
                "public_key": "unused-public-key",
            },
        )

    assert key_response.status_code == 409
    payload = key_response.json()
    assert payload["status"] == 409
    assert payload["instance"] == "/admin/devices/device-200/keys"


@pytest.mark.asyncio
async def test_register_device_returns_conflict_for_duplicate_device_id(tmp_path: Path) -> None:
    db_path = tmp_path / "device-duplicate.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-dup", "display_name": "dup"},
        )
        second = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-dup", "display_name": "dup-2"},
        )

    assert first.status_code == 201
    assert second.status_code == 409
    payload = second.json()
    assert payload["status"] == 409
    assert payload["instance"] == "/admin/devices"


@pytest.mark.asyncio
async def test_rotate_device_key_returns_not_found_for_missing_device(tmp_path: Path) -> None:
    db_path = tmp_path / "device-missing-for-key.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/devices/device-not-exist/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "device-missing-key-v1",
                "algorithm": "ED25519",
                "public_key": "public-key",
            },
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == 404
    assert payload["instance"] == "/admin/devices/device-not-exist/keys"


@pytest.mark.asyncio
async def test_rotate_device_key_returns_conflict_for_duplicate_key_id(tmp_path: Path) -> None:
    db_path = tmp_path / "device-duplicate-key-id.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_device = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-a", "display_name": "A"},
        )
        second_device = await client.post(
            "/admin/devices",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_id": "device-b", "display_name": "B"},
        )
        assert first_device.status_code == 201
        assert second_device.status_code == 201

        first_key = await client.post(
            "/admin/devices/device-a/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "shared-key",
                "algorithm": "ED25519",
                "public_key": "pub-a",
            },
        )
        second_key = await client.post(
            "/admin/devices/device-b/keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "key_id": "shared-key",
                "algorithm": "ED25519",
                "public_key": "pub-b",
            },
        )

    assert first_key.status_code == 201
    assert second_key.status_code == 409
    payload = second_key.json()
    assert payload["status"] == 409
    assert payload["instance"] == "/admin/devices/device-b/keys"


@pytest.mark.asyncio
async def test_disable_device_returns_not_found_for_missing_device(tmp_path: Path) -> None:
    db_path = tmp_path / "device-disable-missing.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-device-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-device-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/devices/device-not-found/disable",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "not found"},
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == 404
    assert payload["instance"] == "/admin/devices/device-not-found/disable"
