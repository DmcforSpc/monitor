"""Read-only REST API.

Endpoints:

* ``GET /api/health`` — liveness probe
* ``GET /api/stats`` — counters + scheduler state
* ``GET /api/items`` — paginated list of collected items
* ``GET /api/items/{item_id}`` — single item
* ``GET /api/collectors`` — registered collectors
* ``GET /api/notifiers`` — registered notifiers
* ``GET /api/runs`` — recent collector runs
* ``GET /api/notifications`` — recent dispatch log
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from src import __version__
from src.core.collectors import collector_registry
from src.core.notifiers import notifier_registry
from src.core.pipeline import load_plugins
from src.db.models import (
    CollectedItem,
    CollectorRun,
    ItemStatus,
    NotificationRecord,
)
from src.db.repository import get_item, list_items
from src.scheduler import scheduler_service
from src.web.deps import SessionDep

router = APIRouter(prefix="/api", tags=["api"])


# ── Response models ────────────────────────────────────────────────


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collector: str
    external_id: str
    fingerprint: str
    title: str
    url: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ItemStatus
    created_at: datetime
    processed_at: datetime | None = None


class ItemListOut(BaseModel):
    total: int
    page: int
    size: int
    items: list[ItemOut]


class PluginOut(BaseModel):
    name: str
    description: str
    enabled: bool


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collector: str
    status: str
    items_found: int
    items_new: int
    duration_ms: int
    error: str
    started_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    notifier: str
    status: str
    detail: str
    created_at: datetime


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/stats", summary="Global counters & scheduler status")
def stats(session: SessionDep) -> dict[str, Any]:
    load_plugins()
    by_status: dict[str, int] = {
        s.value: 0 for s in ItemStatus
    }
    rows = session.execute(
        select(CollectedItem.status, func.count(CollectedItem.id)).group_by(
            CollectedItem.status
        )
    ).all()
    for status_value, count in rows:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        by_status[key] = int(count)

    by_collector = dict(
        session.execute(
            select(CollectedItem.collector, func.count(CollectedItem.id))
            .group_by(CollectedItem.collector)
            .order_by(func.count(CollectedItem.id).desc())
        ).all()
    )

    sched = scheduler_service.status()
    return {
        "total_items": sum(by_status.values()),
        "by_status": by_status,
        "by_collector": by_collector,
        "collectors_registered": len(collector_registry),
        "notifiers_registered": len(notifier_registry),
        "scheduler": {
            "running": sched.running,
            "interval_seconds": sched.interval_seconds,
            "next_run": sched.next_run,
        },
    }


@router.get("/items", summary="List collected items", response_model=ItemListOut)
def items(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    collector: str = Query("", description="Filter by collector name"),
    status: Literal["", "new", "processed", "notified", "skipped"] = Query(""),
    q: str = Query("", description="Search title / external_id / summary"),
) -> ItemListOut:
    total, rows = list_items(
        session,
        collector=collector or None,
        status=ItemStatus(status) if status else None,
        query=q or None,
        limit=size,
        offset=(page - 1) * size,
    )
    return ItemListOut(
        total=total,
        page=page,
        size=size,
        items=[ItemOut.model_validate(r) for r in rows],
    )


@router.get("/items/{item_id}", summary="Item detail", response_model=ItemOut)
def item_detail(item_id: int, session: SessionDep) -> ItemOut:
    row = get_item(session, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemOut.model_validate(row)


@router.get("/collectors", summary="Registered collectors", response_model=list[PluginOut])
def collectors_list() -> list[PluginOut]:
    load_plugins()
    return [
        PluginOut(
            name=cls.name,
            description=cls.description,
            enabled=_safe_enabled(cls),
        )
        for cls in collector_registry.values()
    ]


@router.get("/notifiers", summary="Registered notifiers", response_model=list[PluginOut])
def notifiers_list() -> list[PluginOut]:
    load_plugins()
    return [
        PluginOut(
            name=cls.name,
            description=cls.description,
            enabled=_safe_enabled(cls),
        )
        for cls in notifier_registry.values()
    ]


@router.get("/runs", summary="Recent collector runs", response_model=list[RunOut])
def runs(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[RunOut]:
    rows = session.execute(
        select(CollectorRun).order_by(CollectorRun.started_at.desc()).limit(limit)
    ).scalars().all()
    return [RunOut.model_validate(r) for r in rows]


@router.get(
    "/notifications", summary="Recent notification log", response_model=list[NotificationOut]
)
def notifications(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[NotificationOut]:
    rows = session.execute(
        select(NotificationRecord).order_by(NotificationRecord.created_at.desc()).limit(limit)
    ).scalars().all()
    return [NotificationOut.model_validate(r) for r in rows]


def _safe_enabled(cls: type) -> bool:
    """Best-effort: instantiate the plugin and read its ``enabled`` flag."""
    try:
        instance = cls()
        return bool(instance.enabled)
    except Exception:  # noqa: BLE001
        return False
