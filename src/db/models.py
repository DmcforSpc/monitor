"""Generic ORM models — intentionally CVE-agnostic.

The framework provides three tables:

* ``CollectedItem``  — any item produced by a collector (CVE, GHSA, RSS entry,
  PoC repo …). Source-specific fields live in the ``payload`` JSON column.
* ``CollectorRun``  — execution record per collector invocation.
* ``NotificationRecord`` — dispatch log per (item, notifier) pair.

There is no notion of CVE / RCE / freshness in this layer — that is plugin
territory.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ── Enums ───────────────────────────────────────────────────────────


class ItemStatus(enum.StrEnum):
    """Lifecycle state of a collected item."""

    NEW = "new"
    PROCESSED = "processed"
    NOTIFIED = "notified"
    SKIPPED = "skipped"


class NotificationStatus(enum.StrEnum):
    """Dispatch outcome of a notifier."""

    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(enum.StrEnum):
    """Outcome of a collector run."""

    OK = "ok"
    ERROR = "error"


# ── Tables ──────────────────────────────────────────────────────────


class CollectedItem(Base):
    """A single piece of intelligence harvested by some collector.

    The ``fingerprint`` column is the deduplication key — set it to whatever
    string uniquely identifies the item across runs (typically
    ``f"{collector}:{external_id}"`` or a hash of ``url``).
    """

    __tablename__ = "collected_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    fingerprint: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)

    title: Mapped[str] = mapped_column(String(1024), default="")
    url: Mapped[str] = mapped_column(String(2048), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, native_enum=False, length=16),
        default=ItemStatus.NEW,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_collected_items_fingerprint"),
        Index("ix_collected_items_collector_created", "collector", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CollectedItem id={self.id} collector={self.collector!r} external_id={self.external_id!r}>"


class CollectorRun(Base):
    """Per-invocation record of a collector run."""

    __tablename__ = "collector_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=16),
        default=RunStatus.OK,
        nullable=False,
    )
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )


class NotificationRecord(Base):
    """Per-notifier dispatch outcome for a given collected item."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    notifier: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False, length=16),
        default=NotificationStatus.SENT,
        nullable=False,
    )
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("item_id", "notifier", name="uq_notifications_item_notifier"),
    )
