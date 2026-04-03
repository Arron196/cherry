from __future__ import annotations

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


def _ensure_schema(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    Base.metadata.create_all(engine)


def _compat_recent_events_enabled() -> bool:
    paths = app.openapi().get("paths", {})
    return isinstance(paths, dict) and "/v1/events/recent" in paths


def _insert_event_and_ingest(
    db_path: Path,
    *,
    device_id: str,
    batch_id: str,
    timestamp: str,
    ingest_status: str,
    suffix: str,
    sensor_payload: dict[str, float] | None = None,
    co2_ppm: float | None = None,
    vibration_g: float | None = None,
    supply_chain_stage: str | None = None,
    quality_grade: str | None = None,
) -> int:
    payload = sensor_payload or {"temperature_c": 5.0, "humidity_pct": 70.0}
    with sqlite3.connect(db_path) as connection:
        event_cursor = connection.execute(
            "INSERT INTO events ("
            "version, device_id, batch_id, timestamp, sensor_payload, signature_envelope, canonical_hash,"
            "co2_ppm, vibration_g, supply_chain_stage"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                device_id,
                batch_id,
                timestamp,
                json.dumps(payload),
                json.dumps(
                    {"algorithm": "HMAC_SHA256", "key_id": "n/a", "signature": "n/a"}
                ),
                f"hash-{suffix}",
                co2_ppm,
                vibration_g,
                supply_chain_stage,
            ),
        )
        assert event_cursor.lastrowid is not None
        event_id = int(event_cursor.lastrowid)
        connection.execute(
            "INSERT INTO ingest_requests (idempotency_key, payload_hash, ingest_status, retry_count, event_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"idem-{suffix}", f"hash-{suffix}", ingest_status, 0, event_id),
        )
        if quality_grade is not None:
            connection.execute(
                "INSERT INTO quality_results (event_id, check_name, status, score, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    event_id,
                    "recent-quality",
                    quality_grade,
                    95.0,
                    json.dumps({"grade": quality_grade}),
                ),
            )
        connection.commit()
        return event_id


