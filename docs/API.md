# API 文档（Traceability MVP）

> 语言 / Language: 简体中文 | [English](API.en.md)

本文档覆盖当前服务中**已实现的全部接口**，用于后端联调、测试用例编写与验收。

## 区块链锚定能力与接口稳定性声明

### 当前运行模式

- 当前默认配置为 `ANCHOR_ADAPTER=active_mock`（MVP mock 锚定），即：
  - 锚定流程与状态机完整可用；
  - 默认不要求连接真实区块链节点；
  - 仍会生成并保存锚定回执字段（`network`、`transaction_hash`、`receipt_payload`、`anchored_at`）。
- 若配置 `ANCHOR_ADAPTER=evm_contract`，系统将调用 EVM 合约写入锚定交易；需提供 `ANCHOR_EVM_RPC_URL`、`ANCHOR_EVM_CONTRACT_ADDRESS` 及账户签名配置（`ANCHOR_EVM_PRIVATE_KEY` 或 `ANCHOR_EVM_ACCOUNT_ADDRESS`）。
- `evm_contract` 额外支持：
  - 交易恢复：已提交交易将持久化到 `anchor_submissions`，Worker 重启后可继续查询回执。
  - 最终性控制：`ANCHOR_EVM_REQUIRED_CONFIRMATIONS` 指定确认块数，并进行重组校验。
  - 费率回退：支持 EIP-1559 与 `gasPrice` 双路径，拥堵时按 `ANCHOR_EVM_FEE_BUMP_PERCENT` 逐次上调。
  - 外部签名：可通过 `ANCHOR_EVM_SIGNER_URL` 对接 KMS/HSM/签名网关，避免应用进程持有私钥。
- `evm_contract` 分阶段发布控制（Task 11）：
  - 模式：`ANCHOR_EVM_ROLLOUT_MODE=shadow|canary|full|rollback_safe`（支持 `rollback-safe` 兼容写法）。
  - Canary 分流：`ANCHOR_EVM_CANARY_PERCENT`（0-100，按事件哈希确定性分桶）。
  - 回滚开关：`ANCHOR_EVM_FORCE_ROLLBACK_SAFE=1` 时强制走安全路径（`active_mock`）且不影响 ingest 接收。
  - Canary SLO Gate 默认阈值：
    - success rate `>= 99.0%`（`ANCHOR_EVM_CANARY_MIN_SUCCESS_RATE`）
    - dead-letter rate `<= 0.5%`（`ANCHOR_EVM_CANARY_MAX_DEAD_LETTER_RATE`）
    - p95 confirmation `<= 120s`（`ANCHOR_EVM_CANARY_MAX_P95_CONFIRMATION_SECONDS`）
  - 自动中止：当阈值连续违规达到 `ANCHOR_EVM_CANARY_ABORT_AFTER_SECONDS`（默认 600 秒）时，自动切回 `rollback_safe`。
  - 评估窗口：`ANCHOR_EVM_CANARY_WINDOW_SECONDS`（默认 600 秒）。

### 对前后端的接口承诺（保留且稳定）

- 以下接口与关键字段在“未接真实链”阶段仍保持可用，不因是否上链而移除：
  - `GET /admin/anchoring/tasks`
  - `POST /admin/anchoring/tasks/{ingest_request_id}/requeue`
  - `POST /admin/anchoring/run-once`
  - `GET /v1/trace/{batch_id}` 中的 `anchor.status`、`anchor.transaction_hash`
  - `POST /contracts/trace-events/validate` 中的 `canonical_hash`

### 未来接入真实链时的兼容原则

- 优先通过新增/替换锚定适配器（`ANCHOR_ADAPTER`）实现，不破坏现有 API 契约。
- `reserved_stub` 为未来扩展占位，MVP 阶段默认不启用。

## 基本约定

## Compatibility Layer Deprecation and Closure Gate

