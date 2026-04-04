from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from app.domain.persistence.models import Base
from app.main import app


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-for-alert-action-tests"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"


def _ensure_schema(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    Base.metadata.create_all(engine)


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


def _insert_minimum_event(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO events ("
            "version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-alert-actions-001",
                "batch-alert-actions-001",
                "2026-02-10T08:45:00Z",
                json.dumps({"temperature_c": 7.5, "humidity_pct": 65.0}),
                json.dumps({"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}),
                "hash-alert-actions-001",
            ),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)


def _insert_alert(
    db_path: Path,
    *,
    event_id: int,
    alert_type: str,
    severity: str,
    status: str,
    message: str,
    raised_at: str,
    resolved_at: str | None = None,
) -> int:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO alerts (event_id, alert_type, severity, message, status, raised_at, resolved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, alert_type, severity, message, status, raised_at, resolved_at),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)


def _fetch_alert(db_path: Path, alert_id: int) -> tuple[str, str, str | None]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT status, severity, resolved_at FROM alerts WHERE id = ?",
            (alert_id,),
        ).fetchone()
    assert row is not None
    return str(row[0]), str(row[1]), str(row[2]) if row[2] is not None else None


def _fetch_audits(db_path: Path) -> list[tuple[str, str, str, Any]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT actor, action, target, metadata FROM audits ORDER BY id"
        ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2]), row[3]) for row in rows]


@pytest.mark.asyncio
async def test_alert_action_endpoints_require_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "alert-actions-auth.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/alerts/1/ack")

    assert response.status_code == 401
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 401
    assert payload["instance"] == "/v1/alerts/1/ack"


