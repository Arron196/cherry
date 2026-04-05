import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.observability.logging import TRACE_ID_HEADER

FRONTEND_ORIGIN = "http://localhost:3000"


def _assert_allow_origin_header(value: str) -> None:
    assert value in {"*", FRONTEND_ORIGIN, "http://localhost:18940"}


@pytest.mark.asyncio
async def test_cors_preflight_options_returns_frontend_headers() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

    assert response.status_code == 200
    _assert_allow_origin_header(response.headers["access-control-allow-origin"])
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "access-control-allow-headers" in response.headers


@pytest.mark.asyncio
async def test_cors_get_with_origin_returns_allow_origin_header() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": FRONTEND_ORIGIN})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    _assert_allow_origin_header(response.headers["access-control-allow-origin"])
    assert TRACE_ID_HEADER in response.headers
