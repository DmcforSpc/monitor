# CVE Monitor v1.0

> **可扩展的安全情报采集与推送框架** — 提供数据采集、去重、调度、Web 仪表盘和通知派发的通用基础设施，业务逻辑（具体采集源、通知渠道、评分规则）以**插件式**方式由用户自行扩展。

## 设计理念

- **框架与业务分离**：核心代码不耦合任何具体 CVE / RSS / Webhook 数据源
- **插件化注册**：实现 `BaseCollector` / `BaseNotifier` 子类并放入 `collectors/` / `notifiers/` 即被自动加载
- **通用数据模型**：`CollectedItem` 不绑定 CVE 语义，特定字段存放在 JSON `payload` 列
- **现代 Python 工程**：Pydantic v2 配置、SQLAlchemy 2.0 typed mappings、Typer CLI、uv 包管理、结构化日志

## 快速开始

```bash
# 1. 安装 uv（一次性）
pip install uv   # 或 curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安装依赖并创建 venv
uv sync

# 3. 复制环境变量模板（可选 - 全部有默认值）
cp .env.example .env

# 4. 初始化数据库
uv run cve-monitor db init

# 5. 启动 Web 仪表盘 + 调度器
uv run cve-monitor serve
```

打开 `http://127.0.0.1:8000` 查看仪表盘。

### Docker（生产推荐）

```bash
# 单容器
docker build -t cve-monitor .
docker run -d --name cve-monitor -p 8000:8000 -v cve-data:/data \
    -e CVE_DATABASE_URL=sqlite:////data/cve_monitor.db cve-monitor

# 或用 compose（自动持久化卷 + 健康检查）
docker compose up -d
docker compose logs -f
```

镜像基于 `python:3.11-slim`，多阶段构建用 uv 锁定依赖，运行时为非 root 用户 + 内置 healthcheck。

### 安全中间件（公网部署）

通过环境变量按需启用，全部默认关闭：

```bash
CVE_ALLOWED_HOSTS="cve.example.com,localhost"   # TrustedHost
CVE_CORS_ORIGINS="https://app.example.com"      # 允许浏览器跨域 GET
CVE_CORS_ALLOW_CREDENTIALS=false
```

`SecurityHeadersMiddleware` 默认始终启用（无需配置），会注入 `X-Content-Type-Options`、`X-Frame-Options: DENY`、`Strict-Transport-Security`、`Referrer-Policy`、`Permissions-Policy`、`Cross-Origin-Opener-Policy`。

### 观测性（Logfire，可选）

```bash
uv pip install -e ".[observability]"
export LOGFIRE_TOKEN=lf_xxxxxxxxxxxx   # 从 https://logfire.pydantic.dev 取
uv run cve-monitor serve
```

一行配置自动 instrumentation：FastAPI 请求 span、SQLAlchemy 查询耗时、httpx 出站调用。未装 extras 或没设 token 时全部静默 no-op，不增加任何运行时开销。

### 健康检查端点

| 端点 | 用途 | 行为 |
| --- | --- | --- |
| `GET /api/health` | Liveness 探针 | 进程在线即 200，不做任何 I/O |
| `GET /api/ready`  | Readiness 探针 | 能跑通一次 `SELECT 1` 才 200，否则 503 |

两者**不进版本前缀**——基础设施（K8s、Docker HEALTHCHECK、负载均衡）依赖固定路径。

### API 版本化

所有数据端点位于 `/api/v1/...`，未来重大变更会上 `/api/v2/...` 不打断旧调用方。`/api/health` 和 `/api/ready` 是例外，永远不带版本号。

## CLI 命令

```bash
uv run cve-monitor --help

uv run cve-monitor serve              # 启动 Web + 调度器
uv run cve-monitor collect            # 跑一轮采集 + 派发
uv run cve-monitor collect --once     # 跑完即退（不进调度循环）
uv run cve-monitor list collectors    # 列出注册的采集器
uv run cve-monitor list notifiers     # 列出注册的通知渠道
uv run cve-monitor db init            # 建表
uv run cve-monitor db reset           # ⚠️ 删表重建
uv run cve-monitor version            # 显示版本
```

## 项目结构

