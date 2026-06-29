# 数据模型

三张表，全部位于 `src/db/models.py`，故意不绑定 CVE 语义。

## `collected_items`

主存储 — 所有 collector 产出的事件归一化到这里。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INT PK auto | 主键 |
| `collector` | VARCHAR(64) NOT NULL, indexed | 采集器名（`BaseCollector.name`） |
| `external_id` | VARCHAR(128), indexed | 源系统 ID（CVE-xxxx / GHSA-xxxx / 邮件 ID …），可空 |
| `fingerprint` | VARCHAR(256) NOT NULL **UNIQUE** | **跨源去重唯一键**。必填 |
| `title` | VARCHAR(1024) | 显示标题 |
| `url` | VARCHAR(2048) | 详情链接 |
| `summary` | TEXT | 简短描述 |
| `payload` | JSON NOT NULL | 自由结构 — 源特定字段 |
| `status` | ENUM | `new` / `processed` / `notified` / `skipped` |
| `created_at` | TIMESTAMP TZ NOT NULL, indexed | UTC，自动填 |
| `processed_at` | TIMESTAMP TZ | pipeline 处理时间 |

**索引**：`fingerprint` 唯一、`(collector, created_at)` 复合、各单字段索引。

## `collector_runs`

每次 collector 执行记录一条。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INT PK auto | |
| `collector` | VARCHAR(64), indexed | |
| `status` | ENUM | `ok` / `error` |
| `items_found` | INT | collector 返回的总数 |
| `items_new` | INT | 实际新入库（去重后） |
| `duration_ms` | INT | 总耗时毫秒 |
| `error` | TEXT | 异常 + traceback（status=error 时） |
| `started_at` | TIMESTAMP TZ, indexed | |

## `notifications`

每条 (item × notifier) 派发记录一行。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INT PK auto | |
| `item_id` | INT, indexed | 关联 `collected_items.id`（无外键约束以避免级联开销） |
| `notifier` | VARCHAR(64), indexed | |
| `status` | ENUM | `sent` / `failed` / `skipped` |
| `detail` | TEXT | HTTP 响应文本或错误描述 |
| `created_at` | TIMESTAMP TZ, indexed | |

**唯一约束**：`(item_id, notifier)` — 同一 item 不会被同一 notifier 重复推送。

## ENUM 字段

实现：`enum.StrEnum`（Python 3.11+）。

```python
class ItemStatus(enum.StrEnum):
    NEW = "new"
    PROCESSED = "processed"
    NOTIFIED = "notified"
    SKIPPED = "skipped"
```

数据库里以字符串存储（`Enum(..., native_enum=False)`），可跨 SQLite / Postgres / MySQL 无缝迁移。

## 为什么不为 CVE / EPSS / CVSS 设专用字段

刻意避免 — 不同 collector 关心的字段差异很大：
- `poc_github` 关心 `repo` / `stars` / `cve_id` / `trust`
- `poc_search` 关心 `repo` / `language` / `pushed_at` / `stars`
- RSS 关心 `published_at` / `tags`
- 自建 Webhook 可能有完全不同的字段

**全部存进 `payload` JSON 列**。Web 和 API 透传 dict，不做强制结构。当某些字段在多个 collector 间共享、且想被 dashboard 高亮显示时，再考虑提升到独立列。

## Schema 演进

目前用 `Base.metadata.create_all()`，适合 dev / 演示。生产 schema 演进推荐接 [Alembic](https://alembic.sqlalchemy.org/)：

```bash
uv add alembic
uv run alembic init migrations
uv run alembic revision --autogenerate -m "add my_field"
uv run alembic upgrade head
```

（目前框架尚未集成 Alembic — 在 roadmap 上。）
