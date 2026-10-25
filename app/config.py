"""
FinTwin AI - Central configuration.

Loads settings from the project-root .env file exactly once.
Every other module imports settings from here:

    from app.config import settings

instead of calling os.getenv() directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Project root (app/config.py -> app -> project root)
BASE_DIR: Path = Path(__file__).resolve().parent.parent
APP_DIR: Path = BASE_DIR / "app"
ENV_FILE: Path = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

PLACEHOLDER_SECRET = "replace-with-a-long-random-secret"
DEV_FALLBACK_SECRET = "fintwin-dev-only-secret-change-me-in-env-file"


def _get_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    app_name: str
    app_env: str
    host: str
    port: int
    reload: bool
    storage_secret: str

    mongo_uri: str
    database_name: str

    llm_provider: str
    gemini_api_key: str
    gemini_model: str

    max_upload_mb: int

    base_dir: Path = field(default=BASE_DIR)
    app_dir: Path = field(default=APP_DIR)
    uploads_dir: Path = field(default=APP_DIR / "uploads")
    assets_dir: Path = field(default=APP_DIR / "assets")
    datasets_dir: Path = field(default=BASE_DIR / "datasets")
    models_dir: Path = field(default=BASE_DIR / "trained_models")
    logs_dir: Path = field(default=BASE_DIR / "logs")

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def env_file_found(self) -> bool:
        return ENV_FILE.exists()

    @property
    def storage_secret_configured(self) -> bool:
        return bool(self.storage_secret) and self.storage_secret != PLACEHOLDER_SECRET

    @property
    def effective_storage_secret(self) -> str:
        """Secret used for session signing. Falls back to a dev-only value."""
        return self.storage_secret if self.storage_secret_configured else DEV_FALLBACK_SECRET

    @property
    def uses_mock_database(self) -> bool:
        return self.mongo_uri.lower().startswith("mongomock://")

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider.lower() == "gemini" and bool(self.gemini_api_key)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def _resolve_host() -> str:
    """APP_HOST wins. Otherwise, on a hosting platform (PORT is set) listen on all interfaces."""
    explicit = _get_str("APP_HOST", "")
    if explicit:
        return explicit
    return "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"


def _resolve_port() -> int:
    """Hosting platforms (Render, Railway, Fly, Heroku...) provide PORT; it takes priority over APP_PORT."""
    platform_port = _get_int("PORT", 0)
    return platform_port if platform_port > 0 else _get_int("APP_PORT", 8080)


settings = Settings(
    app_name=_get_str("APP_NAME", "FinTwin AI"),
    app_env=_get_str("APP_ENV", "development"),
    host=_resolve_host(),
    port=_resolve_port(),
    reload=_get_bool("APP_RELOAD", False),
    storage_secret=_get_str("STORAGE_SECRET", ""),
    mongo_uri=_get_str("MONGO_URI", "mongodb://localhost:27017"),
    database_name=_get_str("DATABASE_NAME", "fintwin_ai"),
    llm_provider=_get_str("LLM_PROVIDER", "gemini"),
    gemini_api_key=_get_str("GEMINI_API_KEY", ""),
    gemini_model=_get_str("GEMINI_MODEL", "gemini-2.5-flash"),
    max_upload_mb=max(1, _get_int("MAX_UPLOAD_MB", 10)),
)