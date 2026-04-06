# Frontend README（中文）

> 语言 / Language:
> - 中文: `README.zh-CN.md`
> - English: [`README.en.md`](README.en.md)

## 概览

这是 Cherry Traceability MVP 的 Next.js 前端模块。

- 开发命令：`npm run dev`
- 如果通过项目根目录 `docker compose` 启动，对外访问通常是 `http://localhost:18940`。
- 容器内应用端口仍为 `3000`。

## 锚定联调说明

- 后端默认锚定模式是 mock（`ANCHOR_ADAPTER=active_mock`），适合联调与验收。
- 前端依赖的锚定稳定接口：
  - `GET /admin/anchoring/tasks`
  - `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
  - `POST /admin/anchoring/run-once`
  - `GET /v1/trace/{batch_id}`（包含 `anchor.transaction_hash`）
- 真实链 rollout 由后端 `shadow|canary|full|rollback_safe` 控制，不要求前端改契约。

## Compatibility closure 说明

兼容路由仍是 traffic-gated。前端应优先调用 canonical 路由，兼容路径只作为迁移窗口支持。

## 快速开始

```bash
npm run dev
```

如果需要从项目根目录 Docker 一键启动，使用：

```bash
cp .env.example .env
docker compose up --build -d
```

默认会启动后端与前端，浏览器访问 `http://localhost:18940`。

可从 `app/page.tsx` 开始修改页面。

## 构建与测试

```bash
npm ci
npm run build
npm run test
```

## 相关文档

- 完整 API 文档：[`../docs/API.md`](../docs/API.md)
- 前端接入清单：[`../docs/FRONTEND_INTEGRATION_CHECKLIST.md`](../docs/FRONTEND_INTEGRATION_CHECKLIST.md)
- 项目文档入口：[`../README.md`](../README.md)
