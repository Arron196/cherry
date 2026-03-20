# CONTRACT V1 迁移规范

> 语言 / Language: 简体中文 | [English](CONTRACT_V1_MIGRATION.md)

## 目标与范围

本文档冻结 Contract v1 的 canonical 基线与迁移规则，供前端、后端、硬件调用方统一执行。

本任务范围：

- 冻结 ingest、public trace、stats 的 canonical 基线。
- 定义确定性的 compatibility 到 canonical 字段映射。
- 定义 FE/HW 调用端点到 canonical 与 compatibility 路由的映射。
- 定义 compatibility 弃用时间线、客观退出条件、回滚说明。

## Canonical 基线

### Ingest TraceEvent 基线（冻结）

事实来源：`app/domain/contracts/trace_event.py`（`TraceEvent`、`SignatureEnvelope`、`SensorPayload`）。

Canonical 必填字段：

- `version`
- `device_id`
- `batch_id`
- `timestamp`
- `sensor_payload`
- `signature_envelope`

Canonical 可选扩展字段：

- `co2_ppm`
- `vibration_g`
- `supply_chain_stage`

### Public Trace 基线（冻结）

事实来源：`app/api/public_trace.py`（`PublicTraceResponse`）。

Canonical 顶层键（冻结）：

- `batch_info`
- `timeline`
- `stage_environments`
- `quality`
- `blockchain_anchor`

### Stats 基线（冻结）

事实来源：`app/api/stats.py`。

Canonical stats 端点：

- `GET /v1/stats/overview`
- `GET /v1/stats/temperature-trend`
- `GET /v1/stats/quality-distribution`
- `GET /v1/stats/stage-distribution`

### Signature Policy 基线（冻结）

- Canonical 签名算法 ID：`ECDSA_P256_SHA256`。
- Compatibility 别名处理：`ECDSA` 只允许通过显式归一化映射到 `ECDSA_P256_SHA256`。
- 别名接受仅属于迁移期行为，不是第二种 canonical 算法。

## Canonical 与 Compatibility 字段映射

Compatibility 输入基线：`app/api/compat.py`（`CherryTelemetryPayload` 到 canonical `TraceEvent`）。

| Compatibility 字段 | Canonical 字段 | 规则 |
| --- | --- | --- |
| `seq` | `sensor_payload.seq` | 整数原样复制 |
| `ts` | `timestamp` | Unix 秒转 UTC ISO8601，缺失时用 ingest 服务端时间 |
| `temp_c` | `sensor_payload.temperature_c` | 浮点原样复制 |
| `hum_rh` | `sensor_payload.humidity_pct` | 浮点原样复制 |
| `co2` | `sensor_payload.co2_ppm`、`co2_ppm` | 存在时复制 |
| `vibration` | `sensor_payload.vibration`、`vibration_g` 回退 | 若 `vibration_g` 缺失，`true->1.0`，`false->0.0` |
| `vibration_g` | `vibration_g` | 存在时复制 |
| `digest` | `sensor_payload.digest` | 存在时复制 |
| `device_id` | `device_id` | 字符串原样复制 |
| `batch_id` | `batch_id` | 字符串原样复制 |
| `stage` | `supply_chain_stage` | 允许值：`harvest|storage|transport|retail`，否则默认 `transport` |
| `key_id` | `signature_envelope.key_id` | 字符串原样复制 |
| `signature` | `signature_envelope.signature` | 缺失时回退到 `compat-signature`（当前 compat 行为） |
| implicit compat algorithm | `signature_envelope.algorithm` | 将 `ECDSA` 归一化为 `ECDSA_P256_SHA256` |

## 端点映射表（FE/HW 到 Canonical 与 Compat）