- 兼容层接口：`POST /api/cherry/telemetry`、`GET /v1/events/recent`、`GET /v1/trace/{batch_id}/public`。
- 兼容层响应统一带以下弃用头：
  - `Deprecation: true`
  - `Sunset: Wed, 30 Sep 2026 00:00:00 GMT`
  - `Link: <https://example.com/runbooks/compatibility-closure>; rel="deprecation"; type="text/markdown"`
  - `X-Compat-Deprecated: true`
  - `X-Compat-Replacement: ...`（按端点给出 canonical 替代路径）
  - `X-Compat-Exit-Criteria: 2-releases,14-consecutive-days,<1%-traffic`
- 兼容流量指标：`traceability_compat_requests_total{endpoint,method,status}`。
- 关闭开关：`COMPAT_CLOSURE_ENABLED=1`。仅在退出条件满足时才会真正禁用兼容路由。
- 退出条件：至少 2 个发布版本 + 连续 14 天每天兼容流量占比 `<1%`。
- CI 校验脚本：`python -X utf8 scripts/check_compat_exit_criteria.py`。
- 运行指引：见 `docs/COMPATIBILITY_CLOSURE_RUNBOOK.md`。

- Base URL：`http://localhost:18941`
- 通用响应头：`X-Trace-Id`（可由客户端传入；未传时服务端自动生成并回传）
- 时间格式：ISO 8601（UTC），示例 `2026-02-10T04:30:00Z`

## CORS 配置（前端接入）

- 环境变量：`CORS_ALLOW_ORIGINS`
  - 以英文逗号分隔多个源（Origin），示例：`https://app.example.com,https://ops.example.com`
  - 当前默认值（本地前端）：`http://localhost:3000,http://127.0.0.1:3000`
  - 若变量未设置或解析后为空，服务端会回退到上述默认值
- 当前 CORS 中间件配置：
  - `allow_origins = CORS_ALLOW_ORIGINS` 解析结果
  - `allow_methods = ["*"]`
  - `allow_headers = ["*"]`
- 前端需确认部署域名已加入 `CORS_ALLOW_ORIGINS`，否则浏览器会在预检（`OPTIONS`）或正式请求阶段拦截。
- 当前鉴权采用 `Authorization: Bearer <JWT>` 请求头，不依赖 Cookie 凭证。

## 认证与角色

- 认证方式：`Authorization: Bearer <JWT>`
- JWT 核心声明：
  - `sub`：主体（必填）
  - `iss`：签发方（需匹配服务端配置）
  - `roles`：角色（支持字符串或字符串数组）
  - `exp`：过期时间（可选，若存在则必须未过期）
- 支持角色：`admin`、`regulator`
- 鉴权规则：
  - `public`：无需 JWT
  - `admin`：仅 `admin`
  - `admin | regulator`：`admin` 或 `regulator` 均可

### 前端 Token/角色调用期望

- 仅对需要鉴权的路由携带 Bearer Token（例如 `/admin/*`、`/v1/alerts*`）；`public` 路由可匿名调用。
- JWT 必须满足后端校验规则：
  - `alg=HS256`
  - `iss` 与服务端配置一致（`AUTH_JWT_ISSUER`，默认 `traceability-auth`）
  - `sub` 为非空字符串
  - `roles` 支持字符串或字符串数组（例如 `"admin"` 或 `["regulator"]`）
  - 若提供 `exp`，则必须未过期
- 前端可据状态码快速定位问题：
  - `401 Unauthorized`：Token 缺失/格式错误/签名错误/签发方不匹配/过期
  - `403 Forbidden`：Token 有效，但角色不满足路由要求

## 错误响应约定

除少量基础设施错误外，业务与校验错误统一使用 RFC9457 风格 Problem Details（本项目实现为 RFC9457-like）：

```json
{
  "type": "https://example.com/problems/<problem-type>",
  "title": "Conflict",
  "status": 409,
  "detail": "Idempotency-Key was reused with a different payload.",
  "instance": "/v1/events"
}
```

字段说明：

- `type`：问题类型 URI
- `title`：错误标题
- `status`：HTTP 状态码
- `detail`：可读错误细节
- `instance`：触发错误的请求路径

### 前端错误处理建议（实践版）

