from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security.auth import _decode_jwt


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-login-tests"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"
    os.environ[
        "AUTH_DEMO_CREDENTIALS"
    ] = '{"admin":{"password":"admin123","role":"admin"},"regulator":{"password":"regulator123","role":"regulator"}}'


@pytest.mark.asyncio
async def test_login_api_returns_signed_token_for_valid_admin_credentials(tmp_path: Path) -> None:
    db_path = tmp_path / "auth-login-success.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "Bearer"
    assert payload["role"] == "admin"
    assert payload["expires_in"] == 86400

    claims = _decode_jwt(payload["access_token"])
    assert claims["sub"] == "admin"
    assert claims["roles"] == ["admin"]
    assert claims["iss"] == "traceability-auth"


@pytest.mark.asyncio
async def test_login_api_rejects_invalid_password(tmp_path: Path) -> None:
    db_path = tmp_path / "auth-login-failed.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == 401
    assert payload["instance"] == "/v1/auth/login"


@pytest.mark.asyncio
async def test_login_api_rejects_missing_required_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "auth-login-validation.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/login",
            json={"username": "admin"},
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/v1/auth/login"
    assert "errors" in payload
