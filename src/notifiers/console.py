"""Always-on console / log notifier — zero-config sanity check.

Every successful dispatch is emitted as a single ``structlog.info`` event
with the item's key fields. Useful for:

* verifying the pipeline end-to-end before configuring real channels
* container-only deployments where you want notifications in stdout / logs
  rather than via Webhook

**Enabled by default.** Disable with::

    CVE_PLUGIN_CONSOLE_ENABLED=false
"""

from __future__ import annotations

from src.core.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.db.models import CollectedItem


@register_notifier
class ConsoleNotifier(BaseNotifier):
    name = "console"
    description = "Print every dispatch to the structured logger (default ON)"

    @property
    def enabled(self) -> bool:
        # Default ON — only off if the user explicitly disables it
        raw = self.config.get("enabled", "true")
        return str(raw).lower() not in ("false", "0", "no", "off")

    def send(self, item: CollectedItem) -> NotificationResult:
        self.log.info(
            "item_dispatched",
            id=item.id,
            collector=item.collector,
            external_id=item.external_id,
            title=(item.title or "")[:120],
            url=item.url,
            payload_keys=sorted(item.payload.keys()) if item.payload else [],
        )
        return NotificationResult.success("logged")
