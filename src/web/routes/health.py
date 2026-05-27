"""Liveness and readiness probes.

Two well-known endpoints, intentionally kept outside the versioned ``/api/v1``
prefix so external infrastructure (Kubernetes, Render, Docker HEALTHCHECK …)
can hit fixed paths regardless of API evolution:

* ``GET /api/health`` — liveness. Returns 200 if the process is up. No I/O.
* ``GET /api/ready``  — readiness. Returns 200 only if the database is
  reachable; 503 otherwise with the underlying error in the body.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from src import __version__
from src.logging import get_logger
from src.web.deps import SessionDep

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    """Always returns 200 if the process is reachable."""
    return {"status": "ok", "version": __version__}


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={503: {"description": "Database unreachable"}},
)
def ready(session: SessionDep, response: Response) -> dict[str, object]:
    """Returns 200 only if a trivial DB query succeeds; 503 otherwise."""
    try:
        session.execute(text("SELECT 1")).scalar_one()
    except Exception as exc:  # broad on purpose — any DB hiccup is "not ready"
        log.warning("readiness check failed", error=str(exc))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "error": str(exc)[:200]}
    return {"status": "ready", "version": __version__}