- 统一解析 Problem Details 字段：`type`、`title`、`status`、`detail`、`instance`。
- 推荐按状态码做 UX 分流：
  - `401`：清理本地登录态并跳转登录/刷新 Token。
  - `403`：展示“无权限”并禁用当前操作入口。
  - `404`：资源不存在；详情页展示“数据不存在”，列表页可触发刷新。
  - `409`：并发/状态冲突；提示“状态已变化”，建议刷新后重试。
  - `422`：参数或请求体校验失败；保留用户输入并高亮错误来源。
- 兜底策略：若响应不是 Problem Details，保留原始报文（用于排障）并展示通用错误提示。

## 分页与排序约定（前端列表页）

- 列表接口统一返回分页元信息：`total`、`limit`、`offset`。
- 分页参数约定：
  - `limit` 默认 `50`，通常范围 `1..200`
  - `offset` 默认 `0`，最小 `0`
- 前端建议：
  - 所有列表页以 `offset + limit < total` 判断“是否还有下一页”
  - 切换筛选条件时将 `offset` 重置为 `0`

### 已实现列表接口的确定性排序

| 路径 | 排序语义 | 稳定性补充 |
| --- | --- | --- |
| `GET /v1/batches` | `end_time` 倒序 | 并列时按 `batch_id` 升序，再按 `device_id` 升序 |
| `GET /v1/events` | `timestamp` 倒序 | 并列时按 `id` 倒序 |
| `GET /v1/alerts` | `raised_at` 倒序 | 并列时按 `id` 倒序（响应含 `order="newest_first"`） |
| `GET /admin/anchoring/tasks` | `ingest_request_id` 倒序 | 同筛选条件下可稳定翻页 |
| `GET /v1/devices` | `created_at` 倒序 | 并列时按 `id` 倒序 |
| `GET /admin/devices/{device_id}/keys` | `activated_at` 倒序 | 并列时按 `id` 倒序 |
| `GET /admin/devices/{device_id}/audits` | `created_at` 倒序 | 并列时按 `id` 倒序 |

---

## 接口总览

| 方法 | 路径 | 认证 |
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

---

## 1) Health / Contracts / Ingest / Quality

### GET `/health`

- 认证：`public`
- 请求：
  - Headers：可选 `X-Trace-Id`
  - Query：无
  - Body：无
- 成功响应：`200 OK`

```json
{
  "status": "ok"
}
```

- 常见错误：无业务错误定义（通常不会返回 Problem Details）

### POST `/contracts/trace-events/validate`

- 认证：`public`
- 请求：
  - Headers：`Content-Type: application/json`
  - Query：无
  - Body（最小实用字段）：

```json
{
  "version": "1.0.0",
  "device_id": "device-001",
  "batch_id": "batch-2026-02-10",
  "timestamp": "2026-02-10T02:00:00Z",
  "sensor_payload": {
    "temperature_c": 4.2,
    "humidity_pct": 73.0,
    "status": "stable"
  },
  "signature_envelope": {
    "algorithm": "HMAC_SHA256",
    "signature": "<签名字符串>",
    "key_id": "factory-key-1"
  }
}
```

- 成功响应：`200 OK`

```json
{
  "status": "valid",
  "canonical_hash": "<sha256-hex>"
}
```

- 常见错误：
  - `422 Unprocessable Entity`：字段缺失/类型不符

```json
{
  "type": "https://example.com/problems/validation-error",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "Request payload does not match the trace event contract.",
  "instance": "/contracts/trace-events/validate"
}
```

### POST `/v1/events`

- 认证：`public`
- 请求：
  - Headers：
    - `Idempotency-Key`（必填）
    - `Content-Type: application/json`
  - Query：无
  - Body：与 `TraceEvent` 合同一致（同上）
- 成功响应：`202 Accepted`

```json
{
  "event_id": 1,
  "ingest_status": "RECEIVED"
}
```

- 常见错误：
  - `401 Unauthorized`：签名校验失败（`algorithm` 非 `HMAC_SHA256`、`key_id` 未配置、签名不匹配等）

```json
{
  "type": "https://example.com/problems/signature-mismatch",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Signature verification failed for the supplied trace event.",
  "instance": "/v1/events"
}
```

  - `409 Conflict`：同一 `Idempotency-Key` 对应不同 payload

