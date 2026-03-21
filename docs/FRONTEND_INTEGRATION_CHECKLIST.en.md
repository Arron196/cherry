# Frontend Integration Checklist (Traceability MVP)

> Language / 语言: English | [简体中文](FRONTEND_INTEGRATION_CHECKLIST.md)

> Usage: This checklist is for frontend integration and pre-release self-check. Read it together with `docs/API.en.md`.

## 1) Environment prerequisites

- [ ] **API base URL**: `API_BASE_URL` is configured (example: `http://localhost:18941`) with dev/staging/prod separation.
- [ ] **JWT source**: Bearer token source is clear (login service, gateway, or test issuer), and at least two token types are available:
  - [ ] `admin` role token
  - [ ] `regulator` role token
- [ ] **JWT claims match backend rules**: `alg=HS256`, `iss` matches backend `AUTH_JWT_ISSUER`, non-empty `sub`, `roles` is string or string array, `exp` is not expired.
- [ ] **CORS allowlist**: backend `CORS_ALLOW_ORIGINS` includes current frontend origin (including port), and browser preflight (`OPTIONS`) is verified.
- [ ] **Unified headers in HTTP client**: `Authorization`, optional `X-Trace-Id`, and `Idempotency-Key` (required only for `/v1/events`) are handled consistently.

## 2) API to page mapping

### 2.1 Public query and trace views

- [ ] Batch list page: `GET /v1/batches` (paging `total/limit/offset`, filters `device_id/start_time/end_time`)
- [ ] Event list page: `GET /v1/events` (paging `total/limit/offset`, filters `batch_id/device_id/ingest_status/start_time/end_time`)
- [ ] Batch trace detail page: `GET /v1/trace/{batch_id}` (`timeline_order=oldest_first`)

### 2.2 Alert center (query + actions)

- [ ] Alert list page: `GET /v1/alerts` (requires `admin | regulator`)
- [ ] Acknowledge action: `POST /v1/alerts/{alert_id}/ack`
- [ ] Resolve action: `POST /v1/alerts/{alert_id}/resolve`
- [ ] Escalate action: `POST /v1/alerts/{alert_id}/escalate`

### 2.3 Anchoring admin

- [ ] Anchoring task list page: `GET /admin/anchoring/tasks` (requires `status`, supports `batch_id/device_id` filters)
- [ ] Requeue action: `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
- [ ] Run-once action: `POST /admin/anchoring/run-once`

### 2.4 Device and key management (admin)

- [ ] Device list page: `GET /v1/devices` (paging `total/limit/offset`, `status` filter, order `created_at desc, id desc`)
- [ ] Device detail page: `GET /admin/devices/{device_id}`
- [ ] Device keys page: `GET /admin/devices/{device_id}/keys`
- [ ] Device audit page: `GET /admin/devices/{device_id}/audits`
- [ ] Device create page: `POST /admin/devices`
- [ ] Key rotation page: `POST /admin/devices/{device_id}/keys`
- [ ] Device disable action: `POST /admin/devices/{device_id}/disable`
- [ ] Policy activation action: `POST /admin/policies/{policy_id}/activate`
- [ ] Device onboarding flow: `POST /admin/devices` (with optional `initial_key`) -> `GET /admin/devices/{device_id}` -> `GET /admin/devices/{device_id}/keys`

### 2.5 Auxiliary interfaces (optional pages/ops views)

- [ ] Health page/tool: `GET /health`
- [ ] Contract validation tool page: `POST /contracts/trace-events/validate`
- [ ] Event ingest tool page: `POST /v1/events` (must include `Idempotency-Key`)
- [ ] Quality grading tool page: `POST /v1/quality/grade`
- [ ] Online threshold control: device list supports threshold choices (for example `1/5/15/30 minutes`) and UI status changes accordingly.
- [ ] Metrics page (if exposed by frontend): `GET /metrics`

## 3) Feature integration test checklist

### 3.1 Query APIs (`/v1/batches`, `/v1/events`)

- [ ] Default paging: when omitted, returns `limit=50` and `offset=0`.
- [ ] Stable paging: no duplicates or gaps while paging under same filters.
- [ ] Time-window validation: `start_time > end_time` returns `422`.
- [ ] Ordering matches docs: deterministic descending order for `/v1/batches` and `/v1/events`.

### 3.2 Anchoring admin APIs

- [ ] `status` filter works for `RECEIVED/ANCHORING/ANCHORED/FAILED_RETRYING/DEAD_LETTER`.
- [ ] Requeue is allowed only for `FAILED_RETRYING` and `DEAD_LETTER`; other states return `409`.
- [ ] `run-once` works without body; when `limit` is provided, validation range is `1..1000`.

### 3.3 Alert query and action APIs

- [ ] List API allows both `admin` and `regulator` roles.
- [ ] `ack` allows transition only from `open` to `acknowledged`; invalid transition returns `409`.
- [ ] `resolve` allows transition only from `open` or `acknowledged` to `resolved`.
- [ ] `escalate` raises severity when state allows; escalating after `critical` returns `409`.

### 3.4 Device/key admin APIs

- [ ] Duplicate device create returns `409 device-already-exists`.
- [ ] Rotate key on missing device returns `404 device-not-found`.
- [ ] Rotate key on disabled device returns `409 device-disabled`.
- [ ] Duplicate `key_id` returns `409 device-key-already-exists`.
- [ ] Device list paging and sorting are stable: `created_at desc, id desc` with no data drop on `status` filter switch.
- [ ] Device detail returns `active_key`, `key_count`, and `last_seen_at`.
- [ ] Device keys are ordered by `activated_at desc, id desc`.
- [ ] Device audits are ordered by `created_at desc, id desc`.

## 4) Frontend error-handling checklist (`401/403/404/409/422`)

- [ ] `401 Unauthorized`: run auth-expired flow (clear token, redirect login or refresh token).
- [ ] `403 Forbidden`: show no-permission text, disable or hide actions, keep readable content.
- [ ] `404 Not Found`: show resource-not-found state and provide return-to-list action.
- [ ] `409 Conflict`: show conflict reason (prefer backend `detail`) and offer refresh-and-retry.
- [ ] `422 Unprocessable Entity`: map validation errors to form/filter fields and keep user input.
- [ ] Problem Details adapter parses at least `type/title/status/detail/instance` and logs telemetry.

## 5) Go-live readiness checklist

- [ ] Production origin is included in backend `CORS_ALLOW_ORIGINS`, verified in real browser environment.
- [ ] Production `API_BASE_URL`, auth integration point, and logging flags are switched to release configuration.
- [ ] Frontend has confirmation and anti-double-submit controls for critical actions (`requeue`, `disable`, `escalate`, `resolve`).
- [ ] List pages cover empty/loading/error/no-permission states.
- [ ] Integration records are archived for key APIs (request/response samples + trace IDs).
- [ ] Post-release regression checklist is prepared for batches/events queries, alerts actions, anchoring admin, and device/key admin.
