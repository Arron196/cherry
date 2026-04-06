# Frontend README (English)

> Language / 语言:
> - English: `README.en.md`
> - 中文: [`README.zh-CN.md`](README.zh-CN.md)

## Overview

This is the Next.js frontend for Cherry Traceability MVP.

- Dev server command: `npm run dev`
- If started via project root `docker compose`, external frontend URL is usually `http://localhost:18940`.
- Container internal app port remains `3000`.

## Anchoring integration notes

- Default backend anchoring mode is mock (`ANCHOR_ADAPTER=active_mock`), suitable for integration and acceptance.
- Frontend depends on stable anchoring APIs:
  - `GET /admin/anchoring/tasks`
  - `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
  - `POST /admin/anchoring/run-once`
  - `GET /v1/trace/{batch_id}` (includes `anchor.transaction_hash`)
- Real-chain rollout is controlled by backend rollout modes (`shadow|canary|full|rollback_safe`) and does not require frontend contract changes.

## Compatibility closure note

Compatibility routes remain traffic-gated. Frontend integration should prioritize canonical routes and only treat compatibility paths as migration-period support.

## Getting started

```bash
npm run dev
```

For one-command Docker startup from the repository root, run:

```bash
cp .env.example .env
docker compose up --build -d
```

This starts the backend and frontend together, with the UI exposed at `http://localhost:18940`.

You can start editing by updating `app/page.tsx`.

## Build and test

```bash
npm ci
npm run build
npm run test
```

## Related docs

- Full API docs: [`../docs/API.en.md`](../docs/API.en.md)
- Frontend integration checklist: [`../docs/FRONTEND_INTEGRATION_CHECKLIST.en.md`](../docs/FRONTEND_INTEGRATION_CHECKLIST.en.md)
- Root project docs index: [`../README.md`](../README.md)
