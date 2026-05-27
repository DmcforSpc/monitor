# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `Dockerfile` (multi-stage with uv) + `.dockerignore` + `docker-compose.yml`
  for one-command deployment; runtime container is non-root with healthcheck
- `SecurityHeadersMiddleware` always-on: `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Referrer-Policy`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`
- Opt-in `TrustedHostMiddleware` via `CVE_ALLOWED_HOSTS` (comma-separated)
- Opt-in `CORSMiddleware` via `CVE_CORS_ORIGINS` (read-only API: only `GET`
  is whitelisted; `CVE_CORS_ALLOW_CREDENTIALS` toggles credentials)
- `Settings.allowed_hosts` / `cors_origins` parse comma-separated env values
- `/api/ready` readiness probe (DB health check) alongside `/api/health`
  liveness probe; both kept outside the versioned prefix
- Versioned data API at `/api/v1/...` (stats, items, collectors, notifiers,
  runs, notifications) — future breaking changes can ship as `/api/v2/...`
- Optional Logfire observability bootstrap (`pip install -e ".[observability]"`)
  with one-line FastAPI / SQLAlchemy / httpx auto-instrumentation; opt-in via
  `LOGFIRE_TOKEN`, silently no-op without it

### Changed
- API endpoints moved from `/api/*` to `/api/v1/*` (BREAKING for the data
  endpoints; `/api/health` URL preserved)

## [1.0.0] - 2026-05-27

### Added
- Plugin-based collector / notifier framework with class-level registration
- Generic `CollectedItem` ORM model (source-agnostic, JSON `payload` extension)
- Repository helpers for upsert/dedup, listing, and notification logging
- APScheduler-based background pipeline loop with safe-singleton wrapper
- FastAPI read-only dashboard with REST API (`/api/health`, `/api/stats`,
  `/api/items`, `/api/collectors`, `/api/notifiers`, `/api/runs`,
  `/api/notifications`)
- Typer CLI: `serve` / `collect` / `list collectors|notifiers` /
  `db init|reset` / `version`
- `structlog`-based structured logging with rotating file handler and optional
  JSON output
- Pydantic Settings (env prefix `CVE_`) with plugin namespace
  (`CVE_PLUGIN_<NAME>_*`)
- `pyproject.toml` (hatchling backend) compatible with `uv`
- MIT License, CHANGELOG, CONTRIBUTING guide
- GitHub Actions CI (ruff lint + format check + mypy)
- Pre-commit hooks (ruff, gitleaks, standard whitespace / YAML / TOML checks)

[Unreleased]: https://github.com/DmcforSpc/monitor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/DmcforSpc/monitor/releases/tag/v1.0.0
