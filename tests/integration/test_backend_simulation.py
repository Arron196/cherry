from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import app
from app.domain.persistence.models import Alert, Event, ManagedDevice, QualityResult
from app.services.db_runtime import get_engine
from app.services.simulation import run_simulation_tick, stop_simulation_generator


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["ANCHOR_ADAPTER"] = "active_mock"
    os.environ["ANCHOR_MOCK_MODE"] = "success"
    os.environ["ANCHOR_MAX_RETRIES"] = "3"
    os.environ["AUTH_JWT_SECRET"] = "simulation-test-secret"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_jwt(*, subject: str, roles: list[str]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "iss": "traceability-auth", "roles": roles}
    encoded_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        b"simulation-test-secret", signing_input, hashlib.sha256
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url(signature)}"


async def test_simulation_batch_uses_backend_business_pipeline(tmp_path: Path) -> None:
    _configure_runtime(tmp_path / "simulation.db")
    token = _mint_jwt(subject="admin", roles=["admin"])
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        seed_response = await client.post(
            "/v1/simulation/batches/batch-sim-1000",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert seed_response.status_code == 200
        seed_payload = seed_response.json()
        assert seed_payload["total_events"] == 8
        assert seed_payload["anchored_events"] == 8

        trace_response = await client.get("/v1/trace/batch-sim-1000")
        assert trace_response.status_code == 200
        trace_payload = trace_response.json()
        assert len(trace_payload["timeline"]) == 8
        assert all(
            event["ingest_status"] == "ANCHORED"
            for event in trace_payload["timeline"]
        )
        assert all(event["quality_grade"] for event in trace_payload["timeline"])

        hashes = [
            event["anchor"]["transaction_hash"]
            for event in trace_payload["timeline"]
        ]
        assert all(
            isinstance(tx_hash, str)
            and tx_hash.startswith("0x")
            and len(tx_hash) == 66
            for tx_hash in hashes
        )
        assert all(not tx_hash.endswith("0" * 48) for tx_hash in hashes)

        public_response = await client.get("/v1/public/trace/batch-sim-1000")
        assert public_response.status_code == 200
        public_payload = public_response.json()
        assert public_payload["blockchain_anchor"]["anchored_count"] == 8
        assert public_payload["blockchain_anchor"]["latest_transaction_hash"] in hashes


async def test_simulation_trace_endpoint_self_seeds_without_frontend_mock(tmp_path: Path) -> None:
    _configure_runtime(tmp_path / "simulation-self-seed.db")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        trace_response = await client.get("/v1/trace/batch-sim-1002")
        assert trace_response.status_code == 200
        trace_payload = trace_response.json()
        assert len(trace_payload["timeline"]) == 8
        assert all(
            event["anchor"]["transaction_hash"].startswith("0x")
            and len(event["anchor"]["transaction_hash"]) == 66
            for event in trace_payload["timeline"]
        )


async def test_simulation_generator_tick_uses_backend_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "simulation-generator-tick.db"
    _configure_runtime(db_path)
    token = _mint_jwt(subject="regulator", roles=["regulator"])
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick_response = await client.post(
            "/v1/simulation/generator/tick",
            headers={"Authorization": f"Bearer {token}"},
            json={"batches_per_tick": 8},
        )

        assert tick_response.status_code == 200
        tick_payload = tick_response.json()
        assert tick_payload["generated_events"] == 8
        assert tick_payload["processed_anchoring"] >= 8
        assert len(tick_payload["active_batches"]) == 8

        stats_response = await client.get("/v1/stats/dashboard")

    assert stats_response.status_code == 200
    dashboard_payload = stats_response.json()
    event_items = dashboard_payload["recent_events"]
    generated_items = [
        item for item in event_items if item["batch_id"].startswith("batch-sim-")
    ]
    assert len(generated_items) == 8
    assert {item["supply_chain_stage"] for item in generated_items} >= {
        "harvest",
        "storage",
        "transport",
    }
    assert all(item["ingest_status"] == "ANCHORED" for item in generated_items)
    assert all(item["quality_grade"] for item in generated_items)
    assert all(
        isinstance(item["anchor_transaction_hash"], str)
        and item["anchor_transaction_hash"].startswith("0x")
        and len(item["anchor_transaction_hash"]) == 66
        for item in generated_items
    )

    assert dashboard_payload["overview"]["total_events"] == 8
    assert dashboard_payload["overview"]["active_devices"] >= 3
    assert len(dashboard_payload["recent_events"]) == 8

    engine = get_engine(f"sqlite:///{db_path.as_posix()}")
    with Session(engine) as session:
        quality_count = int(
            session.scalar(select(func.count()).select_from(QualityResult)) or 0
        )
        anchored_count = int(
            session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.batch_id.like("batch-sim-%"))
            )
            or 0
        )
        alert_count = int(
            session.scalar(select(func.count()).select_from(Alert)) or 0
        )
    assert quality_count == 8
    assert anchored_count == 8
    assert alert_count >= tick_payload["alerts_created"]


