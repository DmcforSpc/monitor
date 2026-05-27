"""CISA Known Exploited Vulnerabilities (KEV) catalog collector.

The KEV catalog is the *gold standard* signal: every entry has confirmed
in-the-wild exploitation. Refreshed continuously, ~200 KB JSON, no auth.

Default-disabled. Enable with::

    CVE_PLUGIN_CISA_KEV_ENABLED=true

Optional knobs:

* ``CVE_PLUGIN_CISA_KEV_MAX_ITEMS`` (default 500) — most-recent N entries.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

_FEED_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_DEFAULT_MAX_ITEMS = 500


@register_collector
class CisaKevCollector(BaseCollector):
    name = "cisa_kev"
    description = "CISA Known Exploited Vulnerabilities catalog (high-trust)"

    @property
    def enabled(self) -> bool:
        return _is_true(self.config.get("enabled", "false"))

    def collect(self) -> Iterable[CollectedItem]:
        max_items = int(self.config.get("max_items", _DEFAULT_MAX_ITEMS))
        with self.http_client() as http:
            resp = http.get(_FEED_URL)
            resp.raise_for_status()
        vulns = resp.json().get("vulnerabilities", [])
        for v in vulns[-max_items:]:
            cve = v.get("cveID")
            if not cve:
                continue
            yield CollectedItem(
                collector=self.name,
                external_id=cve,
                fingerprint=f"{self.name}:{cve}",
                title=v.get("vulnerabilityName") or cve,
                url=f"https://nvd.nist.gov/vuln/detail/{cve}",
                summary=v.get("shortDescription", ""),
                payload={
                    "vendor": v.get("vendorProject"),
                    "product": v.get("product"),
                    "date_added": v.get("dateAdded"),
                    "due_date": v.get("dueDate"),
                    "ransomware_known": v.get("knownRansomwareCampaignUse") == "Known",
                    "required_action": v.get("requiredAction"),
                    "trust": "high",
                    "source": "cisa_kev",
                },
            )


def _is_true(v: str | None) -> bool:
    return str(v or "").lower() in ("true", "1", "yes", "on")
