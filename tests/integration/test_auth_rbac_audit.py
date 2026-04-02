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

from app.main import app


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-for-tests"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_jwt(*, subject: str, roles: list[str], issuer: str, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "iss": issuer,
        "roles": roles,
    }
    encoded_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def _audit_rows(db_path: Path) -> list[tuple[str, str, str, Any, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT actor, action, target, metadata, created_at FROM audits ORDER BY id"
        ).fetchall()
    return [(str(r[0]), str(r[1]), str(r[2]), r[3], str(r[4])) for r in rows]


@pytest.mark.asyncio
async def test_public_health_endpoint_remains_anonymous() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_admin_endpoint_returns_401_without_bearer_token(tmp_path: Path) -> None:
    db_path = tmp_path / "auth-401.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/policies/policy-001/activate")

    assert response.status_code == 401
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 401
    assert payload["instance"] == "/admin/policies/policy-001/activate"


@pytest.mark.asyncio
async def test_admin_endpoint_returns_403_for_insufficient_role(tmp_path: Path) -> None:
    db_path = tmp_path / "auth-403.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="auth-secret-for-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/policies/policy-001/activate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 403
    assert payload["instance"] == "/admin/policies/policy-001/activate"


@pytest.mark.asyncio
async def test_admin_endpoint_writes_append_only_audit_row(tmp_path: Path) -> None:
    db_path = tmp_path / "audit-append-only.db"
    _configure_runtime(db_path)
    token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-for-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/policies/policy-123/activate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_id"] == "policy-123"
    assert payload["status"] == "activated"

    rows = _audit_rows(db_path)
    assert len(rows) == 1
    actor, action, target, metadata_raw, created_at = rows[0]
    assert actor == "admin-user"
    assert action == "admin.policy.activate"
    assert target == "policy:policy-123"
    assert created_at

    metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
    assert isinstance(metadata, dict)
    assert metadata["result"] == "success"
