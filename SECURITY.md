# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in the **framework code** (anything
under `src/`, CI workflows, Dockerfile, or default settings) please **do not
open a public GitHub issue**. Use one of these private channels instead:

1. **GitHub Private Vulnerability Reporting** (preferred):
   [github.com/DmcforSpc/monitor/security/advisories/new](https://github.com/DmcforSpc/monitor/security/advisories/new)
2. **Email**: 102737018+DmcforSpc@users.noreply.github.com

Please include:

- A description of the issue and the impact you observed
- Reproduction steps (PoC if possible)
- The version / commit SHA you tested against
- Optional: your suggested fix

## What to expect

| Stage | SLA |
| --- | --- |
| Acknowledgement of receipt | **48 hours** |
| Preliminary assessment + severity rating | **7 days** |
| Fix targeted for next minor / patch | depends on severity |
| Public advisory + CVE request (if applicable) | coordinated with you |

## Scope

| In scope | Out of scope |
| --- | --- |
| Code under `src/` | User-written collectors under `src/collectors/` (report to that plugin's author) |
| `.github/workflows/*` | User-written notifiers under `src/notifiers/` |
| `Dockerfile` | Third-party dependency CVEs (covered by `pip-audit` in CI — file an issue if it's not flagged) |
| Default middleware (`src/web/middleware.py`) | Self-hosted infrastructure (Nginx config, OS hardening, etc.) |

## Supported versions

| Version | Status |
| --- | --- |
| 1.x (current) | ✅ Active support |
| < 1.0 | ❌ Not supported — please upgrade |

## Security tooling already enforced in CI

- **bandit** — static analysis of `src/` for known dangerous patterns
- **pip-audit** — CVE database lookup against all transitive dependencies
- **gitleaks** — pre-commit hook blocks any committed secret

A failing CI check on any of these blocks merging to `main`.
