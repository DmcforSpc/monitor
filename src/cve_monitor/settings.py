"""Application settings — single Pydantic source of truth.

All settings are loaded from environment variables (prefixed ``CVE_``) and
optionally from a ``.env`` file in the project root. Plugins read their own
configuration from ``settings.plugin_config(name)`` which returns the subset
of environment variables matching ``CVE_PLUGIN_<NAME>_*``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CVE_",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ─────────────────────────────────────────────────────────
    app_name: str = "CVE Monitor"
    log_level: LogLevel = "INFO"
    log_file: Path | None = Field(default=Path("cve-monitor.log"))
    log_json: bool = False

    # ── Database ────────────────────────────────────────────────────
    database_url: str = "sqlite:///./cve_monitor.db"

    # ── Scheduler ───────────────────────────────────────────────────
    scheduler_enabled: bool = True
    fetch_interval_seconds: int = Field(default=300, ge=10)

    # ── Web ─────────────────────────────────────────────────────────
    web_host: str = "127.0.0.1"
    web_port: int = Field(default=8000, ge=1, le=65535)
    web_reload: bool = False

    # ── HTTP client defaults ────────────────────────────────────────
    http_timeout: int = Field(default=30, ge=1)
    http_user_agent: str = "CVE-Monitor/4.0"
    http_proxy: str | None = None

    # ── Plugin namespace ────────────────────────────────────────────
    plugin_env_prefix: str = "CVE_PLUGIN_"

    @field_validator("log_file", mode="before")
    @classmethod
    def _empty_log_file_is_none(cls, v: object) -> object:
        if v in ("", None):
            return None
        return v

    # ── Helpers ─────────────────────────────────────────────────────
    def plugin_config(self, name: str) -> dict[str, str]:
        """Return env vars belonging to a plugin namespace.

        For ``name='feishu'`` it returns every ``CVE_PLUGIN_FEISHU_*`` variable
        as a dict with the prefix stripped and keys lower-cased. Empty strings
        are filtered out so plugins can ``if cfg.get("webhook"): ...``.
        """
        prefix = f"{self.plugin_env_prefix}{name.upper()}_"
        result: dict[str, str] = {}
        for key, value in os.environ.items():
            if key.startswith(prefix) and value:
                result[key[len(prefix):].lower()] = value
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — instantiated once per process."""
    return Settings()
