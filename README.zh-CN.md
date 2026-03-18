# Cherry Traceability MVP（中文）

> 语言 / Language:
> - 中文: `README.zh-CN.md`
> - English: [`README.en.md`](README.en.md)

## 项目状态

本仓库实现了 FastAPI 追溯 MVP，当前状态包含 canonical `/v1` 契约、迁移期兼容路由，以及分阶段锚定 rollout 控制。

- 默认锚定模式是 `ANCHOR_ADAPTER=active_mock`。
- 真实链锚定能力已实现，适配器为 `ANCHOR_ADAPTER=evm_contract`。
- 已实现 rollout 模式控制：`ANCHOR_EVM_ROLLOUT_MODE=shadow|canary|full|rollback_safe`。
- 已实现 canary SLO gate 默认阈值：
  - 成功率 `>= 99.0%`
  - dead-letter 比例 `<= 0.5%`
  - p95 确认时延 `<= 120s`
  - 连续违规自动中止窗口 `600s`
- 兼容层关闭是 traffic-gated + release-gated，不是无条件移除。
- 当前项目的 F1、F2、F3、F4 最终验证状态均已完成。

## 本地运行默认值

- SQLite 默认路径：`data/app.db`（`sqlite:///./data/app.db`）
- 可通过 `TRACEABILITY_DATABASE_URL` 覆盖
- 本地 compose 端口：
  - Frontend: `http://localhost:18940`
  - Backend: `http://localhost:18941`

## Compatibility closure gate

兼容路由在迁移期保留，只有 closure gate 全部通过后才会关闭。

- 范围内路由：
  - `POST /api/cherry/telemetry`
  - `GET /v1/events/recent`
  - `GET /v1/trace/{batch_id}/public`
- 关闭请求开关：`COMPAT_CLOSURE_ENABLED=1`
- 固定退出条件：
  - 至少经历 2 个发布版本
  - 至少连续 14 个自然日，每日兼容流量占比 `<1%`
- Gate 检查命令：`python -X utf8 scripts/check_compat_exit_criteria.py`

## 快速启动

```bash
cp .env.example .env
docker compose up --build -d
```

默认会启动 `app` 和 `frontend` 两个服务，可直接访问：

- Frontend: `http://localhost:18940`
- Backend: `http://localhost:18941`

可选服务说明：

- `worker`：使用 `--profile worker` 单独开启后台锚定轮询
- `smoke`：使用 `--profile smoke` 运行一次性验收，不属于默认常驻服务

一键 smoke 验收：

```bash
docker compose --profile smoke up --build --abort-on-container-exit --exit-code-from smoke smoke
```

## 常用验证命令

先安装后端开发 / 测试依赖：

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

## 文档导航

| 主题 | English | 中文 |
| --- | --- | --- |
| API 文档 | [`docs/API.en.md`](docs/API.en.md) | [`docs/API.md`](docs/API.md) |
| Contract 迁移规范 | [`docs/CONTRACT_V1_MIGRATION.md`](docs/CONTRACT_V1_MIGRATION.md) | [`docs/CONTRACT_V1_MIGRATION.zh-CN.md`](docs/CONTRACT_V1_MIGRATION.zh-CN.md) |
| Compatibility 关闭 Runbook | [`docs/COMPATIBILITY_CLOSURE_RUNBOOK.md`](docs/COMPATIBILITY_CLOSURE_RUNBOOK.md) | [`docs/COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md`](docs/COMPATIBILITY_CLOSURE_RUNBOOK.zh-CN.md) |
| 前端接入清单 | [`docs/FRONTEND_INTEGRATION_CHECKLIST.en.md`](docs/FRONTEND_INTEGRATION_CHECKLIST.en.md) | [`docs/FRONTEND_INTEGRATION_CHECKLIST.md`](docs/FRONTEND_INTEGRATION_CHECKLIST.md) |
| Frontend 模块文档 | [`frontend/README.en.md`](frontend/README.en.md) | [`frontend/README.zh-CN.md`](frontend/README.zh-CN.md) |
