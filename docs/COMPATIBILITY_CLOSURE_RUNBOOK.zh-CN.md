# Compatibility Closure Runbook（中文）

> 语言 / Language: 简体中文 | [English](COMPATIBILITY_CLOSURE_RUNBOOK.md)

## 范围

本 runbook 定义了如何安全关闭以下 compatibility 路由：

- `POST /api/cherry/telemetry`
- `GET /v1/events/recent`
- `GET /v1/trace/{batch_id}/public`

关闭策略固定且可判定：

1. 至少经历 2 个发布版本。
2. 至少连续 14 天，每天 compatibility 流量占比都低于 1%。

## 运行时控制

- `COMPAT_CLOSURE_ENABLED=1`
  - 请求启用 compatibility closure 模式。
  - 只有 gate 条件通过时才会禁用 compatibility 路由。
  - 条件不通过或输入无效时，compatibility 路由保持启用。
- `COMPAT_EXIT_HISTORY_PATH`（默认：`data/compat_traffic_history.json`）
  - gate 检查器读取的历史 JSON 文件。
- `COMPAT_EXIT_RELEASES_OBSERVED`（可选覆盖）
  - 强制指定 gate 评估中的发布版本计数。
- `COMPAT_EXIT_REQUIRED_RELEASES`（默认：`2`）
- `COMPAT_EXIT_REQUIRED_CONSECUTIVE_DAYS`（默认：`14`）
- `COMPAT_EXIT_MAX_RATIO_PERCENT`（默认：`1.0`）

## 历史文件格式

```json
{
  "releases_observed": 2,
  "daily": [
    {
      "date": "2026-02-01",
      "total_requests": 10000,
      "compat_requests_by_endpoint": {
        "/api/cherry/telemetry": 40,
        "/v1/events/recent": 25,
        "/v1/trace/{batch_id}/public": 20
      }
    }
  ]
}
```

说明：

- `daily` 中日期必须为唯一 ISO 日期。
- 如果需要，也可以直接提供每日 `compat_ratio`（`0.0..1.0`）。
- 连续天数判断对自然日连续性是严格校验。

## CI Gate

执行检查器：

```bash
python -X utf8 scripts/check_compat_exit_criteria.py
```

行为：

- 未请求 closure：退出码 `0`，状态 `SKIP`。
- 请求 closure 且条件通过：退出码 `0`，状态 `PASS`。
- 请求 closure 但条件不通过：非零退出码，状态 `FAIL`。

## 弃用窗口期间的可观测性要求

所有 compatibility 响应都要带：

- `Deprecation: true`
- `Sunset: Wed, 30 Sep 2026 00:00:00 GMT`
- `Link: <https://example.com/runbooks/compatibility-closure>; rel="deprecation"; type="text/markdown"`
- `X-Compat-Deprecated: true`
- `X-Compat-Replacement: ...`
- `X-Compat-Exit-Criteria: 2-releases,14-consecutive-days,<1%-traffic`

指标：

- `traceability_compat_requests_total{endpoint,method,status}`

## 回滚

如果 closure 引发回归：

1. 设置 `COMPAT_CLOSURE_ENABLED=0`。
2. 重新部署并确认 compatibility 路由恢复对外服务。
3. 保留流量遥测并重新开始资格窗口。
