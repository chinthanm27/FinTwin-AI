"""Authentication pages: /login, /register, /logout"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.responses import RedirectResponse
from nicegui import run, ui
from pymongo.errors import PyMongoError

from app.auth.session import current_user, end_session, safe_next, start_session
from app.components.sidebar import brand
from app.services import auth_service
from app.styles.theme import apply_theme
from app.utils.errors import DatabaseUnavailableError, FinTwinError
from app.utils.logger import get_logger

log = get_logger("pages.auth")

AUTH_SIDE_SVG = """
<svg viewBox="0 0 420 180" style="width:100%;height:auto" aria-hidden="true">
  <path class="ft-draw" d="M10 150 C60 140 90 146 130 120 S200 110 230 92" fill="none" stroke="#3EE6B0" stroke-width="3.5" stroke-linecap="round"/>
  <path class="ft-draw-late" d="M230 92 C280 74 330 60 410 30 L410 80 C330 98 280 104 230 92 Z" fill="rgba(139,124,255,.16)"/>
  <path class="ft-draw-late" d="M230 92 C280 78 330 68 410 54" fill="none" stroke="#8B7CFF" stroke-width="3" stroke-dasharray="8 7" stroke-linecap="round"/>
  <circle cx="230" cy="92" r="6" fill="#070D1A" stroke="#3EE6B0" stroke-width="3"/>
</svg>
"""


def _auth_layout(title: str, subtitle: str, form_builder: Callable[[], None]) -> None:
    apply_theme()
    with ui.element("div").classes("min-h-screen w-full grid lg:grid-cols-2"):
        with ui.column().classes("max-lg:hidden p-12 justify-between").style(
            "background:linear-gradient(160deg, rgba(62,230,176,.08), rgba(139,124,255,.10)); border-right:1px solid var(--line)"
        ):
            brand("text-xl")
            with ui.column().classes("gap-5 max-w-md"):
                ui.html(AUTH_SIDE_SVG, sanitize=False).classes("w-full")
                ui.label("Your past spending is the best model of your future spending.").classes(
                    "ft-display text-3xl font-bold leading-tight"
                )
                ui.label("FinTwin AI turns your transactions into a twin you can question: what you can afford, "
                         "what a raise changes, and what looks out of the ordinary.").classes("ft-muted")
            ui.label("Educational analysis tool. Not financial advice.").classes("text-xs ft-faint")
        with ui.column().classes("w-full items-center justify-center p-5 sm:p-10"):
            with ui.column().classes("w-full max-w-md gap-6"):
                with ui.element("div").classes("lg:hidden"):
                    brand("text-xl")
                with ui.column().classes("gap-1"):
                    ui.label(title).classes("ft-display text-3xl font-bold")
                    ui.label(subtitle).classes("ft-muted")
                form_builder()


def _password_input(label: str) -> ui.input:
    return ui.input(label, password=True, password_toggle_button=True).props("outlined dark").classes("w-full")


@ui.page("/login", title="Log in · FinTwin AI")
def login_page(next: str = "", logged_out: str = "") -> RedirectResponse | None:
    if current_user() is not None:
        return RedirectResponse(safe_next(next), status_code=303)

    def form() -> None:
        if logged_out:
            ui.label("You've been logged out.").classes("ft-chip ft-chip-mint")
        email = ui.input("Email").props('outlined dark type=email autocomplete=email autofocus').classes("w-full")
        password = _password_input("Password").props("autocomplete=current-password")
        error = ui.label("").classes("text-sm ft-coral hidden")

        async def submit() -> None:
            error.classes(add="hidden")
            button.props("loading")
            try:
                user = await run.io_bound(auth_service.authenticate, email.value, password.value)
            except FinTwinError as exc:
                error.text = exc.message
                error.classes(remove="hidden")
                return
            except PyMongoError:
                log.exception("Login failed due to database error")
                error.text = DatabaseUnavailableError.user_message
                error.classes(remove="hidden")
                return
            finally:
                button.props(remove="loading")
            start_session(user)
            ui.navigate.to(safe_next(next))

        password.on("keydown.enter", submit)
        button = ui.button("Log in", on_click=submit).classes("ft-btn-primary w-full py-2.5 text-base").props("color=none text-color=none")
        with ui.row().classes("gap-1 justify-center w-full text-sm"):
            ui.label("New to FinTwin AI?").classes("ft-muted")
            ui.link("Create an account", "/register").classes("ft-mint font-semibold no-underline")

    _auth_layout("Welcome back", "Log in to see your dashboard and talk to your twin.", form)
    return None


@ui.page("/register", title="Create account · FinTwin AI")
def register_page() -> RedirectResponse | None:
    if current_user() is not None:
        return RedirectResponse("/dashboard", status_code=303)

    def form() -> None:
        name = ui.input("Full name").props("outlined dark autocomplete=name autofocus").classes("w-full")
        email = ui.input("Email").props("outlined dark type=email autocomplete=email").classes("w-full")
        password = _password_input("Password").props("autocomplete=new-password")
        hint = ui.label("At least 8 characters, with a letter and a number.").classes("text-xs ft-muted -mt-3")
        confirm = _password_input("Confirm password").props("autocomplete=new-password")
        error = ui.label("").classes("text-sm ft-coral hidden")

        def update_hint() -> None:
            value = password.value or ""
            ok = len(value) >= 8 and any(c.isalpha() for c in value) and any(c.isdigit() for c in value)
            hint.classes(replace="text-xs -mt-3 " + ("ft-mint" if ok else "ft-muted"))
            hint.text = "Strong enough." if ok else "At least 8 characters, with a letter and a number."

        password.on_value_change(update_hint)

        async def submit() -> None:
            error.classes(add="hidden")
            button.props("loading")
            try:
                user = await run.io_bound(
                    auth_service.register_user, name.value, email.value, password.value, confirm.value
                )
            except FinTwinError as exc:
                error.text = exc.message
                error.classes(remove="hidden")
                return
            except PyMongoError:
                log.exception("Registration failed due to database error")
                error.text = DatabaseUnavailableError.user_message
                error.classes(remove="hidden")
                return
            finally:
                button.props(remove="loading")
            start_session(user)
            ui.navigate.to("/dashboard?welcome=1")

        confirm.on("keydown.enter", submit)
        button = ui.button("Create account", on_click=submit).classes("ft-btn-primary w-full py-2.5 text-base").props("color=none text-color=none")
        ui.label("Passwords are hashed with bcrypt. FinTwin AI never stores them in plain text.").classes(
            "text-xs ft-faint text-center w-full"
        )
        with ui.row().classes("gap-1 justify-center w-full text-sm"):
            ui.label("Already have an account?").classes("ft-muted")
            ui.link("Log in", "/login").classes("ft-mint font-semibold no-underline")

    _auth_layout("Create your account", "Set up your financial twin in under a minute.", form)
    return None


@ui.page("/logout")
def logout_page() -> RedirectResponse:
    end_session()
    return RedirectResponse("/login?logged_out=1", status_code=303)
