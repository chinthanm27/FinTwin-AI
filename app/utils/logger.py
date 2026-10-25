"""
Application logging.

Technical errors are written to logs/fintwin.log and the console,
while the UI only ever shows friendly messages.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import settings

_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("fintwin")
    root.setLevel(logging.DEBUG if settings.is_development else logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    file_handler = RotatingFileHandler(
        settings.logs_dir / "fintwin.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logging.INFO)
    root.addHandler(console)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""
    _configure()
    return logging.getLogger(f"fintwin.{name}")
