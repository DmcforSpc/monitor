# REST API 参考

所有端点 **只读**（仅 GET）。基础路径 `/api/v1`，健康检查例外。

## 健康检查（不带版本前缀）

### `GET /api/health` — Liveness

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{ "status": "ok", "version": "1.0.0" }
```

进程在线即 200，不做任何 I/O。

### `GET /api/ready` — Readiness

```bash
curl http://127.0.0.1:8000/api/ready
```

成功：

```json
{ "status": "ready", "version": "1.0.0" }
```

DB 不可用：HTTP 503 +

```json
{ "status": "not_ready", "error": "<exception text>" }
```

## 数据 API（`/api/v1/...`）

### `GET /api/v1/stats`

```json
{
  "total_items": 123,
  "by_status": { "new": 0, "processed": 5, "notified": 118, "skipped": 0 },
  "by_collector": { "cisa_kev": 80, "ghsa": 43 },
  "collectors_registered": 2,
  "notifiers_registered": 1,
  "scheduler": { "running": true, "interval_seconds": 300, "next_run": "..." }
}
```

### `GET /api/v1/items`

| Query | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 1 | 1-based |
| `size` | int | 20 | 1-200 |
| `collector` | str | — | 按采集器过滤 |
| `status` | enum | — | `new` / `processed` / `notified` / `skipped` |
| `q` | str | — | 模糊搜 title / external_id / summary |

返回 `{ total, page, size, items: [...] }`。

### `GET /api/v1/items/{item_id}`

单条详情。404 if 不存在。

### `GET /api/v1/collectors`

```json
[
  { "name": "cisa_kev", "description": "...", "enabled": true },
  { "name": "ghsa", "description": "...", "enabled": false }
]
```

### `GET /api/v1/notifiers`

同上结构，列出注册的通知渠道。

### `GET /api/v1/runs?limit=50`

最近 N 次 collector 执行记录：

```json
[
  {
    "id": 1,
    "collector": "cisa_kev",
    "status": "ok",
    "items_found": 50,
    "items_new": 12,
    "duration_ms": 845,
    "error": "",
    "started_at": "2026-05-27T17:51:23+00:00"
  }
]
```

### `GET /api/v1/notifications?limit=50`

最近 N 次通知派发记录：

```json
[
  {
    "id": 1,
    "item_id": 42,
    "notifier": "feishu",
    "status": "sent",
    "detail": "HTTP 200",
    "created_at": "2026-05-27T17:51:25+00:00"
  }
]
```

## CORS

默认无 CORS。配 `CVE_CORS_ORIGINS` 启用，仅 `GET` 被白名单（API 只读）。

## 鉴权

无。Web/API 设计为可直接公网部署（公开漏洞情报）。如需限制访问，在 Nginx 层加 Basic Auth 或 IP 白名单。

## OpenAPI

启动后访问：

- `http://127.0.0.1:8000/docs` — Swagger UI
- `http://127.0.0.1:8000/redoc` — ReDoc
- `http://127.0.0.1:8000/openapi.json` — 原始 schema