| 调用方 | 来源 | 调用端点 | Canonical 后端路由 | Compat 路由 | 状态 |
| --- | --- | --- | --- | --- | --- |
| FE | `frontend/src/lib/services.ts` | `/v1/auth/login` | `/v1/auth/login` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/health` | `/health` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/contracts/trace-events/validate` | `/contracts/trace-events/validate` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/events` | `/v1/events` | `/api/cherry/telemetry` | Canonical + compat bridge |
| FE | `frontend/src/lib/services.ts` | `/v1/quality/grade` | `/v1/quality/grade` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/batches` | `/v1/batches` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/events` | `/v1/events` | `/v1/events/recent` | Canonical query + compat helper |
| FE | `frontend/src/lib/services.ts` | `/v1/trace/{batch_id}` | `/v1/trace/{batch_id}` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/trace/{batch_id}/public` | `/v1/public/trace/{batch_id}` | `/v1/trace/{batch_id}/public` | Canonical + alias compatibility |
| FE | `frontend/src/lib/services.ts` | `/v1/batches/{batch_id}/stages` | `/v1/batches/{batch_id}/stages` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/batches/{batch_id}/sensors` | `/v1/batches/{batch_id}/sensors` | N/A | Task 2 已实现 |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/overview` | `/v1/stats/overview` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/temperature-trend` | `/v1/stats/temperature-trend` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/quality-distribution` | `/v1/stats/quality-distribution` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/stats/stage-distribution` | `/v1/stats/stage-distribution` | N/A | Canonical |
| FE | `frontend/src/lib/services.ts` | `/v1/events/recent` | `/v1/events` | `/v1/events/recent` | Compat helper 待退出 |
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
| HW | `hardware/cherry/Core/Src/cherry_hw.c` | `/api/cherry/telemetry` | `/v1/events` | `/api/cherry/telemetry` | Compat ingress 映射到 canonical schema |
| HW/Simulator | `simulator/stm32_device.py`, `simulator/gateway.py` | `/v1/events` | `/v1/events` | `/api/cherry/telemetry` | Canonical 优先，compat 兜底 |

## Endpoint Map

FE/HW 使用的 canonical 路由集合：

- `/v1/events`、`/v1/batches`、`/v1/trace/{batch_id}`
- `/v1/public/trace/{batch_id}`、`/v1/batches/{batch_id}/stages`、`/v1/batches/{batch_id}/sensors`
- `/v1/stats/overview`、`/v1/stats/temperature-trend`、`/v1/stats/quality-distribution`、`/v1/stats/stage-distribution`
- `/v1/alerts`、`/v1/alerts/{alert_id}/ack`、`/v1/alerts/{alert_id}/resolve`、`/v1/alerts/{alert_id}/escalate`
- `/v1/auth/login`、`/v1/quality/grade`、`/contracts/trace-events/validate`、`/health`、`/metrics`
- `/admin/anchoring/tasks`、`/admin/anchoring/tasks/{ingest_request_id}/requeue`、`/admin/anchoring/run-once`
- `/admin/policies/{policy_id}/activate`、`/admin/devices`、`/admin/devices/{device_id}`、`/admin/devices/{device_id}/keys`、`/admin/devices/{device_id}/disable`、`/admin/devices/{device_id}/audits`、`/v1/devices`

迁移期保留的 compatibility 路由集合：

- `/api/cherry/telemetry`
- `/v1/trace/{batch_id}/public`
- `/v1/events/recent`

## OpenAPI 路径与形状要求

本节定义 FE/HW 消费路由在 OpenAPI 与运行时的最小契约要求。

| Path | Method | 形状要求 |
| --- | --- | --- |
| `/v1/events` | `POST` | 必须要求 `Idempotency-Key`，请求体匹配 `TraceEvent`，响应包含 `event_id`、`ingest_status` |
| `/v1/events` | `GET` | 分页响应包含 `total`、`limit`、`offset`、`items[]` |
| `/contracts/trace-events/validate` | `POST` | 响应包含 `status` 与 `canonical_hash` |
| `/v1/quality/grade` | `POST` | 响应包含 `grade`、`score`、`max_score`、`reasons`、`threshold_context` |
| `/health` | `GET` | 响应包含 `status` |
| `/v1/auth/login` | `POST` | 响应包含 `access_token`、`token_type`、`expires_in`、`role` |
| `/v1/batches` | `GET` | 返回批次摘要分页结构 |
| `/v1/trace/{batch_id}` | `GET` | 返回追溯时间线与锚定、质量快照 |
| `/v1/public/trace/{batch_id}` | `GET` | 返回 `batch_info`、`timeline`、`stage_environments`、`quality`、`blockchain_anchor` |
| `/v1/trace/{batch_id}/public` | `GET` | 与 `/v1/public/trace/{batch_id}` 契约等价 |
| `/v1/batches/{batch_id}/stages` | `GET` | 返回阶段列表和事件级阶段明细 |
| `/v1/batches/{batch_id}/sensors` | `GET` | 返回批次传感器历史 |
| `/v1/stats/overview` | `GET` | 返回总览与分布字段 |
| `/v1/stats/temperature-trend` | `GET` | 返回趋势点列表与周期信息 |
| `/v1/stats/quality-distribution` | `GET` | 返回质量分布列表与总数 |
| `/v1/stats/stage-distribution` | `GET` | 返回阶段分布列表与总数 |
| `/v1/events/recent` | `GET` | 迁移期 compat helper，仅迁移窗口内保留 |
| `/v1/alerts` | `GET` | 返回告警列表和分页元信息 |
| `/v1/alerts/{alert_id}/ack` | `POST` | 返回状态流转结果 |
| `/v1/alerts/{alert_id}/resolve` | `POST` | 返回 resolved 状态结果 |
| `/v1/alerts/{alert_id}/escalate` | `POST` | 返回升级后的严重级别结果 |
| `/admin/anchoring/tasks` | `GET` | 返回锚定任务分页列表 |
| `/admin/anchoring/tasks/{ingest_request_id}/requeue` | `POST` | 返回 `ingest_request_id`、`status`、`retry_count`、`audit_id` |
| `/admin/anchoring/run-once` | `POST` | 返回 `processed`、`limit`、`audit_id` |
| `/admin/policies/{policy_id}/activate` | `POST` | 返回激活状态与 `audit_id` |
| `/admin/devices` | `POST` | 返回设备创建结果及可选初始密钥信息 |
| `/v1/devices` | `GET` | 返回托管设备分页列表 |
| `/admin/devices/{device_id}` | `GET` | 返回设备详情与 active key、观测字段 |
| `/admin/devices/{device_id}/keys` | `GET` | 返回 `items` 密钥列表包裹结构 |
| `/admin/devices/{device_id}/keys` | `POST` | 返回密钥轮换结果与 `retired_key_ids` |
| `/admin/devices/{device_id}/disable` | `POST` | 返回停用结果、退役密钥与审计记录 |
| `/admin/devices/{device_id}/audits` | `GET` | 返回 `items` 审计日志包裹结构 |
| `/metrics` | `GET` | 返回 Prometheus 文本格式 |
| `/api/cherry/telemetry` | `POST` | Compat ingest，映射到 canonical `TraceEvent` 并返回 accepted/status |

## Compatibility 弃用时间线

涉及端点：`/api/cherry/telemetry`、`/v1/trace/{batch_id}/public`、`/v1/events/recent`。

时间线：

1. Release N：标记 compatibility 路由为 deprecated，补充 telemetry 标签与迁移指引。
2. Release N+1：继续保留路由，观察残余流量，阻止新调用方上车 compat-only 路径。
3. 最早移除版本：N+2，且必须满足 Exit Criteria。

运行参考：

- Runbook：`docs/COMPATIBILITY_CLOSURE_RUNBOOK.md`
- Gate 检查脚本：`scripts/check_compat_exit_criteria.py`

锁定策略：弃用窗口固定为 `2 releases + >=14 consecutive days with <1% compat traffic`。

## Exit Criteria

兼容层移除前必须同时满足：

1. 自弃用开始至少经历 2 个发布版本。
2. 至少连续 14 天，三条 compatibility 路由总流量占比每天都 `<1%`。
3. Compatibility 路由 5xx 比例 <= 0.5%，且不比对应 canonical 路由高出 0.2 个百分点以上。
4. `frontend/src/lib/services.ts` 中无页面路径仅依赖 compatibility-only 行为。
5. 硬件路径已切换到 canonical `/v1/events`，或通过已验证的适配器输出 canonical 等价载荷。

## 回滚说明

若 canary 迁移指标回退或 compatibility 移除引发契约破坏：

- 立即保留或恢复 compatibility 路由，把调用方导回最后已知稳定适配器路径。
- 保持 canonical 契约不变，不做紧急 schema 改动，通过流量路由与配置完成回滚。
- 保留弃用 telemetry，便于量化回滚影响。
- 仅在 contract guard 与本规范验证器全绿后再进入下一轮迁移。

## Skill relevance evaluation

- `playwright`: 不相关（无浏览器任务）
- `frontend-ui-ux`: 不相关（无 UI 设计/样式任务）
- `git-master`: 不相关（无 git 操作请求）
- `dev-browser`: 不相关（无浏览器自动化任务）
