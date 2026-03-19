# API Documentation (Traceability MVP)

> Language / 语言: English | [简体中文](API.md)

This document covers the currently implemented API surface. It is intended for backend integration, frontend integration, and acceptance verification.

## Anchoring capability and API stability statement

### Current runtime modes

- Default runtime mode is `ANCHOR_ADAPTER=active_mock`.
  - Anchoring workflow and states are active.
  - A real blockchain node is not required in default mode.
  - Receipt fields are still persisted (`network`, `transaction_hash`, `receipt_payload`, `anchored_at`).
- Real-chain mode is `ANCHOR_ADAPTER=evm_contract`.
  - Requires EVM RPC and contract config (`ANCHOR_EVM_RPC_URL`, `ANCHOR_EVM_CONTRACT_ADDRESS`).
  - Supports submission recovery via `anchor_submissions`.
  - Supports confirmation/reorg checks via `ANCHOR_EVM_REQUIRED_CONFIRMATIONS`.
  - Supports fee bump strategy and EIP-1559 controls.
  - Supports external signer integration via `ANCHOR_EVM_SIGNER_URL`.

### EVM rollout controls (implemented)

- Rollout mode: `ANCHOR_EVM_ROLLOUT_MODE=shadow|canary|full|rollback_safe`.
- Canary cohort split: `ANCHOR_EVM_CANARY_PERCENT` (`0..100`, deterministic hash bucket).
- Forced safe path: `ANCHOR_EVM_FORCE_ROLLBACK_SAFE=1`.
- Canary SLO gates (defaults):
  - success rate `>= 99.0%`
  - dead-letter rate `<= 0.5%`
  - p95 confirmation `<= 120s`
- Auto-abort: continuous violation duration reaches `ANCHOR_EVM_CANARY_ABORT_AFTER_SECONDS` (default `600`), then decision path switches to `rollback_safe`.
- Window length: `ANCHOR_EVM_CANARY_WINDOW_SECONDS` (default `600`).

### API contract commitment during migration

The following routes and response keys remain available while real-chain rollout is staged:

- `GET /admin/anchoring/tasks`
- `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
- `POST /admin/anchoring/run-once`
- `GET /v1/trace/{batch_id}` with `anchor.status` and `anchor.transaction_hash`
- `POST /contracts/trace-events/validate` with `canonical_hash`

## Compatibility closure gate

Compatibility routes remain traffic-gated and release-gated.

- In-scope routes:
  - `POST /api/cherry/telemetry`
  - `GET /v1/events/recent`
  - `GET /v1/trace/{batch_id}/public`
- Every compatibility response includes deprecation headers:
  - `Deprecation: true`
  - `Sunset: Wed, 30 Sep 2026 00:00:00 GMT`
  - `Link: <https://example.com/runbooks/compatibility-closure>; rel="deprecation"; type="text/markdown"`
  - `X-Compat-Deprecated: true`
  - `X-Compat-Replacement: ...`
  - `X-Compat-Exit-Criteria: 2-releases,14-consecutive-days,<1%-traffic`
- Gate switch: `COMPAT_CLOSURE_ENABLED=1`
- Gate criteria (all required):
  - at least `2` releases observed
  - at least `14` consecutive days with daily compatibility ratio `<1%`
- CI checker: `python -X utf8 scripts/check_compat_exit_criteria.py`
- Runbook: [`COMPATIBILITY_CLOSURE_RUNBOOK.md`](COMPATIBILITY_CLOSURE_RUNBOOK.md)

## Base conventions

- Base URL: `http://localhost:18941`
- Common response header: `X-Trace-Id` (echoed if provided, generated if missing)
- Time format: ISO 8601 UTC, for example `2026-02-10T04:30:00Z`

## CORS

- Environment variable: `CORS_ALLOW_ORIGINS`
  - comma-separated origins
  - default local values: `http://localhost:3000,http://127.0.0.1:3000`
- Middleware behavior:
  - `allow_methods=["*"]`
  - `allow_headers=["*"]`
- Auth transport is Bearer token in `Authorization` header, no cookie dependency.

## Authentication and roles

- Auth scheme: `Authorization: Bearer <JWT>`
- JWT claims:
  - `sub` required
  - `iss` must match backend config (`AUTH_JWT_ISSUER`, default `traceability-auth`)
  - `roles` supports string or string array
  - `exp` optional, must be valid if present
- Supported roles:
  - `admin`
  - `regulator`
- Route auth levels:
  - `public`
  - `admin`
  - `admin | regulator`

## Error response contract

Business and validation failures use RFC9457-like Problem Details.

```json
{
  "type": "https://example.com/problems/<problem-type>",
  "title": "Conflict",
  "status": 409,
  "detail": "Idempotency-Key was reused with a different payload.",
  "instance": "/v1/events"
}
```

Recommended frontend handling is status-aware for `401`, `403`, `404`, `409`, and `422`.

## Pagination and deterministic ordering

- Standard list metadata: `total`, `limit`, `offset`
- Typical defaults: `limit=50`, `offset=0`

Deterministic ordering in implemented list routes:

| Path | Primary order | Tie-breaker |
| --- | --- | --- |
| `GET /v1/batches` | `end_time` desc | `batch_id` asc, then `device_id` asc |
| `GET /v1/events` | `timestamp` desc | `id` desc |
| `GET /v1/alerts` | `raised_at` desc | `id` desc |
| `GET /admin/anchoring/tasks` | `ingest_request_id` desc | stable under same filters |
| `GET /v1/devices` | `created_at` desc | `id` desc |
| `GET /admin/devices/{device_id}/keys` | `activated_at` desc | `id` desc |
| `GET /admin/devices/{device_id}/audits` | `created_at` desc | `id` desc |

