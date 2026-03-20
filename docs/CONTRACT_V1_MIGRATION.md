# CONTRACT V1 MIGRATION SPEC

> Language / 语言: English | [简体中文](CONTRACT_V1_MIGRATION.zh-CN.md)

## Purpose and Scope

This document freezes the canonical Contract v1 baseline and migration rules used by frontend, backend, and hardware callers.

Scope of this task:

- Freeze canonical baselines for ingest, public trace, and stats.
- Define deterministic compatibility-to-canonical field mappings.
- Define endpoint mapping from FE/HW caller routes to canonical and compatibility routes.
- Define compatibility deprecation schedule, objective exit criteria, and rollback note.

## Canonical Baselines

### Ingest TraceEvent Baseline (Frozen)

Source of truth: `app/domain/contracts/trace_event.py` (`TraceEvent`, `SignatureEnvelope`, `SensorPayload`).

Canonical required fields:

- `version`
- `device_id`
- `batch_id`
- `timestamp`
- `sensor_payload`
- `signature_envelope`

Canonical optional extension fields:

- `co2_ppm`
- `vibration_g`
- `supply_chain_stage`

### Public Trace Baseline (Frozen)

Source of truth: `app/api/public_trace.py` (`PublicTraceResponse`).

Canonical top-level keys (frozen):

- `batch_info`
- `timeline`
- `stage_environments`
- `quality`
- `blockchain_anchor`

### Stats Baseline (Frozen)

Source of truth: `app/api/stats.py`.

Canonical stats endpoints:

- `GET /v1/stats/overview`
- `GET /v1/stats/temperature-trend`
- `GET /v1/stats/quality-distribution`
- `GET /v1/stats/stage-distribution`

### Signature Policy Baseline (Frozen)

- Canonical signature algorithm id: `ECDSA_P256_SHA256`.
- Compatibility alias handling: `ECDSA` is accepted only through explicit normalization to `ECDSA_P256_SHA256`.
- Alias acceptance is a migration-only behavior and not a second canonical algorithm.

## Canonical-to-Compatibility Field Mapping

Compatibility source payload baseline: `app/api/compat.py` (`CherryTelemetryPayload` -> canonical `TraceEvent`).

| Compatibility payload field | Canonical field | Rule |
| --- | --- | --- |
| `seq` | `sensor_payload.seq` | Copy integer as-is. |
| `ts` | `timestamp` | Unix seconds to UTC ISO8601; if missing use ingest server time. |
| `temp_c` | `sensor_payload.temperature_c` | Copy float as-is. |
| `hum_rh` | `sensor_payload.humidity_pct` | Copy float as-is. |
| `co2` | `sensor_payload.co2_ppm`, `co2_ppm` | Copy when present. |
| `vibration` | `sensor_payload.vibration`, `vibration_g` fallback | If `vibration_g` missing, map `true->1.0`, `false->0.0`. |
| `vibration_g` | `vibration_g` | Copy float when present. |
| `digest` | `sensor_payload.digest` | Copy string when present. |
| `device_id` | `device_id` | Copy string as-is. |
| `batch_id` | `batch_id` | Copy string as-is. |
| `stage` | `supply_chain_stage` | Allowed: `harvest|storage|transport|retail`; otherwise default `transport`. |
| `key_id` | `signature_envelope.key_id` | Copy string as-is. |
| `signature` | `signature_envelope.signature` | If missing, fallback `compat-signature` (current compat behavior). |
| implicit compat algorithm | `signature_envelope.algorithm` | Normalize `ECDSA` to canonical `ECDSA_P256_SHA256`. |

## Endpoint Mapping Table (FE/HW -> Canonical and Compat)

