# Notifiers

Each module dropped here is auto-imported on `cve-monitor collect` (or on web
startup). Any class decorated with `@register_notifier` becomes part of the
dispatch chain.

## Minimal contract

```python
from cve_monitor.core.notifiers import (
    BaseNotifier,
    NotificationResult,
    register_notifier,
)
from cve_monitor.db.models import CollectedItem


@register_notifier
class FeishuNotifier(BaseNotifier):
    name = "feishu"
    description = "Lark / Feishu group bot webhook"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("webhook"))

    def should_notify(self, item: CollectedItem) -> bool:
        # Optional per-item gate. Default: True.
        # Example: only forward CVSS >= 7.0 items.
        return float(item.payload.get("cvss_score", 0)) >= 7.0

    def send(self, item: CollectedItem) -> NotificationResult:
        body = (
            f"**{item.external_id or item.title}**\n"
            f"{item.summary[:500]}\n"
            f"[Source]({item.url})"
        )
        with self.http_client() as http:
            resp = http.post(
                self.config["webhook"],
                json={
                    "msg_type": "interactive",
                    "card": {
                        "header": {"title": {"tag": "plain_text", "content": item.title[:120]}},
                        "elements": [{"tag": "markdown", "content": body}],
                    },
                },
            )
        if resp.is_success:
            return NotificationResult.success(f"HTTP {resp.status_code}")
        return NotificationResult.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
```

## What you get for free

| Helper | Description |
| --- | --- |
| `self.settings` | Global `Settings` |
| `self.config` | Dict of env vars under `CVE_PLUGIN_<NAME>_*` |
| `self.log` | Pre-bound `structlog` logger (`notifier.<name>`) |
| `self.http_client()` | `httpx.Client` with timeouts + UA + proxy |
| `NotificationResult.success(detail)` | Build an OK result |
| `NotificationResult.failure(detail)` | Build a failed result |

## Dedup of sends

The framework keeps a `(item_id, notifier_name)` unique constraint in the
`notifications` table — you cannot accidentally double-send the same item to
the same channel.

## Errors

Raising from `send()` is fine — the pipeline records a `failed` notification
row with the exception text, and the item is still marked as `processed`.

## Configuration via environment

Same convention as collectors: `CVE_PLUGIN_<UPPER_NAME>_<KEY>`.

```bash
# .env
CVE_PLUGIN_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
CVE_PLUGIN_TELEGRAM_BOT_TOKEN=123456:ABC...
CVE_PLUGIN_TELEGRAM_CHAT_ID=-100123456789
```