async def test_simulation_generator_ticks_grow_batches_and_active_devices(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "simulation-generator-growth.db"
    _configure_runtime(db_path)

    first_tick = run_simulation_tick(batches_per_tick=8)
    engine = get_engine(f"sqlite:///{db_path.as_posix()}")
    with Session(engine) as session:
        first_total_batches = int(
            session.scalar(
                select(func.count(func.distinct(Event.batch_id))).select_from(Event)
            )
            or 0
        )
        first_active_sim_devices = int(
            session.scalar(
                select(func.count())
                .select_from(ManagedDevice)
                .where(
                    ManagedDevice.device_id.like("dev-sim-%"),
                    ManagedDevice.status == "active",
                )
            )
            or 0
        )

    second_tick = run_simulation_tick(batches_per_tick=8)
    assert first_tick.generated_events == 8
    assert second_tick.generated_events == 8

    with Session(engine) as session:
        total_batches = int(
            session.scalar(
                select(func.count(func.distinct(Event.batch_id))).select_from(Event)
            )
            or 0
        )
        active_sim_devices = int(
            session.scalar(
                select(func.count())
                .select_from(ManagedDevice)
                .where(
                    ManagedDevice.device_id.like("dev-sim-%"),
                    ManagedDevice.status == "active",
                )
            )
            or 0
        )

    assert first_total_batches == 8
    assert total_batches == 16
    assert active_sim_devices > first_active_sim_devices


async def test_simulation_generator_start_status_and_stop(tmp_path: Path) -> None:
    _configure_runtime(tmp_path / "simulation-generator.db")
    stop_simulation_generator()
    token = _mint_jwt(subject="admin", roles=["admin"])
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_response = await client.post(
            "/v1/simulation/generator/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"interval_seconds": 60, "batches_per_tick": 3},
        )
        status_response = await client.get(
            "/v1/simulation/generator",
            headers={"Authorization": f"Bearer {token}"},
        )
        stop_response = await client.post(
            "/v1/simulation/generator/stop",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["running"] is True
    assert start_payload["interval_seconds"] == 60
    assert start_payload["batches_per_tick"] == 3
    assert start_payload["generated_events"] >= 3
    assert start_payload["last_tick_at"] is not None

    assert status_response.status_code == 200
    assert status_response.json()["running"] is True

    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False


async def test_simulation_device_detail_self_seeds_from_backend(tmp_path: Path) -> None:
    _configure_runtime(tmp_path / "simulation-device-detail.db")
    token = _mint_jwt(subject="admin", roles=["admin"])
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail_response = await client.get(
            "/admin/devices/dev-sim-2",
            headers={"Authorization": f"Bearer {token}"},
        )
        keys_response = await client.get(
            "/admin/devices/dev-sim-2/keys",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["device_id"] == "dev-sim-2"
    assert detail_payload["status"] == "active"
    assert detail_payload["active_key"]["key_id"] == "dev-sim-2-key-active"

    assert keys_response.status_code == 200
    keys_payload = keys_response.json()
    assert keys_payload["device_id"] == "dev-sim-2"
    assert keys_payload["items"] == [
        {
            "key_id": "dev-sim-2-key-active",
            "algorithm": "HMAC_SHA256",
            "status": "active",
            "activated_at": detail_payload["active_key"]["activated_at"],
            "retired_at": None,
        }
    ]
