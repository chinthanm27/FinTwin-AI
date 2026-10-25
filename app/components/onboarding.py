"""Shared 'get started' actions shown when a user has no data yet."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import run, ui

from app.components.app_shell import notify_error
from app.components.transaction_form import open_transaction_dialog
from app.services import budget_service, demo_data_service, fraud_service, transaction_service


async def load_demo(user_id: str, on_done: Callable[[], None]) -> None:
    notification = ui.notification("Generating 12 months of demo transactions…", spinner=True, timeout=None)
    try:
        count = await run.io_bound(demo_data_service.load_demo_data, user_id)
        df = await run.io_bound(transaction_service.transactions_dataframe, user_id)
        if not budget_service.get_budgets(user_id):
            budget_service.apply_suggested_budgets(user_id, budget_service.average_spend_by_category(df))
        await run.io_bound(fraud_service.scan_user, user_id, df)
    except Exception as exc:
        notification.dismiss()
        notify_error(exc)
        return
    notification.dismiss()
    ui.notify(f"Loaded {count} demo transactions and starter budgets", type="positive")
    on_done()


def onboarding_panel(user_id: str, on_done: Callable[[], None]) -> None:
    with ui.column().classes("ft-glass w-full p-6 sm:p-8 gap-6"):
        with ui.column().classes("gap-2 max-w-2xl"):
            ui.label("Let's give your twin something to learn from").classes("ft-display text-2xl font-bold")
            ui.label("Your dashboard, forecasts and AI answers are all built from your transactions. "
                     "Choose how you'd like to start.").classes("ft-muted")
        with ui.element("div").classes("grid gap-4 md:grid-cols-3 w-full"):
            options = [
                ("science", "#8B7CFF", "Explore with demo data",
                 "12 months of fictional transactions, budgets and a few unusual payments to find.",
                 "Load demo data", lambda: load_demo(user_id, on_done)),
                ("add_card", "#3EE6B0", "Add a transaction",
                 "Enter income, an expense or an investment by hand.",
                 "Add transaction", lambda: open_transaction_dialog(user_id, on_done)),
                ("upload_file", "#4CC2FF", "Upload a bank statement",
                 "Import a CSV or PDF statement. Transactions are categorised for you.",
                 "Upload statement", lambda: ui.navigate.to("/upload")),
            ]
            for icon, color, title, text, button_label, handler in options:
                with ui.column().classes("ft-tile p-5 gap-3"):
                    with ui.element("div").classes("rounded-xl p-2 self-start").style(f"background:{color}1F"):
                        ui.icon(icon, size="22px").style(f"color:{color}")
                    ui.label(title).classes("font-semibold")
                    ui.label(text).classes("text-sm ft-muted flex-grow")
                    ui.button(button_label, on_click=handler).classes(
                        "ft-btn-primary" if icon == "science" else "ft-btn-ghost"
                    ).props("color=none text-color=none")
