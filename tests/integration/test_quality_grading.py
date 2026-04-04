from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_quality_grade_returns_a_with_context_and_reasons() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/quality/grade",
            json={
                "temperature_c": 5.0,
                "humidity_pct": 72.0,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grade"] == "A"
    assert payload["score"] == 4
    assert payload["max_score"] == 4
    assert len(payload["reasons"]) >= 2
    assert set(payload["threshold_context"]) >= {
        "temperature_c",
        "humidity_pct",
        "grade_thresholds",
    }


@pytest.mark.asyncio
async def test_quality_grade_returns_b_for_warning_band() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/quality/grade",
            json={
                "temperature_c": 9.5,
                "humidity_pct": 73.0,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grade"] == "B"
    assert payload["score"] == 3
    assert any("warning" in reason.lower() for reason in payload["reasons"])


@pytest.mark.asyncio
async def test_quality_grade_returns_c_for_failed_band() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/quality/grade",
            json={
                "temperature_c": -10.0,
                "humidity_pct": 95.0,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grade"] == "C"
    assert payload["score"] == 0
    assert any("outside" in reason.lower() for reason in payload["reasons"])


@pytest.mark.asyncio
async def test_quality_grade_rejects_invalid_humidity_range() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/quality/grade",
            json={
                "temperature_c": 5.0,
                "humidity_pct": 101.0,
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == 422
    assert payload["instance"] == "/v1/quality/grade"