@pytest.mark.asyncio
async def test_ack_and_resolve_actions_update_state_and_append_audits(tmp_path: Path) -> None:
    db_path = tmp_path / "alert-actions-ack-resolve.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    event_id = _insert_minimum_event(db_path)
    alert_id = _insert_alert(
        db_path,
        event_id=event_id,
        alert_type="ANCHOR_RETRY_FAILURE",
        severity="medium",
        status="open",
        message="anchor timed out",
        raised_at="2026-02-10 09:10:00",
    )

    regulator_token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-action-tests",
    )
    admin_token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-action-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ack_response = await client.post(
            f"/v1/alerts/{alert_id}/ack",
            headers={"Authorization": f"Bearer {regulator_token}"},
        )
        resolve_response = await client.post(
            f"/v1/alerts/{alert_id}/resolve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert ack_response.status_code == 200
    ack_payload = ack_response.json()
    assert ack_payload["id"] == alert_id
    assert ack_payload["status"] == "acknowledged"
    assert ack_payload["severity"] == "medium"
    assert ack_payload["resolved_at"] is None

    assert resolve_response.status_code == 200
    resolve_payload = resolve_response.json()
    assert resolve_payload["id"] == alert_id
    assert resolve_payload["status"] == "resolved"
    assert resolve_payload["severity"] == "medium"
    assert isinstance(resolve_payload["resolved_at"], str)
    assert resolve_payload["resolved_at"].endswith("Z")

    status, severity, resolved_at = _fetch_alert(db_path, alert_id)
    assert status == "resolved"
    assert severity == "medium"
    assert resolved_at is not None

    audits = _fetch_audits(db_path)
    assert len(audits) == 2

    ack_actor, ack_action, ack_target, ack_metadata_raw = audits[0]
    assert ack_actor == "regulator-user"
    assert ack_action == "alert.acknowledge"
    assert ack_target == f"alert:{alert_id}"
    ack_metadata = (
        json.loads(ack_metadata_raw) if isinstance(ack_metadata_raw, str) else ack_metadata_raw
    )
    assert ack_metadata["result"] == "success"

    resolve_actor, resolve_action, resolve_target, resolve_metadata_raw = audits[1]
    assert resolve_actor == "admin-user"
    assert resolve_action == "alert.resolve"
    assert resolve_target == f"alert:{alert_id}"
    resolve_metadata = (
        json.loads(resolve_metadata_raw)
        if isinstance(resolve_metadata_raw, str)
        else resolve_metadata_raw
    )
    assert resolve_metadata["result"] == "success"


@pytest.mark.asyncio
async def test_escalate_action_is_deterministic_and_keeps_status(tmp_path: Path) -> None:
    db_path = tmp_path / "alert-actions-escalate.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    event_id = _insert_minimum_event(db_path)
    alert_id = _insert_alert(
        db_path,
        event_id=event_id,
        alert_type="ANCHOR_RETRY_FAILURE",
        severity="medium",
        status="acknowledged",
        message="anchor timeout retries",
        raised_at="2026-02-10 09:20:00",
    )

    token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-action-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            f"/v1/alerts/{alert_id}/escalate",
            headers={"Authorization": f"Bearer {token}"},
        )
        second_response = await client.post(
            f"/v1/alerts/{alert_id}/escalate",
            headers={"Authorization": f"Bearer {token}"},
        )
        third_response = await client.post(
            f"/v1/alerts/{alert_id}/escalate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert first_response.status_code == 200
    assert first_response.json()["severity"] == "high"
    assert first_response.json()["status"] == "acknowledged"

    assert second_response.status_code == 200
    assert second_response.json()["severity"] == "critical"
    assert second_response.json()["status"] == "acknowledged"

    assert third_response.status_code == 409
    conflict_payload = third_response.json()
    assert set(conflict_payload) >= {"type", "title", "status", "detail", "instance"}
    assert conflict_payload["status"] == 409
    assert conflict_payload["instance"] == f"/v1/alerts/{alert_id}/escalate"

    status, severity, resolved_at = _fetch_alert(db_path, alert_id)
    assert status == "acknowledged"
    assert severity == "critical"
    assert resolved_at is None


@pytest.mark.asyncio
async def test_alert_actions_return_rfc9457_for_not_found_and_invalid_transitions(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "alert-actions-problems.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    event_id = _insert_minimum_event(db_path)
    resolved_alert_id = _insert_alert(
        db_path,
        event_id=event_id,
        alert_type="ANCHOR_DEAD_LETTER",
        severity="critical",
        status="resolved",
        message="already resolved",
        raised_at="2026-02-10 09:30:00",
        resolved_at="2026-02-10 09:35:00",
    )

    token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-action-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ack_conflict = await client.post(
            f"/v1/alerts/{resolved_alert_id}/ack",
            headers={"Authorization": f"Bearer {token}"},
        )
        resolve_conflict = await client.post(
            f"/v1/alerts/{resolved_alert_id}/resolve",
            headers={"Authorization": f"Bearer {token}"},
        )
        escalate_conflict = await client.post(
            f"/v1/alerts/{resolved_alert_id}/escalate",
            headers={"Authorization": f"Bearer {token}"},
        )
        not_found = await client.post(
            "/v1/alerts/999999/ack",
            headers={"Authorization": f"Bearer {token}"},
        )

    for response, instance in [
        (ack_conflict, f"/v1/alerts/{resolved_alert_id}/ack"),
        (resolve_conflict, f"/v1/alerts/{resolved_alert_id}/resolve"),
        (escalate_conflict, f"/v1/alerts/{resolved_alert_id}/escalate"),
    ]:
        assert response.status_code == 409
        payload = response.json()
        assert set(payload) >= {"type", "title", "status", "detail", "instance"}
        assert payload["status"] == 409
        assert payload["instance"] == instance

    assert not_found.status_code == 404
    not_found_payload = not_found.json()
    assert set(not_found_payload) >= {"type", "title", "status", "detail", "instance"}
    assert not_found_payload["status"] == 404
    assert not_found_payload["instance"] == "/v1/alerts/999999/ack"
