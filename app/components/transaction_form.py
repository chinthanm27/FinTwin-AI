"""Add / edit transaction dialog."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from nicegui import ui

from app.ai.categorizer import categorize
from app.components.app_shell import notify_error
from app.models.transaction import CATEGORIES, CATEGORIES_BY_TYPE, TRANSACTION_TYPES
from app.services import transaction_service


def open_transaction_dialog(user_id: str, on_saved: Callable[[], None], existing: dict[str, Any] | None = None) -> None:
    editing = existing is not None
    data = existing or {}
    with ui.dialog() as dialog, ui.card().classes("ft-dialog w-[480px] max-w-[95vw] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Edit transaction" if editing else "Add transaction").classes("ft-display text-xl font-semibold")
            ui.button(icon="close", on_click=dialog.close).props('flat round dense aria-label="Close"')

        ttype = ui.toggle(TRANSACTION_TYPES, value=data.get("transaction_type", "Expense")).props(
            "spread no-caps unelevated toggle-color=primary toggle-text-color=dark"
        ).classes("w-full")
        description = ui.input("Description", value=data.get("description", "")).props(
            "outlined dark maxlength=200 counter"
        ).classes("w-full")
        suggestion = ui.label("").classes("text-xs ft-iris -mt-2 hidden")
        with ui.row().classes("w-full gap-3 no-wrap"):
            amount = ui.number("Amount (₹)", value=data.get("amount"), min=0, format="%.2f").props(
                "outlined dark"
            ).classes("flex-1")
            date_input = ui.input("Date", value=data.get("date", date.today().isoformat())).props(
                "outlined dark type=date"
            ).classes("flex-1")
        category = ui.select(
            CATEGORIES_BY_TYPE.get(ttype.value, CATEGORIES),
            value=data.get("category") if data.get("category") in CATEGORIES else
            CATEGORIES_BY_TYPE.get(ttype.value, CATEGORIES)[0],
            label="Category",
        ).props("outlined dark options-dense").classes("w-full")

        def on_type_change() -> None:
            options = CATEGORIES_BY_TYPE.get(ttype.value, CATEGORIES)
            category.set_options(options, value=category.value if category.value in options else options[0])

        def on_description_change() -> None:
            text = description.value or ""
            if len(text) < 3:
                suggestion.classes(add="hidden")
                return
            prediction = categorize(text)
            if prediction.confidence >= 0.8:
                suggestion.text = f"Suggested: {prediction.transaction_type} · {prediction.category} (click to apply)"
                suggestion.classes(remove="hidden")
            else:
                suggestion.classes(add="hidden")

        def apply_suggestion() -> None:
            prediction = categorize(description.value or "")
            ttype.value = prediction.transaction_type
            on_type_change()
            if prediction.category in category.options:
                category.value = prediction.category
            suggestion.classes(add="hidden")

        ttype.on_value_change(on_type_change)
        description.on_value_change(on_description_change)
        suggestion.classes(add="cursor-pointer").on("click", apply_suggestion)

        def save() -> None:
            payload = {
                "date": date_input.value,
                "category": category.value,
                "transaction_type": ttype.value,
                "amount": amount.value,
                "description": description.value or "",
            }
            try:
                if editing:
                    transaction_service.update_transaction(user_id, data["id"], payload)
                    ui.notify("Transaction updated", type="positive")
                else:
                    transaction_service.add_transaction(user_id, **payload)
                    ui.notify("Transaction added", type="positive")
            except Exception as exc:
                notify_error(exc)
                return
            dialog.close()
            on_saved()

        with ui.row().classes("w-full justify-end gap-2 pt-2"):
            ui.button("Cancel", on_click=dialog.close).classes("ft-btn-ghost").props("color=none text-color=none")
            ui.button("Save changes" if editing else "Add transaction", on_click=save).classes("ft-btn-primary").props("color=none text-color=none")
    dialog.open()
