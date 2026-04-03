from __future__ import annotations

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


def _ensure_schema(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    Base.metadata.create_all(engine)


def _public_trace_alias_enabled() -> bool:
    paths = app.openapi().get("paths", {})
    return isinstance(paths, dict) and "/v1/trace/{batch_id}/public" in paths


def _compat_expect_routes_disabled() -> bool:
    raw = os.getenv("COMPAT_EXPECT_ROUTES_DISABLED", "0").strip()
    if raw not in {"0", "1"}:
        raise AssertionError("COMPAT_EXPECT_ROUTES_DISABLED must be '0' or '1'")
    return raw == "1"


def _assert_public_trace_alias_expectation() -> bool:
    expect_routes_disabled = _compat_expect_routes_disabled()
    actual_enabled = _public_trace_alias_enabled()
    assert actual_enabled is (not expect_routes_disabled), (
        "Compat route expectation mismatch for /v1/trace/{batch_id}/public: "
        f"COMPAT_EXPECT_ROUTES_DISABLED={int(expect_routes_disabled)} but route is "
        f"{'present' if actual_enabled else 'absent'} in OpenAPI"
    )
    return expect_routes_disabled


def _seed_public_trace_batch(db_path: Path, *, batch_id: str) -> None:
    with sqlite3.connect(db_path) as connection:
        first_event = connection.execute(
            "INSERT INTO events ("
            "version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, "
            "canonical_hash, co2_ppm, vibration_g, supply_chain_stage"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-public-001",
                batch_id,
                "2026-02-15 04:00:00",
                json.dumps({"temperature_c": 3.5, "humidity_pct": 72.2}),
                json.dumps(
                    {
                        "algorithm": "ECDSA_P256_SHA256",
                        "key_id": "factory-key-1",
                        "signature": "sig-1",
                    }
                ),
                f"{'a' * 63}1",
                428.0,
                0.25,
                "storage",
            ),
        )
        assert first_event.lastrowid is not None
        first_event_id = int(first_event.lastrowid)

        second_event = connection.execute(
            "INSERT INTO events ("
            "version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, "
            "canonical_hash, co2_ppm, vibration_g, supply_chain_stage"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-public-001",
                batch_id,
                "2026-02-15 06:30:00",
                json.dumps({"temperature_c": 4.1, "humidity_pct": 69.8}),
                json.dumps(
                    {
                        "algorithm": "ECDSA_P256_SHA256",
                        "key_id": "factory-key-1",
                        "signature": "sig-2",
                    }
                ),
                f"{'a' * 63}2",
                440.0,
                0.31,
                "transport",
            ),
        )
        assert second_event.lastrowid is not None
        second_event_id = int(second_event.lastrowid)

        connection.execute(
            "INSERT INTO quality_results (event_id, check_name, status, score, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                second_event_id,
                "quality.grade",
                "PASS",
                96.5,
                json.dumps({"grade": "A"}),
            ),
        )

        connection.execute(
            "INSERT INTO anchor_receipts (event_id, network, transaction_hash, receipt_payload, anchored_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                first_event_id,
                "active_mock",
                "0xtx-hash-1",
                json.dumps({"status": "ok"}),
                "2026-02-15 05:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO anchor_receipts (event_id, network, transaction_hash, receipt_payload, anchored_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                second_event_id,
                "active_mock",
                "0xtx-hash-2",
                json.dumps({"status": "ok"}),
                "2026-02-15 06:45:00",
            ),
        )

        connection.commit()


def _problem_without_instance(problem: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in problem.items() if key != "instance"}


def test_public_trace_openapi_contract_exposes_canonical_and_alias_routes() -> None:
    openapi = app.openapi()
    paths = openapi.get("paths", {})
    assert isinstance(paths, dict)
    expect_routes_disabled = _assert_public_trace_alias_expectation()

    canonical = paths.get("/v1/public/trace/{batch_id}")
    assert isinstance(canonical, dict)
    canonical_get = canonical.get("get")
    assert isinstance(canonical_get, dict)
    canonical_schema = (
        canonical_get.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    assert canonical_schema == {"$ref": "#/components/schemas/PublicTraceResponse"}

    alias = paths.get("/v1/trace/{batch_id}/public")
    if expect_routes_disabled:
        assert alias is None
    else:
        assert isinstance(alias, dict)
        alias_get = alias.get("get")
        assert isinstance(alias_get, dict)
        alias_schema = (
            alias_get.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        assert alias_schema == {"$ref": "#/components/schemas/PublicTraceResponse"}


@pytest.mark.asyncio
async def test_public_trace_canonical_and_alias_payloads_are_contract_equivalent(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "public-trace-parity.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    _seed_public_trace_batch(db_path, batch_id="batch-public-001")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        canonical = await client.get("/v1/public/trace/batch-public-001")
        alias = await client.get("/v1/trace/batch-public-001/public")

    assert canonical.status_code == 200
    canonical_payload = canonical.json()
    assert set(canonical_payload) == {
        "batch_info",
        "timeline",
        "stage_environments",
        "quality",
        "blockchain_anchor",
    }
    assert canonical_payload["batch_info"]["batch_id"] == "batch-public-001"
    assert len(canonical_payload["timeline"]) == 2
    expect_routes_disabled = _assert_public_trace_alias_expectation()

    if expect_routes_disabled:
        assert alias.status_code == 404
        assert alias.json() == {"detail": "Not Found"}
    else:
        assert alias.status_code == 200
        alias_payload = alias.json()
        assert canonical_payload == alias_payload


@pytest.mark.asyncio
async def test_public_trace_canonical_and_alias_404_semantics_match(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "public-trace-not-found-parity.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        canonical = await client.get("/v1/public/trace/batch-not-found")
        alias = await client.get("/v1/trace/batch-not-found/public")

    assert canonical.status_code == 404
    assert alias.status_code == 404

    canonical_problem = canonical.json()
    assert set(canonical_problem) == {"type", "title", "status", "detail", "instance"}
    assert canonical_problem["instance"] == "/v1/public/trace/batch-not-found"
    expect_routes_disabled = _assert_public_trace_alias_expectation()

    alias_problem = alias.json()
    if expect_routes_disabled:
        assert alias_problem == {"detail": "Not Found"}
    else:
        assert set(alias_problem) == {"type", "title", "status", "detail", "instance"}
        assert _problem_without_instance(
            canonical_problem
        ) == _problem_without_instance(alias_problem)
        assert alias_problem["instance"] == "/v1/trace/batch-not-found/public"


@pytest.mark.asyncio
async def test_public_trace_uses_latest_quality_row_with_valid_grade(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "public-trace-quality-fallback.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    batch_id = "batch-public-quality-fallback"
    _seed_public_trace_batch(db_path, batch_id=batch_id)

    with sqlite3.connect(db_path) as connection:
        event_id_row = connection.execute(
            "SELECT id FROM events WHERE batch_id = ? ORDER BY timestamp DESC, id DESC LIMIT 1",
            (batch_id,),
        ).fetchone()
        assert event_id_row is not None
        newest_event_id = int(event_id_row[0])

        connection.execute(
            "INSERT INTO quality_results (event_id, check_name, status, score, details) VALUES (?, ?, ?, ?, ?)",
            (
                newest_event_id,
                "quality.grade",
                "PASS",
                99.9,
                json.dumps({"note": "missing grade"}),
            ),
        )
        connection.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        canonical = await client.get(f"/v1/public/trace/{batch_id}")

    assert canonical.status_code == 200
    payload = canonical.json()
    assert payload["quality"] == {
        "grade": "A",
        "score": 96.5,
        "max_score": 100,
    }
