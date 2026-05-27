# 通知渠道开发

每个通知是一个继承 `BaseNotifier` 的类，放在 `src/notifiers/` 下，用 `@register_notifier` 注册即自动加载。

## 最小契约

```python
from src.core.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.db.models import CollectedItem


@register_notifier
class MyNotifier(BaseNotifier):
    name = "my_channel"
    description = "Dashboard 上显示的简介"

    @property
    def enabled(self) -> bool:                       # 必须 — 没配 webhook 就别启用
        return bool(self.config.get("webhook"))

    def should_notify(self, item: CollectedItem) -> bool:   # 可选 per-item 过滤
        return float(item.payload.get("cvss_score", 0)) >= 7.0

    def send(self, item: CollectedItem) -> NotificationResult:
        ...
        return NotificationResult.success("HTTP 200")
```

## NotificationResult 构造

```python
NotificationResult.success("optional detail")
NotificationResult.failure("error reason — recorded in DB")
```

## 框架白送的能力

| 属性/方法 | 说明 |
| --- | --- |
| `self.settings` | 全局 Settings |
| `self.config` | dict，含 `CVE_PLUGIN_<NAME>_*` env vars |
| `self.log` | 预绑定 logger（`notifier.<name>`） |
| `self.http_client()` | httpx.Client + 项目默认超时 / UA / 代理 |

## 去重保证

`(item_id, notifier_name)` 在 `notifications` 表上有唯一约束 — 同一 item 不会被同一 notifier 推送两次，无论 pipeline 跑多少轮。**你不需要自己实现去重**。

## 异常处理

`send()` 抛异常 → 框架捕获 → 写入 `notifications` 表 `status="failed"` + 异常文本 → item 仍标记 `processed`（不会卡住）。

## 调试

```bash
# 看推送历史
curl http://127.0.0.1:8000/api/v1/notifications | jq

# 临时跑一轮（先确保 collector 有数据）
uv run cve-monitor collect
```

## 完整示例：飞书

```python title="src/notifiers/feishu.py"
from src.core.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.db.models import CollectedItem


@register_notifier
class FeishuNotifier(BaseNotifier):
    name = "feishu"
    description = "Lark / Feishu 群机器人"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("webhook"))

    def send(self, item: CollectedItem) -> NotificationResult:
        body = f"**{item.external_id or item.title}**\n{item.summary[:500]}\n[Source]({item.url})"
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

配置：

```bash
# .env
CVE_PLUGIN_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
```

## 完整示例：Telegram

```python title="src/notifiers/telegram.py"
from src.core.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.db.models import CollectedItem


@register_notifier
class TelegramNotifier(BaseNotifier):
    name = "telegram"
    description = "Telegram Bot API"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("bot_token") and self.config.get("chat_id"))

    def send(self, item: CollectedItem) -> NotificationResult:
        token = self.config["bot_token"]
        chat = self.config["chat_id"]
        text = f"*{item.external_id or item.title[:80]}*\n{item.summary[:500]}\n{item.url}"
        with self.http_client() as http:
            resp = http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            )
        if resp.is_success:
            return NotificationResult.success(f"HTTP {resp.status_code}")
        return NotificationResult.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
```
