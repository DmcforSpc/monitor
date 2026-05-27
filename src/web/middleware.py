"""Security middleware wiring — TrustedHost, CORS, and a small headers injector.

Middlewares execute in **reverse registration order**, so we install them in
the order we want them to *run last → first*:

1. ``SecurityHeadersMiddleware`` (always on) — appends conservative response
   headers to every response.
2. ``CORSMiddleware`` (opt-in via ``CVE_CORS_ORIGINS``) — Cross-Origin
   Resource Sharing. Read-only API ⇒ only ``GET`` is whitelisted.
3. ``TrustedHostMiddleware`` (opt-in via ``CVE_ALLOWED_HOSTS``) — rejects any
   request whose ``Host`` header is not in the allow-list. Runs first so a
   bad host is dropped before anything else.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.logging import get_logger
from src.settings import Settings

log = get_logger(__name__)

# Conservative defaults safe for a read-only HTML+JSON service.
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append conservative security headers to every response.

    Uses ``setdefault`` so downstream code can override per-route if needed.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


def install_middlewares(app: FastAPI, settings: Settings) -> None:
    """Wire all production middlewares onto ``app``."""
    # Order: registered last == runs first. We want TrustedHost first.
    app.add_middleware(SecurityHeadersMiddleware)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["GET"],  # API is read-only
            allow_headers=["*"],
            max_age=600,
        )
        log.info("CORS enabled", origins=settings.cors_origins)

    if settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
        )
        log.info("TrustedHost enabled", hosts=settings.allowed_hosts)