| Caller | Source | Caller Endpoint | Canonical Backend Route | Compat Route | Status |
| --- | --- | --- | --- | --- | --- |
| FE | `frontend/src/lib/services.ts` | `/v1/auth/login` | `/v1/auth/login` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/health` | `/health` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/contracts/trace-events/validate` | `/contracts/trace-events/validate` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/events` | `/v1/events` | `/api/cherry/telemetry` | Canonical + compat bridge exists |
| FE | `frontend/src/lib/services.ts` | `/v1/quality/grade` | `/v1/quality/grade` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/batches` | `/v1/batches` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/events` | `/v1/events` | `/v1/events/recent` | Canonical query + compat helper |
| FE | `frontend/src/lib/services.ts` | `/v1/trace/{batch_id}` | `/v1/trace/{batch_id}` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/trace/{batch_id}/public` | `/v1/public/trace/{batch_id}` | `/v1/trace/{batch_id}/public` | Canonical + alias compatibility |
| FE | `frontend/src/lib/services.ts` | `/v1/batches/{batch_id}/stages` | `/v1/batches/{batch_id}/stages` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/batches/{batch_id}/sensors` | `/v1/batches/{batch_id}/sensors` | N/A | PLANNED in Task 2 |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/overview` | `/v1/stats/overview` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/temperature-trend` | `/v1/stats/temperature-trend` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/quality-distribution` | `/v1/stats/quality-distribution` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/stage-distribution` | `/v1/stats/stage-distribution` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/events/recent` | `/v1/events` | `/v1/events/recent` | Compat helper scheduled for deprecation |
| FE | `frontend/src/lib/services.ts` | `/v1/alerts` | `/v1/alerts` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/alerts/{alert_id}/ack` | `/v1/alerts/{alert_id}/ack` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/alerts/{alert_id}/resolve` | `/v1/alerts/{alert_id}/resolve` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/alerts/{alert_id}/escalate` | `/v1/alerts/{alert_id}/escalate` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/anchoring/tasks` | `/admin/anchoring/tasks` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/anchoring/tasks/{ingest_request_id}/requeue` | `/admin/anchoring/tasks/{ingest_request_id}/requeue` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/anchoring/run-once` | `/admin/anchoring/run-once` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/policies/{policy_id}/activate` | `/admin/policies/{policy_id}/activate` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/devices` | `/admin/devices` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/devices` | `/v1/devices` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/devices/{device_id}` | `/admin/devices/{device_id}` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/devices/{device_id}/keys` | `/admin/devices/{device_id}/keys` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/devices/{device_id}/disable` | `/admin/devices/{device_id}/disable` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/admin/devices/{device_id}/audits` | `/admin/devices/{device_id}/audits` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/metrics` | `/metrics` | N/A | Canonical |
| HW | `hardware/cherry/Core/Src/cherry_hw.c` | `/api/cherry/telemetry` | `/v1/events` | `/api/cherry/telemetry` | Compat ingress maps to canonical event schema |
| HW/Simulator | `simulator/stm32_device.py`, `simulator/gateway.py` | `/v1/events` | `/v1/events` | `/api/cherry/telemetry` | Canonical preferred; compat fallback exists |

## Endpoint Map

Canonical route set used by FE/HW:

- `/v1/events`, `/v1/batches`, `/v1/trace/{batch_id}`
- `/v1/public/trace/{batch_id}`, `/v1/batches/{batch_id}/stages`, `/v1/batches/{batch_id}/sensors` (planned)
- `/v1/stats/overview`, `/v1/stats/temperature-trend`, `/v1/stats/quality-distribution`, `/v1/stats/stage-distribution`
- `/v1/alerts`, `/v1/alerts/{alert_id}/ack`, `/v1/alerts/{alert_id}/resolve`, `/v1/alerts/{alert_id}/escalate`
- `/v1/auth/login`, `/v1/quality/grade`, `/contracts/trace-events/validate`, `/health`, `/metrics`
- `/admin/anchoring/tasks`, `/admin/anchoring/tasks/{ingest_request_id}/requeue`, `/admin/anchoring/run-once`
- `/admin/policies/{policy_id}/activate`, `/admin/devices`, `/admin/devices/{device_id}`, `/admin/devices/{device_id}/keys`, `/admin/devices/{device_id}/disable`, `/admin/devices/{device_id}/audits`, `/v1/devices`

Compatibility route set retained during migration:

- `/api/cherry/telemetry`
- `/v1/trace/{batch_id}/public`
- `/v1/events/recent`

## OpenAPI Path and Shape Expectations

This section defines the minimum request/response contract obligations expected in OpenAPI and runtime behavior for FE/HW-consumed routes.

