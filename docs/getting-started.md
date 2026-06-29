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

## 6. 启用一个内置默认源（最快）

仓库自带 2 个一手 PoC 采集器 + 1 个默认通知，全部默认 disabled（除了 console）。两行 env 即可看到推送：

```bash
# 启用 nomi-sec PoC 源（一手 PoC 仓库，无需 token）
export CVE_PLUGIN_POC_GITHUB_ENABLED=true
uv run cve-monitor collect
```

启动后日志里能看到形如 `item_dispatched collector=poc_github external_id=CVE-2024-xxxx ...` 的输出，就说明端到端通了。其他可启用的：

| 源 | 启用 env | 备注 |
| --- | --- | --- |
| `poc_github` | `CVE_PLUGIN_POC_GITHUB_ENABLED=true` | nomi-sec PoC-in-GitHub 索引，无 token |
| `poc_search` | `CVE_PLUGIN_POC_SEARCH_ENABLED=true` | 实时 GitHub 仓库搜索，建议设 `POC_SEARCH_TOKEN` 或 `GH_TOKEN`；默认只留名字带具体 `CVE-YYYY-NNNN` 的真 PoC（过滤掉聚合/工具类噪声），设 `POC_SEARCH_REQUIRE_CVE=false` 可放开 |
| `console` | 默认 ON | `CVE_PLUGIN_CONSOLE_ENABLED=false` 关闭 |
| `feishu` | 配 `CVE_PLUGIN_FEISHU_WEBHOOK` 即启用 | 飞书/Lark 群机器人，推送互动卡片；限频 100/min，内置 0.7s 节流 |

## 7. 写第一个采集器

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
