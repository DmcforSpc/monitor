"""Repository helpers — thin functional wrappers around the ORM.

Kept small on purpose; the goal is to centralise deduplication and a couple
of common queries so neither the pipeline nor the web layer has to reinvent
them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from cve_monitor.db.models import (
    CollectedItem,
    CollectorRun,
    ItemStatus,
    NotificationRecord,
    NotificationStatus,
    RunStatus,
)


# ── Items ───────────────────────────────────────────────────────────


def upsert_items(session: Session, items: Iterable[CollectedItem]) -> list[CollectedItem]:
    """Insert items, skipping any whose ``fingerprint`` already exists.

    Returns the list of items that were actually inserted (with their IDs
    populated). Existing items are left untouched.
    """
    inserted: list[CollectedItem] = []
    for item in items:
        if not item.fingerprint:
            raise ValueError("CollectedItem.fingerprint is required for deduplication")
        exists = session.execute(
            select(CollectedItem.id).where(CollectedItem.fingerprint == item.fingerprint)
        ).scalar_one_or_none()
        if exists is not None:
            continue
        session.add(item)
        session.flush()  # populate item.id
        inserted.append(item)
    return inserted


def get_item(session: Session, item_id: int) -> CollectedItem | None:
    return session.get(CollectedItem, item_id)


def list_items(
    session: Session,
    *,
    collector: str | None = None,
    status: ItemStatus | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, Sequence[CollectedItem]]:
    """Return ``(total, items)`` with optional filters."""
    base = select(CollectedItem).order_by(CollectedItem.created_at.desc())
    if collector:
        base = base.where(CollectedItem.collector == collector)
    if status:
        base = base.where(CollectedItem.status == status)
    if query:
        like = f"%{query}%"
        base = base.where(
            CollectedItem.title.contains(query)
            | CollectedItem.external_id.contains(query)
            | CollectedItem.summary.contains(query)
        )
    total = session.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    rows = session.execute(base.offset(offset).limit(limit)).scalars().all()
    return total, rows


def mark_processed(session: Session, item: CollectedItem, *, status: ItemStatus) -> None:
    item.status = status
    item.processed_at = datetime.now(timezone.utc)


# ── Notifications ───────────────────────────────────────────────────


def record_notification(
    session: Session,
    *,
    item_id: int,
    notifier: str,
    status: NotificationStatus,
    detail: str = "",
) -> None:
    """Insert-or-ignore a notification dispatch record.

    Uses ``ON CONFLICT DO NOTHING`` on SQLite; falls back to a SELECT-then-INSERT
    on other backends. The unique constraint on (item_id, notifier) guarantees
    we never double-record a successful dispatch.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    payload = {
        "item_id": item_id,
        "notifier": notifier,
        "status": status,
        "detail": detail[:2000],
    }
    if dialect == "sqlite":
        stmt = sqlite_insert(NotificationRecord).values(**payload)
        stmt = stmt.on_conflict_do_nothing(index_elements=["item_id", "notifier"])
        session.execute(stmt)
    else:
        exists = session.execute(
            select(NotificationRecord.id).where(
                NotificationRecord.item_id == item_id,
                NotificationRecord.notifier == notifier,
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(NotificationRecord(**payload))


def already_notified(session: Session, *, item_id: int, notifier: str) -> bool:
    return (
        session.execute(
            select(NotificationRecord.id).where(
                NotificationRecord.item_id == item_id,
                NotificationRecord.notifier == notifier,
                NotificationRecord.status == NotificationStatus.SENT,
            )
        ).scalar_one_or_none()
        is not None
    )


# ── Collector runs ──────────────────────────────────────────────────


def record_run(
    session: Session,
    *,
    collector: str,
    status: RunStatus,
    items_found: int,
    items_new: int,
    duration_ms: int,
    error: str = "",
) -> None:
    session.add(
        CollectorRun(
            collector=collector,
            status=status,
            items_found=items_found,
            items_new=items_new,
            duration_ms=duration_ms,
            error=error[:2000],
        )
    )
