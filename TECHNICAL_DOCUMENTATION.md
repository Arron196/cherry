# Cherry Traceability Platform — 技术文档

**版本** `1.0` · **状态** `正式发布` · **更新** `2026-03-02`

> 本文档面向平台工程师、安全审计员与运维人员。  
> 阅读前提：熟悉 REST API、基础密码学概念、关系型数据库。

---

## 目录

| # | 章节 |
|---|------|
| 1 | [快速上手](#1-快速上手) |
| 2 | [系统概述与设计哲学](#2-系统概述与设计哲学) |
| 3 | [架构总览](#3-架构总览) |
| 4 | [架构决策记录 ADR](#4-架构决策记录-adr) |
| 5 | [数据模型](#5-数据模型) |
| 6 | [安全威胁模型](#6-安全威胁模型) |
| 7 | [核心服务层](#7-核心服务层) |
| 8 | [区块链锚定引擎](#8-区块链锚定引擎) |
| 9 | [API 参考](#9-api-参考) |
| 10 | [观测性与监控](#10-观测性与监控) |
| 11 | [兼容层与渐进式废弃](#11-兼容层与渐进式废弃) |
| 12 | [设备管理](#12-设备管理) |
| 13 | [前端架构](#13-前端架构) |
| 14 | [运维手册](#14-运维手册) |
| 15 | [性能与 SLO 规格](#15-性能与-slo-规格) |
| 16 | [故障模式目录](#16-故障模式目录) |
| 17 | [数据库与迁移](#17-数据库与迁移) |
| 18 | [部署指南](#18-部署指南) |
| 19 | [开发指南](#19-开发指南) |
| 20 | [词汇表](#20-词汇表) |

---

## 1. 快速上手

> **目标**：从零开始，5 分钟内完成第一个传感器事件的摄入与区块链锚定。

### 前置条件

```
Python >= 3.11
Node.js >= 20
```

### 步骤一：启动后端

```bash
# 安装依赖
pip install -e ".[dev]"

# 初始化数据库（首次运行）
alembic upgrade head

# 启动 API 服务（监听 18941 端口）
uvicorn app.main:app --host 0.0.0.0 --port 18941 --reload
```

验证服务就绪：

```bash
curl http://localhost:18941/health
# {"status": "ok"}
```

### 步骤二：获取访问令牌

```bash
curl -s -X POST http://localhost:18941/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq .access_token
# "eyJ..."
export TOKEN="<上一步输出的 token>"
```

### 步骤三：注册传感器设备与密钥

```bash
# 注册设备
curl -s -X POST http://localhost:18941/admin/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "sensor-001",
    "display_name": "冷链传感器 #1",
    "initial_key_id": "key-001",
    "initial_key_algorithm": "HMAC_SHA256",
    "initial_key_secret": "my-secret-key"
  }'
```

### 步骤四：摄入第一个传感器事件

```bash
# 生成规范化签名（详见第 7.2 节）
SIGNATURE=$(python -c "
import hmac, hashlib, json
payload = json.dumps({
  'version':'1','device_id':'sensor-001','batch_id':'batch-001',
  'timestamp':'2026-03-02T08:00:00.000000+00:00',
  'sensor_payload':{'temperature_c':2.5,'humidity_pct':90.0},
  'supply_chain_stage':'storage',
  'signature_envelope':{'algorithm':'HMAC_SHA256','key_id':'key-001'}
}, sort_keys=True, separators=(',',':'), ensure_ascii=True)
print(hmac.new(b'my-secret-key', payload.encode(), hashlib.sha256).hexdigest())
")

curl -s -X POST http://localhost:18941/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1\",
    \"device_id\": \"sensor-001\",
    \"batch_id\": \"batch-001\",
    \"timestamp\": \"2026-03-02T08:00:00.000000+00:00\",
    \"sensor_payload\": {\"temperature_c\": 2.5, \"humidity_pct\": 90.0},
    \"supply_chain_stage\": \"storage\",
    \"signature_envelope\": {
      \"algorithm\": \"HMAC_SHA256\",
      \"key_id\": \"key-001\",
      \"signature\": \"$SIGNATURE\"
    }
  }"
# {"event_id": 1, "ingest_status": "RECEIVED"}
```

### 步骤五：触发锚定并查询结果

```bash
# 触发锚定 Worker（开发模式手动触发）
curl -s -X POST http://localhost:18941/admin/anchoring/run-once \
  -H "Authorization: Bearer $TOKEN"

# 查询批次溯源时间线
curl -s http://localhost:18941/v1/trace/batch-001 \
  -H "Authorization: Bearer $TOKEN" | jq .
```

预期响应：

```json
{
  "batch_id": "batch-001",
  "timeline_order": "oldest_first",
  "timeline": [{
    "event_id": 1,
    "anchor": { "status": "ANCHORED", "transaction_hash": "0xabc..." },
    "quality_grade": "A"
  }]
}
```

### 步骤六：启动前端仪表板

```bash
cd frontend
npm ci
npm run dev   # 监听 18940 端口
```

打开 `http://localhost:18940`，使用 `admin / admin123` 登录。

---


---

## 2. 系统概述与设计哲学

### 2.1 平台定位

Cherry Traceability Platform 是一套**供应链全程溯源系统**，解决生鲜农产品从采摘到零售全链路的信任问题：

> 消费者如何相信一颗樱桃在运输过程中始终处于合格的冷链环境？

系统的回答是：在每个供应链节点采集传感器数据，对数据加密签名，将不可篡改的内容哈希锚定至区块链，向任意第三方开放公开验证接口。签名保证数据来自合法设备，区块链保证数据发布后不可篡改，两者共同构成完整的可信链条。

### 2.2 能力边界

| 能力 | 范围内 | 范围外 |
|------|------|------|
| 传感器数据摄入 | 温度、湿度、CO₂、振动 | 实时流式摄入（当前为异步轮询）|
| 密码学完整性证明 | HMAC-SHA256 / ECDSA P-256 | PKI 证书链、CA 体系 |
| 区块链锚定 | EVM 兼容链，适配器可扩展 | 跨链、NFT 溯源凭证 |
| 质量评级 | 规则引擎加权评分 | 机器学习异常检测 |
| 消费者验证 | 无认证公开接口 | 移动 App |

### 2.3 设计哲学

**可验证优于可信任**  
任何数据声明必须可由独立第三方通过哈希对比完成验证。系统本身不是信任锚点——区块链是。

**失败隔离**  
签名验证失败不影响数据入库（事件记录，状态标记）；区块链锚定失败不影响 API 可用性（异步重试队列）；Canary 流量故障在 600 秒内自动回滚，不影响主链路。

**幂等是一等公民**  
从 HTTP 层到数据库层，所有写操作均为幂等。硬件设备在弱网络下可无限重试，不产生重复记录。这是 IoT 场景下的基本假设，不是优化项。

**渐进式演进，随时可回滚**  
通过 Rollout 控制器（shadow → canary → full）和兼容层（compat closure）实现零停机演进，每个阶段均可一键回滚，不存在不可逆操作。

**零外部依赖的可观测性**  
Prometheus 指标、结构化日志、告警系统均为纯 Python 自实现。在没有任何第三方监控基础设施的情况下，系统可完整运行并暴露所有关键指标。

### 2.4 系统边界与外部依赖分级

| 依赖项 | 分级 | 缺失时的降级行为 |
|------|------|------|
| 数据库（SQLite/PostgreSQL）| **强依赖** | 服务不可用 |
| EVM 节点（RPC） | **弱依赖** | 自动回退至 mock 锚定，数据摄入不受影响 |
| 消息队列 | **无依赖** | 不需要 |
| 外部认证服务 | **无依赖** | 内置 JWT，可替换 |
| 缓存服务（Redis 等）| **无依赖** | 不需要 |

---

## 3. 架构总览

### 3.1 整体分层

```mermaid
graph TB
    subgraph Devices["硬件设备层"]
        D1[传感器节点 A]
        D2[传感器节点 B]
    end

    subgraph API["接入层 FastAPI :18941"]
        I["POST /v1/events<br/>摄入端点"]
        P["GET /v1/public/trace<br/>公开验证"]
        Q["GET /v1/batches<br/>查询接口"]
        ADM["/admin/*<br/>管理接口"]
    end

    subgraph Core["核心服务层"]
        SIG[签名验证]
        IDEM[幂等性层]
        HASH[哈希规范化]
        QG[质量评分引擎]
    end

    subgraph Anchor["锚定引擎"]
        SM[状态机 Worker]
        RC[Rollout 控制器]
        MA[MockAdapter]
        EA[EvmAdapter]
    end

    subgraph Storage["持久层"]
        DB[(SQLite / PostgreSQL)]
    end

    subgraph Chain["区块链"]
        EVM[EVM 兼容节点]
    end

    subgraph FE["前端 :18940"]
        DASH[仓位板]
        TRACE[溯源页]
    end

    D1 & D2 -->|HMAC/ECDSA 签名| I
    I --> SIG --> IDEM --> HASH --> DB
    HASH --> QG --> DB
    SM -->|RECEIVED/FAILED_RETRYING| DB
    SM --> RC
    RC -->|rollback_safe/shadow| MA --> DB
    RC -->|canary/full| EA --> EVM
    EA --> DB
    Q & P & ADM --> DB
    FE --> API
```

### 3.2 请求生命周期（序列图）

```mermaid
sequenceDiagram
    participant Dev as IoT 设备
    participant API as FastAPI
    participant DB  as 数据库
    participant WK  as Anchor Worker
    participant EVM as EVM 节点

    Dev->>API: POST /v1/events<br/>Idempotency-Key: uuid
    API->>API: 1. 验证签名
    API->>DB:  2. 查询 idempotency_key
    DB-->>API: 不存在
    API->>DB:  3. INSERT Event + IngestRequest(RECEIVED)
    DB-->>API: OK
    API-->>Dev: 202 {event_id, status: RECEIVED}

    Note over WK: 定期批次轮询
    WK->>DB: 查询 RECEIVED 记录
    DB-->>WK: [event_1, event_2, ...]
    WK->>DB: UPDATE status=ANCHORING
    WK->>EVM: anchorEvent(bytes32, uint256)
    EVM-->>WK: tx_hash
    WK->>EVM: 轮询确认，重组检测
    EVM-->>WK: receipt
    WK->>DB: INSERT AnchorReceipt<br/>UPDATE status=ANCHORED

    Dev->>API: GET /v1/public/trace/{batch_id}
    API->>DB: 查询 anchor_receipts
    DB-->>API: tx_hash, anchored_at
    API-->>Dev: {blockchain_anchor: {tx_hash, anchored_count}}
```

### 3.3 项目目录结构

```
cherry/
├── app/                        # 后端服务
│   ├── api/                    # HTTP 路由层 (FastAPI Router)
│   │   ├── auth.py             # POST /v1/auth/login
│   │   ├── ingest.py           # POST /v1/events (核心摄入)
│   │   ├── query.py            # GET /v1/batches, /v1/events
│   │   ├── trace.py            # GET /v1/trace/{batch_id}
│   │   ├── public_trace.py     # GET /v1/public/trace/{batch_id}
│   │   ├── stats.py            # GET /v1/stats/*
│   │   ├── admin.py            # /admin/devices/* 设备管理
│   │   ├── anchoring_admin.py  # /admin/anchoring/*
│   │   ├── alerts.py           # /v1/alerts/*
│   │   ├── metrics.py          # GET /metrics (Prometheus)
│   │   ├── compat.py           # 已废弃兼容路由（条件挂载）
│   │   └── contracts.py        # POST /contracts/trace-events/validate
│   ├── domain/
│   │   ├── persistence/
│   │   │   └── models.py           # SQLAlchemy 2.0 ORM 模型
│   │   ├── contracts/
│   │   │   ├── trace_event.py      # Pydantic 输入合约
│   │   │   └── hash_canonicalization.py  # SHA-256 规范化
│   │   └── quality/
│   │       ├── grading.py          # 评分引擎
│   │       └── rules.yml           # 可配置评分规则
│   ├── services/
│   │   ├── anchoring.py        # 锚定状态机 + Rollout 控制器
│   │   ├── anchor_adapter/     # 适配器模式实现
│   │   ├── idempotency.py      # 幂等性保证
│   │   ├── signature_verification.py
│   │   ├── device_management.py
│   │   ├── query_service.py
│   │   ├── anchoring_management.py
│   │   ├── alerts.py
│   │   ├── audit.py
│   │   └── compat_exit.py      # 已废弃 API 退出判断
│   ├── jobs/
│   │   ├── anchor_worker.py    # 锚定 Worker 入口
│   │   └── retry_worker.py     # 重试 Worker 入口
│   ├── security/
│   │   ├── auth.py             # JWT HS256 实现
│   │   └── rbac.py             # 角色访问控制
│   └── observability/
│       ├── metrics.py          # 零依赖 Prometheus 实现
│       └── logging.py          # 结构化 JSON 日志
├── frontend/               # Next.js 16 前端
├── alembic/                # 数据库迁移
├── tests/                  # pytest 测试套件
└── scripts/                # 合约守卫、退出标准检查
```

---

## 4. 架构决策记录（ADR）

> 此章记录系统中每个重大设计决策的**动机、备选方案**和**最终取舍**，以便后续维护者理解本质。

---

### ADR-001: 哈希规范化算法自实现

**状态**: 已采纳  **日期**: 2026-02-10

#### 问题

区块链需要对同一事件始终生成相同的 SHA-256 哈希。JSON 序列化不具备确定性：键顺序、日期格式、Unicode 转义均因实现而异。

#### 备选方案

| 方案 | 优点 | 劣势 |
|------|------|------|
| 使用现有库（`canonicaljson`） | 成熟 | 增加依赖，前端无对应实现 |
| 使用 Protobuf 序列化 | 确定性极高 | 引入 schema 管理负担 |
|| **自实现规范化算法** | 零依赖，可移植 | 需要额外测试覆盖 |

#### 决策

自实现额外规范化算法，规则如下：

1. 字典键递归升序排列
2. datetime 均转换为 UTC，带 `+00:00` 后缀
3. 字符串两端 trim
4. `ensure_ascii=True`，无多余空格

前端（TypeScript）实现了完全对等版本，确保跨平台一致性。各层单元测试均对相同输入验证哈希完全相同。

---

### ADR-002: 幂等性双层防护

**状态**: 已采纳  **日期**: 2026-02-10

#### 问题

IoT 设备在网络不稳定时会重试提交。如何在不引入额外中间件的情况下保证幂等性？

#### 备选方案

| 方案 | 问题 |
|------|------|
| 仅用 idempotency_key | 设备可用不同 key 提交相同内容 |
| 仅用 canonical_hash | 客户端重试时 key 不存在会重复入库 |
| **双层防护** | 层一 key 防重放，层二 hash 防内容重复 |

#### 决策

采用双层：
- **第一层**：`idempotency_key` UNIQUE 索引——防止客户端重试重复入库
- **第二层**：`canonical_hash` UNIQUE 索引——防止相同内容以不同 key 重复入库

并发竞争通过乐观写入 + `IntegrityError` 捕获 + rollback 再查询处理，无其他锁。

---

### ADR-003: 签名验证密钥分层回退

**状态**: 已采纳  **日期**: 2026-02-10

#### 问题

早期设备用环境变量配置密钥，新设备需要数据库密钥管理。如何允许两种方式共存，同时不降低安全性？

#### 决策

分层回退策略：

```
层一（首选）: 数据库 managed_device_keys
  • HMAC 和 ECDSA 均支持
  • 密钥状态和设备状态验证
  • 支持密钥轮换（旧密钥标记 retired）

层二（回退）: INGEST_SIGNING_KEYS 环境变量
  • 仅支持 HMAC（共享密钥不适合存入相对公开的数据库）
  • ECDSA 不支持环境回退（公钥可公开存入 DB）
  • 仅用于兼容旧设备过渡期
```

**权衡**：旧设备不需重新注册即可继续工作，新设备必须通过管理接口注册密钥。

---
### ADR-004: EVM 渐进式部署而非直接切换

**状态**: 已采纳  **日期**: 2026-02-10

#### 问题

生产切换 EVM 锚定存在风险：节点不稳定、Gas 价格异常、重组。如何在不暂停服务的前提下低风险切换？

#### 备选方案

| 方案 | 风险 |
|------|------|
|| 直接切换 | 任意 EVM 中断就导致锚定停摆 |
| 双写（同时写 mock + EVM） | 写放大 2x，数据一致性复杂 |
| **渐进式 Rollout** | 每阶段可独立评估并回滚 | ✔ |

#### 决策

四阶段 Rollout + SLO 自动回滚：

| 阶段 | 模式 | 目的 |
|------|------|------|
| 0 | `rollback_safe` | 默认安全状态 |
| 1 | `shadow` | 验证连通性，不影响生产 |
| 2 | `canary` | 5% 流量 + SLO 监控 |
| 3 | `full` | 全量切换 |

Canary 阶段设有自动回滚机制：指标违规持续 600s 则永久回退至 `rollback_safe`。

---

### ADR-005: 兼容共存期的 API 兼容层

**状态**: 已采纳  **日期**: 2026-02-10

#### 问题

前端从旧框架迁移到 `/v1` 规范 API 期间，旧路由（`/api/cherry/telemetry`等）和新路由必须同时存在一段时间。如何在可控的时间点关闭旧路由，同时避免永久污染代码库？

#### 备选方案

| 方案 | 问题 |
|------|------|
|| 永久保留 legacy 路由 | 代码库永久劣化 |
| 立即删除，要求前端同步切换 | 不对前端友好 |
|| **兼容共存期 + 数据驱动退出** | 可控迁移，有明确退出日期 | ✔ |

#### 决策

兼容共存期设计：

1. 封锁路径由流量数据驱动，不是手动决策
2. 双重退出门禁：`releases_observed >= 2` AND `14 天内 compat_ratio < 1%`
3. 旧路由自动配置迁移所需响应头，旧客户端不需修改代码即可感知新地址
4. `COMPAT_CLOSURE_ENABLED=1` 将封锁提上议程

---
## 5. 数据模型

### 5.1 实体关系图（ER）

```mermaid
erDiagram
    ManagedDevice ||--o{ ManagedDeviceKey : "has keys"
    ManagedDevice ||--o{ Event            : "device_id (logical)"
    Event         ||--o{ IngestRequest     : "has"
    Event         ||--o{ AnchorSubmissionRecord : "has"
    Event         ||--o{ AnchorReceipt     : "has"
    Event         ||--o{ QualityResult     : "has"
    Event         ||--o{ Alert             : "referenced by (nullable)"
    Event         ||--o{ Audit             : "referenced by (nullable)"

    ManagedDevice {
        int    id PK
        string device_id UK
        string display_name
        string status
        text   disabled_reason
    }

    Event {
        int    id PK
        string version
        string device_id
        string batch_id
        ts     timestamp
        json   sensor_payload
        json   signature_envelope
        string canonical_hash UK
        float  co2_ppm
        float  vibration_g
        string supply_chain_stage
    }

    IngestRequest {
        int    id PK
        string idempotency_key UK
        string payload_hash
        string ingest_status
        int    retry_count
        text   last_error
    }

    AnchorReceipt {
        int    id PK
        string network
        string transaction_hash UK
        json   receipt_payload
        ts     anchored_at
    }
```

### 5.2 表结构详述

#### `events` — 事件主表

| 列名 | 类型 | 约束 | 设计说明 |
|------|------|------|------|
| `id` | INTEGER | PK, autoincrement | 内部自增主键 |
| `version` | VARCHAR(32) | NOT NULL | 协议版本，当前为 `"1"` |
| `device_id` | VARCHAR(128) | NOT NULL | 设备标识符（逻辑关联，无 FK 约束）|
| `batch_id` | VARCHAR(128) | NOT NULL | 批次号，跨事件分组的业务键 |
| `timestamp` | TIMESTAMP+TZ | NOT NULL | **设备采集时间**，非服务器入库时间 |
| `sensor_payload` | JSON | NOT NULL | 原始传感器数据，无 schema 控制 |
| `signature_envelope` | JSON | NOT NULL | `{algorithm, signature, key_id}` |
| `canonical_hash` | VARCHAR(64) | UNIQUE+INDEX | **内容寻址键**，幂等干 + EVM 参数 |
| `co2_ppm` | FLOAT | nullable | 从 payload 提取的平铺字段，便于查询 |
| `vibration_g` | FLOAT | nullable | 同上 |
| `supply_chain_stage` | VARCHAR(32) | nullable | `harvest/storage/transport/retail` |
| `created_at` | TIMESTAMP+TZ | NOT NULL | 服务端入库时间 |

> **关键设计**：`device_id` 不使用数据库外键约束。这是意向的——允许摄入未注册设备的数据（签名失败标记），不多一道 FK 限制。

#### `ingest_requests` — 摄入请求状态机

| 列名 | 类型 | 说明 |
|------|------|------|
| `idempotency_key` | VARCHAR(128) UNIQUE | 客户端提供，防重放一级键 |
| `payload_hash` | VARCHAR(64) | 用于检测幂等冲突（相同 key 不同内容）|
| `ingest_status` | VARCHAR(32) | 状态机当前状态，见下方 |
| `retry_count` | INTEGER DEFAULT 0 | 锚定失败重试计数 |
| `last_error` | TEXT | 最近一次错误信息 |

**IngestStatus 状态机**：
```mermaid
stateDiagram-v2
    [*] --> RECEIVED : 事件入库
    RECEIVED --> ANCHORING : Worker 拾取
    ANCHORING --> ANCHORED : 锚定成功
    ANCHORING --> FAILED_RETRYING : 异常 (retry < 3)
    FAILED_RETRYING --> ANCHORING : 下次 Worker 批次
    FAILED_RETRYING --> DEAD_LETTER : retry >= 3
    DEAD_LETTER --> RECEIVED : 手动 requeue
```

#### `anchor_submission_records` — 提交持久化记录

这张表解决“**Worker 在提交后、收到 receipt 前崩溃**”的死局：

```
故障场景:
  Worker 调用 anchorEvent() 获得 tx_hash
  ↓ 将 tx_hash 持久化到 anchor_submission_records (PENDING)
  ↓ 开始轮询 receipt ... Worker 崩溃
  ↓ Worker 重启, 检测到 PENDING submission
  ↓ 直接用已有 tx_hash 继续轮询 (restore path)
  ↓ 无重复上链。账单不多扣。
```

| `status` | 语义 |
|------|------|
| `PENDING` | 已提交至链，等待 receipt |
| `FINALIZED` | receipt 已验证，正常完成 |
| `REORGED` | 检测到链重组，需重新提交 |

---
## 6. 安全模型

### 6.1 身份认证——JWT HS256 内置实现

```
Header:  {"alg": "HS256", "typ": "JWT"}
Payload: {
  "sub": "<username>",
  "roles": ["admin"],
  "iss": "traceability-auth",   ← AUTH_JWT_ISSUER env
  "iat": <当前时间>,
  "exp": <iat + 86400>           ← 24h 默认
}
Signature: HMAC-SHA256(base64url(header)+'.'+base64url(payload), AUTH_JWT_SECRET)
```

系统实现了完整的 HS256 JWT，无第三方依赖。生产环境必须替换 `AUTH_JWT_SECRET` 默认值。如需接入 OIDC/OAuth2 ，可将 `get_current_principal` 依赖替换为外部 JWT 验证，不需修改业务逻辑。

### 6.2 RBAC 权限矩阵

| 接口类别 | 所需角色 | 说明 |
|------|------|------|
| 事件摄入 `POST /v1/events` | 需登录 | 任意已登录用户 |
| 公开溯源 `GET /v1/public/trace` | 无需 | 完全开放 |
| Prometheus 指标 `GET /metrics` | 无需 | 建议网络侧限制 |
| 告警查看/操作 | `admin` 或 `regulator` | 监管角色可查看但不可注册设备 |
| 设备注册和密钥管理 | 仅 `admin` | 最高权限 |
| 锚定手动触发 / Requeue | 仅 `admin` | 运维操作 |

### 6.3 威胁模型与缓解措施

| 威胁 | 攻击向量 | 缓解措施 |
|------|------|------|
| **重放攻击** | 捕获合法请求重放 | `canonical_hash` UNIQUE 确保相同数据不重复入链 |
| **内容篡改** | 修改已提交数据 | 区块链哈希不可逆。任何篡改嵌入数据将与链上交易不匹配 |
| **设备冒写** | 使用他人设备标识提交数据 | 签名验证：`key_id` 必须关联至已注册的对应 `device_id` |
|| **密鑰泄露**（HMAC） | 环境变量泄露 | 第一优先级使用 DB 密鑰。环境回退仅用于封闭环境 |
| **时序攻击** | 逐字节比较判断 HMAC | `hmac.compare_digest()` 常时比较 |
|| **重组攻击** | EVM 链重组导致交易失效 | 重组检测算法（块哈希 + 典范链检查）自动重新提交 |
| **JWT 仿造** | 伪造 token | HMAC-SHA256 签名验证 + expiry 检查 |
|| **账号爆破** | 无限制登录尝试 | 速率限制在路由层（待添加）；当前需注意 IP 限速中间件 |

### 6.4 生产环境安全清单

- [ ] `AUTH_JWT_SECRET` 设置为随机 256-bit 密钥
- [ ] `CORS_ALLOW_ORIGINS` 限制为实际前端域名，删除默认 `*`
- [ ] EVM 私钥使用外部 HSM (`ANCHOR_EVM_SIGNER_URL`)，不写入环境变量
- [ ] `GET /metrics` 网络层限制内网访问
- [ ] 数据库制备加密存储

---
## 7. 核心服务层

### 7.1 事件摄入与幂等性保证

**接口**：`POST /v1/events` ， HTTP 202 Accepted

```mermaid
flowchart TD
    A[POST /v1/events] --> B{签名验证}
    B -->|失败| C[401 + 审计记录]
    B -->|通过| D{idempotency_key
是否已存在}
    D -->|存在 + hash一致| E[202 返回已有结果]
    D -->|存在 + hash不同| F[409 幂等冲突]
    D -->|不存在| G{canonical_hash
内容寻址}
    G -->|已存在| H[创建 IngestRequest
关联已有 Event]
    G -->|不存在| I[插入 Event
+ IngestRequest]
    H & I --> J[202 Accepted]
    I -->|IntegrityError
并发竞争| K[rollback
再查询回路 G]
```

幂等性语义保证：

- **相同 key + 相同内容**：返回相同结果，无副作用
- **相同 key + 不同内容**：409 冲突错误，客户端应检查请求内容
- **不同 key + 相同内容**：内容寻址去重，新 key 关联已有 Event，不重复入库

---

### 7.2 签名验证系统

#### 支持算法

| 算法 | `algorithm` 值 | 密钥存储 | 安全级别 |
|------|------|------|------|
| HMAC-SHA256 | `HMAC_SHA256` | 共享密钥 | 适合内网设备 |
| ECDSA P-256 | `ECDSA_P256_SHA256` 或 `ECDSA` | PEM 公钥入 DB | 适合高安全場景 |

#### 签名 Payload 构造

```python
# 签名 payload = TraceEvent 的所有字段，但排除 signature_envelope.signature
signing_payload = {
    'version':          event.version,
    'device_id':        event.device_id,
    'batch_id':         event.batch_id,
    'timestamp':        event.timestamp,
    'sensor_payload':   event.sensor_payload,
    'signature_envelope': {
        'algorithm': event.signature_envelope.algorithm,
        'key_id':    event.signature_envelope.key_id,
        # 注意: 不包含 signature 字段 ← 避免圆形依赖
    }
}
canonical_str = canonicalize_payload(signing_payload)  # 规范化后 JSON
```

#### 密钥查找逻辑（优先级顺序）

```mermaid
flowchart TD
    A[key_id 查找] --> B{managed_device_keys
DB 中存在?}
    B -->|Yes| C{设备 active?}
    C -->|No| D[managed_device_disabled]
    C -->|Yes| E{密钥 active?}
    E -->|No| F[managed_key_inactive]
    E -->|Yes| G{algorithm 匹配?}
    G -->|No| H[managed_key_algorithm_mismatch]
    G -->|Yes| I{device_id 匹配?}
    I -->|No| J[managed_key_device_mismatch]
    I -->|Yes| K[验证签名]
    B -->|No| L{HMAC算法?}
    L -->|No
ECDSA| M[ecdsa_key_not_found 401]
    L -->|Yes| N{INGEST_SIGNING_KEYS
env 中存在?}
    N -->|No| O[fallback_key_not_found 401]
    N -->|Yes| P[验证 HMAC]
    K & P --> Q{compare_digest
通过?}
    Q -->|No| R[signature_mismatch 401]
    Q -->|Yes| S[验证通过]
```

---
### 7.3 哈希规范化算法

哈希规范化是整个系统的信任基石。所有以下对象必须对相同输入生成相同哈希：**Python 后端、TypeScript 前端、任意审计工具**。

**算法规范（交互操作文档级别）**：

| 输入类型 | 处理规则 |
|------|------|
| `dict` | 键递归升序排列，値继续递归 |
| `list/tuple` | 保持顺序，元素递归规范化 |
| `str` | 两端 trim；尝试解析为 datetime，成功则标准化 |
| `datetime` | 转换为 UTC，格式：`YYYY-MM-DDTHH:MM:SS.ffffff+00:00` |
| `int/float/bool/None` | 原样保留 |
| Pydantic `BaseModel` | `.model_dump(mode='json')` 后递归 |

**序列化参数（JSON.dumps）**：
```python
json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
#                        键排序      无空格紧凑                非 ASCII 转义
```

**Python 和 TypeScript 应对比验证示例**：

```python
# Python
payload = {'b': 2, 'a': 1, 'ts': '2026-02-14T08:00:00Z'}
canonical_hash(payload)
# => 'a3f2c1...' (与 TypeScript 版完全相同)
```

```typescript
// TypeScript (frontend/src/lib/signing.ts)
const payload = {b: 2, a: 1, ts: '2026-02-14T08:00:00Z'};
sha256(JSON.stringify(canonicalizeValue(payload)));
// => 'a3f2c1...' (相同结果)
```

---

### 7.4 质量评分引擎

基于可配置规则文件 `domain/quality/rules.yml` 的加权频段评分系统。

#### 评分流程

```mermaid
flowchart LR
    A[传感器数据] --> B[加载 rules.yml
lru_cache]
    B --> C[判断各指标频段]
    C --> D[计算加权分]
    D --> E[对比阈值]
    E --> F[Grade A/B/C]
```

#### 频段分数表

| 频段 | 分数 | 说明 |
|------|------|------|
| `ideal` | 100 | 指标在理想区间内 |
| `warning` | 50 | 指标在可接受但需关注的区间 |
| `outside` | 0 | 超出可接受范围 |

#### 加权公式

```
weighted_score = Σ(BandScore_i × weight_i)
             = temp×0.4 + humidity×0.3 + co2×0.2 + vibration×0.1

等级: A (>= 80), B (>= 50), C (< 50)
```

#### 默认规则配置

```yaml
metrics:
  temperature_c:  { ideal: {min:  0, max: 4},  warning: {min: -2, max:  8},  weight: 0.4 }
  humidity_pct:   { ideal: {min: 85, max: 95}, warning: {min: 75, max: 98},  weight: 0.3 }
  co2_ppm:        { ideal: {min:  0, max: 800}, warning: {min:  0, max: 1500}, weight: 0.2 }
  vibration_g:    { ideal: {min:  0, max: 0.3}, warning: {min:  0, max: 0.8},  weight: 0.1 }
grade_thresholds: { A: 80, B: 50 }
```

> **扩展新指标**：修改 `rules.yml` 即可，无需更改任何代码。注意确保所有 `weight` 之和 = 1.0。

**寄存层兼容模式**（仅有 temp + humidity 时）：
采用整数频段积分并归一化，保持安全向下兼容。

---
## 8. 区块链锚定引擎

### 8.1 锚定状态机实现

`run_anchor_state_machine(limit)` 是 Worker 的主入口，每次批量处理 `RECEIVED` 和 `FAILED_RETRYING` 两种状态。

**内部执行流程**：

```python
def _anchor_request(session, ingest_request):
    # Step 1: 标记 ANCHORING（防并发重复提交）
    ingest_request.ingest_status = 'ANCHORING'
    session.flush()

    # Step 2: 幂等检查（已有 receipt）
    existing = session.query(AnchorReceipt).filter_by(event_id=...).first()
    if existing:
        ingest_request.ingest_status = 'ANCHORED'
        return  # 幂等完成

    # Step 3: Rollout 决策（选择适配器）
    path, adapter = rollout_controller.decide(event_id, canonical_hash)

    # Step 4: 可恢复提交检查（Worker 崩溃恢复场景）
    pending = session.query(AnchorSubmissionRecord).filter_by(
        event_id=..., status='PENDING').first()
    if pending:
        tx_hash = pending.transaction_hash  # 恢复已有 tx_hash，跳过提交
    else:
        submission = adapter.anchor_event(...)  # 提交上链
        tx_hash = submission.transaction_hash
        session.add(AnchorSubmissionRecord(status='PENDING', ...))
        session.flush()

    # Step 5: 等待 receipt + 验证
    receipt_data = adapter.get_receipt(tx_hash)  # 重组检测在此内部发生
    if not adapter.verify_anchor(canonical_hash=..., receipt=receipt_data):
        raise AnchorVerificationError('hash mismatch')

    # Step 6: 写入 receipt + 标记 ANCHORED
    session.add(AnchorReceipt(...))
    ingest_request.ingest_status = 'ANCHORED'

    # 异常处理: retry < 3 → FAILED_RETRYING; 否则 → DEAD_LETTER + critical 告警
```

### 8.2 适配器模式与选型

```python
class AnchorAdapter(ABC):
    @abstractmethod
    def anchor_event(self, *, event_id: int, canonical_hash: str,
                     payload: dict) -> AnchorSubmission: ...

    @abstractmethod
    def get_receipt(self, tx_hash: str) -> AnchorReceiptData: ...

    @abstractmethod
    def verify_anchor(self, *, canonical_hash: str,
                      receipt: AnchorReceiptData) -> bool: ...

    def supports_durable_submissions(self) -> bool:
        return False  # 默认不支持持久化提交
```

| 适配器 | `ANCHOR_ADAPTER` | `supports_durable_submissions` | 用途 |
|------|------|------|------|
| `ActiveMockAnchorAdapter` | `active_mock` | False | 开发 / MVP |
| `EvmContractAnchorAdapter` | `evm_contract` | True | 生产 EVM |
| `ReservedStubAdapter` | `reserved_stub` | False | 占位符 |

**Mock 适配器确定性设计**：
```python
tx_hash = '0x' + sha256(f'{event_id}:{canonical_hash}'.encode()).hexdigest()
# 相同 (event_id, canonical_hash) 始终得到相同 tx_hash
# 大量测试可送验证式回放
```

---
### 8.3 EVM 合约适配器深度解析

#### 合约 ABI（默认）

```solidity
// 嵌入式 ABI，可通过 ANCHOR_EVM_CONTRACT_ABI_JSON 覆盖
function anchorEvent(bytes32 canonicalHash, uint256 eventId) external;
event HashAnchored(bytes32 indexed canonicalHash, uint256 eventId);
```

#### 交易构建与费用策略

```python
# EIP-1559 优先，回退到 legacy gasPrice
for attempt in range(ANCHOR_EVM_MAX_SUBMISSION_ATTEMPTS):  # 默认 3
    bump = 1.0 + (ANCHOR_EVM_FEE_BUMP_PERCENT / 100) * attempt  # 默认 +15%/次
    if max_fee_per_gas:
        tx_params = {'maxFeePerGas': int(max_fee * bump),
                     'maxPriorityFeePerGas': int(prio * bump)}
    else:
        tx_params = {'gasPrice': int(gas_price * bump)}
    tx_params['gas'] = ANCHOR_EVM_GAS_LIMIT  # 默认 250000
    # ... 发送交易
```

#### 重组检测算法（三层检查）

```python
# Layer 1: 确认数检查
while current_block - receipt.blockNumber < required_confirmations:
    sleep(ANCHOR_EVM_POLL_INTERVAL_SECONDS)  # 默认 2s
    current_block = w3.eth.block_number

# Layer 2: 块哈希稳定性检查
stored_hash = w3.eth.get_block(receipt.blockNumber).hash
if stored_hash != receipt.blockHash:
    raise AnchorVerificationError('Reorg: block hash changed')

# Layer 3: 典范链一致性检查
canonical_block = w3.eth.get_block(receipt.blockNumber)
if canonical_block.hash != receipt.blockHash:
    raise AnchorVerificationError('Reorg: not on canonical chain')

# AnchorVerificationError 将触发 submission.status = 'REORGED' 并重新提交
```

#### 签名方式选择

| 环境变量 | 安全等级 | 应用场景 |
|------|------|------|
| `ANCHOR_EVM_PRIVATE_KEY` | 中等 | 开发/测试环境 |
| `ANCHOR_EVM_ACCOUNT_ADDRESS` | 中等 | 本地节点账户解锁 |
| `ANCHOR_EVM_SIGNER_URL` + `TOKEN` | 高 | **生产建议**，对接外部 HSM |

---

### 8.4 Rollout 控制器详解

#### 四种模式

```mermaid
stateDiagram-v2
    [*] --> rollback_safe : 默认状态
    rollback_safe --> shadow : 手动设置
    shadow --> canary : 手动设置
    canary --> full : SLO 达标 + 手动确认
    canary --> rollback_safe : SLO 违规 600s 自动回滚
    full --> rollback_safe : 手动回滚
```

#### Canary 分流哈希算法

```python
# 确定性桶分配：相同事件始终路由到相同分桶
raw = sha256(f'{event_id}:{canonical_hash.strip().lower()}'.encode()).hexdigest()
bucket = int(raw, 16) % 100
path = 'evm' if bucket < ANCHOR_EVM_CANARY_PERCENT else 'safe'  # 默认 5%
```

#### SLO 阈值与自动回滚

| SLO 指标 | 阈值 | 环境变量 | 说明 |
|------|------|------|------|
| 成功率 | ≥ 99% | `ANCHOR_EVM_CANARY_MIN_SUCCESS_RATE` | 少于阈值则算违规 |
| Dead-letter 率 | ≤ 0.5% | `ANCHOR_EVM_CANARY_MAX_DEAD_LETTER_RATE` | 超过阈值则算违规 |
| p95 确认时间 | ≤ 120s | `ANCHOR_EVM_CANARY_MAX_P95_CONFIRMATION_SECONDS` | 超过阈值则算违规 |
| 陨断窗口 | 600s | `ANCHOR_EVM_CANARY_ABORT_AFTER_SECONDS` | 违规持续此时间则永久回滚 |

> **注意**：自动回滚后，`_ROLLOUT_RUNTIME.auto_aborted = True` 将在进程生命周期内永久生效。如需全量回滚请重启应用并设置 `ANCHOR_EVM_ROLLOUT_MODE=rollback_safe`。

---
## 9. API 参考

> **错误格式**：所有错误响应遵循 [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457):
> ```json
> {"type": "about:blank", "title": "Unauthorized", "status": 401,
>  "detail": "signature_mismatch", "instance": "/v1/events"}
> ```

---

### 9.1 认证

#### `POST /v1/auth/login`

**无需 Authorization 头**

```http
POST /v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

```http
HTTP/1.1 200 OK

{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "role": "admin"
}
```

| 状态码 | 启动条件 |
|------|------|
| `200` | 登录成功 |
| `401` | 用户名或密码错误 |

---

### 9.2 事件摄入

#### `POST /v1/events`

```http
POST /v1/events
Authorization: Bearer <token>
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
Content-Type: application/json

{
  "version": "1",
  "device_id": "device-cold-chain-01",
  "batch_id": "cherry-batch-2026-001",
  "timestamp": "2026-02-14T08:00:00.000Z",
  "sensor_payload": {
    "temperature_c": 2.5,
    "humidity_pct": 90.0,
    "co2_ppm": 420,
    "vibration_g": 0.08
  },
  "supply_chain_stage": "storage",
  "signature_envelope": {
    "algorithm": "HMAC_SHA256",
    "key_id": "device-key-001",
    "signature": "a3f2c1d4..."
  }
}
```

```http
HTTP/1.1 202 Accepted

{
  "event_id": 42,
  "ingest_status": "RECEIVED"
}
```

| 状态码 | 启动条件 |
|------|------|
| `202` | 摄入成功，异步处理中 |
| `401` | 签名验证失败，`detail` 包含具体原因 |
| `409` | 幂等 Key 冲突（相同 Key + 不同 Payload）|
| `422` | 请求结构校验失败 |

---

### 9.3 批次与事件查询

#### `GET /v1/batches`

```http
GET /v1/batches?limit=20&offset=0&device_id=device-01&start_time=2026-02-01T00:00:00Z
Authorization: Bearer <token>
```

```json
{
  "total": 5,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "batch_id": "cherry-batch-2026-001",
      "device_id": "device-cold-chain-01",
      "event_count": 12,
      "start_time": "2026-02-14T08:00:00Z",
      "end_time": "2026-02-14T20:00:00Z"
    }
  ]
}
```

#### `GET /v1/batches/{batch_id}/stages`

```json
{
  "batch_id": "cherry-batch-2026-001",
  "stages": [
    {
      "stage": "harvest",
      "event_count": 3,
      "start_time": "2026-02-14T06:00:00Z",
      "end_time": "2026-02-14T08:00:00Z",
      "events": [{"event_id": 1, "timestamp": "...", "temperature_c": 18.5}]
    },
    {
      "stage": "storage",
      "event_count": 9,
      "start_time": "2026-02-14T08:30:00Z",
      "end_time": "2026-02-14T20:00:00Z",
      "events": [...]
    }
  ]
}
```

#### `GET /v1/events` 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `batch_id` | string? | 按批次过滤 |
| `device_id` | string? | 按设备过滤 |
| `ingest_status` | enum? | `RECEIVED/ANCHORING/ANCHORED/FAILED_RETRYING/DEAD_LETTER` |
| `supply_chain_stage` | enum? | `harvest/storage/transport/retail` |
| `start_time` / `end_time` | ISO8601? | 时间范围过滤 |
| `limit` | int 1-200 | 默认 50 |
| `offset` | int | 默认 0 |

---
### 9.4 溯源查询

#### `GET /v1/public/trace/{batch_id}` — **无需认证**

```http
GET /v1/public/trace/cherry-batch-2026-001
```

```json
{
  "batch_info": {
    "batch_id": "cherry-batch-2026-001",
    "total_events": 12,
    "stages": ["harvest", "storage", "transport"]
  },
  "timeline": [
    {"event_id": 1, "timestamp": "2026-02-14T06:00:00Z",
     "stage": "harvest", "anchor_status": "ANCHORED"}
  ],
  "stage_environments": {
    "storage": {
      "avg_temperature_c": 2.1, "avg_humidity_pct": 89.5,
      "avg_co2_ppm": 450, "avg_vibration_g": 0.07,
      "event_count": 8
    }
  },
  "quality": {"grade": "A", "score": 87.5},
  "blockchain_anchor": {
    "anchored_count": 12,
    "total_events": 12,
    "latest_transaction_hash": "0x7f3a..."
  }
}
```

#### `GET /v1/trace/{batch_id}` — **需认证，返回完整时序线**

```json
{
  "batch_id": "cherry-batch-2026-001",
  "timeline_order": "oldest_first",
  "timeline": [
    {
      "event_id": 1,
      "timestamp": "2026-02-14T06:00:00Z",
      "ingest_status": "ANCHORED",
      "anchor": {"status": "ANCHORED", "transaction_hash": "0x7f3a..."},
      "quality_grade": "A",
      "alert_snapshot": {"total": 0, "open": 0, "high_open": 0}
    }
  ]
}
```

---

### 9.5 统计接口

| 接口 | 返回 | 说明 |
|------|------|------|
| `GET /v1/stats/overview` | `{total_batches, total_events, active_devices, avg_quality_score, grade_distribution, open_alerts}` | 仓位板总览 |
| `GET /v1/stats/temperature-trend` | `[{timestamp, avg/min/max_temperature}]` | 近 24h 温度时序 |
| `GET /v1/stats/quality-distribution` | `[{grade, count, percentage}]` | A/B/C 占比 |
| `GET /v1/stats/stage-distribution` | `[{stage, count}]` | 阶段事件分布 |

---

### 9.6 管理接口摘要

**所有管理接口均需要 Bearer Token，并检查角色。**

#### 设备管理

```http
# 注册设备 (admin)
POST /admin/devices
{"device_id": "sensor-001", "display_name": "元谋 1 号节点",
 "initial_key_id": "key-001", "initial_key_algorithm": "HMAC_SHA256",
 "initial_key_secret": "<secret>"}

# 轮换密钥 (admin)
POST /admin/devices/{device_id}/keys
{"key_id": "key-002", "algorithm": "ECDSA_P256_SHA256", "public_key": "-----BEGIN PUBLIC KEY-----\n..."}

# 禁用设备 (admin)
POST /admin/devices/{device_id}/disable
{"reason": "设备丢失"}

# 设备列表 (admin+regulator)
GET /v1/devices?status=active&limit=20

# 设备详情含在线状态 (admin)
GET /admin/devices/{device_id}
```

#### 锚定管理

```http
# 任务列表
GET /admin/anchoring/tasks?status=DEAD_LETTER&batch_id=cherry-batch-2026-001

# 重新入队
POST /admin/anchoring/tasks/{ingest_request_id}/requeue

# 手动触发 Worker
POST /admin/anchoring/run-once  {"limit": 50}
```

#### 告警操作

```http
GET  /v1/alerts?limit=20                      # 告警列表
POST /v1/alerts/{alert_id}/ack                # 确认
POST /v1/alerts/{alert_id}/resolve            # 解决
POST /v1/alerts/{alert_id}/escalate           # 升级严重性 (low→medium→high→critical)
```

---
## 10. 观测性与监控

### 10.1 结构化日志

每个请求由中间件 `correlation_id_middleware` 包裹，记录完整生命周期：

```json
// 请求开始
{"event": "request_start", "method": "POST", "path": "/v1/events",
 "trace_id": "a1b2-c3d4-...", "timestamp": "2026-02-14T08:00:00.001Z"}

// 请求完成
{"event": "request_complete", "method": "POST", "path": "/v1/events",
 "status": 202, "latency_seconds": 0.0043, "trace_id": "a1b2-c3d4-..."}
```

**`X-Trace-ID` 响应头**：每个响应均携带 `X-Trace-ID: <uuid>`，可用于客户端问题排查。

---

### 10.2 Prometheus 指标完整清单

**计数器（Counter）**

| 指标 | Labels | 注释 |
|------|------|------|
| `traceability_ingest_requests_total` | `outcome` | `accepted / rejected_signature / idempotency_conflict` |
| `traceability_anchoring_runs_total` | `outcome` | `anchored / failed_retrying / dead_letter / already_anchored` |
| `traceability_anchoring_outcomes_total` | `outcome` | `success / retry / dead_letter` |
| `traceability_anchoring_rollout_decisions_total` | `mode, path` | Rollout 分流次数 |
| `traceability_anchoring_rollout_transitions_total` | `to_state` | 模式切换次数 |
| `traceability_anchoring_rollout_canary_outcomes_total` | `outcome` | Canary 样本结果 |
| `traceability_compat_requests_total` | `endpoint, method, status` | 已废弃接口请求量 |

**直方图（Histogram）**

| 指标 | Buckets | 注释 |
|------|------|------|
| `traceability_ingest_latency_seconds` | 5ms−5s | 摄入延迟分布 |
| `traceability_anchoring_latency_seconds` | 5ms−10s | 锚定延迟分布 |
| `traceability_anchoring_rollout_canary_confirmation_seconds` | 1s−600s | Canary EVM 确认时间 |

#### 关键监控看板建议

```promql
# 摄入成功率
rate(traceability_ingest_requests_total{outcome="accepted"}[5m])
/ rate(traceability_ingest_requests_total[5m])

# 锚定死信塑率
rate(traceability_anchoring_outcomes_total{outcome="dead_letter"}[10m])
/ rate(traceability_anchoring_outcomes_total[10m])

# Canary p95 确认时间
histogram_quantile(0.95,
  rate(traceability_anchoring_rollout_canary_confirmation_seconds_bucket[10m]))

# 已废弃 API 接口流量占比
sum(rate(traceability_compat_requests_total[1d]))
/ sum(rate(traceability_ingest_requests_total[1d]))
```

---

### 10.3 告警系统

```mermaid
stateDiagram-v2
    [*] --> open : create_alert()
    open --> acknowledged : ack(actor)
    open --> resolved : resolve(actor)
    acknowledged --> resolved : resolve(actor)
    open --> open : escalate() 升级 severity
    acknowledged --> acknowledged : escalate() 升级 severity
    note right of open
        severity: low→medium→high→critical
    end note
```

**告警去重**：相同 `(type, severity, message, status, event_id)` 在 `ANCHOR_ALERT_SUPPRESSION_SECONDS`（默认 300s）内不重复创建。防止 Worker 循环导致告警风暴。

| 告警类型 | 触发时机 | 初始严重性 |
|------|------|------|
| `ANCHOR_RETRY_FAILURE` | retry_count < 3 失败 | `high`（第 1 次）/ `medium`（第 2 次）|
| `ANCHOR_DEAD_LETTER` | retry_count >= 3 | `critical` |

---
## 11. 兼容层与渐进式废弃

### 11.1 设计思路

兼容共存期的核心原则：当旧客户端迁移不可避免时，让其可测量、可控制，而不是简单封禁路由。

```mermaid
flowchart TD
    A[应用启动] --> B[evaluate_compat_closure_decision]
    B --> C{COMPAT_CLOSURE_ENABLED=1?}
    C -->|No| D[挂载兼容层路由]
    C -->|Yes| E[加载流量历史文件]
    E --> F{releases >= 2
AND
14 days ratio < 1%?}
    F -->|No| D
    F -->|Yes| G[移除旧路由]
    G --> H[旧客户端接收 404]
```

### 11.2 废弃端点清单

| 废弃端点 | 替代端点 | 日落日期 |
|------|------|------|
| `GET /v1/events/recent` | `GET /v1/events` | 2026-09-30 |
| `GET /v1/trace/{batch_id}/public` | `GET /v1/public/trace/{batch_id}` | 2026-09-30 |
| `POST /api/cherry/telemetry` | `POST /v1/events` | 2026-09-30 |

**废弃响应头（自动附加）**：
```http
Deprecation: true
Sunset: Wed, 30 Sep 2026 00:00:00 GMT
Link: </v1/events>; rel="successor-version"
X-Compat-Deprecated: true
X-Compat-Replacement: GET /v1/events
X-Compat-Exit-Criteria: 2 releases + 14 consecutive days < 1% compat ratio
```

### 11.3 `POST /api/cherry/telemetry` 字段映射

| 源字段 | 目标字段 | 转换 |
|------|------|------|
| `seq` | Idempotency-Key | `hw:{device_id}:{seq}` |
| `ts` | `timestamp` | Unix 时间戳 → ISO8601 UTC |
| `temp_c` | `sensor_payload.temperature_c` | 直接 |
| `hum_rh` | `sensor_payload.humidity_pct` | 直接 |
| `co2` | `co2_ppm` | 延伸字段 |
| `vibration_g` | `vibration_g` | 延伸字段 |
| `stage` | `supply_chain_stage` | 直接 |

**`COMPAT_TELEMETRY_SIGNATURE_MODE`**: `observe`（记录不拒绝）或 `enforce`（强制验证）。

### 11.4 退出条件评估

退出条件文件格式：`data/compat_traffic_history.json`

```json
{
  "releases_observed": 3,
  "daily": [
    {"date": "2026-03-01", "total_requests": 5000,
     "compat_requests": 20, "compat_ratio": 0.004}
  ]
}
```

退出条件评估可集成至 CI/CD：`python scripts/check_compat_exit_criteria.py`

---
## 12. 设备管理

### 12.1 设备生命周期

```mermaid
stateDiagram-v2
    [*] --> active : register_device()
    active --> active : add_or_rotate_device_key()<br/>(旧密钥 retired，新密钥 active)
    active --> disabled : 所有 active key retired
    disabled --> [*] : 终态，不可重新激活
```

### 12.2 密钥轮换原子语义

```python
# add_or_rotate_device_key() 内一个事务内
with session.begin():
    active_keys = session.query(ManagedDeviceKey).filter_by(
        device_id=device.id, status='active'
    ).all()
    retired_ids = []
    for key in active_keys:            # 1. 退役所有现有 active 密鑰
        key.status = 'retired'
        key.retired_at = utcnow()
        retired_ids.append(key.key_id)
    session.add(ManagedDeviceKey(       # 2. 插入新 active 密钥
        status='active', activated_at=utcnow(), ...))
    append_audit_row(                   # 3. 审计日志
        action='admin.device.key.rotate', ...)
# 外层收到对 key 加密的设备将无缝切换到新密钥
```

> **设计约束**：每个设备在任意时刻最多只有 **1** 个 `active` 密钥。历史密钥标记为 `retired` 保留，不删除，用于审计。

### 12.3 设备在线状态判断

```python
DEVICE_ONLINE_THRESHOLD = timedelta(minutes=15)

# GET /admin/devices/{device_id} 内自动计算
last_seen = max(event.timestamp for event in device.events) if device.events else None
status = 'Online' if last_seen and (utcnow() - last_seen) < threshold else 'Offline'
```

### 12.4 审计分析能力

`GET /admin/devices/{device_id}` 自动计算：

| 字段 | 来源 | 说明 |
|------|------|------|
| `signature_failures_last_24h` | `audits` 表 | `action='ingest.signature.verify'` + `result='failure'` + 24h 窗口 |
| `latest_signature_failure_reason` | `audits` 表 | 最近一次失败的 `reason` 字段 |
| `online_status_explanation` | 最近事件时间 | `Online / Offline` + 语境说明 |

**常见运维场景**：设备插入新 SIM 卡后密钥未同步，通过 `signature_failures_last_24h` 和 `latest_signature_failure_reason: managed_key_not_found` 即可定位。

---
## 13. 前端架构

### 13.1 技术选型与分层

| 层级 | 技术 | 选型理由 |
|------|------|------|
| 路由/渲染 | Next.js 16 App Router | SSR 支持、路由组 |
| UI 状态 | TanStack Query v5 | 自动重试、缓存失效、请求加容 |
| 全局状态 | Zustand v5 | 认证 token 管理，轻量无样样板 |
| 数据可视化 | Recharts v3 | 温度趋势、质量分布图表 |
| 样式 | Tailwind CSS v4 | 工具式 CSS |
| 动画 | Framer Motion v12 | 页面切换过渡 |
| 测试 | Vitest | 単元测试 |

### 13.2 API 层设计与拦截器

```typescript
// lib/api.ts - Axios 实例配置
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:18941',
});

// 请求拦截器：受保护路由自动附加 Bearer Token
const PROTECTED_PREFIXES = ['/admin/', '/v1/alerts', '/v1/devices', '/metrics'];
api.interceptors.request.use((config) => {
  if (PROTECTED_PREFIXES.some(p => config.url?.includes(p))) {
    const token = useAuthStore.getState().token;
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：将 RFC9457 转换为统一错误类型 + 自动登出
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) useAuthStore.getState().logout();
    const d = err.response?.data ?? {};
    throw { status: d.status, type: d.type, title: d.title, detail: d.detail };
  }
);
```

### 13.3 客户端 HMAC-SHA256 签名

```typescript
// lib/signing.ts - 使用 Web Crypto API，与服务端 Python 实现语义对齐
async function signTraceEventPayload(payload: TraceEvent, secret: string) {
  // 1. 排除 signature 字段构建签名载荷
  const signingPayload = buildSigningPayload(payload);
  // 2. 规范化（与 Python canonicalize_payload 完全对应）
  const canonical = JSON.stringify(canonicalizeValue(signingPayload));
  // 3. HMAC-SHA256 签名
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(canonical));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2,'0')).join('');
}
```

### 13.4 应对共存期的 API 回退路由

```typescript
// 前端自动处理兼容 API 调用层：先尝试废弃端点，失败后自动回退
async function getRecentEvents() {
  try {
    return await api.get('/v1/events/recent');  // 旧端点
  } catch (err: any) {
    if (err.status === 404 || err.status === 410) {
      return await api.get('/v1/events');        // 新端点
    }
    throw err;
  }
}
```

### 13.5 应用路由

| 路径 | 页面 | 认证 |
|------|------|------|
| `/` | 主仓位板 | 需登录 |
| `/login` | 登录页 | 公开 |
| `/trace` | 公开溯源查询 | 公开 |

---
## 14. 运维手册（Runbook）

### 14.1 Dead-Letter 任务处置流程

当锚定任务重试 3 次后进入 `DEAD_LETTER` 状态，系统自动创建 `critical` 级别告警。

**标准处置步骤**：

```bash
# 第 1 步: 查看 Dead-Letter 任务列表
GET /admin/anchoring/tasks?status=DEAD_LETTER

# 第 2 步: 检查错误信息
# 响应中的 last_error 字段包含最后一次失败的具体错误

# 第 3 步: 根据错误类型处置
# 情况 A: EVM 节点暂时不可用
#   -> 等待节点恢复后执行以下步骤 4
#
# 情况 B: Gas 不足或云端错误
#   -> 检查 Gas 上限和节点状态
#
# 情况 C: 合约 hash 验证失败
#   -> 检查 canonical_hash 是否被篹改（数据完整性问题）

# 第 4 步: 重新入队
POST /admin/anchoring/tasks/{ingest_request_id}/requeue

# 第 5 步: 手动触发 Worker 验证
POST /admin/anchoring/run-once {"limit": 10}

# 第 6 步: 解决对应 critical 告警
POST /v1/alerts/{alert_id}/resolve
```

---

### 14.2 Canary 异常响应 SOP

**触发条件**：`GET /metrics` 中出现以下任意一项违规持续 > 5 分钟：
- `canary_outcomes{outcome='dead_letter'}` 超过 0.5%
- `canary_outcomes{outcome='retry'}` 超过 1%，且成功率 < 99%
- Canary `confirmation_seconds` p95 超过 120s

**手动回滚步骤**：

```bash
# 第 1 步: 立即回滚
export ANCHOR_EVM_ROLLOUT_MODE=rollback_safe

# 第 2 步: 重启应用
# （Kubernetes: kubectl rollout restart deployment/traceability-api）

# 第 3 步: 验证 rollout 指标全部展示 rollback_safe
# traceability_anchoring_rollout_decisions_total{mode='rollback_safe'} 应递增

# 第 4 步: 检查是否存在 Dead-Letter 积压任务
GET /admin/anchoring/tasks?status=DEAD_LETTER

# 第 5 步: 分析异常根因后重新制定 Canary 计划
```

---

### 14.3 数据库备份与恢复

```bash
# SQLite 备份建议使用 WAL 模式 + 定期备份
sqlite3 data/app.db '.backup data/app.db.bak'

# 验证备份完整性
sqlite3 data/app.db.bak 'PRAGMA integrity_check;'

# PostgreSQL 生产环境建议使用：
# TRACEABILITY_DATABASE_URL=postgresql+psycopg2://user:pass@host/db

# 版本升级前备份
alembic upgrade head  # 重新迁移局幂等，已应用的迁移不重执行
```

### 14.4 健康检查端点

| 端点 | 用途 |
|------|------|
| `GET /health` | 应用健康状态（负载均衡 / K8s liveness probe）|
| `GET /metrics` | Prometheus 指标（建议内网侧访问）|

---
## 15. 性能规格与 SLO

### 15.1 延迟预算

| 路径 | P50 预期 | P99 预期 | 主要开销 |
|------|------|------|------|
|| `POST /v1/events`（mock 锚定） | < 10ms | < 50ms | 签名验证 + DB 写入 |
| `GET /v1/public/trace` | < 20ms | < 100ms | 多表 JOIN + 聚合 |
| `GET /v1/stats/overview` | < 30ms | < 200ms | 多 COUNT + GROUP BY |
| EVM 锚定（全流程） | ~30s | ~120s | 链上确认等待 |

> 以上数据基于 SQLite 单实例、第 1000 条事件以内的参考值。生产环境建议通过 `GET /metrics` 建立基准线后确定具体指标。

### 15.2 写放大分析

一条事件摄入产生的数据库写入：

| 操作 | 写入条数 | 表 |
|------|------|------|
| 事件摄入 | 1 | `events` |
| 摄入请求 | 1 | `ingest_requests` |
| 质量评分（如开启）| 1 | `quality_results` |
| 锚定提交 | 1 | `anchor_submission_records` |
| 锚定回执 | 1 | `anchor_receipts` |
| 最多审计记录 | 1-2 | `audits` |
| **合计** | **6-7** | 每条事件的最大 DB 写入 |

### 15.3 容量规划建议

| 场景 | 建议 |
|------|------|
| 事件量 < 10 万/天 | SQLite + 单实例可支撑 |
| 事件量 10-100 万/天 | 切换到 PostgreSQL |
| 事件量 > 100 万/天 | PostgreSQL + 指标优化 + Worker 水平扩展 |
| EVM 高并发 | 多 Worker 实例 + 不同 nonce 管理 |

### 15.4 关键索引

```sql
-- 已建索引
CREATE UNIQUE INDEX ON events(canonical_hash);         -- 内容去重
CREATE UNIQUE INDEX ON ingest_requests(idempotency_key); -- 幂等一级
CREATE INDEX ON events(batch_id, timestamp);            -- 批次查询
CREATE INDEX ON events(device_id);                     -- 设备过滤
CREATE INDEX ON ingest_requests(ingest_status);        -- Worker 拾取
CREATE UNIQUE INDEX ON managed_devices(device_id);     -- 设备标识
CREATE UNIQUE INDEX ON managed_device_keys(key_id);    -- 密钥查找
```

---
## 16. 故障模式目录

本节列举所有已知故障模式及其根因和恢复清单。

### 16.1 摄入层故障

| 现象 | HTTP 状态码 | `detail` | 根因 | 处置 |
|------|------|------|------|------|
|| 签名算法不支持 | 401 | `unsupported_algorithm` | 设备使用了未支持的算法 | 检查 `signature_envelope.algorithm` |
| 密钥 ID 不存在 | 401 | `managed_key_not_found` / `fallback_key_not_found` | `key_id` 尚未注册 | 注册密钥或检查 env |
| 设备已禁用 | 401 | `managed_device_disabled` | 设备被禁用 | 检查管理后台 |
|| 密鑰已退役 | 401 | `managed_key_inactive` | 密鑰被轮换 | 更新设备至新密鑰 |
| device_id 不匹配 | 401 | `managed_key_device_mismatch` | 设备使用了其他设备的密钥 | 安全审查 |
| 幂等冲突 | 409 | `idempotency_conflict` | 相同 Key 不同内容 | 检查客户端重试逻辑 |

### 16.2 锚定层故障

| 现象 | 状态流转 | 根因 | 处置 |
|------|------|------|------|
| EVM 节点无法连接 | ANCHORING → FAILED_RETRYING | `ConnectionError` | 检查 `ANCHOR_EVM_RPC_URL` 和网络 |
|| Gas 费用不足 | ANCHORING → FAILED_RETRYING | `insufficient funds` | 补充 Gas 余额 |
| 重组检测 | ANCHORING → FAILED_RETRYING | `AnchorVerificationError` | 系统自动重新提交 |
| Hash 验证失败 | ANCHORING → FAILED_RETRYING | `hash mismatch` | **严重**: 可能存在数据篡改，需人工审查 |
| 达到最大重试 | FAILED_RETRYING → DEAD_LETTER | retry >= 3 | 查看具体错误后 requeue |
| Canary SLO 违规 600s | 自动回滚 rollback_safe | 节点异常 | 检查 EVM 节点状态，重新出发 |

### 16.3 降级备选方案（Fallback）

| 场景 | 自动降级行为 |
|------|------|
| EVM 节点完全不可用 | `rollback_safe` 模式下全部走 mock，摄入不受影响 |
| Canary SLO 持续违规 | 自动回滚 `rollback_safe`，不需人工干预 |
| Worker 崩溃重启 | `PENDING` submission 恢复机制，不重复上链 |
| DB 写入并发冲突 | `IntegrityError` 捕获 + rollback + 再查询 |

---
## 17. 数据库迁移

### 17.1 迁移历史

| 版本 | 日期 | 内容 |
|------|------|------|
| `20260210_0201` | 2026-02-10 | 初始化：`events`, `audits`, `quality_results` |
| `20260210_0315` | 2026-02-10 | 摄入状态机：`ingest_requests`, `anchor_receipts`, `anchor_submission_records` |
| `20260210_0400` | 2026-02-10 | 设备管理：`managed_devices`, `managed_device_keys`, `alerts` |
| `20260214_0100` | 2026-02-14 | 延伸字段：`events.co2_ppm`, `vibration_g`, `supply_chain_stage` |

### 17.2 常用命令

```bash
alembic upgrade head      # 应用所有未应用迁移
alembic downgrade -1      # 回滚一版本
alembic current           # 查看当前版本
alembic history --verbose # 历史记录
alembic revision --autogenerate -m 'add_new_column'  # 生成迁移
```

### 17.3 并发安全模式初始化

服务和 Worker 均采用双重检查锁模式懒初始化 schema，多进程安全：

```python
_SCHEMA_READY: bool = False
_SCHEMA_LOCK: threading.Lock = threading.Lock()

def _ensure_schema(engine):
    global _SCHEMA_READY
    if _SCHEMA_READY: return            # 快速路径（无锁）
    with _SCHEMA_LOCK:
        if not _SCHEMA_READY:           # 二次检查，防止并发重复初始化
            Base.metadata.create_all(engine)  # 幂等操作
            _SCHEMA_READY = True
```

---

## 18. 部署指南

### 18.1 核心环境变量

```bash
# === 必设（生产环境）===
AUTH_JWT_SECRET=<随机 256-bit 密钥>
CORS_ALLOW_ORIGINS=https://your-frontend.example.com
TRACEABILITY_DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/traceability

# === EVM 配置（如开启区块链锚定）===
ANCHOR_ADAPTER=evm_contract
ANCHOR_EVM_ROLLOUT_MODE=shadow        # 建议先开 shadow 验证
ANCHOR_EVM_RPC_URL=https://your-node.example.com
ANCHOR_EVM_CONTRACT_ADDRESS=0x...
ANCHOR_EVM_SIGNER_URL=https://hsm.internal/sign  # 生产建议使用 HSM
ANCHOR_EVM_SIGNER_TOKEN=<token>

# === 默认值（通常不需修改）===
ANCHOR_EVM_GAS_LIMIT=250000
ANCHOR_EVM_REQUIRED_CONFIRMATIONS=1
ANCHOR_EVM_MAX_SUBMISSION_ATTEMPTS=3
ANCHOR_ALERT_SUPPRESSION_SECONDS=300
ANCHOR_WORKER_BATCH_SIZE=100
```

### 18.2 EVM 切换步骤路径图

```mermaid
flowchart LR
    A[rollback_safe
默认安全] -->|ROLLOUT_MODE=shadow| B[shadow
验证连通性]
    B -->|ROLLOUT_MODE=canary| C[canary 5%
SLO 监控]
    C -->|SLO 达标 + 手动确认| D[full
全量 EVM]
    C -->|SLO 违规 600s| A
    D -->|ROLLOUT_MODE=rollback_safe| A
```

### 18.3 开发环境快速启动

```bash
# 后端
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --port 18941 --reload

# Worker (可选)
python -m app.jobs.anchor_worker --poll-seconds 5

# 前端
cd frontend && npm ci && npm run dev
```

---
## 19. 开发指南

### 19.1 测试体系

```bash
# 单元测试（asyncio_mode=auto）
pytest tests/ -m 'not e2e'

# e2e 测试（需本地 EVM 节点）
pytest tests/ -m e2e

# 单个测试文件
pytest tests/unit/test_hash_canonicalization.py -v

# 前端测试
cd frontend && npx vitest run
```

**关键测试策略**：
- 对哈希规范化必需覆盖 Python + TypeScript 双端一致性验证
- 摄入测试使用 Mock DB，避免状态污染
- EVM 测试使用 Hardhat/Anvil 本地节点

### 19.2 合约守卫

```bash
# 验证 API 合约未破坏（建议集成至 CI）
python scripts/contract_guard.py

# 检查兼容层退出条件
python scripts/check_compat_exit_criteria.py
```

### 19.3 扩展新锚定适配器

```python
# 1. 继承 AnchorAdapter ABC
class MyChainAdapter(AnchorAdapter):
    def anchor_event(self, *, event_id, canonical_hash, payload) -> AnchorSubmission:
        ...
    def get_receipt(self, tx_hash: str) -> AnchorReceiptData:
        ...
    def verify_anchor(self, *, canonical_hash, receipt) -> bool:
        ...
    def supports_durable_submissions(self) -> bool:
        return True

# 2. 在工厂函数注册
# anchoring.py 内的 _build_adapter() 函数中添加 elif 分支

# 3. 设置环境变量
# ANCHOR_ADAPTER=my_chain
```

### 19.4 扩展质量评分指标

```yaml
# domain/quality/rules.yml 添加新指标，无需修改代码
metrics:
  ethylene_ppm:  # 举例：乙烯浓度监测
    ideal:   { min: 0, max: 5 }
    warning: { min: 0, max: 20 }
    weight: 0.05   # 确保所有 weight 合计 = 1.0
```

---

## 20. 词汇表

| 术语 | 定义 |
|------|------|
|| **canonical hash** | 通过确定性规范化算法对 payload 计算的 SHA-256 哈希。不同平台对相同输入必得到相同哈希（cross-platform deterministic normalization）。 |
|| **HMAC** | 基于哈希的消息认证码（Hash-based Message Authentication Code）。本项目使用 HMAC-SHA256 对事件 payload 进行签名验证。 |
| **IngestStatus** | 事件锚定进度的标识符: `RECEIVED → ANCHORING → ANCHORED` 或 `FAILED_RETRYING → DEAD_LETTER`。 |
| **Rollout Mode** | EVM 锚定的嵌入式部署模式。`rollback_safe` 为默认安全状态；`canary` 为 5% 分流验证阶段。 |
| **Durable Submission** | EVM 交易提交后在收到 receipt 前将 `tx_hash` 持久化到 DB，保证 Worker 崩溃后可恢复，不重复上链。 |
|| **Compat Closure** | 兼容层封锁，移除已废弃路由。由流量数据评估退出条件后执行。 |
| **Idempotency Key** | 客户端提供的请求唯一标识符，确保重试安全。通常为 UUID v4。 |
| **SLO** | 服务级别目标（Service Level Objective）。Canary 阶段的 SLO：成功率 >= 99%、dead-letter率 <= 0.5%、p95 确认 <= 120s。 |
| **ADR** | 架构决策记录（Architecture Decision Record）。记录关键设计决策的背景、备选方案和最终取舍。 |
| **supply_chain_stage** | 供应链阶段枚举：`harvest`（采摘）/ `storage`（存储）/ `transport`（运输）/ `retail`（零售）。 |
| **ABI** | 应用二进制接口（Application Binary Interface）。定义 EVM 合约函数调用和事件的编码方式。 |
| **EVM** | 以太坊虚拟机（Ethereum Virtual Machine）。广泛用于区块链合约执行。 |
|| **Reorg** | 区块链重组（Reorganization）。协议用更长的链替换了之前的最新块，导致已包含的交易失效。 |
| **HSM** | 硬件安全模块（Hardware Security Module）。生产环境推荐用于存储 EVM 私钥。 |
