"""Centralized configuration — every env var lives here (single source of truth).

Debugging tip: if a feed or agent is "dark", check `settings.feature_flags()`
which reports exactly which capabilities are enabled given the current env.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = .../pulsenet-v2 (three levels up from this file:
# app/config.py -> app -> pulsenet-engine -> mini-services -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = REPO_ROOT / "db" / "custom.db"


class Settings(BaseSettings):
    """All runtime configuration, loaded from env / .env."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(__file__).resolve().parents[1] / ".env"),
        env_prefix="",
        extra="ignore",
    )

    # --- Gemini (dual key for Alpha/Beta consensus) ---
    gemini_api_key_a: str = ""
    gemini_api_key_b: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- Optional feeds (dark until a key is supplied) ---
    acled_key: str = ""
    acled_email: str = ""
    # ACLED OAuth (preferred over legacy key)
    acled_access_token: str = ""
    acled_refresh_token: str = ""
    comtrade_key: str = ""


    # --- Data store (shared SQLite file owned by Prisma) ---
    database_path: str = str(DEFAULT_DB_PATH)

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # --- Engine knobs ---
    monte_carlo_trials: int = 4000
    feeds_config_path: str = str(Path(__file__).resolve().parent / "feeds" / "feeds.yaml")
    max_feed_items: int = 14
    log_level: str = "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy connection string for the shared SQLite file."""
        return f"sqlite:///{self.database_path}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def has_dual_gemini(self) -> bool:
        return bool(self.gemini_api_key_a and self.gemini_api_key_b)

    def has_any_gemini(self) -> bool:
        return bool(self.gemini_api_key_a or self.gemini_api_key_b)

    def feature_flags(self) -> dict[str, bool]:
        """Snapshot of which capabilities are live — surfaced at /health."""
        return {
            "gemini_alpha": bool(self.gemini_api_key_a),
            "gemini_beta": bool(self.gemini_api_key_b),
            "dual_consensus": self.has_dual_gemini(),
            "acled": bool(self.acled_key or self.acled_access_token),
            "comtrade_key": bool(self.comtrade_key),
        }



@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (use as a FastAPI dependency)."""
    return Settings()


def reset_settings_cache() -> None:
    """Test helper — clears the cache so env overrides take effect."""
    get_settings.cache_clear()
    # Also drop any GEMINI keys that leaked into os.environ during tests.
    os.environ.pop("PULSENET_TEST_RESET", None)
