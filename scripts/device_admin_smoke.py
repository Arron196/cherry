from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from typing import Any

import httpx


def _timestamp_suffix() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")


def _print_result(payload: dict[str, Any]) -> None:
    print(f"DEVICE_ADMIN_SMOKE_RESULT {json.dumps(payload, ensure_ascii=False, sort_keys=True)}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _request_json(
    *,
    client: httpx.Client,
    method: str,
    url: str,
    trace_id: str,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    headers: dict[str, str] = {
        "X-Trace-Id": trace_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = client.request(method=method, url=url, headers=headers, json=json_body)
    payload = response.json() if response.content else {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    return response.status_code, payload


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    device_id = args.device_id or f"smoke-device-{_timestamp_suffix()}"
    initial_key_id = args.initial_key_id or f"{device_id}-key-v1"
    rotate_key_id = args.rotate_key_id or f"{device_id}-key-v2"
    trace_id = args.trace_id or f"device-admin-smoke-{device_id}"

    with httpx.Client(base_url=args.base_url, timeout=args.timeout_seconds) as client:
        login_status, login_payload = _request_json(
            client=client,
            method="POST",
            url="/v1/auth/login",
            trace_id=trace_id,
            json_body={"username": args.username, "password": args.password},
        )
        _require(login_status == 200, f"login failed status={login_status} payload={login_payload}")
        token = str(login_payload.get("access_token") or "")
        _require(token != "", "login response missing access_token")

        register_status, register_payload = _request_json(
            client=client,
            method="POST",
            url="/admin/devices",
            trace_id=trace_id,
            token=token,
            json_body={
                "device_id": device_id,
                "display_name": f"Smoke Device {device_id}",
                "initial_key": {
                    "key_id": initial_key_id,
                    "algorithm": args.initial_key_algorithm,
                    "secret": args.initial_key_secret,
                },
            },
        )
        _require(
            register_status == 201,
            f"register failed status={register_status} payload={register_payload}",
        )
        _require(register_payload.get("device_id") == device_id, "register response device_id mismatch")

        detail_status, detail_payload = _request_json(
            client=client,
            method="GET",
            url=f"/admin/devices/{device_id}",
            trace_id=trace_id,
            token=token,
        )
        _require(detail_status == 200, f"detail failed status={detail_status} payload={detail_payload}")
        _require(detail_payload.get("device_id") == device_id, "detail response device_id mismatch")

        audits_before_status, audits_before_payload = _request_json(
            client=client,
            method="GET",
            url=f"/admin/devices/{device_id}/audits",
            trace_id=trace_id,
            token=token,
        )
        _require(
            audits_before_status == 200,
            f"audits(before) failed status={audits_before_status} payload={audits_before_payload}",
        )
        audits_before_items = audits_before_payload.get("items")
        _require(isinstance(audits_before_items, list), "audits(before) missing items[]")

        rotate_status, rotate_payload = _request_json(
            client=client,
            method="POST",
            url=f"/admin/devices/{device_id}/keys",
            trace_id=trace_id,
            token=token,
            json_body={
                "key_id": rotate_key_id,
                "algorithm": args.rotate_key_algorithm,
                "public_key": args.rotate_public_key,
            },
        )
        _require(
            rotate_status == 201,
            f"rotate failed status={rotate_status} payload={rotate_payload}",
        )
        _require(rotate_payload.get("key_id") == rotate_key_id, "rotate response key_id mismatch")

        disable_status, disable_payload = _request_json(
            client=client,
            method="POST",
            url=f"/admin/devices/{device_id}/disable",
            trace_id=trace_id,
            token=token,
            json_body={"reason": args.disable_reason},
        )
        _require(
            disable_status == 200,
            f"disable failed status={disable_status} payload={disable_payload}",
        )
        _require(disable_payload.get("status") == "disabled", "disable response status mismatch")

        audits_after_status, audits_after_payload = _request_json(
            client=client,
            method="GET",
            url=f"/admin/devices/{device_id}/audits",
            trace_id=trace_id,
            token=token,
        )
        _require(
            audits_after_status == 200,
            f"audits(after) failed status={audits_after_status} payload={audits_after_payload}",
        )
        audits_after_items = audits_after_payload.get("items")
        _require(isinstance(audits_after_items, list), "audits(after) missing items[]")

        actions = [str(item.get("action")) for item in audits_after_items if isinstance(item, dict)]
        _require("admin.device.register" in actions, "audits missing admin.device.register")
        _require("admin.device.key.rotate" in actions, "audits missing admin.device.key.rotate")
        _require("admin.device.disable" in actions, "audits missing admin.device.disable")

    return {
        "status": "PASS",
        "base_url": args.base_url,
        "device_id": device_id,
        "initial_key_id": initial_key_id,
        "rotate_key_id": rotate_key_id,
        "audits_before_count": len(audits_before_items),
        "audits_after_count": len(audits_after_items),
        "trace_id": trace_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Device admin smoke test against running backend")
    parser.add_argument("--base-url", default="http://localhost:18941")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--device-id", default=None)
    parser.add_argument("--initial-key-id", default=None)
    parser.add_argument("--initial-key-algorithm", default="HMAC_SHA256")
    parser.add_argument("--initial-key-secret", default="smoke-init-secret")
    parser.add_argument("--rotate-key-id", default=None)
    parser.add_argument("--rotate-key-algorithm", default="HMAC_SHA256")
    parser.add_argument("--rotate-public-key", default="smoke-rotate-secret")
    parser.add_argument("--disable-reason", default="device-admin-smoke")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--timeout-seconds", default=20.0, type=float)
    args = parser.parse_args()

    try:
        result = run_smoke(args)
        _print_result(result)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI smoke should always emit parseable status.
        _print_result(
            {
                "status": "FAIL",
                "base_url": args.base_url,
                "error": str(exc),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