```json
{
  "type": "https://example.com/problems/idempotency-conflict",
  "title": "Conflict",
  "status": 409,
  "detail": "Idempotency-Key was reused with a different payload.",
  "instance": "/v1/events"
}
```

  - `422 Unprocessable Entity`：Body 校验失败

### POST `/v1/quality/grade`

- 认证：`public`
- 请求：
  - Headers：`Content-Type: application/json`
  - Query：无
  - Body（最小实用字段）：

```json
{
  "temperature_c": 5.0,
  "humidity_pct": 72.0
}
```

- 成功响应：`200 OK`

```json
{
  "grade": "A",
  "score": 4,
  "max_score": 4,
  "reasons": [
    "temperature_c is within ideal range [2.0, 8.0].",
    "humidity_pct is within ideal range [60.0, 85.0]."
  ],
  "threshold_context": {
    "temperature_c": {
      "ideal": {
        "min": 2.0,
        "max": 8.0
      },
      "warning": {
        "min": 0.0,
        "max": 10.0
      }
    },
    "humidity_pct": {
      "ideal": {
        "min": 60.0,
        "max": 85.0
      },
      "warning": {
        "min": 50.0,
        "max": 90.0
      }
    },
    "grade_thresholds": {
      "A": 4,
      "B": 2
    },
    "bands": {
      "temperature_c": "ideal",
      "humidity_pct": "ideal"
    }
  }
}
```

- 常见错误：
  - `422 Unprocessable Entity`：`humidity_pct` 超出 `0..100` 或字段类型不合法

---

## 2) Admin 策略 / 设备 / 密钥管理

### POST `/admin/policies/{policy_id}/activate`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`policy_id`（字符串）
  - Query：无
  - Body：无
- 成功响应：`200 OK`

```json
{
  "policy_id": "policy-123",
  "status": "activated",
  "audit_id": 1
}
```

- 常见错误：
  - `401 Unauthorized`：缺失/非法 Bearer Token
  - `403 Forbidden`：角色不满足（例如只有 `regulator`）

### POST `/admin/devices`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>` + `Content-Type: application/json`
  - Query：无
  - Body（最小实用字段）：

```json
{
  "device_id": "device-001",
  "display_name": "Line 1 Sensor"
}
```

- 成功响应：`201 Created`

```json
{
  "device_id": "device-001",
  "status": "active",
  "audit_id": 2
}
```

- 常见错误：
  - `409 Conflict`：`device_id` 已存在

```json
{
  "type": "https://example.com/problems/device-already-exists",
  "title": "Conflict",
  "status": 409,
  "detail": "A managed device with this device_id already exists.",
  "instance": "/admin/devices"
}
```

  - `401` / `403`：鉴权失败

### POST `/admin/devices/{device_id}/keys`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>` + `Content-Type: application/json`
  - Path：`device_id`（字符串）
  - Body：

```json
{
  "key_id": "device-001-key-v2",
  "algorithm": "ED25519",
  "public_key": "ed25519-public-key-v2"
}
```

- 成功响应：`201 Created`

```json
{
  "device_id": "device-001",
  "key_id": "device-001-key-v2",
  "algorithm": "ED25519",
  "status": "active",
  "retired_key_ids": [
    "device-001-key-v1"
  ],
  "audit_id": 3
}
```

- 常见错误：
  - `404 Not Found`：设备不存在（`device-not-found`）
  - `409 Conflict`：设备已禁用（`device-disabled`）
  - `409 Conflict`：`key_id` 已存在（`device-key-already-exists`）
  - `401` / `403`：鉴权失败

### POST `/admin/devices/{device_id}/disable`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>` + `Content-Type: application/json`
  - Path：`device_id`（字符串）
  - Body（可选字段）：

```json
{
  "reason": "device decommissioned"
}
```

- 成功响应：`200 OK`

```json
{
  "device_id": "device-001",
  "status": "disabled",
  "retired_key_ids": [
    "device-001-key-v2"
  ],
  "audit_id": 4
}
```

- 常见错误：
  - `404 Not Found`：设备不存在（`device-not-found`）
  - `401` / `403`：鉴权失败

### GET `/admin/devices/{device_id}`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`device_id`（字符串）
- 成功响应：`200 OK`

