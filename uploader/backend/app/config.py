"""Application configuration.

All settings come from environment variables (optionally loaded from a local
``.env`` file). Nothing here reaches out to any external service. See
``.env.example`` for the full list of supported variables and safe defaults.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the uploader backend.

    Defaults are intentionally *safe*: sandbox environment, export disabled,
    no admin token required for local dev, and no external export URLs.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core environment -------------------------------------------------
    # APP_ENV: "sandbox" (local, relaxed auth, dry-run only) or "production".
    app_env: Literal["sandbox", "production"] = "sandbox"

    # EXPORT_ENABLED: master switch for *real* exports. False by default and
    # even when True the current build never calls the four websites (transport
    # is intentionally not implemented yet).
    export_enabled: bool = False

    # DATABASE_PATH: local SQLite file used for sandbox / local storage.
    # (A full DATABASE_URL is a future extension; a local file is enough today.)
    database_path: str = "data/uploader_sandbox.db"

    # ADMIN_API_TOKEN: simple bearer token required for mutations in production.
    # In sandbox this is optional (auth is intentionally relaxed for local dev).
    admin_api_token: Optional[str] = None

    # CORS_ALLOW_ORIGINS: comma-separated list of allowed frontend origins.
    cors_allow_origins: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"
    )

    # --- Future export targets (NOT called yet) ---------------------------
    # These are read only so they can be surfaced in the export preview. The
    # current build never issues a request to any of them.
    export_url_tkp: Optional[str] = None
    export_url_tcp: Optional[str] = None
    export_url_agm: Optional[str] = None
    export_url_yq: Optional[str] = None

    # --- Derived helpers --------------------------------------------------
    @property
    def is_sandbox(self) -> bool:
        return self.app_env == "sandbox"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    def export_url(self, program: str) -> Optional[str]:
        """Return the (future) export target URL for a program, or None."""
        return {
            "TKP": self.export_url_tkp,
            "TCP": self.export_url_tcp,
            "AGM": self.export_url_agm,
            "YQ": self.export_url_yq,
        }.get(program.upper())
