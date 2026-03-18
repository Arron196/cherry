# Cherry Traceability MVP

> Language / 语言:
> - English: [`README.en.md`](README.en.md)
> - 中文: [`README.zh-CN.md`](README.zh-CN.md)

This file is the bilingual entry for project documentation.

## Documentation map

| Topic | English | 中文 |
| --- | --- | --- |
| Project overview | [`README.en.md`](README.en.md) | [`README.zh-CN.md`](README.zh-CN.md) |
| Full API contract | [`docs/API.en.md`](docs/API.en.md) | [`docs/API.md`](docs/API.md) |
| Contract v1 migration spec | [`docs/CONTRACT_V1_MIGRATION.md`](docs/CONTRACT_V1_MIGRATION.md) | [`docs/CONTRACT_V1_MIGRATION.zh-CN.md`](docs/CONTRACT_V1_MIGRATION.zh-CN.md) |
| Compatibility closure runbook | [`docs/COMPATIBILITY_CLOSURE_RUNBOOK.md`](docs/COMPATIBILITY_CLOSURE_RUNBOOK.md) | [`docs/COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md`](docs/COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md) |
| Frontend integration checklist | [`docs/FRONTEND_INTEGRATION_CHECKLIST.en.md`](docs/FRONTEND_INTEGRATION_CHECKLIST.en.md) | [`docs/FRONTEND_INTEGRATION_CHECKLIST.md`](docs/FRONTEND_INTEGRATION_CHECKLIST.md) |
| Frontend module docs | [`frontend/README.en.md`](frontend/README.en.md) | [`frontend/README.zh-CN.md`](frontend/README.zh-CN.md) |

## Current implementation highlights

- Anchoring default is `ANCHOR_ADAPTER=active_mock`; real-chain path exists via `ANCHOR_ADAPTER=evm_contract`.
- EVM rollout controls are implemented with `shadow|canary|full|rollback_safe` modes and canary SLO/abort gates.
- Compatibility closure is traffic-gated, not unconditional; closure only applies when release and traffic criteria are met.
- F1 to F4 final verification is completed in current project state.
