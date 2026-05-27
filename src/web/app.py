"""FastAPI application factory.

The web layer is intentionally read-only: there is no auth, no write endpoint,
and no mutation. Anything that changes data goes through the CLI or the
scheduler. This keeps public deployments safe by construction.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src import __version__
from src.db.base import init_db
from src.logging import configure_logging, get_logger
from src.scheduler import scheduler_service
from src.settings import get_settings

log = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    init_db()
    if settings.scheduler_enabled:
        scheduler_service.start()
    log.info(
        "web application ready",
        version=__version__,
        host=settings.web_host,
        port=settings.web_port,
    )
    try:
        yield
    finally:
        scheduler_service.shutdown()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Read-only security intelligence dashboard.",
        lifespan=_lifespan,
    )

    # Routers
    from src.web.routes.api import router as api_router
    from src.web.routes.pages import router as pages_router

    app.include_router(api_router)
    app.include_router(pages_router)

    return app
