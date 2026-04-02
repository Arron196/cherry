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

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.main import app


def _configure_runtime(db_path: Path, *, anchor_mode: str = "success", max_retries: int = 3) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({"factory-key-1": "super-secret"})
    os.environ["ANCHOR_ADAPTER"] = "active_mock"
    os.environ["ANCHOR_MOCK_MODE"] = anchor_mode
    os.environ["ANCHOR_MAX_RETRIES"] = str(max_retries)
    os.environ["AUTH_JWT_SECRET"] = "anchoring-admin-secret"
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
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _event_payload(*, device_id: str, batch_id: str, timestamp: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": device_id,
        "batch_id": batch_id,
        "timestamp": timestamp,
        "sensor_payload": {
            "temperature_c": 4.7,
            "humidity_pct": 71.2,
            "status": "stable",
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": "factory-key-1",
        },
    }
    payload["signature_envelope"]["signature"] = _sign_payload(payload, "super-secret")
    return payload


def _fetch_ingest_request(
    db_path: Path, idempotency_key: str
) -> tuple[int, int, str, int, str | None, str, str]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT ir.id, ir.event_id, ir.ingest_status, ir.retry_count, ir.last_error, e.batch_id, e.device_id "
            "FROM ingest_requests ir "
            "JOIN events e ON e.id = ir.event_id "
            "WHERE ir.idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    assert row is not None
    return (
        int(row[0]),
        int(row[1]),
        str(row[2]),
        int(row[3]),
        str(row[4]) if row[4] is not None else None,
        str(row[5]),
        str(row[6]),
    )


def _set_ingest_state(
    db_path: Path,
    *,
    idempotency_key: str,
    status: str,
    retry_count: int,
    last_error: str | None,
) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE ingest_requests SET ingest_status = ?, retry_count = ?, last_error = ? "
            "WHERE idempotency_key = ?",
            (status, retry_count, last_error, idempotency_key),
        )
        connection.commit()


def _fetch_status_counts(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT ingest_status, COUNT(*) FROM ingest_requests GROUP BY ingest_status"
        ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _fetch_audits(db_path: Path) -> list[tuple[str, str, str, Any]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT actor, action, target, metadata FROM audits ORDER BY id"
        ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2]), row[3]) for row in rows]


@pytest.mark.asyncio
async def test_admin_anchoring_task_listing_requires_admin_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-list-auth.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/anchoring/tasks", params={"status": "RECEIVED"})

    assert response.status_code == 401
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 401
    assert payload["instance"] == "/admin/anchoring/tasks"


@pytest.mark.asyncio
async def test_list_anchoring_tasks_is_deterministic_and_filterable(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-list.db"
    _configure_runtime(db_path)
    admin_token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for idempotency_key, device_id, batch_id, timestamp in [
            ("anchor-list-key-1", "device-001", "batch-a", "2026-02-10T10:00:00Z"),
            ("anchor-list-key-2", "device-002", "batch-a", "2026-02-10T10:01:00Z"),
            ("anchor-list-key-3", "device-001", "batch-b", "2026-02-10T10:02:00Z"),
        ]:
            response = await client.post(
                "/v1/events",
                headers={"Idempotency-Key": idempotency_key},
                json=_event_payload(device_id=device_id, batch_id=batch_id, timestamp=timestamp),
            )
            assert response.status_code == 202

        _set_ingest_state(
            db_path,
            idempotency_key="anchor-list-key-1",
            status="FAILED_RETRYING",
            retry_count=1,
            last_error="timeout",
        )
        _set_ingest_state(
            db_path,
            idempotency_key="anchor-list-key-2",
            status="FAILED_RETRYING",
            retry_count=2,
            last_error="adapter unavailable",
        )
        _set_ingest_state(
            db_path,
            idempotency_key="anchor-list-key-3",
            status="DEAD_LETTER",
            retry_count=3,
            last_error="exhausted",
        )

        list_response = await client.get(
            "/admin/anchoring/tasks",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"status": "FAILED_RETRYING", "limit": 10, "offset": 0},
        )

        filtered_response = await client.get(
            "/admin/anchoring/tasks",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={
                "status": "FAILED_RETRYING",
                "batch_id": "batch-a",
                "device_id": "device-002",
                "limit": 10,
                "offset": 0,
            },
        )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert len(payload["items"]) == 2
    assert [item["ingest_request_id"] for item in payload["items"]] == sorted(
        [item["ingest_request_id"] for item in payload["items"]], reverse=True
    )
    assert [item["status"] for item in payload["items"]] == ["FAILED_RETRYING", "FAILED_RETRYING"]

    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["total"] == 1
    assert len(filtered_payload["items"]) == 1
    assert filtered_payload["items"][0]["batch_id"] == "batch-a"
    assert filtered_payload["items"][0]["device_id"] == "device-002"


