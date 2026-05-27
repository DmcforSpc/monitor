# 观测性

## 默认日志

开箱即用 `structlog` 结构化日志：
- 控制台彩色（有 TTY 时）/ JSON（设 `CVE_LOG_JSON=true`）
- 文件 `cve-monitor.log` 自动 5MB × 3 轮转

```bash
CVE_LOG_LEVEL=DEBUG    # DEBUG / INFO / WARNING / ERROR
CVE_LOG_FILE=""        # 留空 = 仅控制台（容器场景推荐）
CVE_LOG_JSON=true      # 接 ELK / Loki / Datadog 等聚合器时打开
```

## Logfire 自动 instrumentation

[Logfire](https://logfire.pydantic.dev) 是 Pydantic 团队的可观测性平台，一行接入 FastAPI / SQLAlchemy / httpx 全链路 trace。**完全可选** — 没装 extras / 没设 token 全部 no-op。

### 安装

```bash
uv pip install -e ".[observability]"
```

### 配置

```bash
export LOGFIRE_TOKEN=lf_xxxxxxxxxxxx   # 从 https://logfire.pydantic.dev 拿
uv run cve-monitor serve
```

启动日志会看到：

```
[info] Logfire observability enabled
```

### 自动捕获

| 来源 | 捕获内容 |
| --- | --- |
| FastAPI | 每个请求的 method / path / status / latency / headers（已去敏） |
| SQLAlchemy | 每条 SQL 的参数化文本 + 执行耗时 |
| httpx | 所有 collector / notifier 出站调用 |

### Dashboard

Logfire 控制台自动汇聚 trace、metrics、logs，比 grep 日志快 100 倍：

- 慢请求 trace 自动高亮
- p50/p95/p99 延迟分布按路由切片
- DB 查询热点 top N

## OpenTelemetry（如果你拒绝 SaaS）

Logfire 内部基于 OTel，所以你可以同样接 OTel collector：

```python title="src/observability.py 自定义版"
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def configure_observability(app, settings):
    provider = TracerProvider(resource=Resource.create({"service.name": settings.app_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317")))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```

接 Jaeger / Tempo / Honeycomb / 自托管 collector 都行。

## 健康检查

容器编排（K8s、Render、ECS）应分别接：

| 探针 | 端点 | 行为 |
| --- | --- | --- |
| liveness | `/api/health` | 进程在线即 200 |
| readiness | `/api/ready` | 跑通 `SELECT 1` 才 200，否则 503 |

Docker `HEALTHCHECK` 默认接的是 `/api/health`，已写进 Dockerfile。