| Path | Method | Shape expectation |
| --- | --- | --- |
| `/v1/events` | `POST` | Requires `Idempotency-Key`; body matches `TraceEvent`; returns `event_id`, `ingest_status`. |
| `/v1/events` | `GET` | Paginated response with `total`, `limit`, `offset`, `items[]`. |
| `/contracts/trace-events/validate` | `POST` | Returns `status` and `canonical_hash`. |
| `/v1/quality/grade` | `POST` | Returns `grade`, `score`, `max_score`, `reasons`, `threshold_context`. |
| `/health` | `GET` | Returns `status`. |
| `/v1/auth/login` | `POST` | Returns `access_token`, `token_type`, `expires_in`, `role`. |
| `/v1/batches` | `GET` | Paginated response with batch summaries. |
| `/v1/trace/{batch_id}` | `GET` | Returns trace timeline with anchor and quality snapshots. |
| `/v1/public/trace/{batch_id}` | `GET` | Returns `batch_info`, `timeline`, `stage_environments`, `quality`, `blockchain_anchor`. |
| `/v1/trace/{batch_id}/public` | `GET` | Alias endpoint must be contract-equivalent to `/v1/public/trace/{batch_id}`. |
| `/v1/batches/{batch_id}/stages` | `GET` | Returns stage list with event-level stage details. |
| `/v1/batches/{batch_id}/sensors` | `GET` | Planned canonical route for sensor history (Task 2). |
| `/v1/stats/overview` | `GET` | Returns overview totals and grade distribution object. |
| `/v1/stats/temperature-trend` | `GET` | Returns trend payload (point list and period metadata). |
| `/v1/stats/quality-distribution` | `GET` | Returns quality distribution list and total. |
| `/v1/stats/stage-distribution` | `GET` | Returns stage distribution list and total. |
| `/v1/events/recent` | `GET` | Compat helper; returns recent event list for migration window only. |
| `/v1/alerts` | `GET` | Returns alert list payload including `alerts` and paging metadata. |
| `/v1/alerts/{alert_id}/ack` | `POST` | Returns alert action result with state transition metadata. |
| `/v1/alerts/{alert_id}/resolve` | `POST` | Returns alert action result with resolved state. |
| `/v1/alerts/{alert_id}/escalate` | `POST` | Returns alert action result with escalated severity. |
| `/admin/anchoring/tasks` | `GET` | Returns paginated anchoring task list. |
| `/admin/anchoring/tasks/{ingest_request_id}/requeue` | `POST` | Returns requeue result with `ingest_request_id`, `status`, `retry_count`, `audit_id`. |
| `/admin/anchoring/run-once` | `POST` | Returns run result with `processed`, `limit`, `audit_id`. |
| `/admin/policies/{policy_id}/activate` | `POST` | Returns policy activation status and `audit_id`. |
| `/admin/devices` | `POST` | Returns registered device and optional initial key metadata. |
| `/v1/devices` | `GET` | Returns paginated managed-device list. |
| `/admin/devices/{device_id}` | `GET` | Returns managed-device detail with active key and observability fields. |
| `/admin/devices/{device_id}/keys` | `GET` | Returns key list envelope with `items`. |
| `/admin/devices/{device_id}/keys` | `POST` | Returns key-rotation result with `retired_key_ids`. |
| `/admin/devices/{device_id}/disable` | `POST` | Returns disable result with retired key IDs and audit record. |
| `/admin/devices/{device_id}/audits` | `GET` | Returns audit list envelope with `items`. |
| `/metrics` | `GET` | Returns Prometheus text format. |
| `/api/cherry/telemetry` | `POST` | Compat ingest route; maps telemetry payload to canonical `TraceEvent` and returns accepted/status. |

## Compatibility Deprecation Schedule

Compatibility endpoints in scope: `/api/cherry/telemetry`, `/v1/trace/{batch_id}/public`, `/v1/events/recent`.

Deprecation timeline:

1. Release N: mark compatibility routes deprecated; add deprecation telemetry labels and migration guidance.
2. Release N+1: maintain routes, monitor residual traffic, and block new callers from onboarding to compat-only paths.
3. Earliest removal release: N+2, only when Exit Criteria are met.

Operational references:

- Runbook: `docs/COMPATIBILITY_CLOSURE_RUNBOOK.md`
- Gate checker: `scripts/check_compat_exit_criteria.py`

Locked policy requirement: deprecation window is `2 releases + >=14 consecutive days with <1% compat traffic`.

## Exit Criteria

All criteria are mandatory before compatibility removal:

1. At least 2 releases elapsed since deprecation started.
2. At least 14 consecutive days with `<1% compat traffic` across the three compatibility routes.
3. Compatibility route 5xx rate remains <= 0.5% and does not exceed canonical equivalent 5xx rate by > 0.2 percentage points.
4. No FE route in `frontend/src/lib/services.ts` depends exclusively on compatibility-only behavior.
5. Hardware path is operating on canonical `/v1/events` or through a verified adapter that emits canonical-equivalent payloads.

## Rollback Note

If canary migration metrics regress or compatibility removal causes contract breakage:

- Immediately keep/restore compatibility routes and route callers back to the last known-good adapter behavior.
- Keep canonical contracts unchanged (no emergency schema edits) and rollback by traffic routing/configuration only.
- Preserve deprecation telemetry so rollback impact can be measured.
- Re-enter migration only after a full green run of contract guard and this spec validator.

## Skill Relevance Evaluation

- `playwright`: not relevant (no browser task).
- `frontend-ui-ux`: not relevant (no UI design/styling task).
- `git-master`: not relevant (no git operation requested).
- `dev-browser`: not relevant (no browser automation task).
