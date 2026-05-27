"""Recent CVEs from the NIST National Vulnerability Database (NVD) API 2.0.

Default-disabled. Enable with::

    CVE_PLUGIN_NVD_RECENT_ENABLED=true

Optional knobs:

* ``CVE_PLUGIN_NVD_RECENT_API_KEY`` — NVD API key (free at
  https://nvd.nist.gov/developers/request-an-api-key). Lifts rate limit
  from 5 req/30s to 50 req/30s.
* ``CVE_PLUGIN_NVD_RECENT_LOOKBACK_DAYS`` (default 7) — window in days.
* ``CVE_PLUGIN_NVD_RECENT_RESULTS_PER_PAGE`` (default 100, max 2000).

Each yielded item carries CVSS v3.1 (preferred) or v3.0 metrics in payload.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem

_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_DEFAULT_LOOKBACK_DAYS = 7
_DEFAULT_PER_PAGE = 100


@register_collector
class NvdRecentCollector(BaseCollector):
    name = "nvd_recent"
    description = "Recent CVEs from NIST NVD API 2.0 (configurable window)"

    @property
    def enabled(self) -> bool:
        return _is_true(self.config.get("enabled", "false"))

    def collect(self) -> Iterable[CollectedItem]:
        days = int(self.config.get("lookback_days", _DEFAULT_LOOKBACK_DAYS))
        end = datetime.now(UTC).replace(microsecond=0)
        start = end - timedelta(days=days)

        headers: dict[str, str] = {"User-Agent": self.settings.http_user_agent}
        if api_key := self.config.get("api_key"):
            headers["apiKey"] = api_key

        params = {
            "pubStartDate": start.isoformat(),
            "pubEndDate": end.isoformat(),
            "resultsPerPage": int(self.config.get("results_per_page", _DEFAULT_PER_PAGE)),
        }

        with self.http_client(headers=headers) as http:
            resp = http.get(_API, params=params)
            resp.raise_for_status()

        for vuln in resp.json().get("vulnerabilities", []):
            cve_data = vuln.get("cve", {})
            cve_id = cve_data.get("id")
            if not cve_id:
                continue

            description = ""
            for d in cve_data.get("descriptions", []):
                if d.get("lang") == "en":
                    description = d.get("value", "")
                    break

            cvss_score = 0.0
            cvss_vector = ""
            severity = ""
            metrics = cve_data.get("metrics", {})
            for key in ("cvssMetricV31", "cvssMetricV30"):
                entries = metrics.get(key, [])
                if entries:
                    data = entries[0].get("cvssData", {})
                    cvss_score = float(data.get("baseScore", 0))
                    cvss_vector = data.get("vectorString", "")
                    severity = data.get("baseSeverity", "")
                    break

            yield CollectedItem(
                collector=self.name,
                external_id=cve_id,
                fingerprint=f"{self.name}:{cve_id}",
                title=cve_id,
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                summary=description,
                payload={
                    "cvss_score": cvss_score,
                    "cvss_vector": cvss_vector,
                    "severity": severity.upper(),
                    "published": cve_data.get("published"),
                    "last_modified": cve_data.get("lastModified"),
                    "trust": "high",
                    "source": "nvd",
                },
            )


def _is_true(v: str | None) -> bool:
    return str(v or "").lower() in ("true", "1", "yes", "on")
