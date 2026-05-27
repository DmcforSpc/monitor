"""Structured logging via structlog with stdlib bridge.

The setup is idempotent: calling :func:`configure_logging` more than once is
safe. We send logs to stdout (always) and to an optional rotating file.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

import structlog

from src.settings import Settings, get_settings

_configured = False


def configure_logging(settings: Settings | None = None) -> None:
    """Configure structlog + stdlib logging once."""
    global _configured
    if _configured:
        return

    settings = settings or get_settings()
    level = logging.getLevelName(settings.log_level)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                settings.log_file,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
        )

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=False)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )

    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=level,
        force=True,
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "apscheduler", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    configure_logging()
    return structlog.get_logger(name or "cve_monitor")