@pytest.mark.asyncio
async def test_requeue_resets_retry_metadata_and_appends_audit_row(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-requeue.db"
    _configure_runtime(db_path)
    admin_token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-requeue-key"},
            json=_event_payload(
                device_id="device-requeue",
                batch_id="batch-requeue",
                timestamp="2026-02-10T11:00:00Z",
            ),
        )
        assert ingest_response.status_code == 202

        ingest_request_id, _, _, _, _, _, _ = _fetch_ingest_request(db_path, "anchor-requeue-key")
        _set_ingest_state(
            db_path,
            idempotency_key="anchor-requeue-key",
            status="DEAD_LETTER",
            retry_count=5,
            last_error="anchor adapter verification failure",
        )

        requeue_response = await client.post(
            f"/admin/anchoring/tasks/{ingest_request_id}/requeue",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert requeue_response.status_code == 200
    payload = requeue_response.json()
    assert payload["ingest_request_id"] == ingest_request_id
    assert payload["status"] == "RECEIVED"
    assert payload["retry_count"] == 0

    _, _, status, retry_count, last_error, _, _ = _fetch_ingest_request(db_path, "anchor-requeue-key")
    assert status == "RECEIVED"
    assert retry_count == 0
    assert last_error is None

    audits = _fetch_audits(db_path)
    assert len(audits) == 1
    actor, action, target, metadata_raw = audits[0]
    assert actor == "admin-user"
    assert action == "admin.anchoring.task.requeue"
    assert target == f"ingest_request:{ingest_request_id}"
    metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
    assert metadata["result"] == "success"
    assert metadata["from_status"] == "DEAD_LETTER"
    assert metadata["to_status"] == "RECEIVED"


@pytest.mark.asyncio
async def test_requeue_returns_rfc9457_problem_for_ineligible_status(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-requeue-conflict.db"
    _configure_runtime(db_path)
    admin_token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-requeue-conflict-key"},
            json=_event_payload(
                device_id="device-eligible",
                batch_id="batch-eligible",
                timestamp="2026-02-10T11:10:00Z",
            ),
        )
        assert ingest_response.status_code == 202
        ingest_request_id, _, _, _, _, _, _ = _fetch_ingest_request(
            db_path, "anchor-requeue-conflict-key"
        )
        _set_ingest_state(
            db_path,
            idempotency_key="anchor-requeue-conflict-key",
            status="ANCHORED",
            retry_count=0,
            last_error=None,
        )

        response = await client.post(
            f"/admin/anchoring/tasks/{ingest_request_id}/requeue",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 409
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 409
    assert payload["instance"] == f"/admin/anchoring/tasks/{ingest_request_id}/requeue"


@pytest.mark.asyncio
async def test_requeue_returns_rfc9457_problem_for_missing_ingest_request(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-requeue-not-found.db"
    _configure_runtime(db_path)
    admin_token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/anchoring/tasks/9999/requeue",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 404
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 404
    assert payload["instance"] == "/admin/anchoring/tasks/9999/requeue"


@pytest.mark.asyncio
async def test_run_once_endpoint_delegates_to_state_machine_and_appends_audit_row(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-run-once.db"
    _configure_runtime(db_path, anchor_mode="success", max_retries=2)
    admin_token = _mint_jwt(
        subject="admin-worker",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for idempotency_key in ["anchor-run-once-key-1", "anchor-run-once-key-2"]:
            ingest_response = await client.post(
                "/v1/events",
                headers={"Idempotency-Key": idempotency_key},
                json=_event_payload(
                    device_id="device-run-once",
                    batch_id="batch-run-once",
                    timestamp="2026-02-10T11:20:00Z",
                ),
            )
            assert ingest_response.status_code == 202

        run_once_response = await client.post(
            "/admin/anchoring/run-once",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"limit": 1},
        )

    assert run_once_response.status_code == 200
    payload = run_once_response.json()
    assert payload["processed"] == 1
    assert payload["limit"] == 1

    counts = _fetch_status_counts(db_path)
    assert counts.get("ANCHORED", 0) == 1
    assert counts.get("RECEIVED", 0) == 1

    audits = _fetch_audits(db_path)
    assert len(audits) == 1
    actor, action, target, metadata_raw = audits[0]
    assert actor == "admin-worker"
    assert action == "admin.anchoring.run_once"
    assert target == "anchoring_worker"
    metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
    assert metadata["result"] == "success"
    assert metadata["processed"] == 1
    assert metadata["limit"] == 1


@pytest.mark.asyncio
async def test_run_once_endpoint_uses_default_limit_when_body_is_omitted(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-run-once-default-limit.db"
    _configure_runtime(db_path, anchor_mode="success", max_retries=2)
    admin_token = _mint_jwt(
        subject="admin-worker",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": "anchor-run-once-default-key-1"},
            json=_event_payload(
                device_id="device-run-once-default",
                batch_id="batch-run-once-default",
                timestamp="2026-02-10T11:40:00Z",
            ),
        )
        assert ingest_response.status_code == 202

        run_once_response = await client.post(
            "/admin/anchoring/run-once",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert run_once_response.status_code == 200
    payload = run_once_response.json()
    assert payload["processed"] == 1
    assert payload["limit"] == 100


@pytest.mark.asyncio
async def test_list_anchoring_tasks_rejects_invalid_status_query(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-list-invalid-status.db"
    _configure_runtime(db_path)
    admin_token = _mint_jwt(
        subject="admin-user",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/anchoring/tasks",
            params={"status": "NOT_A_STATE"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/admin/anchoring/tasks"
    assert "errors" in payload


@pytest.mark.asyncio
async def test_list_anchoring_tasks_rejects_regulator_role(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-list-forbidden-role.db"
    _configure_runtime(db_path)
    regulator_token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/anchoring/tasks",
            params={"status": "RECEIVED"},
            headers={"Authorization": f"Bearer {regulator_token}"},
        )

    assert response.status_code == 403
    payload = response.json()
    assert payload["status"] == 403
    assert payload["instance"] == "/admin/anchoring/tasks"


@pytest.mark.asyncio
async def test_run_once_requires_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-run-once-auth.db"
    _configure_runtime(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/anchoring/run-once", json={"limit": 1})

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == 401
    assert payload["instance"] == "/admin/anchoring/run-once"


@pytest.mark.asyncio
async def test_run_once_rejects_regulator_role(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-run-once-forbidden-role.db"
    _configure_runtime(db_path)
    regulator_token = _mint_jwt(
        subject="regulator-user",
        roles=["regulator"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/anchoring/run-once",
            headers={"Authorization": f"Bearer {regulator_token}"},
            json={"limit": 1},
        )

    assert response.status_code == 403
    payload = response.json()
    assert payload["status"] == 403
    assert payload["instance"] == "/admin/anchoring/run-once"


@pytest.mark.asyncio
async def test_run_once_rejects_invalid_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "anchoring-run-once-invalid-limit.db"
    _configure_runtime(db_path)
    admin_token = _mint_jwt(
        subject="admin-worker",
        roles=["admin"],
        issuer="traceability-auth",
        secret="anchoring-admin-secret",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/anchoring/run-once",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"limit": 0},
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/admin/anchoring/run-once"
    assert "errors" in payload
