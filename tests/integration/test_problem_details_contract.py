import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_trace_event_contract_validate_success_returns_canonical_hash() -> None:
    payload = {
        "version": "1.0.0",
        "device_id": "device-001",
        "batch_id": "batch-001",
        "timestamp": "2026-02-10T03:00:00Z",
        "sensor_payload": {
            "temperature_c": 4.2,
            "humidity_pct": 71.5,
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "placeholder-signature",
            "key_id": "factory-key-1",
        },
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/contracts/trace-events/validate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert isinstance(body["canonical_hash"], str)
    assert len(body["canonical_hash"]) == 64


@pytest.mark.asyncio
async def test_invalid_trace_event_payload_returns_rfc9457_shape() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/contracts/trace-events/validate",
            json={"version": "1.0.0", "device_id": "device-001"},
        )

    assert response.status_code == 422
    payload = response.json()
    assert set(payload) >= {"type", "title", "status", "detail", "instance"}
    assert payload["status"] == 422
    assert "errors" in payload
    assert payload["instance"] == "/contracts/trace-events/validate"
