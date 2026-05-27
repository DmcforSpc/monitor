"""GitHub Security Advisories (GHSA) collector.

Pulls reviewed advisories with severity *critical* and *high* from the
public ``/advisories`` REST endpoint.

Default-disabled. Enable with::

    CVE_PLUGIN_GHSA_ENABLED=true

Optional knobs:

* ``CVE_PLUGIN_GHSA_TOKEN`` (or fallback to ``GH_TOKEN`` env) — GitHub PAT.
  Without a token the rate limit is 60 req/hour; with one, 5000 req/hour.
* ``CVE_PLUGIN_GHSA_PER_PAGE`` (default 30, max 100).
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

_API = "https://api.github.com/advisories"
_SEVERITIES = ("critical", "high")
_DEFAULT_PER_PAGE = 30


@register_collector
class GhsaCollector(BaseCollector):
    name = "ghsa"
    description = "GitHub Security Advisories (severity ≥ high)"

    @property
    def enabled(self) -> bool:
        return _is_true(self.config.get("enabled", "false"))

    def collect(self) -> Iterable[CollectedItem]:
        token = self.config.get("token") or os.environ.get("GH_TOKEN", "")
        headers: dict[str, str] = {
            "User-Agent": self.settings.http_user_agent,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        per_page = int(self.config.get("per_page", _DEFAULT_PER_PAGE))
        seen: set[str] = set()

        with self.http_client(headers=headers) as http:
            for severity in _SEVERITIES:
                params = {"type": "reviewed", "severity": severity, "per_page": per_page}
                resp = http.get(_API, params=params)
                if resp.status_code == 403:
                    self.log.warning(
                        "GHSA API rate-limited or forbidden",
                        status=resp.status_code,
                        reset=resp.headers.get("X-RateLimit-Reset"),
                    )
                    return
                resp.raise_for_status()
                for adv in resp.json():
                    ghsa = adv.get("ghsa_id")
                    if not ghsa or ghsa in seen:
                        continue
                    seen.add(ghsa)
                    cvss_raw = (adv.get("cvss") or {}).get("score") or 0
                    yield CollectedItem(
                        collector=self.name,
                        external_id=ghsa,
                        fingerprint=f"{self.name}:{ghsa}",
                        title=adv.get("summary") or ghsa,
                        url=adv.get("html_url") or f"https://github.com/advisories/{ghsa}",
                        summary=(adv.get("description") or "")[:2000],
                        payload={
                            "cve_id": adv.get("cve_id"),
                            "severity": str(adv.get("severity", "")).upper(),
                            "cvss_score": float(cvss_raw),
                            "cvss_vector": (adv.get("cvss") or {}).get("vector_string", ""),
                            "published_at": adv.get("published_at"),
                            "updated_at": adv.get("updated_at"),
                            "trust": "high",
                            "source": "ghsa",
                        },
                    )


def _is_true(v: str | None) -> bool:
    return str(v or "").lower() in ("true", "1", "yes", "on")
