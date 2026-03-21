# Cherry 项目技术实现详解（分段撰写）

> 文档方式：按要求“每次写一段”，本文件持续追加。  
> 当前进度：第 1 段（已重写为实现细节级，不是条目枚举）。

---

## 第 1 段：系统总体架构与端到端数据流（实现细节版）

本段目标不是“列模块名”，而是解释系统在代码层如何协作：

- 请求如何进入系统并决定是否挂载兼容路由
- 兼容上报如何被映射为 canonical 事件并参与验签
- 锚定状态机如何推进、重试、降级与回滚
- compat 退场如何被量化门控，而不是人为下线
- 指标如何覆盖“决策、结果、延迟”三个维度

---

### 1.1 应用启动时的“路由拓扑决策”不是静态的

在 `app/main.py` 中，路由注册并不是一次性固定表；兼容路由是否加入由启动时决策决定：

1. 启动时调用 `evaluate_compat_closure_decision()`。
2. 若 `include_compat_router == True`，才执行 `app.include_router(compat_router)`。
3. 若用户设置了 `COMPAT_CLOSURE_ENABLED=1`，系统会额外记录 gate 日志：
   - 通过：记录 `compatibility_router_disabled ...`
   - 未通过：记录 `compatibility_router_kept_enabled ... reasons=...`

这意味着 compat 不是靠“删代码”退场，而是靠**可审计配置 + 可重复判定**退场。该点直接影响后续测试设计：

- 默认模式下，compat 路由存在。
- closure 达标模式下，compat 路由应不存在，相关请求预期 404。

同一文件还实现了相关横切能力：

- `correlation_id_middleware` 在每个请求上注入 trace id（头名见 `TRACE_ID_HEADER`）。
- 对异常、完成耗时、状态码统一记录，保证 API 与异步锚定日志可关联。

---

### 1.2 兼容上报接口不是“旁路”，而是规范化入口

`app/api/compat.py` 的 `/api/cherry/telemetry` 路径并不是简单透传，而是完整做了“兼容协议 -> canonical 事件”的结构重建。

#### 1.2.1 请求模型与字段映射

兼容模型 `CherryTelemetryPayload`（如 `temp_c`, `hum_rh`, `co2`, `vibration`, `seq`, `ts`）被转换为 canonical `TraceEvent`：

- `sensor_payload` 最低保留 `temperature_c`, `humidity_pct`, `seq`
- 可选注入 `co2_ppm`, `vibration`, `digest`
- `stage` 字符串只接受 `harvest|storage|transport|retail`，否则回落 `transport`
- `signature_envelope.algorithm` 在兼容入口里先设 alias 再规范化

这里的关键不是字段名变换，而是把“历史输入”投影到统一契约，让下游全部按同一事件模型工作。

#### 1.2.2 兼容验签双模式（observe / enforce）

`COMPAT_TELEMETRY_SIGNATURE_MODE` 决定兼容验签失败时的行为：

- `observe`：记录审计与告警日志，但允许入库（用于迁移期观测）
- `enforce`：直接返回 401（Problem JSON）

验签结果由 `verify_trace_event_signature_with_reason(...)` 返回，不是 bool-only，带 reason，便于审计归因。

#### 1.2.3 幂等冲突与 Problem 响应

兼容入口使用 `ingest_trace_event(...)`，幂等键优先取 `Idempotency-Key`，否则构造 `hw:{device_id}:{seq}`。冲突会转成 409 Problem 响应。

#### 1.2.4 兼容退场信号注入

compat 响应统一注入：

- `Deprecation: true`
- `Sunset`
- `Link`
- `X-Compat-Deprecated`
- `X-Compat-Replacement`
- `X-Compat-Exit-Criteria`

并上报 `traceability_compat_requests_total{endpoint,method,status}`。这使“退场进度”可量化，而不是口头约定。

---

### 1.3 签名验证链路：算法归一、密钥来源优先级、失败原因可解释

签名逻辑在 `app/services/signature_verification.py`，实现上有几个关键原则。

#### 1.3.1 算法归一化

