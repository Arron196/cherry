from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from app.domain.persistence.models import Base
from app.main import app


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-for-alert-tests"
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


def _insert_alert(
    db_path: Path,
    *,
    event_id: int,
    alert_type: str,
    severity: str,
    message: str,
    status: str,
    raised_at: str,
) -> int:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO alerts (event_id, alert_type, severity, message, status, raised_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, alert_type, severity, message, status, raised_at),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)


def _insert_minimum_event(
    db_path: Path,
    *,
    device_id: str = "device-alert-query-001",
    batch_id: str = "batch-alert-query-001",
    suffix: str = "alert-query-001",
) -> int:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO events ("
            "version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                device_id,
                batch_id,
                "2026-02-10T08:30:00Z",
                json.dumps({"temperature_c": 5.0, "humidity_pct": 70.0}),
                json.dumps({"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}),
                f"hash-{suffix}",
            ),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)


def _ensure_schema(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    Base.metadata.create_all(engine)


@pytest.mark.asyncio
async def test_alert_query_api_requires_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "alerts-api-auth.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/alerts")

    assert response.status_code == 401
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 401
    assert payload["instance"] == "/v1/alerts"


@pytest.mark.asyncio
async def test_alert_query_api_returns_recent_alerts_with_deterministic_defaults(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "alerts-api-query.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)

    event_id = _insert_minimum_event(db_path)
    oldest_id = _insert_alert(
        db_path,
        event_id=event_id,
        alert_type="ANCHOR_RETRY_FAILURE",
        severity="high",
        message="first failure",
        status="open",
        raised_at="2026-02-10 09:00:00",
    )
    tie_older_id = _insert_alert(
        db_path,
        event_id=event_id,
        alert_type="ANCHOR_RETRY_FAILURE",
        severity="high",
        message="second failure",
        status="open",
        raised_at="2026-02-10 09:10:00",
    )
    tie_newer_id = _insert_alert(
        db_path,
        event_id=event_id,
        alert_type="ANCHOR_DEAD_LETTER",
        severity="critical",
        message="moved to dead letter",
        status="open",
        raised_at="2026-02-10 09:10:00",
    )

    token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-tests",
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/alerts",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["order"] == "newest_first"
    assert payload["offset"] == 0
    assert payload["limit"] == 50
    assert payload["total"] == 3

    alert_ids = [item["id"] for item in payload["alerts"]]
    assert alert_ids == [tie_newer_id, tie_older_id, oldest_id]

    first = payload["alerts"][0]
    assert first["severity"] == "critical"
    assert first["status"] == "open"
    assert first["alert_type"] == "ANCHOR_DEAD_LETTER"

    paged = None
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        paged = await client.get(
            "/v1/alerts?limit=2&offset=1",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert paged is not None
    assert paged.status_code == 200
    paged_payload = paged.json()
    assert paged_payload["limit"] == 2
    assert paged_payload["offset"] == 1
    assert [item["id"] for item in paged_payload["alerts"]] == [tie_older_id, oldest_id]


@pytest.mark.asyncio
async def test_alert_query_can_exclude_simulation_namespace(tmp_path: Path) -> None:
    db_path = tmp_path / "alerts-api-real-mode.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    real_event_id = _insert_minimum_event(
        db_path,
        device_id="device-alert-real",
        batch_id="batch-alert-real",
        suffix="alert-real",
    )
    sim_event_id = _insert_minimum_event(
        db_path,
        device_id="dev-sim-1",
        batch_id="batch-sim-3000",
        suffix="alert-sim",
    )
    real_alert_id = _insert_alert(
        db_path,
        event_id=real_event_id,
        alert_type="ANCHOR_RETRY_FAILURE",
        severity="high",
        message="real failure",
        status="open",
        raised_at="2026-02-10 09:00:00",
    )
    _insert_alert(
        db_path,
        event_id=sim_event_id,
        alert_type="simulation.temperature_excursion",
        severity="medium",
        message="sim failure",
        status="open",
        raised_at="2026-02-10 09:10:00",
    )

    token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-tests",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        default_response = await client.get(
            "/v1/alerts",
            headers={"Authorization": f"Bearer {token}"},
        )
        real_mode_response = await client.get(
            "/v1/alerts?include_simulation=false",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert default_response.status_code == 200
    assert default_response.json()["total"] == 2
    assert real_mode_response.status_code == 200
    real_mode_payload = real_mode_response.json()
    assert real_mode_payload["total"] == 1
    assert [item["id"] for item in real_mode_payload["alerts"]] == [real_alert_id]


@pytest.mark.asyncio
async def test_alert_query_api_rejects_admin_forbidden_role(tmp_path: Path) -> None:
    db_path = tmp_path / "alerts-api-forbidden.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    token = _mint_jwt(
        subject="public-user",
        roles=["public"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/alerts",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    payload = response.json()
    assert payload["status"] == 403
    assert payload["instance"] == "/v1/alerts"


@pytest.mark.asyncio
async def test_alert_query_api_rejects_invalid_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "alerts-api-invalid-limit.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="auth-secret-for-alert-tests",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/alerts?limit=9999",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/v1/alerts"
    assert "errors" in payload