```json
{
  "device_id": "device-001",
  "name": "Line 1 Sensor",
  "status": "active",
  "last_seen_at": "2026-02-11T09:30:00Z",
  "created_at": "2026-02-11T09:00:00Z",
  "key_count": 2,
  "signature_failures_last_24h": 1,
  "latest_signature_failure_reason": "signature_mismatch",
  "online_status_explanation": "Offline: last event at 2026-02-11T09:30:00Z is older than the 15-minute threshold.",
  "active_key": {
    "key_id": "device-001-key-v2",
    "algorithm": "HMAC_SHA256",
    "status": "active",
    "activated_at": "2026-02-11T09:10:00Z"
  }
}
```

- 常见错误：
  - `404 Not Found`：设备不存在（`device-not-found`）
  - `401` / `403`：鉴权失败

字段说明（设备详情可观测性）：

- `signature_failures_last_24h`：过去 24 小时该设备签名校验失败次数。
- `latest_signature_failure_reason`：最近一次签名失败原因（如 `signature_mismatch`）。
- `online_status_explanation`：后端给出的在线/离线判定解释（含阈值或停用原因）。

### GET `/admin/devices/{device_id}/keys`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`device_id`（字符串）
- 成功响应：`200 OK`

```json
{
  "device_id": "device-001",
  "items": [
    {
      "key_id": "device-001-key-v2",
      "algorithm": "HMAC_SHA256",
      "status": "active",
      "activated_at": "2026-02-11T09:10:00Z",
      "retired_at": null
    }
  ]
}
```

- 常见错误：
  - `404 Not Found`：设备不存在（`device-not-found`）
  - `401` / `403`：鉴权失败

### GET `/admin/devices/{device_id}/audits`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`device_id`（字符串）
- 成功响应：`200 OK`

```json
{
  "device_id": "device-001",
  "items": [
    {
      "audit_id": 101,
      "actor": "admin-user",
      "action": "admin.device.disable",
      "target": "device:device-001",
      "metadata": {
        "reason": "device decommissioned",
        "retired_key_ids": ["device-001-key-v2"]
      },
      "created_at": "2026-02-11T10:00:00Z"
    }
  ]
}
```

- 常见错误：
  - `404 Not Found`：设备不存在（`device-not-found`）
  - `401` / `403`：鉴权失败

### GET `/v1/devices`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Query：
    - `limit`：默认 `50`，范围 `1..200`
    - `offset`：默认 `0`
    - `status`：可选（`active` / `disabled`）
  - Body：无
- 成功响应：`200 OK`

```json
{
  "total": 2,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "device_id": "device-001",
      "name": "Line 1 Sensor",
      "status": "active",
      "last_seen_at": "2026-02-11T09:30:00Z",
      "created_at": "2026-02-11T09:00:00Z"
    }
  ]
}
```

- 常见错误：
  - `401` / `403`：鉴权失败
  - `422`：`limit/offset` 越界或类型错误

---

## 3) Query APIs（`/v1/batches`、`/v1/events`）

### GET `/v1/batches`

- 认证：`public`
- 请求：
  - Headers：可选 `X-Trace-Id`
  - Query：
    - `limit`：默认 `50`，范围 `1..200`
    - `offset`：默认 `0`，最小 `0`
    - `device_id`：可选
    - `start_time`：可选（ISO 8601）
    - `end_time`：可选（ISO 8601）
  - Body：无
- 成功响应：`200 OK`

```json
{
  "total": 3,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "batch_id": "batch-c",
      "device_id": "device-2",
      "event_count": 1,
      "start_time": "2026-02-10T04:00:00Z",
      "end_time": "2026-02-10T04:00:00Z"
    }
  ]
}
```

- 常见错误：
  - `422`：`limit/offset` 越界或类型错误
  - `422`：`start_time > end_time`（`invalid-query-parameter`）

### GET `/v1/events`

- 认证：`public`
- 请求：
  - Headers：可选 `X-Trace-Id`
  - Query：
    - `limit`：默认 `50`，范围 `1..200`
    - `offset`：默认 `0`
    - `batch_id`：可选
    - `device_id`：可选
    - `ingest_status`：可选（例如 `RECEIVED`、`ANCHORED`、`FAILED_RETRYING`）
    - `start_time` / `end_time`：可选（ISO 8601）
  - Body：无
