# 前端接入清单（Traceability MVP）

> 语言 / Language: 简体中文 | [English](FRONTEND_INTEGRATION_CHECKLIST.en.md)

> 使用方式：本清单用于前端联调与上线自检；接口细节请配合 `docs/API.md` 一起使用。

## 1) 环境前置检查

- [ ] **API 地址**：已配置 `API_BASE_URL`（示例：`http://localhost:18941`），并在前端环境区分 dev/staging/prod。
- [ ] **JWT 来源**：已明确 Bearer Token 来源（登录服务、网关或测试签发脚本），并可提供至少两类测试 Token：
  - [ ] `admin` 角色 Token
  - [ ] `regulator` 角色 Token
- [ ] **JWT 声明符合后端要求**：`alg=HS256`、`iss` 匹配后端 `AUTH_JWT_ISSUER`、`sub` 非空、`roles` 为字符串或字符串数组、`exp` 未过期。
- [ ] **CORS 白名单**：后端 `CORS_ALLOW_ORIGINS` 已包含当前前端域名（含端口），并已验证浏览器预检（`OPTIONS`）通过。
- [ ] **统一请求头策略**：已在 HTTP 客户端层统一处理 `Authorization`、`X-Trace-Id`（可选透传）与 `Idempotency-Key`（仅 `/v1/events` 必填）。

## 2) 接口到页面映射清单

### 2.1 公共查询与追溯视图

- [ ] 批次列表页：`GET /v1/batches`（分页 `total/limit/offset`，筛选 `device_id/start_time/end_time`）
- [ ] 事件列表页：`GET /v1/events`（分页 `total/limit/offset`，筛选 `batch_id/device_id/ingest_status/start_time/end_time`）
- [ ] 批次追溯详情页：`GET /v1/trace/{batch_id}`（时间线 `timeline_order=oldest_first`）

### 2.2 告警中心（查询 + 动作）

- [ ] 告警列表页：`GET /v1/alerts`（需 `admin | regulator`）
- [ ] 告警确认操作：`POST /v1/alerts/{alert_id}/ack`
- [ ] 告警解决操作：`POST /v1/alerts/{alert_id}/resolve`
- [ ] 告警升级操作：`POST /v1/alerts/{alert_id}/escalate`

### 2.3 锚定管理（Admin）

- [ ] 锚定任务列表页：`GET /admin/anchoring/tasks`（需 `status`，支持 `batch_id/device_id` 过滤）
- [ ] 重入队操作：`POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
- [ ] 手动执行一次锚定：`POST /admin/anchoring/run-once`

### 2.4 设备与密钥管理（Admin）

- [ ] 设备列表页：`GET /v1/devices`（分页 `total/limit/offset`，筛选 `status`，排序 `created_at desc, id desc`）
- [ ] 设备详情页：`GET /admin/devices/{device_id}`
- [ ] 设备密钥列表页：`GET /admin/devices/{device_id}/keys`
- [ ] 设备审计日志页：`GET /admin/devices/{device_id}/audits`
- [ ] 设备创建页：`POST /admin/devices`
- [ ] 密钥轮换页：`POST /admin/devices/{device_id}/keys`
- [ ] 设备停用操作：`POST /admin/devices/{device_id}/disable`
- [ ] 策略激活操作：`POST /admin/policies/{policy_id}/activate`
- [ ] 设备接入向导：`POST /admin/devices`（可含 `initial_key`）→ `GET /admin/devices/{device_id}` → `GET /admin/devices/{device_id}/keys`

### 2.5 辅助接口（可选页面/运维视图）

- [ ] 系统健康检查：`GET /health`
- [ ] 合同校验工具页：`POST /contracts/trace-events/validate`
- [ ] 事件写入工具页：`POST /v1/events`（必带 `Idempotency-Key`）
- [ ] 质量评分工具页：`POST /v1/quality/grade`
- [ ] 在线阈值配置：设备列表支持阈值切换（如 `1/5/15/30 分钟`），并正确影响在线/离线判定展示
- [ ] 指标查看页（若前端暴露）：`GET /metrics`

## 3) 分功能联调测试清单

### 3.1 Query APIs（`/v1/batches`、`/v1/events`）

- [ ] 默认分页：不传参数时返回 `limit=50`、`offset=0`。
- [ ] 翻页稳定性：连续翻页无重复/漏项（同一筛选条件下）。
- [ ] 时间窗口校验：`start_time > end_time` 时收到 `422`。
- [ ] 排序符合文档：`/v1/batches` 与 `/v1/events` 为确定性倒序。

### 3.2 Anchoring Admin APIs

- [ ] `status` 过滤有效（`RECEIVED/ANCHORING/ANCHORED/FAILED_RETRYING/DEAD_LETTER`）。
- [ ] 仅 `FAILED_RETRYING` 与 `DEAD_LETTER` 可 requeue，其他状态应返回 `409`。
- [ ] `run-once` 在不传 body 时可成功执行；传 `limit` 时范围校验为 `1..1000`。

### 3.3 Alerts 查询与动作 APIs

- [ ] 列表接口支持 `admin` 与 `regulator` 双角色访问。
- [ ] `ack` 仅允许从 `open` 进入 `acknowledged`，非法流转返回 `409`。
- [ ] `resolve` 仅允许从 `open/acknowledged` 进入 `resolved`。
- [ ] `escalate` 在状态允许时提升严重级别；到 `critical` 后再次升级返回 `409`。

### 3.4 Device/Key Admin APIs

- [ ] 重复创建设备返回 `409 device-already-exists`。
- [ ] 对不存在设备轮换密钥返回 `404 device-not-found`。
- [ ] 对已禁用设备轮换密钥返回 `409 device-disabled`。
- [ ] 重复 `key_id` 返回 `409 device-key-already-exists`。
- [ ] 设备列表分页与排序稳定：`created_at desc, id desc`，切换 `status` 过滤不丢数据。
- [ ] 设备详情返回 `active_key`、`key_count`、`last_seen_at` 字段。
- [ ] 设备密钥列表按 `activated_at desc, id desc` 排序。
- [ ] 设备审计日志按 `created_at desc, id desc` 排序。

## 4) 前端错误处理清单（401/403/404/409/422）

- [ ] `401 Unauthorized`：统一触发登录态失效流程（清 Token、跳转登录或刷新 Token）。
- [ ] `403 Forbidden`：展示无权限文案，隐藏/禁用按钮，保留页面可读内容。
- [ ] `404 Not Found`：详情页显示“资源不存在/已删除”，并提供返回列表入口。
- [ ] `409 Conflict`：展示冲突原因（优先 `detail`），提供“刷新数据后重试”操作。
- [ ] `422 Unprocessable Entity`：将后端校验错误映射到筛选区或表单字段，避免直接清空用户输入。
- [ ] Problem Details 统一适配：前端错误层至少解析 `type/title/status/detail/instance` 并打点。

## 5) 上线前就绪清单（Go-Live）

- [ ] 生产域名已加入后端 `CORS_ALLOW_ORIGINS`，并完成浏览器真实环境验证。
- [ ] 生产 `API_BASE_URL`、鉴权接入点、日志打点开关已切换到正式配置。
- [ ] 前端已对关键管理动作（requeue、disable、escalate、resolve）增加二次确认与防重复提交。
- [ ] 列表页已覆盖空态、加载态、错误态、无权限态。
- [ ] 关键接口联调记录已留档（请求/响应样例 + Trace ID）。
- [ ] 发布后回归清单已准备：批次查询、事件查询、告警动作、锚定管理、设备密钥管理。
