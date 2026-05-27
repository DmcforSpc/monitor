# 部署安全

## 凭据管理

| 文件 | 状态 | 说明 |
| --- | --- | --- |
| `.env` | **绝不入 git** | 在 `.gitignore` 中，本地 `chmod 600` |
| `.env.example` | 入 git | 占位符模板，仅说明 |
| `config.yaml` | **绝不入 git** | 同上（已加入 `.gitignore`） |

CI 已经接 [gitleaks](https://github.com/gitleaks/gitleaks)（pre-commit 钩子 + GitHub Actions），任何 token 哪怕一秒提交进 git 都会被拦下来。

## 安全中间件

`SecurityHeadersMiddleware`（始终启用，无需配置）会注入：

| 响应头 | 值 |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |

按需启用：

```bash
CVE_ALLOWED_HOSTS="cve.example.com,localhost"   # TrustedHost — Host 头不匹配直接 400
CVE_CORS_ORIGINS="https://app.example.com"      # CORS — 仅这些来源能 GET
CVE_CORS_ALLOW_CREDENTIALS=false
```

## 只读 API

设计上没有写入端点。即使 token 泄漏，攻击者也最多只能 GET 公开数据。Web 仪表盘同样无登录、无表单。

如果你将来想加写入端点（如手动触发 collect），强烈建议加：
- API Key 鉴权（FastAPI 依赖注入 + `X-API-Key` header）
- 限流（`slowapi` 之类）
- 写入操作日志

## 反向代理

直接暴露 `0.0.0.0:8000` 没问题，但生产建议 Nginx + Let's Encrypt：

```bash
sudo certbot --nginx -d cve.example.com
```

并配 `CVE_ALLOWED_HOSTS` 卡死合法域名，防止 Host header 注入。

## CI 安全扫描

每次 push / PR 都自动跑：

| 工具 | 检查 |
| --- | --- |
| `bandit` | 静态分析 Python 代码里的危险用法（弱加密、shell 注入、SQL 注入等） |
| `pip-audit` | 依赖里的已知 CVE |
| `gitleaks` | 提交里的明文 secrets |

任何一项失败 → CI 红 → PR 无法合并。

## 数据备份

```bash
# 服务运行中安全备份（WAL 模式允许在线复制）
sqlite3 cve_monitor.db ".backup /backup/cve_monitor-$(date +%F).db"
```

## 不要这么干

- ❌ 用 `root` 跑（Docker 镜像已是 `app` 用户）
- ❌ 在公网监听 `8000` 不带 TLS（让搜索引擎索引你的运维数据）
- ❌ 把 `.env` 复制进 Docker 镜像（用 `--env-file` 或 K8s Secret 代替）
- ❌ 给采集器配 GitHub PAT 时申请 `repo` 权限（只需要 `public_repo`）
