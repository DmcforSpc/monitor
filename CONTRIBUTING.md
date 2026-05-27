# Contributing

Thanks for considering a contribution! This project is a **plugin-based framework** — most contributions land as new collectors / notifiers rather than core changes.

## Development setup

```bash
git clone https://github.com/DmcforSpc/monitor.git
cd monitor
pip install uv          # one-time
uv pip install -e ".[dev]"
```

## Local checks

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # format check (use `ruff format .` to fix)
uv run mypy src/               # type check
```

> **Tests note**: the `tests/` directory is excluded from version control on this repo. Maintainers run the in-house smoke suite locally before merging.

## Pre-commit hooks (strongly recommended)

```bash
pip install pre-commit
pre-commit install
```

Installed hooks:

- **ruff** — lint + auto-format
- **gitleaks** — block any commit containing a leaked secret (tokens, webhooks, private keys)
- **standard hooks** — trailing whitespace, EOL, YAML / TOML validity, merge-conflict markers, accidentally-large files, private-key detection

## Adding a collector

Full contract: `src/collectors/README.md`. Minimal recipe:

```python
from collections.abc import Iterable
from src.core.collectors import BaseCollector, register_collector
from src.db.models import CollectedItem


@register_collector
class MyCollector(BaseCollector):
    name = "my_source"
    description = "Short blurb shown on the dashboard."

    def collect(self) -> Iterable[CollectedItem]:
        with self.http_client() as http:
            data = http.get("https://example.com/feed.json").json()
        for entry in data["items"]:
            yield CollectedItem(
                collector=self.name,
                external_id=entry["id"],
                fingerprint=self.fingerprint(entry["id"]),
                title=entry["title"],
                url=entry["link"],
                summary=entry.get("summary", ""),
                payload={"severity": entry.get("severity")},
            )
```

Drop the file under `src/collectors/`. Auto-discovered on the next pipeline run.

## Adding a notifier

Same pattern, see `src/notifiers/README.md`. Implement `send(item) -> NotificationResult`.

## Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
| --- | --- |
| `feat:` | New end-user feature |
| `fix:` | Bug fix |
| `refactor:` | Internal change without behaviour shift |
| `perf:` | Performance improvement |
| `docs:` | Documentation only |
| `chore:` | Tooling / housekeeping |
| `ci:` | CI configuration |
| `test:` | Adding or fixing tests |

Use the imperative mood ("add X", not "added X"). Keep the subject line under 72 chars; details in the body.

## Pull request checklist

- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `mypy src/` passes (or you've explained why the failure is acceptable)
- [ ] Public APIs have docstrings
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No secrets committed (pre-commit's `gitleaks` should catch this; do not rely on review alone)

## Security

If you discover a vulnerability in the framework itself (not a plugin), **do not file a public issue**. Email the maintainer or use GitHub's private vulnerability reporting on the repository.
