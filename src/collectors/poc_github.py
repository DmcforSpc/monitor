"""First-hand PoC repositories via the nomi-sec PoC-in-GitHub feed.

A community-maintained index that continuously scrapes GitHub for repos whose
name contains a CVE id — i.e. published proof-of-concept / exploit code. No
auth required, clean signal (already filtered to CVE-named repos), ~JSON.

Each item is a *real PoC repository*, not a vulnerability advisory: the
``url`` points straight at the GitHub repo holding the exploit code.

Default-disabled. Enable with::

    CVE_PLUGIN_POC_GITHUB_ENABLED=true

Optional knobs:

* ``CVE_PLUGIN_POC_GITHUB_MAX_ITEMS`` (default 100) — most-recent N PoCs.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

_API = "https://poc-in-github.motikan2010.net/api/v1/"
_DEFAULT_MAX_ITEMS = 100


@register_collector
class PocGithubCollector(BaseCollector):
    name = "poc_github"
    description = "First-hand PoC repos from the nomi-sec PoC-in-GitHub feed"

    @property
    def enabled(self) -> bool:
        return _is_true(self.config.get("enabled", "false"))

    def collect(self) -> Iterable[CollectedItem]:
        max_items = int(self.config.get("max_items", _DEFAULT_MAX_ITEMS))
        params = {"sort": "created", "order": "desc"}

        seen = 0
        with self.http_client() as http:
            resp = http.get(_API, params=params)
            resp.raise_for_status()

        for poc in resp.json().get("pocs", []):
            if seen >= max_items:
                break
            full_name = poc.get("full_name")
            html_url = poc.get("html_url")
            if not full_name or not html_url:
                continue
            seen += 1
            cve = poc.get("cve_id") or ""
            try:
                stars = int(poc.get("stargazers_count") or 0)
            except (TypeError, ValueError):
                stars = 0
            yield CollectedItem(
                collector=self.name,
                external_id=cve or full_name,
                # Dedup on the repo, not the CVE: many PoCs can share one CVE.
                fingerprint=f"{self.name}:{full_name}",
                title=full_name,
                url=html_url,
                summary=(poc.get("description") or "")[:2000],
                payload={
                    "cve_id": cve,
                    "repo": full_name,
                    "owner": poc.get("owner"),
                    "stars": stars,
                    "vuln_description": (poc.get("vuln_description") or "")[:2000],
                    "created_at": poc.get("created_at"),
                    "updated_at": poc.get("updated_at"),
                    "pushed_at": poc.get("pushed_at"),
                    "trust": "medium",
                    "source": "poc_github",
                },
            )


def _is_true(v: str | None) -> bool:
    return str(v or "").lower() in ("true", "1", "yes", "on")