- 成功响应：`200 OK`

```json
{
  "total": 3,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": 12,
      "batch_id": "batch-a",
      "device_id": "device-1",
      "timestamp": "2026-02-10T03:00:00Z",
      "ingest_status": "ANCHORED"
    }
  ]
}
```

- 常见错误：
  - `422`：参数校验失败（范围、时间格式、时间窗口反转）

---

## 4) Trace API

### GET `/v1/trace/{batch_id}`

- 认证：`public`
- 请求：
  - Headers：可选 `X-Trace-Id`
  - Path：`batch_id`
  - Query：无
  - Body：无
- 成功响应：`200 OK`

```json
{
  "batch_id": "batch-trace-001",
  "timeline_order": "oldest_first",
  "timeline": [
    {
      "event_id": 101,
      "timestamp": "2026-02-10T04:00:00Z",
      "ingest_status": "ANCHORED",
      "anchor": {
        "status": "ANCHORED",
        "transaction_hash": "0xabc123"
      },
      "quality_grade": "B",
      "alert_snapshot": {
        "total": 2,
        "open": 1,
        "high_open": 1
      }
    }
  ]
}
```

- 常见错误：
  - `404 Not Found`：批次不存在（`trace-batch-not-found`）

```json
{
  "type": "https://example.com/problems/trace-batch-not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "No trace timeline found for batch_id 'batch-not-found'.",
  "instance": "/v1/trace/batch-not-found"
}
```

---

## 5) Alerts 查询与动作 API

### GET `/v1/alerts`

- 认证：`admin | regulator`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Query：
    - `limit`：默认 `50`，范围 `1..200`
    - `offset`：默认 `0`
  - Body：无
- 成功响应：`200 OK`

```json
{
  "order": "newest_first",
  "total": 3,
  "limit": 50,
  "offset": 0,
  "alerts": [
    {
      "id": 7,
      "event_id": 12,
      "alert_type": "ANCHOR_DEAD_LETTER",
      "severity": "critical",
      "status": "open",
      "message": "moved to dead letter",
      "raised_at": "2026-02-10T09:10:00Z",
      "resolved_at": null
    }
  ]
}
```

- 常见错误：
  - `401`：无 Token / Token 非法
  - `403`：角色不满足

### POST `/v1/alerts/{alert_id}/ack`

- 认证：`admin | regulator`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`alert_id`（整数）
  - Body：无
- 成功响应：`200 OK`

```json
{
  "id": 7,
  "status": "acknowledged",
  "severity": "medium",
  "resolved_at": null,
  "audit_id": 11
}
```

- 常见错误：
  - `404`：告警不存在（`alert-not-found`）
  - `409`：状态流转不允许（`alert-transition-conflict`）
  - `401` / `403`：鉴权失败

### POST `/v1/alerts/{alert_id}/resolve`

- 认证：`admin | regulator`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`alert_id`（整数）
  - Body：无
- 成功响应：`200 OK`

```json
{
  "id": 7,
  "status": "resolved",
  "severity": "medium",
  "resolved_at": "2026-02-10T09:35:00Z",
  "audit_id": 12
}
```

- 常见错误：
  - `404`：告警不存在
  - `409`：仅允许从 `open` / `acknowledged` 进入 `resolved`
  - `401` / `403`：鉴权失败

### POST `/v1/alerts/{alert_id}/escalate`

- 认证：`admin | regulator`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`alert_id`（整数）
  - Body：无
- 成功响应：`200 OK`

```json
{
  "id": 7,
  "status": "acknowledged",
  "severity": "high",
  "resolved_at": null,
  "audit_id": 13
}
```

- 常见错误：
  - `404`：告警不存在
  - `409`：
    - 当前状态不可升级（例如已 `resolved`）
    - 严重级别已到上限 `critical`
  - `401` / `403`：鉴权失败

---

## 6) Anchoring Admin APIs

