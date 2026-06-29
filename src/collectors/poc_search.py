"""First-hand PoC repositories via the GitHub repository search API.

Searches GitHub directly for repos whose name looks like a CVE PoC — this
catches brand-new exploit repos *before* third-party indexes pick them up,
at the cost of needing a token for a usable rate limit.

Each item is a *real PoC repository*: ``url`` points at the GitHub repo
holding the exploit code, not at an advisory.

Default-disabled. Enable with::

    CVE_PLUGIN_POC_SEARCH_ENABLED=true

Optional knobs:

* ``CVE_PLUGIN_POC_SEARCH_TOKEN`` (or fallback to ``GH_TOKEN`` env) — GitHub
  PAT. Without one the search rate limit is 10 req/min; with one, 30 req/min.
* ``CVE_PLUGIN_POC_SEARCH_QUERY`` (default ``CVE-`` in name) — raw search
  qualifier appended to the ``q`` param.
* ``CVE_PLUGIN_POC_SEARCH_PER_PAGE`` (default 50, max 100).
* ``CVE_PLUGIN_POC_SEARCH_REQUIRE_CVE`` (default ``true``) — only keep repos
  whose name carries a concrete ``CVE-YYYY-NNNN`` id. The raw GitHub search
  for ``CVE- in:name`` otherwise drags in aggregators / trackers / tooling
  (``cvelist``, ``cve-radar``, ``cve-aggregator-bot`` …) rather than first-hand
  exploit repos. Set to ``false`` to keep the unfiltered firehose.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

_API = "https://api.github.com/search/repositories"
_DEFAULT_QUERY = "CVE- in:name"
_DEFAULT_PER_PAGE = 50

# A real CVE id: CVE-<4-digit year>-<4-or-more-digit sequence>. Used both to
# pull the id out of a repo name and to reject names that merely contain the
# word "cve" (aggregators, trackers, tooling) instead of a concrete exploit.
_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)


@register_collector
class PocSearchCollector(BaseCollector):
    name = "poc_search"
    description = "First-hand PoC repos via live GitHub repository search"

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

        query = self.config.get("query") or _DEFAULT_QUERY
        per_page = min(int(self.config.get("per_page", _DEFAULT_PER_PAGE)), 100)
        require_cve = _is_true(self.config.get("require_cve", "true"))
        params = {"q": query, "sort": "updated", "order": "desc", "per_page": per_page}

        with self.http_client(headers=headers) as http:
            resp = http.get(_API, params=params)
            if resp.status_code == 403:
                self.log.warning(
                    "GitHub search rate-limited or forbidden",
                    status=resp.status_code,
                    reset=resp.headers.get("X-RateLimit-Reset"),
                )
                return
            resp.raise_for_status()

        for repo in resp.json().get("items", []):
            full_name = repo.get("full_name")
            html_url = repo.get("html_url")
            if not full_name or not html_url:
                continue
            cve = _extract_cve(repo.get("name") or "")
            # Without a concrete CVE id the repo is almost always an aggregator /
            # tracker / tool, not a first-hand PoC — drop it unless opted out.
            if require_cve and not cve:
                continue
            yield CollectedItem(
                collector=self.name,
                external_id=cve or full_name,
                fingerprint=f"{self.name}:{full_name}",
                title=full_name,
                url=html_url,
                summary=(repo.get("description") or "")[:2000],
                payload={
                    "cve_id": cve,
                    "repo": full_name,
                    "owner": (repo.get("owner") or {}).get("login"),
                    "stars": int(repo.get("stargazers_count") or 0),
                    "language": repo.get("language"),
                    "pushed_at": repo.get("pushed_at"),
                    "created_at": repo.get("created_at"),
                    "updated_at": repo.get("updated_at"),
                    "trust": "low",
                    "source": "poc_search",
                },
            )


def _extract_cve(name: str) -> str:
    """Return the first full ``CVE-YYYY-NNNN`` id in a repo name, else ``""``.

    Requires the complete pattern (year + >=4-digit sequence). A bare ``cve``
    token or ``CVE-Monitor`` style name yields ``""`` so the caller can treat
    it as noise rather than a first-hand PoC.
    """
    m = _CVE_RE.search(name)
    return m.group(0).upper() if m else ""


def _is_true(v: str | None) -> bool:
    return str(v or "").lower() in ("true", "1", "yes", "on")
