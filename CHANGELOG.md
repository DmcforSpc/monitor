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

### Security & DevEx
- CI now runs `bandit` (static analysis) and `pip-audit` (CVE in dependencies)
  in parallel with the lint and smoke jobs
- `[tool.bandit]` section in `pyproject.toml` (excludes tests/build/venv,
  whitelists the `SELECT 1` literal in `/api/ready`)
- `.github/dependabot.yml`: weekly pip / GitHub Actions / Docker updates with
  grouping (runtime vs dev deps) and Conventional-Commits prefixes
- `.devcontainer/devcontainer.json`: one-click VS Code / GitHub Codespaces
  environment (Python 3.11 + uv + ruff + mypy + recommended extensions,
  auto-installs project + pre-commit)

### Documentation
- MkDocs Material site under `docs/` covering quickstart, architecture,
  plugin development (collectors & notifiers), deployment (Docker /
  security / observability), and CLI / API / configuration / data model
  references
- `[docs]` extras group: `mkdocs-material` + `pymdown-extensions`
- `.github/workflows/docs.yml`: build (`mkdocs build --strict`) + deploy to
  GitHub Pages on every push to `main` that touches docs

### Default plugins (bundled, all opt-in)
- **`poc_github`** collector — first-hand PoC repositories from the nomi-sec
  PoC-in-GitHub feed (repos whose name contains a CVE id; no auth, clean
  signal). `CVE_PLUGIN_POC_GITHUB_ENABLED=true`.
- **`poc_search`** collector — first-hand PoC repositories via the live GitHub
  repository search API (catches brand-new exploit repos before third-party
  indexes pick them up). `CVE_PLUGIN_POC_SEARCH_ENABLED=true`; set
  `CVE_PLUGIN_POC_SEARCH_TOKEN` (or `GH_TOKEN`) for a usable rate limit.
  Defaults to keeping only repos whose name carries a concrete `CVE-YYYY-NNNN`
  id (drops aggregators / trackers / tooling); set
  `CVE_PLUGIN_POC_SEARCH_REQUIRE_CVE=false` for the unfiltered firehose.
- **`feishu`** notifier — pushes each new item to a Feishu / Lark group via a
  custom-bot webhook as an interactive card. `CVE_PLUGIN_FEISHU_WEBHOOK=...`;
  optional `CVE_PLUGIN_FEISHU_SECRET` for signature-verified bots. Inspects the
  Feishu JSON `code` (not just HTTP status) so app-level errors surface as
  failures, and self-throttles to `CVE_PLUGIN_FEISHU_MIN_INTERVAL` (default
  0.7s) between sends to stay under the 100 msg/min custom-bot cap.
- **`console`** notifier — structlog dispatcher; **enabled by default** so
  the pipeline produces visible output without any configuration. Disable
  with `CVE_PLUGIN_CONSOLE_ENABLED=false`.

### Fixed
- `Settings.plugin_config()` now reads `CVE_PLUGIN_*` values from the `.env`
  file as well as the process environment (env vars still take precedence).
  Previously pydantic loaded `.env` without exporting to `os.environ`, so
  plugin config set only in `.env` (e.g. `CVE_PLUGIN_POC_GITHUB_ENABLED`) was
  silently ignored and bundled collectors never ran unless the var was exported.

### Processing logic
- `httpx-retries` integrated into `BaseCollector.http_client()` and
  `BaseNotifier.http_client()` via the shared factory `src/core/http.py`.
  Default policy: 3 attempts, exponential backoff (0.5s × 2^n + jitter),
  honours `Retry-After`, retries on 429 / 5xx.

### Community & release
- `SECURITY.md`: vulnerability reporting policy, SLAs, scope, supported versions
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1
- `.editorconfig`: universal editor settings (LF / UTF-8 / trailing whitespace)
- `.github/ISSUE_TEMPLATE/{bug,feature,config}.yml`: GitHub issue form
  templates with pre-flight checklists, dropdowns, secret-redaction reminders
- `.github/PULL_REQUEST_TEMPLATE.md`: PR checklist (lint / format / tests /
  CHANGELOG / docs / no secrets)
- `.github/workflows/release.yml`: triggered on `v*.*.*` tag — verifies
  pyproject.toml version == tag, builds multi-arch (amd64 + arm64) Docker
  image, pushes to GHCR with `:latest` / `:1.x.y` / `:1.x` / `:1` tags,
  creates GitHub Release with auto-generated notes + Docker pull example

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