```
src/
├── settings.py              # Pydantic Settings（所有配置入口）
├── logging.py               # structlog 配置
├── cli.py                   # Typer CLI 命令
├── scheduler.py             # APScheduler 封装
├── db/
│   ├── base.py              # engine + Session + Base
│   ├── models.py            # CollectedItem / NotificationRecord / CollectorRun
│   └── repository.py        # 通用 CRUD（去重、查询）
├── core/
│   ├── collectors.py        # BaseCollector + 注册表 + 加载器
│   ├── notifiers.py         # BaseNotifier + 注册表 + 加载器
│   └── pipeline.py          # 采集 → 去重 → 派发 编排
├── web/
│   ├── app.py               # FastAPI 工厂
│   ├── deps.py              # 依赖注入（DB session）
│   ├── middleware.py        # SecurityHeaders / TrustedHost / CORS
│   ├── routes/
│   │   ├── health.py        # /api/health + /api/ready（不带版本）
│   │   ├── api.py           # /api/v1/* 数据 API
│   │   └── pages.py         # 仪表盘
│   └── templates/
│       └── dashboard.html
├── observability.py         # Logfire opt-in 自动 instrumentation
├── collectors/              # 👇 你的采集器实现放这里
└── notifiers/               # 👇 你的通知渠道实现放这里
```

## 扩展：实现一个采集器

新建 `src/collectors/cisa_kev.py`：

```python
from collections.abc import Iterable
from datetime import datetime

import httpx

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem


@register_collector
class CisaKevCollector(BaseCollector):
    name = "cisa_kev"
    description = "CISA Known Exploited Vulnerabilities catalog"
    trust = "high"

    def collect(self) -> Iterable[CollectedItem]:
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        resp = httpx.get(url, timeout=self.settings.http_timeout)
        resp.raise_for_status()
        for v in resp.json().get("vulnerabilities", [])[-50:]:
            cve_id = v["cveID"]
            yield CollectedItem(
                collector=self.name,
                external_id=cve_id,
                title=v["vulnerabilityName"],
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                summary=v.get("shortDescription", ""),
                payload={
                    "vendor": v.get("vendorProject"),
                    "product": v.get("product"),
                    "trust": self.trust,
                },
            )
```

下次 `uv run cve-monitor collect` 就会自动跑它。

## 扩展：实现一个通知渠道

新建 `src/notifiers/feishu.py`：

```python
import httpx

from src.core.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.db.models import CollectedItem


@register_notifier
class FeishuNotifier(BaseNotifier):
    name = "feishu"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("webhook"))

    def send(self, item: CollectedItem) -> NotificationResult:
        resp = httpx.post(
            self.config["webhook"],
            json={
                "msg_type": "interactive",
                "card": {
                    "header": {"title": {"tag": "plain_text", "content": item.title}},
                    "elements": [{"tag": "markdown", "content": item.summary or item.url}],
                },
            },
            timeout=self.settings.http_timeout,
        )
        return NotificationResult(ok=resp.is_success, detail=resp.text[:500])
```

通过环境变量配置：
```bash
CVE_PLUGIN_FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
```

## 数据模型

唯一的"漏洞"表是 `CollectedItem`，结构刻意保持通用：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 主键 |
| `collector` | str | 采集器名称（`name` 字段） |
| `external_id` | str | 源系统 ID（CVE-2024-xxxx、GHSA-xxxx 等，可空） |
| `fingerprint` | str | 跨源去重哈希（`collector:external_id` 或 `collector:url`） |
| `title` / `url` / `summary` | str | 基础展示字段 |
| `payload` | JSON | 任意结构的扩展字段（CVSS、EPSS、PoC、severity ...） |
| `status` | enum | `new` / `processed` / `notified` / `skipped` |
| `created_at` / `processed_at` | datetime | 时间戳 |

如果你需要 CVE 专属字段（CVSS、EPSS 等），存进 `payload` 即可，Web/API 透传。

## 配置（所有变量带 `CVE_` 前缀）

完整列表见 `.env.example`。常用：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_DATABASE_URL` | `sqlite:///./cve_monitor.db` | 数据库 URL |
| `CVE_FETCH_INTERVAL_SECONDS` | `300` | 调度器轮询间隔 |
| `CVE_WEB_HOST` / `CVE_WEB_PORT` | `127.0.0.1` / `8000` | Web 监听 |
| `CVE_LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `CVE_HTTP_TIMEOUT` | `30` | HTTP 超时秒数 |
| `CVE_HTTP_PROXY` | （无） | 代理地址 |

插件配置使用 `CVE_PLUGIN_<NAME>_<KEY>` 命名空间，自动注入到对应 collector/notifier 的 `self.config`。

## 安全

- **永远不要把 `.env` 或 `config.yaml` 提交进 git** — `.gitignore` 已默认排除
- 生产环境 `chmod 600 .env`
- Web 仪表盘默认只读，无写入端点；公网部署建议 Nginx + HTTPS + IP 白名单
- 不要用 `root` 运行；推荐 systemd + 普通用户

## 开发

```bash
uv sync --extra dev      # 装开发依赖
uv run pytest            # 跑测试
uv run ruff check .      # lint
uv run ruff format .     # 格式化
uv run mypy src/         # 类型检查
```

## License

MIT