### GET `/admin/anchoring/tasks`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Query：
    - `status`（必填）：`RECEIVED` / `ANCHORING` / `ANCHORED` / `FAILED_RETRYING` / `DEAD_LETTER`
    - `limit`：默认 `50`，范围 `1..200`
    - `offset`：默认 `0`
    - `batch_id`：可选
    - `device_id`：可选
  - Body：无
- 成功响应：`200 OK`

```json
{
  "total": 2,
  "limit": 10,
  "offset": 0,
  "items": [
    {
      "ingest_request_id": 9,
      "event_id": 18,
      "batch_id": "batch-a",
      "device_id": "device-002",
      "status": "FAILED_RETRYING",
      "retry_count": 2,
      "last_error": "adapter unavailable",
      "created_at": "2026-02-10T11:01:00Z"
    }
  ]
}
```

- 常见错误：
  - `401` / `403`：鉴权失败
  - `422`：查询参数校验失败

### POST `/admin/anchoring/tasks/{ingest_request_id}/requeue`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>`
  - Path：`ingest_request_id`（整数）
  - Query：无
  - Body：无
- 成功响应：`200 OK`

```json
{
  "ingest_request_id": 9,
  "status": "RECEIVED",
  "retry_count": 0,
  "audit_id": 21
}
```

- 常见错误：
  - `404`：任务不存在（`anchoring-task-not-found`）
  - `409`：当前状态不可重入队（仅 `FAILED_RETRYING` / `DEAD_LETTER` 可重入队）
  - `401` / `403`：鉴权失败

### POST `/admin/anchoring/run-once`

- 认证：`admin`
- 请求：
  - Headers：`Authorization: Bearer <JWT>` + `Content-Type: application/json`
  - Query：无
  - Body（可选）：

```json
{
  "limit": 1
}
```

> 说明：Body 可省略；省略时服务内部使用默认上限（当前实现为 100）。

- 成功响应：`200 OK`

```json
{
  "processed": 1,
  "limit": 1,
  "audit_id": 22
}
```

- 常见错误：
  - `401` / `403`：鉴权失败
  - `422`：`limit` 不在允许范围（`1..1000`）

---

## 7) Metrics

### GET `/metrics`

- 认证：`public`
- 请求：
  - Headers：无强制要求
  - Query：无
  - Body：无
- 成功响应：`200 OK`
  - `Content-Type: text/plain; version=0.0.4; charset=utf-8`
  - 示例片段：

```text
traceability_ingest_requests_total{outcome="accepted"} 12
traceability_anchoring_runs_total{outcome="anchored"} 12
traceability_ingest_latency_seconds_bucket{le="0.1"} 12
traceability_anchoring_latency_seconds_bucket{le="0.1"} 12
```

- 常见错误：无业务错误定义

---

## 附：常用调用示例

```bash
# 健康检查
curl -i http://localhost:18941/health

# 合同校验
curl -i -X POST http://localhost:18941/contracts/trace-events/validate \
  -H "Content-Type: application/json" \
  -d '{"version":"1.0.0","device_id":"device-001","batch_id":"batch-2026-02-10","timestamp":"2026-02-10T02:00:00Z","sensor_payload":{"temperature_c":4.2,"humidity_pct":73.0},"signature_envelope":{"algorithm":"HMAC_SHA256","signature":"<sig>","key_id":"factory-key-1"}}'

# 事件写入（需 Idempotency-Key）
curl -i -X POST http://localhost:18941/v1/events \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: idem-001" \
  -d '{"version":"1.0.0","device_id":"device-001","batch_id":"batch-2026-02-10","timestamp":"2026-02-10T02:00:00Z","sensor_payload":{"temperature_c":4.2,"humidity_pct":73.0},"signature_envelope":{"algorithm":"HMAC_SHA256","signature":"<sig>","key_id":"factory-key-1"}}'

# Admin 接口示例
curl -i -X POST http://localhost:18941/admin/devices \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"device-001","display_name":"Line 1 Sensor"}'

# Alerts 查询（admin/regulator）
curl -i "http://localhost:18941/v1/alerts?limit=50&offset=0" \
  -H "Authorization: Bearer <jwt>"

# Prometheus 指标
curl -i http://localhost:18941/metrics
```