## Implemented endpoint catalog

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/health` | public |
| POST | `/contracts/trace-events/validate` | public |
| POST | `/v1/events` | public |
| POST | `/v1/quality/grade` | public |
| POST | `/admin/policies/{policy_id}/activate` | admin |
| POST | `/admin/devices` | admin |
| POST | `/admin/devices/{device_id}/keys` | admin |
| POST | `/admin/devices/{device_id}/disable` | admin |
| GET | `/admin/devices/{device_id}` | admin |
| GET | `/admin/devices/{device_id}/keys` | admin |
| GET | `/admin/devices/{device_id}/audits` | admin |
| GET | `/v1/devices` | admin |
| GET | `/v1/batches` | public |
| GET | `/v1/events` | public |
| GET | `/v1/trace/{batch_id}` | public |
| GET | `/v1/alerts` | admin \| regulator |
| POST | `/v1/alerts/{alert_id}/ack` | admin \| regulator |
| POST | `/v1/alerts/{alert_id}/resolve` | admin \| regulator |
| POST | `/v1/alerts/{alert_id}/escalate` | admin \| regulator |
| GET | `/admin/anchoring/tasks` | admin |
| POST | `/admin/anchoring/tasks/{ingest_request_id}/requeue` | admin |
| POST | `/admin/anchoring/run-once` | admin |
| GET | `/metrics` | public |

## Key request and response contracts

### Health, contract validation, ingest, quality

- `GET /health`
  - response: `{"status":"ok"}`
- `POST /contracts/trace-events/validate`
  - validates `TraceEvent`-contract payload
  - success includes `status` and `canonical_hash`
- `POST /v1/events`
  - requires `Idempotency-Key`
  - body must match `TraceEvent`
  - success `202` with `event_id` and `ingest_status`
  - common conflicts include idempotency key payload mismatch (`409`)
- `POST /v1/quality/grade`
  - returns `grade`, `score`, `max_score`, `reasons`, and `threshold_context`

### Device and admin management

- `POST /admin/policies/{policy_id}/activate`
  - returns activation status and `audit_id`
- `POST /admin/devices`
  - creates managed device
  - duplicate `device_id` returns `409 device-already-exists`
- `POST /admin/devices/{device_id}/keys`
  - rotates key and returns `retired_key_ids`
  - missing device returns `404 device-not-found`
  - disabled device returns `409 device-disabled`
- `POST /admin/devices/{device_id}/disable`
  - disables device and retires active keys
- `GET /admin/devices/{device_id}`
  - includes observability fields such as `active_key`, `key_count`, `last_seen_at`, `signature_failures_last_24h`
- `GET /admin/devices/{device_id}/keys`
  - returns key list envelope with `items`
- `GET /admin/devices/{device_id}/audits`
  - returns audit list envelope with `items`
- `GET /v1/devices`
  - paginated managed-device list with optional `status` filter

### Query and trace

- `GET /v1/batches`
  - paginated batch summaries with optional `device_id`, `start_time`, `end_time` filters
- `GET /v1/events`
  - paginated events with filters: `batch_id`, `device_id`, `ingest_status`, `start_time`, `end_time`
- `GET /v1/trace/{batch_id}`
  - returns timeline, anchor status/hash, quality and alert snapshot fields
  - unknown batch returns `404 trace-batch-not-found`

### Alerts

- `GET /v1/alerts`
  - role: `admin | regulator`
  - returns alert list payload and paging metadata
- `POST /v1/alerts/{alert_id}/ack`
  - state transition to `acknowledged` when valid
- `POST /v1/alerts/{alert_id}/resolve`
  - transition allowed from `open` or `acknowledged`
- `POST /v1/alerts/{alert_id}/escalate`
  - increases severity when state allows
  - returns `409` if already at max severity or state disallows escalation

### Anchoring admin

- `GET /admin/anchoring/tasks`
  - requires query `status` (`RECEIVED|ANCHORING|ANCHORED|FAILED_RETRYING|DEAD_LETTER`)
  - supports `batch_id` and `device_id` filters
- `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
  - allowed for `FAILED_RETRYING` and `DEAD_LETTER`
- `POST /admin/anchoring/run-once`
  - body optional
  - optional `limit` range: `1..1000`
  - omitted body uses internal default limit (`100` in current implementation)

### Metrics

- `GET /metrics`
  - Prometheus text exposition format
  - includes migration and compatibility counters, including compatibility traffic metrics

## Common call examples

```bash
# health
curl -i http://localhost:18941/health

# contract validation
curl -i -X POST http://localhost:18941/contracts/trace-events/validate \
  -H "Content-Type: application/json" \
  -d '{"version":"1.0.0","device_id":"device-001","batch_id":"batch-2026-02-10","timestamp":"2026-02-10T02:00:00Z","sensor_payload":{"temperature_c":4.2,"humidity_pct":73.0},"signature_envelope":{"algorithm":"HMAC_SHA256","signature":"<sig>","key_id":"factory-key-1"}}'

# ingest (Idempotency-Key required)
curl -i -X POST http://localhost:18941/v1/events \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: idem-001" \
  -d '{"version":"1.0.0","device_id":"device-001","batch_id":"batch-2026-02-10","timestamp":"2026-02-10T02:00:00Z","sensor_payload":{"temperature_c":4.2,"humidity_pct":73.0},"signature_envelope":{"algorithm":"HMAC_SHA256","signature":"<sig>","key_id":"factory-key-1"}}'

# metrics
curl -i http://localhost:18941/metrics
```
