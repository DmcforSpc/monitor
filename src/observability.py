"""Optional Logfire observability bootstrap.

Install the extra to enable instrumentation::

    uv pip install -e ".[observability]"

Then set ``LOGFIRE_TOKEN`` in the environment (Pydantic Logfire dashboard
gives you one). If either the package or the token is missing, this module
is a silent no-op — the app keeps running with structlog-only logs.

What gets instrumented when active:
* FastAPI request spans (incoming HTTP + status + latency)
* SQLAlchemy queries (timing + parameterised SQL)
* httpx outbound calls (used by collectors / notifiers)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from src.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

    from src.settings import Settings

log = get_logger(__name__)


def configure_observability(app: FastAPI, settings: Settings) -> bool:
    """Configure Logfire if available + LOGFIRE_TOKEN is set.

    Returns ``True`` if instrumentation was activated, ``False`` otherwise.
    """
    if not os.environ.get("LOGFIRE_TOKEN"):
        return False
    try:
        import logfire
    except ImportError:
        log.warning(
            "LOGFIRE_TOKEN set but 'logfire' not installed — run: pip install -e '.[observability]'"
        )
        return False

    try:
        logfire.configure(
            service_name=settings.app_name.lower().replace(" ", "-"),
            service_version=_version(),
            send_to_logfire="if-token-present",
        )
        logfire.instrument_fastapi(app, capture_headers=False)
        # SQLAlchemy + httpx instrument the engine / client at the library
        # level — no instance arguments needed.
        logfire.instrument_sqlalchemy()
        logfire.instrument_httpx()
        log.info("Logfire observability enabled")
        return True
    except Exception as exc:  # broad: never crash startup over telemetry
        log.warning("Logfire setup failed; continuing without it", error=str(exc))
        return False


def _version() -> str:
    from src import __version__  # local import to avoid circulars at module load

    return __version__
