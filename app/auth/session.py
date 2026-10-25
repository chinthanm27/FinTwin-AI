"""
Session handling on top of NiceGUI's per-browser user storage.

app.storage.user is stored server-side and identified by a signed
browser cookie (signed with STORAGE_SECRET), so the client cannot
forge a user id.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi.responses import RedirectResponse
from nicegui import app

from app.models.user import User
from app.utils.dates import utcnow
from app.utils.logger import get_logger

log = get_logger("session")

SESSION_LIFETIME = timedelta(days=7)
SAFE_NEXT_PATHS = {
    "/dashboard", "/transactions", "/budget", "/financial-health", "/forecast",
    "/fraud", "/ai-twin", "/upload", "/reports", "/settings",
}


def start_session(user: User) -> None:
    app.storage.user.update(
        {
            "authenticated": True,
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "login_at": utcnow().isoformat(),
        }
    )


def end_session() -> None:
    app.storage.user.clear()


def update_session_name(full_name: str) -> None:
    app.storage.user["full_name"] = full_name


def current_user() -> User | None:
    """Return the logged-in user from the session, or None if not authenticated/expired."""
    try:
        data = app.storage.user
    except (RuntimeError, AssertionError):
        return None
    if not data.get("authenticated") or not data.get("user_id"):
        return None
    try:
        login_at = datetime.fromisoformat(data.get("login_at", ""))
    except ValueError:
        end_session()
        return None
    if utcnow() - login_at > SESSION_LIFETIME:
        log.info("Session expired for user %s", data.get("user_id"))
        end_session()
        return None
    return User(
        id=data["user_id"],
        full_name=data.get("full_name", ""),
        email=data.get("email", ""),
        password_hash="",
    )


def login_redirect(next_path: str = "/dashboard") -> RedirectResponse:
    target = next_path if next_path in SAFE_NEXT_PATHS else "/dashboard"
    return RedirectResponse(f"/login?next={quote(target)}", status_code=303)


def safe_next(next_path: str | None) -> str:
    """Prevent open redirects: only allow known internal pages."""
    return next_path if next_path in SAFE_NEXT_PATHS else "/dashboard"
