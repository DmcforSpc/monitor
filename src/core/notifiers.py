"""Notifier abstraction and registry.

To add a notification channel, subclass :class:`BaseNotifier`, set a unique
``name``, implement :meth:`send`, and decorate with :func:`register_notifier`.

Example::

    @register_notifier
    class FeishuNotifier(BaseNotifier):
        name = "feishu"

        @property
        def enabled(self) -> bool:
            return bool(self.config.get("webhook"))

        def send(self, item: CollectedItem) -> NotificationResult:
            ...
"""

from __future__ import annotations

import abc
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, TypeVar

import httpx

from src.core.http import build_http_client
from src.db.models import CollectedItem
from src.logging import get_logger
from src.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class NotificationResult:
    """Outcome of a single ``notifier.send(item)`` call."""

    ok: bool
    detail: str = ""

    @classmethod
    def success(cls, detail: str = "") -> NotificationResult:
        return cls(True, detail)

    @classmethod
    def failure(cls, detail: str) -> NotificationResult:
        return cls(False, detail)


@dataclass(slots=True)
class DispatchSummary:
    """Aggregated result of dispatching one item to all notifiers."""

    sent: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def any_sent(self) -> bool:
        return bool(self.sent)


class BaseNotifier(abc.ABC):
    """Abstract base for outbound notification channels."""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init__(self, settings: Settings | None = None) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define a 'name' class attribute")
        self.settings: Settings = settings or get_settings()
        self.config: dict[str, str] = self.settings.plugin_config(self.name)
        self.log = get_logger(f"notifier.{self.name}")

    # ── Override points ─────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """Default: enabled. Override to require configuration presence."""
        return True

    def should_notify(self, item: CollectedItem) -> bool:
        """Per-item gate — override to filter on ``item.payload`` etc."""
        return True

    @abc.abstractmethod
    def send(self, item: CollectedItem) -> NotificationResult:
        """Push ``item`` to the channel. Return a :class:`NotificationResult`."""

    # ── Helpers ─────────────────────────────────────────────────────

    def http_client(self, **overrides: object) -> httpx.Client:
        """Return an httpx.Client with project defaults + retry transport.

        See :mod:`src.core.http` for the shared retry policy.
        """
        return build_http_client(self.settings, **overrides)


# ── Registry ────────────────────────────────────────────────────────

notifier_registry: dict[str, type[BaseNotifier]] = {}

N = TypeVar("N", bound=type[BaseNotifier])


def register_notifier(cls: N) -> N:
    """Class decorator — register a notifier under its ``name``."""
    if not getattr(cls, "name", ""):
        raise ValueError(f"{cls.__name__} must define a non-empty 'name'")
    if cls.name in notifier_registry and notifier_registry[cls.name] is not cls:
        raise ValueError(f"Notifier name {cls.name!r} already registered")
    notifier_registry[cls.name] = cls
    return cls


def iter_enabled_notifiers(settings: Settings | None = None) -> Iterable[BaseNotifier]:
    """Yield instantiated, enabled notifiers in registration order."""
    s = settings or get_settings()
    for cls in notifier_registry.values():
        try:
            instance = cls(s)
        except Exception as exc:
            get_logger("notifiers").error(
                "notifier instantiation failed", notifier=cls.name, error=str(exc)
            )
            continue
        if instance.enabled:
            yield instance
