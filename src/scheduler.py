"""APScheduler wrapper — start/stop a background pipeline loop."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from src.core.pipeline import run_pipeline
from src.logging import get_logger
from src.settings import Settings, get_settings

log = get_logger(__name__)


@dataclass(slots=True)
class SchedulerStatus:
    running: bool
    interval_seconds: int
    next_run: str | None


class SchedulerService:
    """Singleton-style wrapper around APScheduler.BackgroundScheduler."""

    _JOB_ID = "main_pipeline"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._scheduler: BackgroundScheduler | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return bool(self._scheduler and self._scheduler.running)

    def start(self) -> None:
        if not self.settings.scheduler_enabled:
            log.info("scheduler disabled via settings")
            return
        with self._lock:
            if self.running:
                return
            scheduler = BackgroundScheduler(job_defaults={"max_instances": 1, "coalesce": True})
            scheduler.add_job(
                _safe_run_pipeline,
                trigger="interval",
                seconds=self.settings.fetch_interval_seconds,
                id=self._JOB_ID,
                replace_existing=True,
                next_run_time=None,  # do not run immediately
            )
            scheduler.start()
            self._scheduler = scheduler
            log.info(
                "scheduler started",
                interval_seconds=self.settings.fetch_interval_seconds,
            )

    def shutdown(self, *, wait: bool = False) -> None:
        with self._lock:
            if self._scheduler and self._scheduler.running:
                self._scheduler.shutdown(wait=wait)
                log.info("scheduler stopped")
            self._scheduler = None

    def trigger_now(self) -> None:
        """Run the pipeline once in a background thread."""
        threading.Thread(target=_safe_run_pipeline, daemon=True).start()

    def status(self) -> SchedulerStatus:
        next_run: str | None = None
        if self._scheduler:
            job = self._scheduler.get_job(self._JOB_ID)
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        return SchedulerStatus(
            running=self.running,
            interval_seconds=self.settings.fetch_interval_seconds,
            next_run=next_run,
        )


def _safe_run_pipeline(*_: Any) -> None:
    try:
        run_pipeline()
    except Exception as exc:
        log.error("pipeline crashed", error=str(exc))


# Module-level singleton for the embedded FastAPI lifespan.
scheduler_service = SchedulerService()
