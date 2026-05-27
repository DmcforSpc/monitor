"""Shared HTTP client factory for collectors and notifiers.

A single source of truth for outbound HTTP defaults: timeouts, User-Agent,
optional proxy, and retry semantics (handled by ``httpx-retries`` —
exponential backoff + ``Retry-After`` honoured + jitter for safe 5xx / 429
retries without thundering-herd effects).

Plugins access this through :meth:`BaseCollector.http_client` /
:meth:`BaseNotifier.http_client`; they should rarely need to build their own
client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from httpx_retries import Retry, RetryTransport

if TYPE_CHECKING:
    from src.settings import Settings

# Tuned for typical CVE / RSS / GitHub-style APIs:
# - total=3 hand-offs is enough to ride out brief upstream blips
# - backoff_factor=0.5 → 0.5s, 1.0s, 2.0s between attempts (plus jitter)
# - status_forcelist covers the standard transient HTTP failures
# - respect_retry_after_header=True is essential for GitHub (`Retry-After` on 429)
_DEFAULT_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    respect_retry_after_header=True,
)


def build_http_client(settings: Settings, **overrides: Any) -> httpx.Client:
    """Return a configured :class:`httpx.Client`.

    The client is wrapped in a :class:`RetryTransport` so any GET / POST is
    transparently retried on transient failures. Override anything by passing
    keyword arguments — e.g. ``timeout=60``, ``headers={...}``.
    """
    transport_kwargs: dict[str, Any] = {}
    if settings.http_proxy:
        transport_kwargs["proxy"] = settings.http_proxy
    base = httpx.HTTPTransport(**transport_kwargs)

    kwargs: dict[str, Any] = {
        "timeout": settings.http_timeout,
        "headers": {"User-Agent": settings.http_user_agent},
        "follow_redirects": True,
        "transport": RetryTransport(transport=base, retry=_DEFAULT_RETRY),
    }
    kwargs.update(overrides)
    return httpx.Client(**kwargs)
