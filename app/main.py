"""
FinTwin AI - application entry point.

Run from the project root:

    python -m app.main
"""

from __future__ import annotations

import threading

from nicegui import app, ui

from app.config import settings
from app.utils.logger import get_logger

# Importing the page modules registers their routes with NiceGUI.
from app.pages import (  # noqa: F401  (imported for side effects)
    ai_twin,
    auth,
    budget,
    dashboard,
    financial_health,
    forecast,
    fraud,
    landing,
    reports,
    settings_page,
    transactions,
    upload,
)

log = get_logger("main")


def _warm_up() -> None:
    """Connect to MongoDB and prepare the spending model in the background."""
    from app.ai.spending_predictor import load_model
    from app.database.mongodb import check_connection

    ok, message = check_connection()
    if ok:
        log.info("Database check: %s", message)
    else:
        log.error("Database check failed: %s", message)
    try:
        bundle = load_model()
        if bundle:
            log.info("Spending model ready: %s", bundle["model_name"])
    except Exception as exc:  # the app still works without the model
        log.warning("Spending model warm-up failed: %s", exc)


@app.on_startup
def on_startup() -> None:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    if not settings.storage_secret_configured:
        log.warning("STORAGE_SECRET is not set in .env; using a development-only secret.")
    threading.Thread(target=_warm_up, name="fintwin-warmup", daemon=True).start()


app.add_static_files("/assets", str(settings.assets_dir))


def main() -> None:
    log.info("Starting %s on http://%s:%s", settings.app_name, settings.host, settings.port)
    ui.run(
        title=settings.app_name,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        dark=True,
        favicon="💰",
        storage_secret=settings.effective_storage_secret,
        show=settings.is_development,
        show_welcome_message=True,
        reconnect_timeout=10.0,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
