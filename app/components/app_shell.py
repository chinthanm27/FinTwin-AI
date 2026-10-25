"""
Authenticated application shell: header, sidebar drawer, content area.

`app_shell` is a context manager. Anything raised while building page
content is caught here and replaced by a friendly message, while the
technical details go to the log.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui
from pymongo.errors import PyMongoError

from app.auth.session import end_session
from app.components.dashboard_cards import error_state
from app.components.notification_panel import notification_bell
from app.components.sidebar import brand, sidebar
from app.models.user import User
from app.styles.theme import apply_theme
from app.utils.errors import DatabaseUnavailableError, FinTwinError
from app.utils.logger import get_logger

log = get_logger("ui")


def logout() -> None:
    end_session()
    ui.navigate.to("/login?logged_out=1")


@contextmanager
def app_shell(user: User, active: str) -> Iterator[ui.column]:
    apply_theme()
    drawer = ui.left_drawer(value=None, fixed=True).props("width=260 breakpoint=1024").classes("ft-drawer p-0")
    with drawer:
        sidebar(active, logout)

    with ui.header().classes("ft-header px-4 py-2 items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=drawer.toggle).props('flat round dense aria-label="Menu"').classes(
                "text-white lg:hidden"
            )
            with ui.element("div").classes("lg:hidden"):
                brand("text-base")
        with ui.row().classes("items-center gap-2 no-wrap"):
            try:
                notification_bell(user.id)
            except (FinTwinError, PyMongoError) as exc:
                log.warning("Notification bell unavailable: %s", exc)
            with ui.button().props("flat no-caps dense").classes("px-2 text-white"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.label(user.initials).classes(
                        "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                    ).style("background:linear-gradient(135deg,#3EE6B0,#8B7CFF); color:#06111C")
                    with ui.column().classes("gap-0 items-start max-sm:hidden"):
                        ui.label(user.full_name).classes("text-sm font-semibold leading-tight")
                        ui.label(user.email).classes("text-[11px] ft-muted leading-tight")
                with ui.menu().classes("w-56"):
                    ui.menu_item("Settings", on_click=lambda: ui.navigate.to("/settings"))
                    ui.menu_item("Reports", on_click=lambda: ui.navigate.to("/reports"))
                    ui.separator()
                    ui.menu_item("Log out", on_click=logout)

    content = ui.column().classes("ft-content")
    with content:
        try:
            yield content
        except DatabaseUnavailableError as exc:
            log.error("Database unavailable on page %s", active)
            content.clear()
            with content:
                error_state(exc.message, "Start MongoDB (net start MongoDB) and refresh this page.")
        except PyMongoError as exc:
            log.exception("Database error on page %s: %s", active, exc)
            content.clear()
            with content:
                error_state(DatabaseUnavailableError.user_message)
        except FinTwinError as exc:
            content.clear()
            with content:
                error_state(exc.message)
        except Exception:  # last line of defence: never show a traceback
            log.exception("Unexpected error on page %s", active)
            content.clear()
            with content:
                error_state("An unexpected error occurred. The details were written to logs/fintwin.log.")


def notify_error(exc: Exception, fallback: str = "Something went wrong. Please try again.") -> None:
    """Friendly toast for errors raised by UI actions."""
    if isinstance(exc, FinTwinError):
        ui.notify(exc.message, type="negative")
    elif isinstance(exc, PyMongoError):
        log.exception("Database error during action")
        ui.notify(DatabaseUnavailableError.user_message, type="negative", multi_line=True)
    else:
        log.exception("Unexpected error during action")
        ui.notify(fallback, type="negative")
