# 配置参考

所有变量带 `CVE_` 前缀，从环境变量 / `.env` 文件读。

## 应用

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_APP_NAME` | `CVE Monitor` | 仪表盘标题 |
| `CVE_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `CVE_LOG_FILE` | `cve-monitor.log` | 日志文件路径；留空 = 仅控制台 |
| `CVE_LOG_JSON` | `false` | `true` = JSON 行（便于 ELK / Loki 等抓取） |

## 数据库

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_DATABASE_URL` | `sqlite:///./cve_monitor.db` | SQLAlchemy URL；支持 SQLite / Postgres / MySQL |

Postgres 示例：`postgresql+psycopg://user:pass@host:5432/cve`。SQLite 在容器里挂卷：`sqlite:////data/cve_monitor.db`（注意 4 个斜杠）。

## 调度器

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_SCHEDULER_ENABLED` | `true` | 设 false 跳过自动调度（CLI 一次性场景） |
| `CVE_FETCH_INTERVAL_SECONDS` | `300` | 两次完整 pipeline 之间的秒数；`>= 10` |

## Web

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_WEB_HOST` | `127.0.0.1` | 公网部署改 `0.0.0.0` |
| `CVE_WEB_PORT` | `8000` | 1-65535 |
| `CVE_WEB_RELOAD` | `false` | 仅开发；生产关掉 |

## 安全中间件（opt-in）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_ALLOWED_HOSTS` | （空） | 逗号分隔；空 = 不启 TrustedHostMiddleware |
| `CVE_CORS_ORIGINS` | （空） | 逗号分隔；空 = 不启 CORSMiddleware |
| `CVE_CORS_ALLOW_CREDENTIALS` | `false` | 跨域是否带 Cookie / Authorization |

## HTTP 客户端默认

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CVE_HTTP_TIMEOUT` | `30` | 所有 collector/notifier `self.http_client()` 默认超时 |
| `CVE_HTTP_USER_AGENT` | `CVE-Monitor/1.0` | 出站 UA |
| `CVE_HTTP_PROXY` | （空） | 如 `http://127.0.0.1:7890` |

## 观测性（可选）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LOGFIRE_TOKEN` | （空） | 设置后启用 Logfire；要先 `pip install -e ".[observability]"` |

## 插件命名空间

约定：`CVE_PLUGIN_<UPPER_PLUGIN_NAME>_<KEY>`，会被 `plugin.config["<key_lower>"]` 读到。

```bash
# 例：feishu notifier
CVE_PLUGIN_FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"

# 例：cisa_kev collector
CVE_PLUGIN_CISA_KEV_API_TIMEOUT=60
```

## 读取顺序

1. 进程实际环境变量（最高优先级）
2. 项目根目录的 `.env` 文件
3. `Settings` 类里的字段默认值

`.env` 不入 git（已在 `.gitignore`）。生产推荐用容器编排的 secret 注入（K8s Secret / Docker Secret / SystemD `EnvironmentFile`）。