- canonical 基线：`ECDSA_P256_SHA256`
- alias：`ECDSA`
- `normalize_signature_algorithm(...)` 将 alias 统一到 canonical 名称

这避免了“同算法不同字符串导致策略分叉”的问题。

#### 1.3.2 验签输入不是原始 JSON，而是 canonicalize 后的签名子集

HMAC 与 ECDSA 都基于 `_signature_payload(...)` 提取固定字段，再走 `canonicalize_payload(...)`，从而避免 JSON key 顺序/空白差异导致验签不稳定。

#### 1.3.3 密钥来源优先级

优先查设备管理表：

- `ManagedDeviceKey` + `ManagedDevice` 联表
- 要求 device/key 状态均为 active
- 要求 key 算法与事件算法匹配

若管理表未命中：

- HMAC 允许 fallback 到环境变量 `INGEST_SIGNING_KEYS`
- ECDSA **不允许** fallback（返回 `ecdsa_key_not_found`）

这条策略把“迁移期便利”与“强安全约束”分开处理。

#### 1.3.4 ECDSA 签名格式兼容

ECDSA 验证支持两种十六进制输入：

- 64 字节 raw `r||s`（自动编码为 DER）
- DER 结构（先 decode 校验合法）

统一后调用 `cryptography` 库做 `ec.ECDSA(SHA256)` 验证。

---

### 1.4 锚定状态机：从“写一次交易”提升为“可恢复流程”

`app/services/anchoring.py` 并不是单函数提交交易，而是完整状态机执行器。

#### 1.4.1 状态与事件

业务状态：

- `RECEIVED`
- `ANCHORING`
- `ANCHORED`
- `FAILED_RETRYING`
- `DEAD_LETTER`

提交记录状态：

- `PENDING`
- `FINALIZED`
- `REORGED`

#### 1.4.2 批处理入口

`run_anchor_state_machine(limit=...)` 只拉取三类“需处理”状态：

- `RECEIVED`
- `ANCHORING`
- `FAILED_RETRYING`

按 `IngestRequest.id` 有序处理，保证重试行为可预测。

#### 1.4.3 `_anchor_request(...)` 的关键分支

1. **已有回执短路**：若该 event 已有 `AnchorReceipt`，直接标记 `ANCHORED`，输出 `already_anchored`。  
2. **提交恢复**：若存在 `PENDING` 提交记录且适配器支持 durable submission，则走恢复路径查询 receipt，而非重复发交易。  
3. **正常提交**：`anchor_event -> get_receipt -> verify_anchor`。  
4. **验证失败处理**：触发异常分支，按重试次数转 `FAILED_RETRYING` 或 `DEAD_LETTER`，并创建告警。

无论成功失败，`finally` 块都会记录运行指标和结果指标，避免观测盲区。

---

### 1.5 锚定灰度控制：不是开关，而是“决策 + 统计 + 自动降级”闭环

核心结构是 `_RolloutController` + `_record_canary_sample(...)`。

#### 1.5.1 模式与默认

支持四种模式：

- `shadow`
- `canary`
- `full`
- `rollback_safe`

默认 `ANCHOR_EVM_ROLLOUT_MODE=rollback_safe`。

#### 1.5.2 决策函数 `decide(...)`

- `full`：优先走 EVM
- `canary`：基于 `_is_canary_cohort(...)` 决定 `safe` 或 `evm`
- `shadow`：主路径 `safe`，并触发 `run_shadow_probe(...)`
- 不可用/强制回滚：统一收敛 `rollback_safe`

#### 1.5.3 canary 分桶算法（稳定且可重现）

分桶种子是 `f"{event_id}:{canonical_hash.lower()}"`，做 `sha256`，取前 8 hex 转 int 后 `% 100`。

这保证：

- 同一事件在重试/重启后仍落同一桶
- 不使用随机数，避免实验组漂移

#### 1.5.4 SLO 判定与自动回滚

窗口内统计样本并评估三条约束：

