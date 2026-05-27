"""Dashboard page — Jinja2 rendered, read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from src import __version__
from src.core.collectors import collector_registry
from src.core.notifiers import notifier_registry
from src.core.pipeline import load_plugins
from src.db.models import CollectedItem, CollectorRun
from src.scheduler import scheduler_service
from src.settings import get_settings
from src.web.deps import SessionDep

router = APIRouter(tags=["pages"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse, summary="Dashboard")
def dashboard(request: Request, session: SessionDep) -> Any:
    load_plugins()
    settings = get_settings()

    total = session.execute(select(func.count(CollectedItem.id))).scalar_one()
    by_collector = list(
        session.execute(
            select(CollectedItem.collector, func.count(CollectedItem.id))
            .group_by(CollectedItem.collector)
            .order_by(func.count(CollectedItem.id).desc())
        ).all()
    )
    recent_items = (
        session.execute(
            select(CollectedItem).order_by(CollectedItem.created_at.desc()).limit(20)
        )
        .scalars()
        .all()
    )
    recent_runs = (
        session.execute(
            select(CollectorRun).order_by(CollectorRun.started_at.desc()).limit(10)
        )
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "app_name": settings.app_name,
            "version": __version__,
            "total": total,
            "by_collector": by_collector,
            "collectors": list(collector_registry.values()),
            "notifiers": list(notifier_registry.values()),
            "recent_items": recent_items,
            "recent_runs": recent_runs,
            "scheduler": scheduler_service.status(),
        },
    )
