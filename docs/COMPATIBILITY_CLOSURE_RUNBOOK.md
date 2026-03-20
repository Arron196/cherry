# Compatibility Closure Runbook

> Language / 语言: English | [简体中文](COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md)

## Scope

This runbook defines how to close the compatibility layer safely for:

- `POST /api/cherry/telemetry`
- `GET /v1/events/recent`
- `GET /v1/trace/{batch_id}/public`

The closure policy is fixed and deterministic:

1. At least 2 releases observed.
2. At least 14 consecutive days where compatibility traffic ratio is below 1% every day.

## Runtime Controls

- `COMPAT_CLOSURE_ENABLED=1`
  - Requests compatibility closure mode.
  - Routes are disabled only when gate criteria pass.
  - If criteria fail or input is invalid, routes stay enabled.
- `COMPAT_EXIT_HISTORY_PATH` (default: `data/compat_traffic_history.json`)
  - JSON history consumed by the exit checker.
- `COMPAT_EXIT_RELEASES_OBSERVED` (optional override)
  - Forces release count for gate evaluation.
- `COMPAT_EXIT_REQUIRED_RELEASES` (default: `2`)
- `COMPAT_EXIT_REQUIRED_CONSECUTIVE_DAYS` (default: `14`)
- `COMPAT_EXIT_MAX_RATIO_PERCENT` (default: `1.0`)

## History File Format

```json
{
  "releases_observed": 2,
  "daily": [
    {
      "date": "2026-02-01",
      "total_requests": 10000,
      "compat_requests_by_endpoint": {
        "/api/cherry/telemetry": 40,
        "/v1/events/recent": 25,
        "/v1/trace/{batch_id}/public": 20
      }
    }
  ]
}
```

Notes:

- `daily` entries must have unique ISO date values.
- `compat_ratio` can be supplied directly per day (`0.0..1.0`) when preferred.
- Trailing streak logic is strict on calendar-day continuity.

## CI Gate

Run checker:

```bash
python -X utf8 scripts/check_compat_exit_criteria.py
```

Behavior:

- Closure not requested: exits `0` with status `SKIP`.
- Closure requested and criteria pass: exits `0` with status `PASS`.
- Closure requested and criteria fail: exits non-zero with status `FAIL`.

## Observability Requirements During Deprecation Window

All compatibility responses emit:

- `Deprecation: true`
- `Sunset: Wed, 30 Sep 2026 00:00:00 GMT`
- `Link: <https://example.com/runbooks/compatibility-closure>; rel="deprecation"; type="text/markdown"`
- `X-Compat-Deprecated: true`
- `X-Compat-Replacement: ...`
- `X-Compat-Exit-Criteria: 2-releases,14-consecutive-days,<1%-traffic`

Metrics:

- `traceability_compat_requests_total{endpoint,method,status}`

## Rollback

If closure causes regressions:

1. Set `COMPAT_CLOSURE_ENABLED=0`.
2. Redeploy and verify compatibility routes are served again.
3. Keep traffic telemetry enabled and restart the qualification window.
