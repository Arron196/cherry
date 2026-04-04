from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

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


def _ensure_legacy_stats_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "version VARCHAR(32) NOT NULL, "
            "device_id VARCHAR(128) NOT NULL, "
            "batch_id VARCHAR(128) NOT NULL, "
            "timestamp DATETIME NOT NULL, "
            "sensor_payload JSON NOT NULL, "
            "signature_envelope JSON NOT NULL, "
            "canonical_hash VARCHAR(64) NOT NULL UNIQUE, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL"
            ")"
        )
        connection.execute(
            "CREATE TABLE ingest_requests ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "idempotency_key VARCHAR(128) NOT NULL UNIQUE, "
            "payload_hash VARCHAR(64) NOT NULL, "
            "ingest_status VARCHAR(32) NOT NULL, "
            "retry_count INTEGER DEFAULT 0 NOT NULL, "
            "last_error TEXT, "
            "event_id INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL"
            ")"
        )
        connection.execute(
            "CREATE TABLE quality_results ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event_id INTEGER NOT NULL, "
            "check_name VARCHAR(128) NOT NULL, "
            "status VARCHAR(32) NOT NULL, "
            "score FLOAT, "
            "details JSON, "
            "evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL"
            ")"
        )
        connection.execute(
            "CREATE TABLE alerts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event_id INTEGER, "
            "alert_type VARCHAR(64) NOT NULL, "
            "severity VARCHAR(32) NOT NULL, "
            "message TEXT NOT NULL, "
            "status VARCHAR(32) NOT NULL DEFAULT 'open', "
            "raised_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
            "resolved_at DATETIME"
            ")"
        )
        connection.execute(
            "CREATE TABLE managed_devices ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "device_id VARCHAR(128) NOT NULL UNIQUE, "
            "display_name VARCHAR(255), "
            "status VARCHAR(32) NOT NULL DEFAULT 'active', "
            "disabled_reason TEXT, "
            "disabled_at DATETIME, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL"
            ")"
        )
        connection.commit()


def _insert_managed_device(db_path: Path, *, device_id: str, status: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO managed_devices (device_id, status) VALUES (?, ?)",
            (device_id, status),
        )
        connection.commit()


def _insert_event(
    db_path: Path,
    *,
    device_id: str,
    batch_id: str,
    timestamp: str,
    temperature_c: float,
    humidity_pct: float,
    canonical_suffix: str,
    stage: str | None,
) -> int:
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO events ("
            "version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash, supply_chain_stage"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                device_id,
                batch_id,
                timestamp,
                json.dumps(
                    {
                        "temperature_c": temperature_c,
                        "humidity_pct": humidity_pct,
                    }
                ),
                json.dumps(
                    {
                        "algorithm": "HMAC_SHA256",
                        "key_id": "n/a",
                        "signature": "n/a",
                    }
                ),
                f"hash-{canonical_suffix}",
                stage,
            ),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)


def _insert_quality_result(
    db_path: Path,
    *,
    event_id: int,
    score: float,
    grade: str,
) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO quality_results (event_id, check_name, status, score, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event_id,
                "dashboard-quality",
                "PASS",
                score,
                json.dumps({"grade": grade}),
            ),
        )
        connection.commit()


def _insert_alert(db_path: Path, *, event_id: int, status: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO alerts (event_id, alert_type, severity, message, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event_id,
                "temperature_spike",
                "high",
                "temp exceeded threshold",
                status,
            ),
        )
        connection.commit()


