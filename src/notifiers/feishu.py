"""Feishu / Lark custom-bot notifier — pushes each new item as a card.

Posts every dispatched :class:`CollectedItem` to a Feishu (Lark) group via a
custom-bot incoming webhook, rendered as an ``interactive`` message card with
the PoC repo, CVE id, stars, and a button-style link to the exploit code.

**Default-disabled** — only runs once a webhook is configured::

    CVE_PLUGIN_FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"

Optional knobs:

* ``CVE_PLUGIN_FEISHU_SECRET`` — signing secret. Set this only if the bot has
  "signature verification" (签名校验) turned on; the notifier then sends the
  required ``timestamp`` + HMAC-SHA256 ``sign`` fields.
* ``CVE_PLUGIN_FEISHU_MIN_INTERVAL`` (default ``0.7`` seconds) — minimum gap
  between two sends. Feishu custom bots are capped at 100 messages/minute;
  during a first-run backfill of many items the burst would otherwise trip the
  limit (``code=11232 frequency limited``). Set to ``0`` to disable throttling.

Note: Feishu returns HTTP 200 even for application-level errors (bad webhook,
expired sign, rate limit). The real outcome is in the JSON ``code`` field
(``0`` == success), so we inspect that rather than the HTTP status alone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import threading
import time

from src.core.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.db.models import CollectedItem

_DEFAULT_MIN_INTERVAL = 0.7


@register_notifier
class FeishuNotifier(BaseNotifier):
    name = "feishu"
    description = "Push each new item to a Feishu/Lark group via custom-bot webhook"

    # Throttle state is class-level on purpose: the pipeline re-instantiates the
    # notifier for every item (see ``_dispatch_item``), so per-instance state
    # would reset each send and never actually space out the burst.
    _throttle_lock = threading.Lock()
    _last_send_monotonic = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("webhook"))

    def send(self, item: CollectedItem) -> NotificationResult:
        webhook = self.config.get("webhook", "")
        if not webhook:
            return NotificationResult.failure("no webhook configured")

        self._throttle()

        body: dict[str, object] = {
            "msg_type": "interactive",
            "card": self._build_card(item),
        }

        secret = self.config.get("secret")
        if secret:
            timestamp = str(int(time.time()))
            body["timestamp"] = timestamp
            body["sign"] = _sign(timestamp, secret)

        with self.http_client() as http:
            resp = http.post(webhook, json=body)
            resp.raise_for_status()
            data = resp.json()

        # Feishu signals app-level errors via `code` (0 == ok), not HTTP status.
        code = data.get("code", 0)
        if code != 0:
            return NotificationResult.failure(
                f"feishu code={code} msg={data.get('msg', '')[:200]}"
            )
        return NotificationResult.success("delivered")

    # ── Throttling ───────────────────────────────────────────────────

    def _throttle(self) -> None:
        """Block just long enough to keep sends ``min_interval`` apart.

        Feishu custom bots cap at 100 msg/min; a first-run backfill of many
        items bursts past that and gets ``code=11232``. We serialise sends and
        sleep out the remaining gap. ``min_interval=0`` disables it.
        """
        try:
            min_interval = float(self.config.get("min_interval", _DEFAULT_MIN_INTERVAL))
        except (TypeError, ValueError):
            min_interval = _DEFAULT_MIN_INTERVAL
        if min_interval <= 0:
            return
        with FeishuNotifier._throttle_lock:
            wait = min_interval - (time.monotonic() - FeishuNotifier._last_send_monotonic)
            if wait > 0:
                time.sleep(wait)
            FeishuNotifier._last_send_monotonic = time.monotonic()

    # ── Card rendering ───────────────────────────────────────────────

    def _build_card(self, item: CollectedItem) -> dict[str, object]:
        payload = item.payload or {}
        cve = str(payload.get("cve_id") or item.external_id or "")
        repo = str(payload.get("repo") or item.title or "")
        stars = payload.get("stars")
        owner = payload.get("owner")
        language = payload.get("language")
        trust = str(payload.get("trust") or "")

        # ``lark_md`` lets us mix bold labels + a clickable repo link in one block.
        lines: list[str] = []
        if cve:
            lines.append(f"**CVE:** {cve}")
        if repo:
            lines.append(f"**Repo:** [{repo}]({item.url})")
        meta: list[str] = []
        if owner:
            meta.append(f"owner `{owner}`")
        if isinstance(stars, int):
            meta.append(f"⭐ {stars}")
        if language:
            meta.append(str(language))
        if trust:
            meta.append(f"trust={trust}")
        if meta:
            lines.append(" · ".join(meta))
        summary = (item.summary or "").strip()
        if summary:
            lines.append(summary[:500])

        header_title = cve or repo or "New PoC"
        # Red for the high-signal nomi-sec feed, blue for the broader live search.
        template = "red" if payload.get("source") == "poc_github" else "blue"

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": template,
                "title": {"tag": "plain_text", "content": f"🛠 一手 PoC · {header_title}"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "\n".join(lines) or item.url},
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看 PoC 仓库"},
                            "url": item.url,
                            "type": "primary",
                        }
                    ],
                },
            ],
        }


def _sign(timestamp: str, secret: str) -> str:
    """Feishu custom-bot signature: HMAC-SHA256 keyed by ``"{ts}\\n{secret}"``.

    The message body is empty; the timestamp+secret string IS the HMAC key.
    """
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")
