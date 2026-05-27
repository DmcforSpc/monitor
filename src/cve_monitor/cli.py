"""Typer-based command-line interface.

::

    cve-monitor serve                 # start web + scheduler
    cve-monitor collect               # run one full pipeline cycle
    cve-monitor collect --name xx     # run a single collector
    cve-monitor list collectors       # show registered plugins
    cve-monitor list notifiers
    cve-monitor db init               # create tables
    cve-monitor db reset --yes        # DROP + CREATE (destructive)
    cve-monitor version               # print version
"""

from __future__ import annotations

import typer

from cve_monitor import __version__
from cve_monitor.logging import configure_logging, get_logger
from cve_monitor.settings import get_settings

app = typer.Typer(
    name="cve-monitor",
    help="Extensible security intelligence framework.",
    no_args_is_help=True,
    add_completion=False,
)

list_app = typer.Typer(help="List registered plugins.", no_args_is_help=True)
db_app = typer.Typer(help="Database administration.", no_args_is_help=True)
app.add_typer(list_app, name="list")
app.add_typer(db_app, name="db")


# ── Top-level commands ────────────────────────────────────────────


@app.command()
def version() -> None:
    """Print version and exit."""
    typer.echo(f"cve-monitor {__version__}")


@app.command()
def serve(
    host: str = typer.Option(None, help="Bind address (overrides CVE_WEB_HOST)."),
    port: int = typer.Option(None, help="Bind port (overrides CVE_WEB_PORT)."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes."),
) -> None:
    """Start the web dashboard + embedded scheduler."""
    import uvicorn

    settings = get_settings()
    configure_logging(settings)

    bind_host = host or settings.web_host
    bind_port = port or settings.web_port

    typer.echo(f"Starting {settings.app_name} v{__version__} on http://{bind_host}:{bind_port}")
    uvicorn.run(
        "cve_monitor.web.app:create_app",
        factory=True,
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_config=None,
    )


@app.command()
def collect(
    name: str = typer.Option("", "--name", "-n", help="Run only the named collector."),
    once: bool = typer.Option(  # noqa: ARG001 - reserved for future loop mode
        True, "--once/--loop", help="Reserved: currently always one-shot."
    ),
) -> None:
    """Run one collection cycle synchronously and exit."""
    from cve_monitor.core.pipeline import load_plugins, run_collector, run_pipeline

    settings = get_settings()
    configure_logging(settings)
    log = get_logger("cli")
    load_plugins()

    if name:
        result = run_collector(name, settings)
        log.info(
            "collector finished",
            collector=result.collector,
            status=result.status.value,
            new=result.items_new,
            sent=result.notifications_sent,
        )
        if result.error:
            raise typer.Exit(code=1)
        return

    summary = run_pipeline(settings)
    log.info(
        "pipeline finished",
        collectors=len(summary.results),
        new=summary.total_new,
        notifications=summary.total_notifications,
    )


# ── list ──────────────────────────────────────────────────────────


@list_app.command("collectors")
def list_collectors() -> None:
    """Show all registered collectors."""
    from cve_monitor.core.collectors import collector_registry
    from cve_monitor.core.pipeline import load_plugins

    load_plugins()
    if not collector_registry:
        typer.secho("No collectors registered.", fg=typer.colors.YELLOW)
        typer.echo("Add modules under src/cve_monitor/collectors/ — see README.")
        return
    typer.echo(f"{'NAME':<24} ENABLED  DESCRIPTION")
    for cls in collector_registry.values():
        enabled = _safe_enabled(cls)
        typer.echo(f"{cls.name:<24} {('yes' if enabled else 'no'):<7}  {cls.description}")


@list_app.command("notifiers")
def list_notifiers() -> None:
    """Show all registered notifiers."""
    from cve_monitor.core.notifiers import notifier_registry
    from cve_monitor.core.pipeline import load_plugins

    load_plugins()
    if not notifier_registry:
        typer.secho("No notifiers registered.", fg=typer.colors.YELLOW)
        typer.echo("Add modules under src/cve_monitor/notifiers/ — see README.")
        return
    typer.echo(f"{'NAME':<24} ENABLED  DESCRIPTION")
    for cls in notifier_registry.values():
        enabled = _safe_enabled(cls)
        typer.echo(f"{cls.name:<24} {('yes' if enabled else 'no'):<7}  {cls.description}")


# ── db ────────────────────────────────────────────────────────────


@db_app.command("init")
def db_init() -> None:
    """Create tables if they do not exist."""
    from cve_monitor.db.base import init_db

    configure_logging()
    init_db()
    typer.secho("Database initialised.", fg=typer.colors.GREEN)


@db_app.command("reset")
def db_reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """DROP and recreate all tables (destructive)."""
    from cve_monitor.db.base import reset_db

    configure_logging()
    settings = get_settings()
    if not yes:
        typer.confirm(
            f"This will DROP all tables in {settings.database_url}. Continue?",
            abort=True,
        )
    reset_db()
    typer.secho("Database reset.", fg=typer.colors.YELLOW)


# ── Helpers ───────────────────────────────────────────────────────


def _safe_enabled(cls: type) -> bool:
    try:
        instance = cls()
        return bool(instance.enabled)
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    app()
