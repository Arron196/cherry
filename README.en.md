# Cherry Traceability MVP (English)

> Language / 语言:
> - English: `README.en.md`
> - 中文: [`README.zh-CN.md`](README.zh-CN.md)

## Project status

This repository implements a FastAPI traceability MVP with canonical `/v1` contracts, temporary compatibility routes, and staged anchoring rollout controls.

- Default runtime anchoring mode is `ANCHOR_ADAPTER=active_mock`.
- Real-chain anchoring is implemented by `ANCHOR_ADAPTER=evm_contract`.
- Rollout controls are implemented: `ANCHOR_EVM_ROLLOUT_MODE=shadow|canary|full|rollback_safe`.
- Canary SLO gate defaults are implemented:
  - success rate `>= 99.0%`
  - dead-letter rate `<= 0.5%`
  - p95 confirmation `<= 120s`
  - continuous violation auto-abort window `600s`
- Compatibility closure is traffic-gated and release-gated, it is never unconditional.
- Final verification state is complete for F1, F2, F3, and F4.

## Local runtime defaults

- Default SQLite path: `data/app.db` (`sqlite:///./data/app.db`)
- Override with `TRACEABILITY_DATABASE_URL`
- Local compose ports:
  - Frontend: `http://localhost:18940`
  - Backend: `http://localhost:18941`

## Compatibility closure gate

Compatibility routes are retained during migration and only close when all gate conditions pass.

- Routes in scope:
  - `POST /api/cherry/telemetry`
  - `GET /v1/events/recent`
  - `GET /v1/trace/{batch_id}/public`
- Closure request switch: `COMPAT_CLOSURE_ENABLED=1`
- Locked exit criteria:
  - at least 2 releases observed
  - at least 14 consecutive calendar days with daily compat ratio `<1%`
- Gate checker command: `python -X utf8 scripts/check_compat_exit_criteria.py`

## Quick start

```bash
cp .env.example .env
docker compose up --build -d
```

By default this starts the `app` and `frontend` services, available at:

- Frontend: `http://localhost:18940`
- Backend: `http://localhost:18941`

Optional services:

- `worker`: enable with `--profile worker` for background anchoring polling
- `smoke`: enable with `--profile smoke` for one-off acceptance validation; it is not part of the default long-running stack

Smoke profile flow:

```bash
docker compose --profile smoke up --build --abort-on-container-exit --exit-code-from smoke smoke
```

## Verification commands

Install backend dev/test dependencies first:

```bash
python -m pip install -e ".[dev]"
```

```bash
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
python -X utf8 scripts/contract_guard.py
python -X utf8 scripts/check_compat_exit_criteria.py
```

## Documentation map

| Topic | English | 中文 |
| --- | --- | --- |
| API docs | [`docs/API.en.md`](docs/API.en.md) | [`docs/API.md`](docs/API.md) |
| Contract migration spec | [`docs/CONTRACT_V1_MIGRATION.md`](docs/CONTRACT_V1_MIGRATION.md) | [`docs/CONTRACT_V1_MIGRATION.zh-CN.md`](docs/CONTRACT_V1_MIGRATION.zh-CN.md) |
| Compatibility closure runbook | [`docs/COMPATIBILITY_CLOSURE_RUNBOOK.md`](docs/COMPATIBILITY_CLOSURE_RUNBOOK.md) | [`docs/COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md`](docs/COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md) |
| Frontend integration checklist | [`docs/FRONTEND_INTEGRATION_CHECKLIST.en.md`](docs/FRONTEND_INTEGRATION_CHECKLIST.en.md) | [`docs/FRONTEND_INTEGRATION_CHECKLIST.md`](docs/FRONTEND_INTEGRATION_CHECKLIST.md) |
| Frontend module docs | [`frontend/README.en.md`](frontend/README.en.md) | [`frontend/README.zh-CN.md`](frontend/README.zh-CN.md) |
