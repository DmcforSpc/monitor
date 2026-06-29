# 采集器开发

每个采集器是一个继承 `BaseCollector` 的类，放在 `src/collectors/` 下任意 `.py` 文件里，用 `@register_collector` 装饰即被自动加载。

## 最小契约

```python
from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem


@register_collector
class MyCollector(BaseCollector):
    name = "my_source"            # 必须唯一，lower_snake_case
    description = "Dashboard 上显示的简介"

    @property
    def enabled(self) -> bool:    # 可选，默认 True
        return bool(self.config.get("api_key"))

    def collect(self) -> Iterable[CollectedItem]:
        with self.http_client() as http:
            data = http.get("https://example.com/feed.json").json()
        for entry in data["items"]:
            yield CollectedItem(
                collector=self.name,
                external_id=entry["id"],
                fingerprint=self.fingerprint(entry["id"]),
                title=entry["title"],
                url=entry["link"],
                summary=entry.get("summary", ""),
                payload={
                    "severity": entry.get("severity"),
                    "tags": entry.get("tags", []),
                },
            )
```

## 框架白送的能力

| 属性/方法 | 来源 | 说明 |
| --- | --- | --- |
| `self.settings` | `BaseCollector.__init__` | 全局 `Settings` 对象 |
| `self.config` | 自动注入 | dict，含 `CVE_PLUGIN_<NAME>_*` 环境变量（前缀剥掉、key 小写） |
| `self.log` | structlog | 预绑定的 logger，名字为 `collector.<name>` |
| `self.http_client()` | 工厂 | `httpx.Client`，含项目默认超时 / UA / 代理 |
| `self.fingerprint(*parts)` | 工具 | SHA-256(`<name>:<part1>:<part2>...`)，用做去重键 |

## 必填字段

| 字段 | 备注 |
| --- | --- |
| `collector` | 必须等于 `self.name` |
| `fingerprint` | **跨源唯一**。要么 `self.fingerprint(...)`，要么自然键如 `f"{self.name}:{cve_id}"` |
| `external_id` | 推荐填（CVE-xxxx / GHSA-xxxx），可空 |
| `title` / `url` / `summary` | 展示三件套 |
| `payload` | 源特定字段，自由 JSON dict |

**不要设置** `id` / `status` / `created_at` / `processed_at` — 框架管这些。

## 插件配置（环境变量）

约定 `CVE_PLUGIN_<UPPER_NAME>_<KEY>`，会被 `self.config["<key_lower>"]` 读到：

```bash
# .env
CVE_PLUGIN_MY_SOURCE_API_KEY=sk-xxxxx
CVE_PLUGIN_MY_SOURCE_PAGE_SIZE=50
```

```python
api_key   = self.config.get("api_key", "")
page_size = int(self.config.get("page_size", "20"))
```

## 异常处理

`collect()` 抛任何异常 → 框架捕获 → 写入 `CollectorRun` 表 `status="error"` + 完整 traceback → 继续跑下一个采集器，不会拖垮整个 pipeline。

## 调试

```bash
# 仅跑某个 collector，便于单测
uv run cve-monitor collect --name my_source

# 看运行历史
curl http://127.0.0.1:8000/api/v1/runs | jq

# DEBUG 级日志
CVE_LOG_LEVEL=DEBUG uv run cve-monitor collect --name my_source
```

## 完整示例：一手 PoC 仓库（poc_github）

仓库自带的 `poc_github` 采集器就是个真实例子 —— 它从 nomi-sec PoC-in-GitHub 源
拉取名字里带 CVE 编号的 GitHub 仓库，每条 `url` 直指存放 exploit 代码的仓库本身，
而非漏洞通告。注意 `fingerprint` 用仓库全名而不是 CVE：同一个 CVE 可能有多个 PoC。

```python title="src/collectors/poc_github.py"
from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

_API = "https://poc-in-github.motikan2010.net/api/v1/"


@register_collector
class PocGithubCollector(BaseCollector):
    name = "poc_github"
    description = "First-hand PoC repos from the nomi-sec PoC-in-GitHub feed"

    @property
    def enabled(self) -> bool:
        return str(self.config.get("enabled", "false")).lower() in ("true", "1", "yes", "on")

    def collect(self) -> Iterable[CollectedItem]:
        with self.http_client() as http:
            resp = http.get(_API, params={"sort": "created", "order": "desc"})
            resp.raise_for_status()
        for poc in resp.json().get("pocs", []):
            full_name = poc.get("full_name")
            html_url = poc.get("html_url")
            if not full_name or not html_url:
                continue
            cve = poc.get("cve_id") or ""
            yield CollectedItem(
                collector=self.name,
                external_id=cve or full_name,
                # 按仓库去重，不按 CVE：一个 CVE 可能有多个 PoC 仓库
                fingerprint=f"{self.name}:{full_name}",
                title=full_name,
                url=html_url,
                summary=(poc.get("description") or "")[:2000],
                payload={
                    "cve_id": cve,
                    "repo": full_name,
                    "stars": int(poc.get("stargazers_count") or 0),
                    "trust": "medium",
                    "source": "poc_github",
                },
            )
```