- `success_rate >= min_success_rate`（默认 0.99）
- `dead_letter_rate <= max_dead_letter_rate`（默认 0.005）
- `p95_confirmation_seconds <= max_p95_confirmation_seconds`（默认 120）

若持续违规超过 `abort_after_seconds`（默认 600），置 `auto_aborted=True` 并发出 rollout transition 到 `rollback_safe`。之后 `_effective_mode()` 会强制回退。

这比“手工观察后切换”更安全，且可自动化。

---

### 1.6 compat 退场门控：判定逻辑不是一句阈值，而是时间序列约束

`app/services/compat_exit.py` 做了三层工作。

#### 1.6.1 配置加载

- `COMPAT_CLOSURE_ENABLED`
- `COMPAT_EXIT_REQUIRED_RELEASES`（默认 2）
- `COMPAT_EXIT_REQUIRED_CONSECUTIVE_DAYS`（默认 14）
- `COMPAT_EXIT_MAX_RATIO_PERCENT`（默认 1.0）
- `COMPAT_EXIT_HISTORY_PATH`
- `COMPAT_EXIT_RELEASES_OBSERVED`（可覆盖）

#### 1.6.2 历史解析与校验

`parse_compat_traffic_history(...)` 会校验：

- 日期合法（ISO）
- 计数字段必须非负整数
- 可接受 `compat_requests` 或 `compat_requests_by_endpoint` 聚合
- 支持显式 `compat_ratio`，否则按 `compat_requests/total_requests` 计算
- 禁止重复日期

#### 1.6.3 连续天数判定

从最新样本逆序扫描，只有同时满足“低于阈值 + 日期连续”才计入 streak；中间断一天就中断。

这样避免了“14 个散点天数也算达标”的误判。

#### 1.6.4 安全失败原则

若 history 文件损坏/格式错误，`evaluate_compat_closure_decision()` 不会让路由下线，而是构造 `criteria_passed=False` 并保留 compat router。

这属于“失败保守”设计。

---

### 1.7 可观测性模型：把“决策过程”也指标化

在 `app/observability/metrics.py`，不仅记录最终结果，还记录策略过程：

- `traceability_anchoring_rollout_decisions_total{mode,path}`
- `traceability_anchoring_rollout_transitions_total{to_state}`
- `traceability_anchoring_rollout_canary_outcomes_total{outcome}`
- `traceability_anchoring_rollout_canary_confirmation_seconds`（histogram）
- `traceability_compat_requests_total{endpoint,method,status}`
- `traceability_anchoring_outcomes_total{outcome}`

这使得“为什么回滚”“回滚前发生了什么”可以在指标层追溯，而不是只能翻日志。

---

### 1.8 端到端时序示例（从 compat 上报到 anchor 完成）

1. 设备调用 `/api/cherry/telemetry`。  
2. `compat.py` 将 payload 组装为 `TraceEvent`，算法名归一后验签。  
3. 根据 `COMPAT_TELEMETRY_SIGNATURE_MODE` 决定“仅观察”还是“严格拒绝”。  
4. 通过 `ingest_trace_event(...)` 写入业务事实（含幂等语义）。  
5. 锚定 worker 拉到请求，进入 `_anchor_request(...)`。  
6. rollout controller 决策路径（safe/evm/shadow）。  
7. 交易提交、回执查询、锚定验证，落 `AnchorReceipt`。  
8. 结果状态更新到 `ANCHORED` 或重试/死信，并发指标。  
9. 查询 API / 前端读取 canonical 视图；compat 是否可用由 closure gate 决定。

---

### 1.9 本段结论（工程含义）

本项目的关键不在“有几个 API”，而在于把以下能力串成闭环：

- **协议治理**：compat -> canonical 的迁移可量化、可回滚。
- **执行治理**：锚定流程有状态机、可恢复提交、故障分级。
- **发布治理**：EVM 上链能力不是硬切换，而是灰度控制 + SLO 自动回退。
- **观测治理**：不仅有结果指标，还有决策和转移指标。

换句话说，这是一套“可上线持续演进”的实现，不是一次性的演示工程。
