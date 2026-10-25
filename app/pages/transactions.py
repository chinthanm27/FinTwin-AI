"""Transaction management: /transactions"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.auth.session import current_user, login_redirect
from app.components.app_shell import app_shell, notify_error
from app.components.dashboard_cards import page_header, panel
from app.components.onboarding import onboarding_panel
from app.components.transaction_form import open_transaction_dialog
from app.components.transaction_table import transactions_table
from app.models.transaction import CATEGORIES, TRANSACTION_TYPES
from app.services import transaction_service
from app.utils.formatters import format_inr

SORT_OPTIONS = {
    "date_desc": "Newest first", "date_asc": "Oldest first",
    "amount_desc": "Largest amount", "amount_asc": "Smallest amount",
}


@ui.page("/transactions", title="Transactions · FinTwin AI")
def transactions_page():
    user = current_user()
    if user is None:
        return login_redirect("/transactions")

    filters: dict[str, Any] = {"search": "", "type": "", "category": "", "start": "", "end": "", "sort": "date_desc"}

    with app_shell(user, "transactions"):
        def header_actions() -> None:
            ui.button("Export CSV", icon="download", on_click=export).classes("ft-btn-ghost").props("color=none text-color=none")
            ui.button("Add transaction", icon="add",
                      on_click=lambda: open_transaction_dialog(user.id, refresh_all)).classes("ft-btn-primary").props("color=none text-color=none")

        def current_list():
            sort_field, direction = filters["sort"].rsplit("_", 1)
            return transaction_service.list_transactions(
                user.id,
                search=filters["search"] or None,
                transaction_type=filters["type"] or None,
                category=filters["category"] or None,
                start_date=transaction_service.parse_date_input(filters["start"]),
                end_date=transaction_service.parse_date_input(filters["end"]),
                sort_by=sort_field,
                descending=direction == "desc",
            )

        def export() -> None:
            try:
                data = transaction_service.export_csv(current_list())
                ui.download.content(data, transaction_service.export_filename("transactions", "csv"), "text/csv")
            except Exception as exc:
                notify_error(exc)

        page_header("Transactions", "Every income, expense and investment you've recorded.", header_actions)

        def delete_row(row: dict[str, Any]) -> None:
            with ui.dialog() as dialog, ui.card().classes("ft-dialog p-6 gap-4 w-[420px] max-w-[95vw]"):
                ui.label("Delete this transaction?").classes("ft-display text-lg font-semibold")
                ui.label(f"{row['description'] or row['category']} · {format_inr(row['amount'])} on {row['date']}").classes(
                    "text-sm ft-muted")
                ui.label("This can't be undone.").classes("text-sm")

                def confirm() -> None:
                    try:
                        transaction_service.delete_transaction(user.id, row["id"])
                        ui.notify("Transaction deleted", type="positive")
                    except Exception as exc:
                        notify_error(exc)
                    dialog.close()
                    refresh_all()

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).classes("ft-btn-ghost").props("color=none text-color=none")
                    ui.button("Delete", icon="delete", on_click=confirm).classes("ft-btn-danger").props("color=none text-color=none")
            dialog.open()

        def edit_row(row: dict[str, Any]) -> None:
            open_transaction_dialog(user.id, refresh_all, existing=row)

        @ui.refreshable
        def results() -> None:
            items = current_list()
            rows = [t.to_row() for t in items]
            income = sum(t.amount for t in items if t.transaction_type == "Income")
            expense = sum(t.amount for t in items if t.transaction_type == "Expense")
            invest = sum(t.amount for t in items if t.transaction_type == "Investment")
            with ui.row().classes("w-full gap-2 wrap items-center"):
                ui.label(f"{len(items)} transactions").classes("ft-chip")
                ui.label(f"Income {format_inr(income)}").classes("ft-chip ft-chip-mint")
                ui.label(f"Expenses {format_inr(expense)}").classes("ft-chip ft-chip-coral")
                ui.label(f"Investments {format_inr(invest)}").classes("ft-chip ft-chip-sky")
            transactions_table(rows, edit_row, delete_row)

        @ui.refreshable
        def page_body() -> None:
            if not transaction_service.has_transactions(user.id):
                onboarding_panel(user.id, refresh_all)
                return
            with panel():
                with ui.element("div").classes("grid gap-3 w-full sm:grid-cols-2 lg:grid-cols-6"):
                    ui.input("Search description or category", value=filters["search"],
                             on_change=lambda e: (filters.update(search=e.value), results.refresh())).props(
                        "outlined dark dense clearable debounce=300").classes("lg:col-span-2").props("prepend-icon=search")
                    ui.select({"": "All types", **{t: t for t in TRANSACTION_TYPES}}, value=filters["type"], label="Type",
                              on_change=lambda e: (filters.update(type=e.value), results.refresh())).props("outlined dark dense")
                    ui.select({"": "All categories", **{c: c for c in CATEGORIES}}, value=filters["category"],
                              label="Category",
                              on_change=lambda e: (filters.update(category=e.value), results.refresh())).props(
                        "outlined dark dense")
                    ui.input("From", value=filters["start"],
                             on_change=lambda e: (filters.update(start=e.value), results.refresh())).props(
                        "outlined dark dense type=date stack-label")
                    ui.input("To", value=filters["end"],
                             on_change=lambda e: (filters.update(end=e.value), results.refresh())).props(
                        "outlined dark dense type=date stack-label")
                with ui.row().classes("w-full items-center justify-between gap-2 wrap"):
                    ui.select(SORT_OPTIONS, value=filters["sort"], label="Sort",
                              on_change=lambda e: (filters.update(sort=e.value), results.refresh())).props(
                        "outlined dark dense").classes("w-48")
                    ui.button("Clear filters", icon="filter_alt_off", on_click=clear_filters).props("flat no-caps").classes(
                        "ft-muted")
                results()

        def clear_filters() -> None:
            filters.update(search="", type="", category="", start="", end="", sort="date_desc")
            page_body.refresh()

        def refresh_all() -> None:
            page_body.refresh()

        page_body()
    return None
