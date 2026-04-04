from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.compat_exit import (
    CompatExitCriteriaConfig,
    CompatTrafficSample,
    evaluate_compat_closure_decision,
    evaluate_compat_exit_criteria,
)


def _configure_runtime(db_path: Path) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["COMPAT_TELEMETRY_SIGNATURE_MODE"] = "observe"
    os.environ["COMPAT_CLOSURE_ENABLED"] = os.getenv("COMPAT_CLOSURE_ENABLED", "0")


def _compat_expect_routes_disabled() -> bool:
    raw = os.getenv("COMPAT_EXPECT_ROUTES_DISABLED", "0").strip()
    if raw not in {"0", "1"}:
        raise AssertionError("COMPAT_EXPECT_ROUTES_DISABLED must be '0' or '1'")
    return raw == "1"


def _assert_compat_route_expectations() -> bool:
    paths = app.openapi().get("paths", {})
    assert isinstance(paths, dict)
    expect_routes_disabled = _compat_expect_routes_disabled()
    expected_present = not expect_routes_disabled
    for route in (
        "/api/cherry/telemetry",
        "/v1/events/recent",
        "/v1/trace/{batch_id}/public",
    ):
        actual_present = route in paths
        assert actual_present is expected_present, (
            f"Compat route expectation mismatch for {route}: "
            f"COMPAT_EXPECT_ROUTES_DISABLED={int(expect_routes_disabled)} but route is "
            f"{'present' if actual_present else 'absent'} in OpenAPI"
        )
    return expect_routes_disabled


def _extract_compat_metric(
    metrics_text: str,
    *,
    endpoint: str,
    method: str,
    status: int,
) -> float:
    labels = f'endpoint="{endpoint}",method="{method}",status="{status}"'
    pattern = re.compile(
        rf"^traceability_compat_requests_total\{{{re.escape(labels)}\}}\s+([0-9]+(?:\.[0-9]+)?)$",
        re.MULTILINE,
    )
    match = pattern.search(metrics_text)
    if match is None:
        return 0.0
    return float(match.group(1))


