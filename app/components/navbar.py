"""Public (landing page) navigation bar."""

from __future__ import annotations

from nicegui import ui

from app.components.sidebar import brand

LINKS = [("Features", "#features"), ("Preview", "#preview"), ("How it works", "#how"), ("AI", "#ai")]


def landing_navbar(logged_in: bool = False) -> None:
    with ui.header().classes("ft-header px-4 sm:px-8 py-3"):
        with ui.row().classes("w-full max-w-[1200px] mx-auto items-center justify-between no-wrap"):
            brand("text-lg")
            with ui.row().classes("items-center gap-7 max-md:hidden"):
                for label, href in LINKS:
                    ui.link(label, href).classes("no-underline text-sm font-semibold ft-muted hover:text-white")
            with ui.row().classes("items-center gap-2 no-wrap"):
                if logged_in:
                    ui.button("Open dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("ft-btn-primary").props("color=none text-color=none")
                else:
                    ui.button("Log in", on_click=lambda: ui.navigate.to("/login")).classes("ft-btn-ghost max-sm:hidden").props("color=none text-color=none")
                    ui.button("Get started", on_click=lambda: ui.navigate.to("/register")).classes("ft-btn-primary").props("color=none text-color=none")
                with ui.button(icon="menu").props('flat round dense aria-label="Menu"').classes("text-white md:hidden"):
                    with ui.menu():
                        for label, href in LINKS:
                            ui.menu_item(label, on_click=lambda h=href: ui.navigate.to(h))
                        if not logged_in:
                            ui.menu_item("Log in", on_click=lambda: ui.navigate.to("/login"))
