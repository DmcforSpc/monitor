# Collectors

Each module dropped here is auto-imported on `cve-monitor collect` (or on web
startup). Any class decorated with `@register_collector` becomes part of the
pipeline.

## Minimal contract

```python
from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem


@register_collector
class MyCollector(BaseCollector):
    name = "my_source"            # unique, lower_snake_case
    description = "A short blurb shown on the dashboard."

    @property
    def enabled(self) -> bool:
        # Optional. Default: True. Read self.config or self.settings here.
        return True

    def collect(self) -> Iterable[CollectedItem]:
        with self.http_client() as http:
            resp = http.get("https://example.com/feed.json")
            resp.raise_for_status()
            for entry in resp.json()["items"]:
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

## What you get for free

| Helper | Description |
| --- | --- |
| `self.settings` | The global `Settings` object |
| `self.config` | Dict of env vars under `CVE_PLUGIN_<NAME>_*` (lower-case keys) |
| `self.log` | Pre-bound `structlog` logger (`collector.<name>`) |
| `self.http_client()` | `httpx.Client` with project timeouts + UA + proxy |
| `self.fingerprint(*parts)` | SHA-256 helper for deduplication keys |

## Required fields on `CollectedItem`

| Field | Notes |
| --- | --- |
| `collector` | Must equal `self.name` |
| `fingerprint` | **Unique across all collectors.** Used for dedup. Either `self.fingerprint(...)` or a natural key like `f"{self.name}:{cve_id}"` |
| `external_id` | Source-system identifier (CVE-2024-xxxx, GHSA-xxxx, …). Optional but recommended |
| `title` / `url` / `summary` | Display fields |
| `payload` | Free-form JSON dict for source-specific data |

Do **not** set `id`, `status`, `created_at`, or `processed_at` — those are
managed by the framework.

## Configuration via environment

Plugin-specific variables follow the pattern `CVE_PLUGIN_<UPPER_NAME>_<KEY>`
and are exposed as `self.config["<key_lower>"]`. Example:

```bash
# .env
CVE_PLUGIN_MY_SOURCE_API_KEY=sk-...
CVE_PLUGIN_MY_SOURCE_PAGE_SIZE=50
```

```python
api_key = self.config.get("api_key", "")
page_size = int(self.config.get("page_size", "20"))
```

## Errors

Raising any exception from `collect()` is fine — the pipeline catches it,
logs a `CollectorRun` row with `status="error"`, and continues with the next
collector.
