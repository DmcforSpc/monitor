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

## 完整示例：CISA KEV

```python title="src/collectors/cisa_kev.py"
from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


@register_collector
class CisaKevCollector(BaseCollector):
    name = "cisa_kev"
    description = "CISA Known Exploited Vulnerabilities catalog"

    def collect(self) -> Iterable[CollectedItem]:
        with self.http_client() as http:
            data = http.get(KEV_URL).json()
        for v in data.get("vulnerabilities", [])[-100:]:
            cve = v["cveID"]
            yield CollectedItem(
                collector=self.name,
                external_id=cve,
                fingerprint=f"{self.name}:{cve}",   # natural key
                title=v.get("vulnerabilityName", cve),
                url=f"https://nvd.nist.gov/vuln/detail/{cve}",
                summary=v.get("shortDescription", ""),
                payload={
                    "vendor": v.get("vendorProject"),
                    "product": v.get("product"),
                    "ransomware_known": v.get("knownRansomwareCampaignUse") == "Known",
                    "trust": "high",
                },
            )
```
