"""Collector abstraction and registry.

To register a collector, subclass :class:`BaseCollector`, give it a unique
``name`` class attribute, implement :meth:`collect`, and decorate the class
with :func:`register_collector`.

Example::

    @register_collector
    class MyCollector(BaseCollector):
        name = "my_source"

        def collect(self) -> Iterable[CollectedItem]:
            ...

Place the module under :mod:`src.collectors` and it will be picked up
automatically on the next pipeline run.
"""

from __future__ import annotations

import abc
import hashlib
from collections.abc import Iterable
from typing import ClassVar, TypeVar

import httpx

from src.core.http import build_http_client
from src.db.models import CollectedItem
from src.logging import get_logger
from src.settings import Settings, get_settings


class BaseCollector(abc.ABC):
    """Abstract base for all collectors.

    Subclasses **must** set :attr:`name` and implement :meth:`collect`.
    Override :attr:`enabled` (or compute it from ``self.config``) to opt out
    at runtime; disabled collectors are skipped by the pipeline.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init__(self, settings: Settings | None = None) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define a 'name' class attribute")
        self.settings: Settings = settings or get_settings()
        self.config: dict[str, str] = self.settings.plugin_config(self.name)
        self.log = get_logger(f"collector.{self.name}")

    # ── Override points ─────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """Return ``True`` if this collector should run.

        Override to gate on configuration, e.g.::

            @property
            def enabled(self) -> bool:
                return bool(self.config.get("api_key"))
        """
        return True

    @abc.abstractmethod
    def collect(self) -> Iterable[CollectedItem]:
        """Yield :class:`CollectedItem` instances (do not persist yourself)."""

    # ── Helpers ─────────────────────────────────────────────────────

    def fingerprint(self, *parts: object) -> str:
        """Build a stable, dedup-safe fingerprint from arbitrary parts.

        Uses SHA-256 of ``"<collector>:<part1>:<part2>:..."``. Override if your
        source has a natural unique key (e.g. ``f"{self.name}:{cve_id}"``).
        """
        joined = ":".join(str(p) for p in (self.name, *parts))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def http_client(self, **overrides: object) -> httpx.Client:
        """Return an httpx.Client pre-configured with project defaults.

        Includes automatic retries (3 attempts, exponential backoff, honours
        ``Retry-After``) for transient HTTP failures (429, 5xx). See
        :mod:`src.core.http` for the retry policy.
        """
        return build_http_client(self.settings, **overrides)


# ── Registry ────────────────────────────────────────────────────────

collector_registry: dict[str, type[BaseCollector]] = {}

C = TypeVar("C", bound=type[BaseCollector])


def register_collector(cls: C) -> C:
    """Class decorator — register a collector under its ``name``."""
    if not getattr(cls, "name", ""):
        raise ValueError(f"{cls.__name__} must define a non-empty 'name'")
    if cls.name in collector_registry and collector_registry[cls.name] is not cls:
        raise ValueError(f"Collector name {cls.name!r} already registered")
    collector_registry[cls.name] = cls
    return cls
