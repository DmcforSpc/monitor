"""Pipeline orchestration — discover plugins, collect, persist, notify.

Two entry points:

* :func:`run_pipeline` — one full cycle across every enabled collector
* :func:`run_collector` — execute a single collector by name

Plugin discovery is lazy: :func:`load_plugins` walks the ``src.collectors``
and ``src.notifiers`` namespaces with :mod:`pkgutil` and imports every
submodule, which triggers the registration decorators.
"""

from __future__ import annotations

import importlib
import pkgutil
import time
import traceback
from dataclasses import dataclass, field

import src.collectors as _collectors_pkg
import src.notifiers as _notifiers_pkg
from src.core.collectors import BaseCollector, collector_registry
from src.core.notifiers import (
    DispatchSummary,
    NotificationResult,
    iter_enabled_notifiers,
)
from src.db.base import db_session
from src.db.models import (
    CollectedItem,
    ItemStatus,
    NotificationStatus,
    RunStatus,
)
from src.db.repository import (
    mark_processed,
    record_notification,
    record_run,
    upsert_items,
)
from src.logging import get_logger
from src.settings import Settings, get_settings

log = get_logger(__name__)

_PLUGINS_LOADED = False


def load_plugins(*, force: bool = False) -> None:
    """Import every module under ``collectors/`` and ``notifiers/``.

    Safe to call repeatedly; subsequent calls are no-ops unless ``force=True``.
    """
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED and not force:
        return
    for pkg in (_collectors_pkg, _notifiers_pkg):
        for mod_info in pkgutil.iter_modules(pkg.__path__):
            if mod_info.name.startswith("_"):
                continue
            full_name = f"{pkg.__name__}.{mod_info.name}"
            try:
                importlib.import_module(full_name)
            except Exception as exc:
                log.error("plugin import failed", module=full_name, error=str(exc))
    _PLUGINS_LOADED = True


# ── Result containers ───────────────────────────────────────────────


@dataclass(slots=True)
class CollectorResult:
    collector: str
    status: RunStatus
    items_found: int = 0
    items_new: int = 0
    duration_ms: int = 0
    notifications_sent: int = 0
    error: str = ""


@dataclass(slots=True)
class PipelineResult:
    results: list[CollectorResult] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(r.items_new for r in self.results)

    @property
    def total_notifications(self) -> int:
        return sum(r.notifications_sent for r in self.results)


# ── Core execution ──────────────────────────────────────────────────


def run_pipeline(settings: Settings | None = None) -> PipelineResult:
    """Run every enabled collector once and dispatch notifications."""
    settings = settings or get_settings()
    load_plugins()

    result = PipelineResult()
    if not collector_registry:
        log.warning("no collectors registered — nothing to do")
        return result

    for name, cls in collector_registry.items():
        try:
            instance = cls(settings)
        except Exception as exc:
            log.error("collector instantiation failed", collector=name, error=str(exc))
            result.results.append(
                CollectorResult(
                    collector=name,
                    status=RunStatus.ERROR,
                    error=f"init: {exc}",
                )
            )
            continue
        if not instance.enabled:
            log.info("collector disabled, skipping", collector=name)
            continue
        result.results.append(run_collector(instance, settings))
    return result


def run_collector(
    collector: BaseCollector | str, settings: Settings | None = None
) -> CollectorResult:
    """Execute a single collector by instance or registered name."""
    settings = settings or get_settings()
    load_plugins()

    if isinstance(collector, str):
        cls = collector_registry.get(collector)
        if cls is None:
            raise KeyError(f"Unknown collector: {collector!r}")
        instance = cls(settings)
    else:
        instance = collector

    log_ = log.bind(collector=instance.name)
    start = time.monotonic()
    items: list[CollectedItem] = []
    new_items: list[CollectedItem] = []
    notifications_sent = 0
    err = ""
    status = RunStatus.OK

    try:
        items = list(instance.collect())
        with db_session() as session:
            new_items = upsert_items(session, items)
        log_.info("collected", found=len(items), new=len(new_items))

        for item in new_items:
            summary = _dispatch_item(item, settings)
            with db_session() as session:
                persistent = session.merge(item)
                mark_processed(
                    session,
                    persistent,
                    status=(ItemStatus.NOTIFIED if summary.any_sent else ItemStatus.PROCESSED),
                )
            notifications_sent += len(summary.sent)
    except Exception as exc:
        status = RunStatus.ERROR
        err = f"{exc}\n{traceback.format_exc()}"
        log_.error("collector failed", error=str(exc))

    duration_ms = int((time.monotonic() - start) * 1000)

    with db_session() as session:
        record_run(
            session,
            collector=instance.name,
            status=status,
            items_found=len(items),
            items_new=len(new_items),
            duration_ms=duration_ms,
            error=err,
        )

    return CollectorResult(
        collector=instance.name,
        status=status,
        items_found=len(items),
        items_new=len(new_items),
        duration_ms=duration_ms,
        notifications_sent=notifications_sent,
        error=err,
    )


def _dispatch_item(item: CollectedItem, settings: Settings) -> DispatchSummary:
    """Send a single item to every enabled notifier; log each outcome."""
    summary = DispatchSummary()
    for notifier in iter_enabled_notifiers(settings):
        if not notifier.should_notify(item):
            summary.skipped.append(notifier.name)
            with db_session() as session:
                record_notification(
                    session,
                    item_id=item.id,
                    notifier=notifier.name,
                    status=NotificationStatus.SKIPPED,
                )
            continue
        try:
            result: NotificationResult = notifier.send(item)
        except Exception as exc:
            notifier.log.error("dispatch failed", item_id=item.id, error=str(exc))
            result = NotificationResult.failure(str(exc))
        status = NotificationStatus.SENT if result.ok else NotificationStatus.FAILED
        with db_session() as session:
            record_notification(
                session,
                item_id=item.id,
                notifier=notifier.name,
                status=status,
                detail=result.detail,
            )
        (summary.sent if result.ok else summary.failed).append(notifier.name)
    return summary