def _event_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.asyncio
async def test_compat_endpoints_emit_deprecation_headers_and_endpoint_metrics(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compat-deprecation-metrics.db"
    _configure_runtime(db_path)

    compat_payload: dict[str, Any] = {
        "seq": 77,
        "ts": 1770688800,
        "temp_c": 4.1,
        "hum_rh": 71.2,
        "co2": 418.0,
        "vibration": False,
        "digest": "a1" * 32,
        "signature": "00" * 64,
        "device_id": "compat-metrics-device",
        "batch_id": "compat-metrics-batch",
        "stage": "transport",
        "key_id": "compat-metrics-key",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        baseline_metrics = await client.get("/metrics")
        assert baseline_metrics.status_code == 200

        before_recent = _extract_compat_metric(
            baseline_metrics.text,
            endpoint="/v1/events/recent",
            method="GET",
            status=200,
        )
        before_telemetry = _extract_compat_metric(
            baseline_metrics.text,
            endpoint="/api/cherry/telemetry",
            method="POST",
            status=202,
        )
        before_public_alias_404 = _extract_compat_metric(
            baseline_metrics.text,
            endpoint="/v1/trace/{batch_id}/public",
            method="GET",
            status=404,
        )

        recent_response = await client.get("/v1/events/recent?limit=5")
        public_alias_response = await client.get("/v1/trace/batch-not-found/public")
        telemetry_response = await client.post(
            "/api/cherry/telemetry",
            headers={"Idempotency-Key": "compat-metrics-idem"},
            json=compat_payload,
        )
        current_metrics = await client.get("/metrics")

    assert current_metrics.status_code == 200
    expect_routes_disabled = _assert_compat_route_expectations()
    if expect_routes_disabled:
        assert recent_response.status_code == 404
        assert public_alias_response.status_code == 404
        assert telemetry_response.status_code == 404
        assert recent_response.json() == {"detail": "Not Found"}
        assert public_alias_response.json() == {"detail": "Not Found"}
        assert telemetry_response.json() == {"detail": "Not Found"}

        for response in (recent_response, public_alias_response, telemetry_response):
            assert response.headers.get("x-compat-deprecated") is None
            assert response.headers.get("x-compat-replacement") is None

        assert (
            _extract_compat_metric(
                current_metrics.text,
                endpoint="/v1/events/recent",
                method="GET",
                status=200,
            )
            == before_recent
        )
        assert (
            _extract_compat_metric(
                current_metrics.text,
                endpoint="/api/cherry/telemetry",
                method="POST",
                status=202,
            )
            == before_telemetry
        )
        assert (
            _extract_compat_metric(
                current_metrics.text,
                endpoint="/v1/trace/{batch_id}/public",
                method="GET",
                status=404,
            )
            == before_public_alias_404
        )
    else:
        assert recent_response.status_code == 200
        assert public_alias_response.status_code == 404
        assert telemetry_response.status_code == 202
        assert _event_count(db_path) == 1

        expected_headers = {
            "deprecation": "true",
            "sunset": "Wed, 30 Sep 2026 00:00:00 GMT",
            "link": '<https://example.com/runbooks/compatibility-closure>; rel="deprecation"; type="text/markdown"',
            "x-compat-deprecated": "true",
            "x-compat-exit-criteria": "2-releases,14-consecutive-days,<1%-traffic",
        }
        for header_name, header_value in expected_headers.items():
            assert recent_response.headers.get(header_name) == header_value
            assert public_alias_response.headers.get(header_name) == header_value
            assert telemetry_response.headers.get(header_name) == header_value

        assert recent_response.headers.get("x-compat-replacement") == "GET /v1/events"
        assert (
            public_alias_response.headers.get("x-compat-replacement")
            == "GET /v1/public/trace/{batch_id}"
        )
        assert (
            telemetry_response.headers.get("x-compat-replacement") == "POST /v1/events"
        )

        assert (
            _extract_compat_metric(
                current_metrics.text,
                endpoint="/v1/events/recent",
                method="GET",
                status=200,
            )
            >= before_recent + 1
        )
        assert (
            _extract_compat_metric(
                current_metrics.text,
                endpoint="/api/cherry/telemetry",
                method="POST",
                status=202,
            )
            >= before_telemetry + 1
        )
        assert (
            _extract_compat_metric(
                current_metrics.text,
                endpoint="/v1/trace/{batch_id}/public",
                method="GET",
                status=404,
            )
            >= before_public_alias_404 + 1
        )


def _samples_for_range(
    *, start_day: date, days: int, ratio: float = 0.005
) -> list[CompatTrafficSample]:
    return [
        CompatTrafficSample(
            day=start_day + timedelta(days=index),
            compat_requests=1,
            total_requests=200,
            compat_ratio=ratio,
        )
        for index in range(days)
    ]


def test_compat_exit_criteria_requires_releases_and_consecutive_day_streak() -> None:
    config = CompatExitCriteriaConfig(
        required_releases=2,
        required_consecutive_days=14,
        max_compat_ratio=0.01,
    )
    samples = _samples_for_range(start_day=date(2026, 2, 1), days=14, ratio=0.009)

    passed = evaluate_compat_exit_criteria(
        releases_observed=2,
        samples=samples,
        config=config,
    )
    assert passed.criteria_passed is True
    assert passed.trailing_streak_days == 14

    release_failed = evaluate_compat_exit_criteria(
        releases_observed=1,
        samples=samples,
        config=config,
    )
    assert release_failed.criteria_passed is False
    assert any(
        reason.startswith("releases_below_threshold")
        for reason in release_failed.reasons
    )

    gapped_samples = samples[:7] + samples[8:]
    streak_failed = evaluate_compat_exit_criteria(
        releases_observed=2,
        samples=gapped_samples,
        config=config,
    )
    assert streak_failed.criteria_passed is False
    assert streak_failed.trailing_streak_days < 14


def test_compat_closure_decision_is_traffic_gated(monkeypatch, tmp_path: Path) -> None:
    history_path = tmp_path / "compat-history.json"

    passing_history = {
        "releases_observed": 2,
        "daily": [
            {
                "date": (date(2026, 2, 1) + timedelta(days=index)).isoformat(),
                "total_requests": 1000,
                "compat_requests": 5,
            }
            for index in range(14)
        ],
    }
    history_path.write_text(json.dumps(passing_history), encoding="utf-8")

    monkeypatch.setenv("COMPAT_CLOSURE_ENABLED", "1")
    monkeypatch.setenv("COMPAT_EXIT_HISTORY_PATH", str(history_path))
    decision_pass = evaluate_compat_closure_decision()
    assert decision_pass.closure_requested is True
    assert decision_pass.include_compat_router is False
    assert decision_pass.evaluation is not None
    assert decision_pass.evaluation.criteria_passed is True

    failing_history = {
        "releases_observed": 1,
        "daily": [
            {
                "date": (date(2026, 2, 1) + timedelta(days=index)).isoformat(),
                "total_requests": 1000,
                "compat_requests": 20,
            }
            for index in range(5)
        ],
    }
    history_path.write_text(json.dumps(failing_history), encoding="utf-8")

    decision_fail = evaluate_compat_closure_decision()
    assert decision_fail.closure_requested is True
    assert decision_fail.include_compat_router is True
    assert decision_fail.evaluation is not None
    assert decision_fail.evaluation.criteria_passed is False
    assert len(decision_fail.evaluation.reasons) >= 1