@pytest.mark.asyncio
async def test_batches_query_supports_filters_pagination_and_deterministic_sorting(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-batches.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-a",
        timestamp="2026-02-10 01:00:00",
        ingest_status="RECEIVED",
        suffix="batch-a-1",
    )
    _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-a",
        timestamp="2026-02-10 03:00:00",
        ingest_status="ANCHORED",
        suffix="batch-a-2",
    )
    _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-b",
        timestamp="2026-02-10 02:00:00",
        ingest_status="FAILED_RETRYING",
        suffix="batch-b-1",
    )
    _insert_event_and_ingest(
        db_path,
        device_id="device-2",
        batch_id="batch-c",
        timestamp="2026-02-10 04:00:00",
        ingest_status="RECEIVED",
        suffix="batch-c-1",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/batches")

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 3
        assert payload["limit"] == 50
        assert payload["offset"] == 0
        assert [item["batch_id"] for item in payload["items"]] == [
            "batch-c",
            "batch-a",
            "batch-b",
        ]
        assert payload["items"][1] == {
            "batch_id": "batch-a",
            "device_id": "device-1",
            "event_count": 2,
            "start_time": "2026-02-10T01:00:00Z",
            "end_time": "2026-02-10T03:00:00Z",
        }

        filtered = await client.get("/v1/batches?device_id=device-1")
        assert filtered.status_code == 200
        filtered_payload = filtered.json()
        assert filtered_payload["total"] == 2
        assert [item["batch_id"] for item in filtered_payload["items"]] == [
            "batch-a",
            "batch-b",
        ]

        paged = await client.get("/v1/batches?limit=1&offset=1")
        assert paged.status_code == 200
        paged_payload = paged.json()
        assert paged_payload["total"] == 3
        assert paged_payload["limit"] == 1
        assert paged_payload["offset"] == 1
        assert [item["batch_id"] for item in paged_payload["items"]] == ["batch-a"]

        time_window = await client.get(
            "/v1/batches?start_time=2026-02-10T02:30:00Z&end_time=2026-02-10T04:00:00Z"
        )
        assert time_window.status_code == 200
        time_window_payload = time_window.json()
        assert time_window_payload["total"] == 2
        assert [item["batch_id"] for item in time_window_payload["items"]] == [
            "batch-c",
            "batch-a",
        ]


@pytest.mark.asyncio
async def test_events_query_supports_filters_pagination_and_hides_sensitive_fields(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-events.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    event_a1 = _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-a",
        timestamp="2026-02-10 01:00:00",
        ingest_status="RECEIVED",
        suffix="event-a1",
    )
    event_a2 = _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-a",
        timestamp="2026-02-10 03:00:00",
        ingest_status="ANCHORED",
        suffix="event-a2",
    )
    event_b1 = _insert_event_and_ingest(
        db_path,
        device_id="device-2",
        batch_id="batch-b",
        timestamp="2026-02-10 03:00:00",
        ingest_status="FAILED_RETRYING",
        suffix="event-b1",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/events")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 3
        assert payload["limit"] == 50
        assert payload["offset"] == 0
        assert [item["id"] for item in payload["items"]] == [
            event_b1,
            event_a2,
            event_a1,
        ]

        first = payload["items"][0]
        assert set(first) == {
            "id",
            "batch_id",
            "device_id",
            "timestamp",
            "ingest_status",
        }
        assert {"sensor_payload", "signature_envelope", "canonical_hash"}.isdisjoint(
            first
        )

        filtered = await client.get("/v1/events?batch_id=batch-a&device_id=device-1")
        assert filtered.status_code == 200
        filtered_payload = filtered.json()
        assert filtered_payload["total"] == 2
        assert [item["id"] for item in filtered_payload["items"]] == [
            event_a2,
            event_a1,
        ]

        status_filtered = await client.get("/v1/events?ingest_status=ANCHORED")
        assert status_filtered.status_code == 200
        status_payload = status_filtered.json()
        assert status_payload["total"] == 1
        assert [item["id"] for item in status_payload["items"]] == [event_a2]

        time_window = await client.get(
            "/v1/events?start_time=2026-02-10T02:30:00Z&end_time=2026-02-10T03:00:00Z"
        )
        assert time_window.status_code == 200
        time_payload = time_window.json()
        assert time_payload["total"] == 2
        assert [item["id"] for item in time_payload["items"]] == [event_b1, event_a2]

        paged = await client.get("/v1/events?limit=1&offset=1")
        assert paged.status_code == 200
        paged_payload = paged.json()
        assert paged_payload["total"] == 3
        assert paged_payload["limit"] == 1
        assert paged_payload["offset"] == 1
        assert [item["id"] for item in paged_payload["items"]] == [event_a2]


@pytest.mark.asyncio
async def test_query_list_endpoints_can_exclude_simulation_namespace(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-real-mode.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    real_event_id = _insert_event_and_ingest(
        db_path,
        device_id="device-real-1",
        batch_id="batch-real-1",
        timestamp="2026-02-10 10:00:00",
        ingest_status="ANCHORED",
        suffix="real-mode-event",
    )
    _insert_event_and_ingest(
        db_path,
        device_id="dev-sim-1",
        batch_id="batch-sim-3000",
        timestamp="2026-02-10 11:00:00",
        ingest_status="ANCHORED",
        suffix="sim-mode-event",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        default_batches = await client.get("/v1/batches")
        real_batches = await client.get("/v1/batches?include_simulation=false")
        default_events = await client.get("/v1/events")
        real_events = await client.get("/v1/events?include_simulation=false")
        real_recent = await client.get(
            "/v1/events/recent?limit=10&include_simulation=false"
        )

    assert default_batches.status_code == 200
    assert default_batches.json()["total"] == 2
    assert real_batches.status_code == 200
    real_batches_payload = real_batches.json()
    assert real_batches_payload["total"] == 1
    assert [item["batch_id"] for item in real_batches_payload["items"]] == [
        "batch-real-1"
    ]

    assert default_events.status_code == 200
    assert default_events.json()["total"] == 2
    assert real_events.status_code == 200
    real_events_payload = real_events.json()
    assert real_events_payload["total"] == 1
    assert [item["id"] for item in real_events_payload["items"]] == [real_event_id]

    if _compat_recent_events_enabled():
        assert real_recent.status_code == 200
        assert [item["id"] for item in real_recent.json()] == [real_event_id]


@pytest.mark.asyncio
async def test_recent_events_returns_newest_first_and_matches_events_semantics(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-recent.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    inserted: list[tuple[str, int]] = []
    for index in range(12):
        event_id = _insert_event_and_ingest(
            db_path,
            device_id=f"device-{index % 3}",
            batch_id=f"batch-{index % 4}",
            timestamp=f"2026-02-10 {index:02d}:00:00",
            ingest_status="ANCHORED" if index % 2 == 0 else "RECEIVED",
            suffix=f"recent-{index}",
            sensor_payload={
                "temperature_c": 10.0 + index,
                "humidity_pct": 60.0 + index,
            },
            co2_ppm=400.0 + index,
            vibration_g=0.1 * index,
            supply_chain_stage="transport" if index % 2 == 0 else "storage",
            quality_grade="A" if index == 11 else None,
        )
        inserted.append((f"2026-02-10T{index:02d}:00:00Z", event_id))

    expected_ids = [
        event_id
        for _, event_id in sorted(
            inserted,
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )[:10]
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/events/recent?limit=10")
        events_response = await client.get("/v1/events?limit=10")
        assert events_response.status_code == 200
        events_payload = events_response.json()

        if _compat_recent_events_enabled():
            assert response.status_code == 200
            payload = response.json()

            assert len(payload) == 10
            assert [item["id"] for item in payload] == expected_ids

            required_fields = {
                "id",
                "batch_id",
                "device_id",
                "timestamp",
                "ingest_status",
            }
            optional_fields = {
                "temperature_c",
                "humidity_pct",
                "co2_ppm",
                "vibration_g",
                "supply_chain_stage",
                "quality_grade",
            }
            for item in payload:
                assert required_fields.issubset(item.keys())
                assert optional_fields.issubset(item.keys())

            first = payload[0]
            assert first["temperature_c"] == pytest.approx(21.0)
            assert first["humidity_pct"] == pytest.approx(71.0)
            assert first["co2_ppm"] == pytest.approx(411.0)
            assert first["vibration_g"] == pytest.approx(1.1)
            assert first["quality_grade"] == "A"
            assert [item["id"] for item in payload] == [
                item["id"] for item in events_payload["items"]
            ]
        else:
            assert response.status_code == 404
            assert response.json().get("detail") == "Not Found"
            assert [item["id"] for item in events_payload["items"]] == expected_ids


@pytest.mark.asyncio
async def test_recent_events_returns_empty_array_on_clean_database(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-recent-empty.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/events/recent?limit=10")

    if _compat_recent_events_enabled():
        assert response.status_code == 200
        assert response.json() == []
    else:
        assert response.status_code == 404
        assert response.json().get("detail") == "Not Found"


@pytest.mark.asyncio
async def test_query_endpoints_invalid_params_return_rfc9457_shape(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-invalid.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        invalid_limit = await client.get("/v1/events?limit=0")
        assert invalid_limit.status_code == 422
        invalid_limit_payload = invalid_limit.json()
        assert set(invalid_limit_payload) >= {
            "type",
            "title",
            "status",
            "detail",
            "instance",
        }
        assert invalid_limit_payload["status"] == 422
        assert "errors" in invalid_limit_payload
        assert invalid_limit_payload["instance"] == "/v1/events"

        invalid_range = await client.get(
            "/v1/batches?start_time=2026-02-10T10:00:00Z&end_time=2026-02-10T09:00:00Z"
        )
        assert invalid_range.status_code == 422
        invalid_range_payload = invalid_range.json()
        assert set(invalid_range_payload) >= {
            "type",
            "title",
            "status",
            "detail",
            "instance",
        }
        assert invalid_range_payload["status"] == 422
        assert invalid_range_payload["instance"] == "/v1/batches"


@pytest.mark.asyncio
async def test_events_query_rejects_invalid_ingest_status_filter(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-invalid-status.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/events?ingest_status=NOT_A_STATUS")

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/v1/events"
    assert "errors" in payload


@pytest.mark.asyncio
async def test_batch_sensors_query_returns_canonical_sensor_history(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-batch-sensors.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-sensors",
        timestamp="2026-02-10 01:00:00",
        ingest_status="RECEIVED",
        suffix="batch-sensors-1",
        sensor_payload={"temperature_c": 4.2, "humidity_pct": 71.5},
        co2_ppm=420.0,
        vibration_g=0.02,
        supply_chain_stage="harvest",
    )
    _insert_event_and_ingest(
        db_path,
        device_id="device-1",
        batch_id="batch-sensors",
        timestamp="2026-02-10 02:00:00",
        ingest_status="ANCHORED",
        suffix="batch-sensors-2",
        sensor_payload={"temperature_c": 4.8, "humidity_pct": 69.0},
        supply_chain_stage="storage",
    )
    _insert_event_and_ingest(
        db_path,
        device_id="device-2",
        batch_id="batch-other",
        timestamp="2026-02-10 03:00:00",
        ingest_status="RECEIVED",
        suffix="batch-other-1",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/batches/batch-sensors/sensors")

    assert response.status_code == 200
    payload = response.json()
    required_fields = {"timestamp", "temperature_c", "humidity_pct"}
    for item in payload:
        assert required_fields.issubset(set(item.keys()))

    assert payload == [
        {
            "timestamp": "2026-02-10T01:00:00Z",
            "temperature_c": 4.2,
            "humidity_pct": 71.5,
            "co2_ppm": 420.0,
            "vibration_g": 0.02,
            "supply_chain_stage": "harvest",
        },
        {
            "timestamp": "2026-02-10T02:00:00Z",
            "temperature_c": 4.8,
            "humidity_pct": 69.0,
            "supply_chain_stage": "storage",
        },
    ]

    openapi = app.openapi()
    paths = openapi.get("paths", {})
    assert isinstance(paths, dict)
    assert "/v1/batches/{batch_id}/sensors" in paths

    sensors_schema = (
        paths.get("/v1/batches/{batch_id}/sensors", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    assert sensors_schema.get("type") == "array"
    assert sensors_schema.get("items") == {
        "$ref": "#/components/schemas/SensorPointView"
    }

    components = openapi.get("components", {})
    assert isinstance(components, dict)
    schemas = components.get("schemas", {})
    assert isinstance(schemas, dict)
    sensor_point = schemas.get("SensorPointView", {})
    assert isinstance(sensor_point, dict)
    schema_required = sensor_point.get("required", [])
    assert isinstance(schema_required, list)
    assert required_fields.issubset(set(schema_required))


@pytest.mark.asyncio
async def test_batch_sensors_query_returns_404_for_missing_batch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-batch-sensors-missing.db"
    _configure_runtime(db_path)
    _ensure_schema(db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/batches/batch-not-found/sensors")

    assert response.status_code == 404
    payload = response.json()
    assert payload == {
        "type": "https://example.com/problems/batch-not-found",
        "title": "Not Found",
        "status": 404,
        "detail": "No events found for batch_id 'batch-not-found'.",
        "instance": "/v1/batches/batch-not-found/sensors",
    }
