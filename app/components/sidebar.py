"""Application sidebar navigation."""

from __future__ import annotations

from nicegui import ui

NAV_ITEMS: list[tuple[str, str, str, str]] = [
    # key, label, icon, path
    ("dashboard", "Dashboard", "space_dashboard", "/dashboard"),
    ("transactions", "Transactions", "receipt_long", "/transactions"),
    ("budget", "Budget", "account_balance_wallet", "/budget"),
    ("health", "Financial Health", "monitor_heart", "/financial-health"),
    ("twin", "AI Twin", "auto_awesome", "/ai-twin"),
    ("forecast", "Forecast", "query_stats", "/forecast"),
    ("fraud", "Fraud Detection", "policy", "/fraud"),
    ("upload", "Statements", "upload_file", "/upload"),
    ("reports", "Reports", "description", "/reports"),
    ("settings", "Settings", "settings", "/settings"),
]


def brand(size: str = "text-lg") -> None:
    with ui.link(target="/").classes("no-underline flex items-center gap-2").style("color:inherit"):
        ui.label("💰").classes(size)
        ui.label("FinTwin AI").classes(f"ft-display font-bold {size}")


def sidebar(active: str, on_logout) -> None:
    with ui.column().classes("w-full gap-1 p-4 min-h-screen").style("background:#0A1222"):
        with ui.row().classes("items-center px-2 pb-5 pt-1"):
            brand()
        for key, label, icon, path in NAV_ITEMS:
            classes = "ft-nav-item" + (" active" if key == active else "")
            with ui.link(target=path).classes(classes):
                ui.icon(icon, size="20px")
                ui.label(label)
        ui.space()
        ui.element("div").classes("ft-divider my-2")
        with ui.element("div").classes("ft-nav-item cursor-pointer").on("click", on_logout):
            ui.icon("logout", size="20px")
            ui.label("Log out")
        ui.label("Educational analysis tool. Not financial advice.").classes("text-[11px] ft-faint px-2 pt-2")
