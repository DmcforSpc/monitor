# 快速开始

## 1. 安装 uv

```bash
pip install uv
# 或 Unix 一行装：curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. 克隆 + 安装

```bash
git clone https://github.com/DmcforSpc/monitor.git
cd monitor
uv pip install -e ".[dev]"
```

## 3. 配置（可选 — 全部有默认值）

```bash
cp .env.example .env
$EDITOR .env
```

常用变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_DATABASE_URL` | `sqlite:///./cve_monitor.db` | DB 连接串 |
| `CVE_FETCH_INTERVAL_SECONDS` | `300` | 调度间隔 |
| `CVE_WEB_HOST` / `CVE_WEB_PORT` | `127.0.0.1` / `8000` | Web 监听 |

完整列表见 [配置参考](reference/configuration.md)。

## 4. 初始化数据库

```bash
uv run cve-monitor db init
```

## 5. 启动

```bash
uv run cve-monitor serve
```

打开 `http://127.0.0.1:8000` → 仪表盘。空数据库是预期 — 还没有 collector。

## 6. 写第一个采集器

```python title="src/collectors/example.py"
from collections.abc import Iterable
from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem


@register_collector
class ExampleCollector(BaseCollector):
    name = "example"
    description = "Hello world collector"

    def collect(self) -> Iterable[CollectedItem]:
        yield CollectedItem(
            collector=self.name,
            external_id="HELLO-1",
            fingerprint=self.fingerprint("HELLO-1"),
            title="Hello from example collector",
            url="https://example.com",
            summary="It works.",
            payload={"hello": "world"},
        )
```

```bash
uv run cve-monitor collect
```

刷新仪表盘 → 看到 1 条新数据。详细做法见 [采集器开发](plugins/collectors.md)。

## 7. 写第一个通知

参见 [通知渠道开发](plugins/notifiers.md)。

## 出错怎么办

| 症状 | 原因 / 修法 |
| --- | --- |
| `ModuleNotFoundError: No module named 'src'` | 没跑 `uv pip install -e .` 把项目装进 venv |
| `sqlite3.OperationalError: database is locked` | 多进程同时写 SQLite。改 Postgres 或合并到单进程 |
| Web 启动后立即退出 | 检查 `cve-monitor.log` 或设 `CVE_LOG_LEVEL=DEBUG` 重试 |
| 端口被占 | `python -m src serve --port 8001` |
