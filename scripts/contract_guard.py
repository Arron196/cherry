from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app


def _collect_parameters(
    operation: dict[str, object], location: str
) -> dict[str, dict[str, object]]:
    parameters: dict[str, dict[str, object]] = {}
    operation_parameters = operation.get("parameters")
    if not isinstance(operation_parameters, list):
        return parameters

    for item in operation_parameters:
        if not isinstance(item, dict):
            continue
        if item.get("in") != location:
            continue
        name = item.get("name")
        if isinstance(name, str):
            parameters[name] = item
    return parameters


def _is_required_parameter(parameters: dict[str, dict[str, object]], name: str) -> bool:
    parameter = parameters.get(name)
    if parameter is None:
        return False
    return bool(parameter.get("required"))


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "y", "on"}


def _require_compat_routes() -> bool:
    raw_override = os.getenv("CONTRACT_GUARD_REQUIRE_COMPAT_ROUTES")
    if raw_override is not None:
        return _bool_env("CONTRACT_GUARD_REQUIRE_COMPAT_ROUTES", True)
    return not _bool_env("COMPAT_CLOSURE_ENABLED", False)


def _load_openapi() -> dict[str, object]:
    override_path = os.getenv("CONTRACT_GUARD_OPENAPI_OVERRIDE")
    if not override_path:
        return app.openapi()

    payload = json.loads(Path(override_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CONTRACT_GUARD_OPENAPI_OVERRIDE must point to a JSON object")
    return payload


def _resolve_schema(
    openapi: dict[str, object], schema: dict[str, object]
) -> dict[str, object] | None:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema

    prefix = "#/components/schemas/"
    if not ref.startswith(prefix):
        return None

    schema_name = ref[len(prefix) :]
    components = openapi.get("components")
    if not isinstance(components, dict):
        return None
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return None
    target = schemas.get(schema_name)
    if isinstance(target, dict):
        return target
    return None


def _operation_response_schema(
    operation: dict[str, object],
    *,
    statuses: tuple[str, ...],
) -> dict[str, object] | None:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return None

    for status in statuses:
        candidate = responses.get(status)
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        application_json = content.get("application/json")
        if not isinstance(application_json, dict):
            continue
        schema = application_json.get("schema")
        if isinstance(schema, dict):
            return schema
    return None


def _required_field_set(schema: dict[str, object]) -> set[str]:
    required = schema.get("required")
    if not isinstance(required, list):
        return set()
    return {name for name in required if isinstance(name, str)}


def _assert_required_fields(
    failures: list[str],
    *,
    schema_name: str,
    schema: dict[str, object] | None,
    required_fields: tuple[str, ...],
) -> None:
    if schema is None:
        failures.append(f"Missing required schema: {schema_name}")
        return
    schema_required_fields = _required_field_set(schema)
    for field in required_fields:
        if field not in schema_required_fields:
            failures.append(f"{schema_name} schema must require `{field}`")


def main() -> int:
    openapi = _load_openapi()
    failures: list[str] = []

    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        failures.append("OpenAPI missing top-level `paths` map")
        paths = {}

    required_operations: dict[str, tuple[str, ...]] = {
        "/health": ("get",),
        "/contracts/trace-events/validate": ("post",),
        "/v1/events": ("post", "get"),
        "/v1/batches": ("get",),
        "/v1/batches/{batch_id}/sensors": ("get",),
        "/v1/trace/{batch_id}": ("get",),
        "/v1/public/trace/{batch_id}": ("get",),
        "/v1/stats/overview": ("get",),
        "/v1/stats/temperature-trend": ("get",),
        "/v1/stats/quality-distribution": ("get",),
        "/v1/stats/stage-distribution": ("get",),
    }
    if _require_compat_routes():
        required_operations.update(
            {
                "/v1/events/recent": ("get",),
                "/v1/trace/{batch_id}/public": ("get",),
                "/api/cherry/telemetry": ("post",),
            }
        )

    for route, methods in required_operations.items():
        route_item = paths.get(route)
        if not isinstance(route_item, dict):
            failures.append(f"Missing required path: {route}")
            continue
        for method in methods:
            if method not in route_item:
                failures.append(f"Missing required operation: {method.upper()} {route}")

    events_path = paths.get("/v1/events")
    if isinstance(events_path, dict):
        post_operation = events_path.get("post")
        if isinstance(post_operation, dict):
            header_parameters = _collect_parameters(post_operation, "header")
            if not _is_required_parameter(header_parameters, "Idempotency-Key"):
                failures.append("POST /v1/events must require header `Idempotency-Key`")

            request_body = post_operation.get("requestBody")
            if not isinstance(request_body, dict):
                failures.append("POST /v1/events missing requestBody")
            else:
                if request_body.get("required") is not True:
                    failures.append("POST /v1/events requestBody must be required")
                content = request_body.get("content")
                if not isinstance(content, dict) or "application/json" not in content:
                    failures.append(
                        "POST /v1/events requestBody must include application/json"
                    )
        else:
            failures.append("Missing required operation: POST /v1/events")

        get_operation = events_path.get("get")
        if isinstance(get_operation, dict):
            query_parameters = _collect_parameters(get_operation, "query")
            required_query_parameters = (
                "limit",
                "offset",
                "batch_id",
                "device_id",
                "ingest_status",
                "start_time",
                "end_time",
            )
            for query_name in required_query_parameters:
                if query_name not in query_parameters:
                    failures.append(
                        f"GET /v1/events missing query parameter `{query_name}`"
                    )
        else:
            failures.append("Missing required operation: GET /v1/events")

    components = openapi.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    trace_event = schemas.get("TraceEvent") if isinstance(schemas, dict) else None
    if not isinstance(trace_event, dict):
        failures.append("Missing required schema: TraceEvent")
    else:
        required_fields = trace_event.get("required")
        required_field_set = (
            set(required_fields) if isinstance(required_fields, list) else set()
        )
        for field in (
            "version",
            "device_id",
            "batch_id",
            "timestamp",
            "sensor_payload",
            "signature_envelope",
        ):
            if field not in required_field_set:
                failures.append(f"TraceEvent schema must require `{field}`")

    recent_path = paths.get("/v1/events/recent")
    if isinstance(recent_path, dict):
        recent_get = recent_path.get("get")
        if isinstance(recent_get, dict):
            recent_schema_ref = _operation_response_schema(
                recent_get, statuses=("200",)
            )
            if not isinstance(recent_schema_ref, dict):
                failures.append(
                    "GET /v1/events/recent missing 200 application/json schema"
                )
            else:
                if recent_schema_ref.get("type") != "array":
                    failures.append(
                        "GET /v1/events/recent response schema must be an array"
                    )
                recent_items = recent_schema_ref.get("items")
                resolved_recent_item = (
                    _resolve_schema(openapi, recent_items)
                    if isinstance(recent_items, dict)
                    else None
                )
                _assert_required_fields(
                    failures,
                    schema_name="RecentEventView",
                    schema=resolved_recent_item,
                    required_fields=(
                        "id",
                        "batch_id",
                        "device_id",
                        "timestamp",
                        "ingest_status",
                    ),
                )

    telemetry_path = paths.get("/api/cherry/telemetry")
    if isinstance(telemetry_path, dict):
        telemetry_post = telemetry_path.get("post")
        if isinstance(telemetry_post, dict):
            telemetry_schema_ref = _operation_response_schema(
                telemetry_post,
                statuses=("202", "200"),
            )
            resolved_telemetry_schema = (
                _resolve_schema(openapi, telemetry_schema_ref)
                if isinstance(telemetry_schema_ref, dict)
                else None
            )
            _assert_required_fields(
                failures,
                schema_name="CherryTelemetryResponse",
                schema=resolved_telemetry_schema,
                required_fields=("accepted", "event_id", "ingest_status"),
            )

    public_trace_routes = (
        "/v1/public/trace/{batch_id}",
        "/v1/trace/{batch_id}/public",
    )
    for route in public_trace_routes:
        route_item = paths.get(route)
        if not isinstance(route_item, dict):
            continue
        route_get = route_item.get("get")
        if not isinstance(route_get, dict):
            continue
        route_schema_ref = _operation_response_schema(route_get, statuses=("200",))
        resolved_route_schema = (
            _resolve_schema(openapi, route_schema_ref)
            if isinstance(route_schema_ref, dict)
            else None
        )
        _assert_required_fields(
            failures,
            schema_name=f"PublicTraceResponse ({route})",
            schema=resolved_route_schema,
            required_fields=(
                "batch_info",
                "timeline",
                "stage_environments",
                "quality",
                "blockchain_anchor",
            ),
        )

    sensors_path = paths.get("/v1/batches/{batch_id}/sensors")
    if isinstance(sensors_path, dict):
        sensors_get = sensors_path.get("get")
        if isinstance(sensors_get, dict):
            sensors_schema_ref = _operation_response_schema(
                sensors_get, statuses=("200",)
            )
            if not isinstance(sensors_schema_ref, dict):
                failures.append(
                    "GET /v1/batches/{batch_id}/sensors missing 200 application/json schema"
                )
            else:
                if sensors_schema_ref.get("type") != "array":
                    failures.append(
                        "GET /v1/batches/{batch_id}/sensors response schema must be an array"
                    )
                sensor_items = sensors_schema_ref.get("items")
                resolved_sensor_item = (
                    _resolve_schema(openapi, sensor_items)
                    if isinstance(sensor_items, dict)
                    else None
                )
                _assert_required_fields(
                    failures,
                    schema_name="SensorPointView",
                    schema=resolved_sensor_item,
                    required_fields=("timestamp", "temperature_c", "humidity_pct"),
                )

    stats_expected_array_shapes: dict[str, tuple[str, ...]] = {
        "/v1/stats/temperature-trend": (
            "timestamp",
            "avg_temperature",
            "min_temperature",
            "max_temperature",
        ),
        "/v1/stats/quality-distribution": ("grade", "count", "percentage"),
        "/v1/stats/stage-distribution": ("stage", "count"),
    }
    for route, required_fields in stats_expected_array_shapes.items():
        route_item = paths.get(route)
        if not isinstance(route_item, dict):
            continue
        route_get = route_item.get("get")
        if not isinstance(route_get, dict):
            continue
        route_schema_ref = _operation_response_schema(route_get, statuses=("200",))
        if not isinstance(route_schema_ref, dict):
            failures.append(f"GET {route} missing 200 application/json schema")
            continue
        if route_schema_ref.get("type") != "array":
            failures.append(f"GET {route} response schema must be an array")
            continue
        schema_items = route_schema_ref.get("items")
        resolved_schema_items = (
            _resolve_schema(openapi, schema_items)
            if isinstance(schema_items, dict)
            else None
        )
        _assert_required_fields(
            failures,
            schema_name=f"{route} item",
            schema=resolved_schema_items,
            required_fields=required_fields,
        )

    overview_path = paths.get("/v1/stats/overview")
    if isinstance(overview_path, dict):
        overview_get = overview_path.get("get")
        if isinstance(overview_get, dict):
            overview_schema_ref = _operation_response_schema(
                overview_get, statuses=("200",)
            )
            resolved_overview_schema = (
                _resolve_schema(openapi, overview_schema_ref)
                if isinstance(overview_schema_ref, dict)
                else None
            )
            _assert_required_fields(
                failures,
                schema_name="OverviewResponse",
                schema=resolved_overview_schema,
                required_fields=(
                    "total_batches",
                    "total_events",
                    "active_devices",
                    "avg_quality_score",
                    "grade_distribution",
                    "open_alerts",
                ),
            )

    if failures:
        print(
            "CONTRACT_GUARD_RESULT",
            json.dumps({"status": "FAIL", "count": len(failures)}),
        )
        for issue in failures:
            print(f"- {issue}")
        return 1

    print(
        "CONTRACT_GUARD_RESULT",
        json.dumps({"status": "PASS", "checked": "openapi+migration_surface"}),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
