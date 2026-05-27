# CVE Monitor

> **可扩展的安全情报采集与推送框架** — 提供数据采集、去重、调度、Web 仪表盘和通知派发的通用基础设施。具体业务（采集源、通知渠道、评分规则）以**插件式**由你自行扩展。

## 设计理念

- :material-puzzle: **框架与业务分离**：核心代码不耦合任何具体 CVE / RSS / Webhook 数据源
- :material-link-variant: **插件化注册**：实现 `BaseCollector` / `BaseNotifier` 子类放入 `collectors/` / `notifiers/` 自动加载
- :material-database: **通用数据模型**：`CollectedItem` 不绑定 CVE 语义，扩展字段存 JSON `payload`
- :material-rocket-launch: **现代 Python 工程**：Pydantic v2、SQLAlchemy 2.0、Typer、uv、structlog

## 30 秒预览

```bash
pip install uv
uv pip install -e ".[dev]"
uv run cve-monitor db init
uv run cve-monitor serve
```

打开 `http://127.0.0.1:8000` → 仪表盘已上线。

## 接下来读什么

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **[快速开始](getting-started.md)**

    ---

    5 分钟从零到运行中的实例

-   :material-sitemap:{ .lg .middle } **[架构](architecture.md)**

    ---

    三层管线 + 插件加载 + 数据流动

-   :material-puzzle-plus:{ .lg .middle } **[插件开发](plugins/collectors.md)**

    ---

    第一个 collector / notifier 实战

-   :material-server:{ .lg .middle } **[部署](deployment/docker.md)**

    ---

    Docker · 安全中间件 · 观测性

</div>