def test_stats_openapi_contract_shapes_are_canonical() -> None:
    openapi = app.openapi()
    paths = openapi.get("paths", {})
    assert isinstance(paths, dict)

    overview_schema = (
        paths.get("/v1/stats/overview", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    trend_schema = (
        paths.get("/v1/stats/temperature-trend", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    quality_schema = (
        paths.get("/v1/stats/quality-distribution", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    stage_schema = (
        paths.get("/v1/stats/stage-distribution", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    dashboard_schema = (
        paths.get("/v1/stats/dashboard", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )

    assert overview_schema == {"$ref": "#/components/schemas/OverviewResponse"}
    assert trend_schema.get("type") == "array"
    assert quality_schema.get("type") == "array"
    assert stage_schema.get("type") == "array"
    assert dashboard_schema == {"$ref": "#/components/schemas/DashboardStatsResponse"}

    components = openapi.get("components", {})
    assert isinstance(components, dict)
    schemas = components.get("schemas", {})
    assert isinstance(schemas, dict)
    overview = schemas.get("OverviewResponse", {})
    assert isinstance(overview, dict)
    required = overview.get("required", [])
    assert isinstance(required, list)
    assert {"avg_quality_score", "open_alerts"}.issubset(set(required))


@pytest.mark.asyncio
async def test_stats_endpoints_return_dashboard_contract_shapes(tmp_path: Path) -> None:
    db_path = tmp_path / "stats-contract.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    now = datetime.now(UTC).replace(microsecond=0)
    ts_1 = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    ts_2 = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    ts_3 = (now - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")

    _insert_managed_device(db_path, device_id="device-1", status="active")
    _insert_managed_device(db_path, device_id="device-2", status="active")
    _insert_managed_device(db_path, device_id="device-3", status="disabled")

    event_1 = _insert_event(
        db_path,
        device_id="device-1",
        batch_id="batch-1",
        timestamp=ts_1,
        temperature_c=5.0,
        humidity_pct=70.0,
        canonical_suffix="stats-1",
        stage="harvest",
    )
    event_2 = _insert_event(
        db_path,
        device_id="device-1",
        batch_id="batch-1",
        timestamp=ts_2,
        temperature_c=7.0,
        humidity_pct=69.0,
        canonical_suffix="stats-2",
        stage="transport",
    )
    event_3 = _insert_event(
        db_path,
        device_id="device-2",
        batch_id="batch-2",
        timestamp=ts_3,
        temperature_c=9.0,
        humidity_pct=68.0,
        canonical_suffix="stats-3",
        stage="storage",
    )

    _insert_quality_result(db_path, event_id=event_1, score=90.0, grade="A")
    _insert_quality_result(db_path, event_id=event_2, score=80.0, grade="B")
    _insert_quality_result(db_path, event_id=event_3, score=100.0, grade="A")

    _insert_alert(db_path, event_id=event_1, status="open")
    _insert_alert(db_path, event_id=event_2, status="resolved")
    _insert_alert(db_path, event_id=event_3, status="open")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        overview_response = await client.get("/v1/stats/overview")
        temperature_response = await client.get("/v1/stats/temperature-trend")
        quality_response = await client.get("/v1/stats/quality-distribution")
        stage_response = await client.get("/v1/stats/stage-distribution")
        dashboard_response = await client.get("/v1/stats/dashboard")

    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert set(overview_payload) == {
        "total_batches",
        "total_events",
        "active_devices",
        "avg_quality_score",
        "grade_distribution",
        "open_alerts",
    }
    assert overview_payload["total_batches"] == 2
    assert overview_payload["total_events"] == 3
    assert overview_payload["active_devices"] == 2
    assert overview_payload["avg_quality_score"] == pytest.approx(90.0)
    assert overview_payload["grade_distribution"] == {"A": 2, "B": 1, "C": 0}
    assert overview_payload["open_alerts"] == 2

    assert temperature_response.status_code == 200
    temperature_payload = temperature_response.json()
    assert temperature_payload == [
        {
            "timestamp": ts_1,
            "avg_temperature": 5.0,
            "min_temperature": 5.0,
            "max_temperature": 5.0,
        },
        {
            "timestamp": ts_2,
            "avg_temperature": 7.0,
            "min_temperature": 7.0,
            "max_temperature": 7.0,
        },
        {
            "timestamp": ts_3,
            "avg_temperature": 9.0,
            "min_temperature": 9.0,
            "max_temperature": 9.0,
        },
    ]

    assert quality_response.status_code == 200
    quality_payload = quality_response.json()
    assert quality_payload == [
        {"grade": "A", "count": 2, "percentage": 66.7},
        {"grade": "B", "count": 1, "percentage": 33.3},
    ]

    assert stage_response.status_code == 200
    stage_payload = stage_response.json()
    assert stage_payload == [
        {"stage": "harvest", "count": 1},
        {"stage": "storage", "count": 1},
        {"stage": "transport", "count": 1},
    ]

    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {
        "overview": overview_payload,
        "temperature_trend": temperature_payload,
        "quality_distribution": quality_payload,
        "stage_distribution": stage_payload,
        "recent_events": [
            {
                "id": event_3,
                "batch_id": "batch-2",
                "device_id": "device-2",
                "timestamp": ts_3,
                "ingest_status": "UNKNOWN",
                "temperature_c": 9.0,
                "humidity_pct": 68.0,
                "co2_ppm": None,
                "vibration_g": None,
                "supply_chain_stage": "storage",
                "quality_grade": "A",
                "anchor_transaction_hash": None,
            },
            {
                "id": event_2,
                "batch_id": "batch-1",
                "device_id": "device-1",
                "timestamp": ts_2,
                "ingest_status": "UNKNOWN",
                "temperature_c": 7.0,
                "humidity_pct": 69.0,
                "co2_ppm": None,
                "vibration_g": None,
                "supply_chain_stage": "transport",
                "quality_grade": "B",
                "anchor_transaction_hash": None,
            },
            {
                "id": event_1,
                "batch_id": "batch-1",
                "device_id": "device-1",
                "timestamp": ts_1,
                "ingest_status": "UNKNOWN",
                "temperature_c": 5.0,
                "humidity_pct": 70.0,
                "co2_ppm": None,
                "vibration_g": None,
                "supply_chain_stage": "harvest",
                "quality_grade": "A",
                "anchor_transaction_hash": None,
            },
        ],
    }


@pytest.mark.asyncio
async def test_dashboard_stats_can_exclude_simulation_namespace(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stats-real-mode.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    now = datetime.now(UTC).replace(microsecond=0)
    real_ts = (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
    sim_ts = (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")

    _insert_managed_device(db_path, device_id="device-real-1", status="active")
    _insert_managed_device(db_path, device_id="dev-sim-1", status="active")

    real_event = _insert_event(
        db_path,
        device_id="device-real-1",
        batch_id="batch-real-1",
        timestamp=real_ts,
        temperature_c=4.2,
        humidity_pct=71.0,
        canonical_suffix="real-mode-real",
        stage="transport",
    )
    sim_event = _insert_event(
        db_path,
        device_id="dev-sim-1",
        batch_id="batch-sim-3000",
        timestamp=sim_ts,
        temperature_c=8.8,
        humidity_pct=65.0,
        canonical_suffix="real-mode-sim",
        stage="storage",
    )

    _insert_quality_result(db_path, event_id=real_event, score=96.0, grade="A")
    _insert_quality_result(db_path, event_id=sim_event, score=72.0, grade="C")
    _insert_alert(db_path, event_id=real_event, status="open")
    _insert_alert(db_path, event_id=sim_event, status="open")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        default_response = await client.get("/v1/stats/dashboard")
        real_mode_response = await client.get(
            "/v1/stats/dashboard?include_simulation=false"
        )
        real_mode_overview_response = await client.get(
            "/v1/stats/overview?include_simulation=false"
        )
        real_mode_temperature_response = await client.get(
            "/v1/stats/temperature-trend?include_simulation=false"
        )
        real_mode_quality_response = await client.get(
            "/v1/stats/quality-distribution?include_simulation=false"
        )
        real_mode_stage_response = await client.get(
            "/v1/stats/stage-distribution?include_simulation=false"
        )

    assert default_response.status_code == 200
    default_payload = default_response.json()
    assert default_payload["overview"]["total_batches"] == 2
    assert default_payload["overview"]["active_devices"] == 2
    assert default_payload["overview"]["open_alerts"] == 2

    assert real_mode_response.status_code == 200
    real_mode_payload = real_mode_response.json()
    assert real_mode_payload["overview"] == {
        "total_batches": 1,
        "total_events": 1,
        "active_devices": 1,
        "avg_quality_score": 96.0,
        "grade_distribution": {"A": 1, "B": 0, "C": 0},
        "open_alerts": 1,
    }
    assert real_mode_payload["temperature_trend"] == [
        {
            "timestamp": real_ts,
            "avg_temperature": 4.2,
            "min_temperature": 4.2,
            "max_temperature": 4.2,
        }
    ]
    assert real_mode_payload["quality_distribution"] == [
        {"grade": "A", "count": 1, "percentage": 100.0}
    ]
    assert real_mode_payload["stage_distribution"] == [
        {"stage": "transport", "count": 1}
    ]
    assert [item["batch_id"] for item in real_mode_payload["recent_events"]] == [
        "batch-real-1"
    ]
    assert real_mode_overview_response.json() == real_mode_payload["overview"]
    assert real_mode_temperature_response.json() == real_mode_payload[
        "temperature_trend"
    ]
    assert real_mode_quality_response.json() == real_mode_payload[
        "quality_distribution"
    ]
    assert real_mode_stage_response.json() == real_mode_payload["stage_distribution"]


@pytest.mark.asyncio
async def test_temperature_trend_ignores_non_numeric_and_boolean_sensor_values(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stats-temp-filter.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    now = datetime.now(UTC).replace(microsecond=0)
    valid_ts = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    bool_ts = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    string_ts = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO events (version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash, supply_chain_stage) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-1",
                "batch-1",
                valid_ts,
                json.dumps({"temperature_c": 4.5, "humidity_pct": 70.0}),
                json.dumps(
                    {"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}
                ),
                "hash-temp-valid",
                "harvest",
            ),
        )
        connection.execute(
            "INSERT INTO events (version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash, supply_chain_stage) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-1",
                "batch-1",
                bool_ts,
                json.dumps({"temperature_c": True, "humidity_pct": 70.0}),
                json.dumps(
                    {"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}
                ),
                "hash-temp-bool",
                "harvest",
            ),
        )
        connection.execute(
            "INSERT INTO events (version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash, supply_chain_stage) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-1",
                "batch-1",
                string_ts,
                json.dumps({"temperature_c": "6.5", "humidity_pct": 70.0}),
                json.dumps(
                    {"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}
                ),
                "hash-temp-string",
                "harvest",
            ),
        )
        connection.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/stats/temperature-trend")

    assert response.status_code == 200
    assert response.json() == [
        {
            "timestamp": valid_ts,
            "avg_temperature": 4.5,
            "min_temperature": 4.5,
            "max_temperature": 4.5,
        }
    ]


@pytest.mark.asyncio
async def test_temperature_trend_is_bounded_for_large_event_windows(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stats-temp-large-window.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)
    now = datetime.now(UTC).replace(microsecond=0)

    for index in range(120):
        timestamp = (now - timedelta(minutes=119 - index)).isoformat().replace(
            "+00:00", "Z"
        )
        _insert_event(
            db_path,
            device_id=f"device-{index % 4}",
            batch_id=f"batch-{index // 4}",
            timestamp=timestamp,
            temperature_c=4.0 + (index % 8) * 0.2,
            humidity_pct=70.0,
            canonical_suffix=f"large-window-{index}",
            stage="transport",
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        trend_response = await client.get("/v1/stats/temperature-trend")
        dashboard_response = await client.get("/v1/stats/dashboard")

    assert trend_response.status_code == 200
    trend_payload = trend_response.json()
    assert 0 < len(trend_payload) <= 96
    assert len(trend_payload) < 120
    assert [item["timestamp"] for item in trend_payload] == sorted(
        item["timestamp"] for item in trend_payload
    )
    assert all(
        item["min_temperature"] <= item["avg_temperature"] <= item["max_temperature"]
        for item in trend_payload
    )

    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["temperature_trend"] == trend_payload


@pytest.mark.asyncio
async def test_stats_endpoints_return_empty_window_defaults_without_errors(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stats-empty.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        overview_response = await client.get("/v1/stats/overview")
        temperature_response = await client.get("/v1/stats/temperature-trend")
        quality_response = await client.get("/v1/stats/quality-distribution")
        stage_response = await client.get("/v1/stats/stage-distribution")
        dashboard_response = await client.get("/v1/stats/dashboard")

    assert overview_response.status_code == 200
    assert overview_response.json() == {
        "total_batches": 0,
        "total_events": 0,
        "active_devices": 0,
        "avg_quality_score": 0.0,
        "grade_distribution": {"A": 0, "B": 0, "C": 0},
        "open_alerts": 0,
    }

    assert temperature_response.status_code == 200
    assert temperature_response.json() == []

    assert quality_response.status_code == 200
    assert quality_response.json() == []

    assert stage_response.status_code == 200
    assert stage_response.json() == []

    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {
        "overview": overview_response.json(),
        "temperature_trend": [],
        "quality_distribution": [],
        "stage_distribution": [],
        "recent_events": [],
    }


@pytest.mark.asyncio
async def test_dashboard_stats_supports_legacy_schema_without_optional_event_columns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stats-legacy-schema.db"
    _configure_runtime(db_path)
    _ensure_legacy_stats_schema(db_path)

    now = datetime.now(UTC).replace(microsecond=0)
    ts_1 = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    ts_2 = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO managed_devices (device_id, status) VALUES (?, ?)",
            ("device-legacy", "active"),
        )
        connection.execute(
            "INSERT INTO events (version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-legacy",
                "batch-legacy",
                ts_1,
                json.dumps({"temperature_c": 4.0, "humidity_pct": 70.0}),
                json.dumps(
                    {"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}
                ),
                "hash-legacy-1",
            ),
        )
        connection.execute(
            "INSERT INTO events (version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "device-legacy",
                "batch-legacy",
                ts_2,
                json.dumps({"temperature_c": 6.0, "humidity_pct": 68.0}),
                json.dumps(
                    {"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}
                ),
                "hash-legacy-2",
            ),
        )
        event_ids = [
            row[0]
            for row in connection.execute("SELECT id FROM events ORDER BY id ASC")
        ]
        connection.execute(
            "INSERT INTO ingest_requests (idempotency_key, payload_hash, ingest_status, retry_count, event_id) VALUES (?, ?, ?, ?, ?)",
            ("legacy-idem-1", "hash-legacy-1", "RECEIVED", 0, event_ids[0]),
        )
        connection.execute(
            "INSERT INTO ingest_requests (idempotency_key, payload_hash, ingest_status, retry_count, event_id) VALUES (?, ?, ?, ?, ?)",
            ("legacy-idem-2", "hash-legacy-2", "ANCHORED", 0, event_ids[1]),
        )
        connection.execute(
            "INSERT INTO quality_results (event_id, check_name, status, score, details) VALUES (?, ?, ?, ?, ?)",
            (
                event_ids[1],
                "dashboard-quality",
                "PASS",
                88.0,
                json.dumps({"grade": "B"}),
            ),
        )
        connection.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        dashboard_response = await client.get("/v1/stats/dashboard")

    assert dashboard_response.status_code == 200
    payload = dashboard_response.json()
    assert payload["overview"]["total_events"] == 2
    assert payload["overview"]["active_devices"] == 1
    assert payload["stage_distribution"] == [{"stage": "unknown", "count": 2}]
    assert payload["recent_events"] == [
        {
            "id": event_ids[1],
            "batch_id": "batch-legacy",
            "device_id": "device-legacy",
            "timestamp": ts_2,
            "ingest_status": "ANCHORED",
            "supply_chain_stage": None,
            "temperature_c": 6.0,
            "humidity_pct": 68.0,
            "co2_ppm": None,
            "vibration_g": None,
            "quality_grade": "B",
            "anchor_transaction_hash": None,
        },
        {
            "id": event_ids[0],
            "batch_id": "batch-legacy",
            "device_id": "device-legacy",
            "timestamp": ts_1,
            "ingest_status": "RECEIVED",
            "supply_chain_stage": None,
            "temperature_c": 4.0,
            "humidity_pct": 70.0,
            "co2_ppm": None,
            "vibration_g": None,
            "quality_grade": None,
            "anchor_transaction_hash": None,
        },
    ]
