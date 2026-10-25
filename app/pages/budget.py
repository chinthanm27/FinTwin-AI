"""Budget management: /budget"""

from __future__ import annotations

from datetime import date

from nicegui import ui

from app.auth.session import current_user, login_redirect
from app.components.app_shell import app_shell, notify_error
from app.components.dashboard_cards import empty_state, kpi_card, page_header, panel, progress_bar
from app.models.budget import BudgetStatus
from app.models.transaction import CATEGORY_ICONS, EXPENSE_CATEGORIES
from app.services import analytics_service, budget_service, transaction_service
from app.styles.theme import COLORS
from app.utils.formatters import format_inr

STATUS = {
    "ok": (COLORS["mint"], "On track", "mint"),
    "warning": (COLORS["amber"], "Almost used", "amber"),
    "exceeded": (COLORS["coral"], "Over budget", "coral"),
}


@ui.page("/budget", title="Budget · FinTwin AI")
def budget_page():
    user = current_user()
    if user is None:
        return login_redirect("/budget")

    with app_shell(user, "budget"):
        def open_dialog(existing: BudgetStatus | None = None) -> None:
            with ui.dialog() as dialog, ui.card().classes("ft-dialog p-6 gap-4 w-[420px] max-w-[95vw]"):
                ui.label("Edit budget" if existing and existing.budget_id else "New budget").classes("ft-display text-xl font-semibold")
                category = ui.select(EXPENSE_CATEGORIES, value=existing.category if existing else "Food",
                                     label="Category").props("outlined dark").classes("w-full")
                if existing:
                    category.disable()  # category is the budget's identity; change the limit only
                amount = ui.number("Monthly limit (₹)", value=existing.budget if existing else None, min=0,
                                   step=500).props("outlined dark").classes("w-full")

                def save() -> None:
                    try:
                        budget_service.set_budget(user.id, category.value, amount.value)
                    except Exception as exc:
                        notify_error(exc)
                        return
                    ui.notify("Budget saved", type="positive")
                    dialog.close()
                    body.refresh()

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).classes("ft-btn-ghost").props("color=none text-color=none")
                    ui.button("Save budget", on_click=save).classes("ft-btn-primary").props("color=none text-color=none")
            dialog.open()

        def remove(status: BudgetStatus) -> None:
            try:
                budget_service.delete_budget(user.id, status.budget_id)
                ui.notify(f"{status.category} budget removed", type="positive")
            except Exception as exc:
                notify_error(exc)
            body.refresh()

        def apply_suggested() -> None:
            try:
                df = transaction_service.transactions_dataframe(user.id)
                count = budget_service.apply_suggested_budgets(user.id, budget_service.average_spend_by_category(df))
                ui.notify(f"Created {count} starter budgets", type="positive")
            except Exception as exc:
                notify_error(exc)
            body.refresh()

        page_header("Budget", f"Monthly limits for {date.today().strftime('%B %Y')}. Alerts start at 80% used.",
                    lambda: ui.button("New budget", icon="add", on_click=lambda: open_dialog()).classes("ft-btn-primary").props("color=none text-color=none"))

        @ui.refreshable
        def body() -> None:
            df = transaction_service.transactions_dataframe(user.id)
            statuses = budget_service.budget_status(user.id, df)
            if not statuses:
                with panel():
                    empty_state(
                        "No budgets yet",
                        "Start with suggested limits for Food, Transport, Shopping, Entertainment and Bills. "
                        "If you have history, they're based on your own averages.",
                        "account_balance_wallet",
                        lambda: (ui.button("Use suggested budgets", on_click=apply_suggested).classes("ft-btn-primary").props("color=none text-color=none"),
                                 ui.button("Create one", on_click=lambda: open_dialog()).classes("ft-btn-ghost").props("color=none text-color=none")),
                    )
                return

            totals = budget_service.budget_totals(statuses)
            with ui.element("div").classes("grid gap-3 grid-cols-2 lg:grid-cols-4 w-full"):
                kpi_card("Total budget", format_inr(totals["budget"]), "account_balance_wallet", COLORS["iris"])
                kpi_card("Spent", format_inr(totals["spent"]), "north_east", COLORS["coral"])
                kpi_card("Remaining", format_inr(totals["remaining"]), "savings",
                         COLORS["mint"] if totals["remaining"] >= 0 else COLORS["coral"])
                kpi_card("Used", f"{totals['percent_used']:.0f}%", "donut_large",
                         COLORS["amber"] if totals["percent_used"] >= 80 else COLORS["mint"])

            alerts = budget_service.budget_alerts(statuses)
            for alert in alerts:
                tone = "coral" if alert["level"] == "negative" else "amber"
                with ui.row().classes(f"w-full items-center gap-3 p-3 rounded-xl no-wrap ft-chip-{tone}").style(
                    "border-width:1px; border-style:solid"
                ):
                    ui.icon("error_outline" if tone == "coral" else "warning_amber", size="20px")
                    with ui.column().classes("gap-0"):
                        ui.label(alert["title"]).classes("text-sm font-semibold")
                        ui.label(alert["text"]).classes("text-xs opacity-80")

            with ui.element("div").classes("grid gap-4 md:grid-cols-2 xl:grid-cols-3 w-full"):
                for s in statuses:
                    color, label, tone = STATUS[s.status]
                    with ui.column().classes("ft-panel p-5 gap-3"):
                        with ui.row().classes("w-full items-center justify-between no-wrap"):
                            with ui.row().classes("items-center gap-3 no-wrap"):
                                with ui.element("div").classes("rounded-xl p-2").style(f"background:{color}1A"):
                                    ui.icon(CATEGORY_ICONS.get(s.category, "category"), size="20px").style(f"color:{color}")
                                ui.label(s.category).classes("font-semibold")
                            ui.label(label).classes(f"ft-chip ft-chip-{tone}")
                        with ui.row().classes("items-baseline gap-2"):
                            ui.label(format_inr(s.spent)).classes("ft-num text-2xl font-bold")
                            ui.label(f"of {format_inr(s.budget)}").classes("text-sm ft-muted")
                        progress_bar(s.percent_used, color)
                        with ui.row().classes("w-full justify-between text-xs"):
                            ui.label(f"{s.percent_used:.0f}% used").classes("ft-muted")
                            ui.label(f"{format_inr(abs(s.remaining))} {'left' if s.remaining >= 0 else 'over'}").classes(
                                "ft-mint" if s.remaining >= 0 else "ft-coral")
                        with ui.row().classes("w-full justify-end gap-1"):
                            ui.button("Edit", icon="edit", on_click=lambda st=s: open_dialog(st)).props(
                                "flat dense no-caps size=sm").classes("ft-muted")
                            ui.button("Remove", icon="delete_outline", on_click=lambda st=s: remove(st)).props(
                                "flat dense no-caps size=sm color=negative")

            budgeted = {s.category for s in statuses}
            unbudgeted = {k: v for k, v in analytics_service.current_month_expenses_by_category(df).items()
                          if k not in budgeted}
            if unbudgeted:
                with panel("Spending without a budget", "This month's expenses in categories you haven't limited"):
                    for category, amount in sorted(unbudgeted.items(), key=lambda kv: -kv[1]):
                        with ui.row().classes("w-full justify-between items-center no-wrap py-1"):
                            ui.label(category).classes("text-sm")
                            with ui.row().classes("items-center gap-3 no-wrap"):
                                ui.label(format_inr(amount)).classes("text-sm font-semibold ft-num")
                                ui.button("Set budget", on_click=lambda c=category, a=amount: open_dialog(
                                    BudgetStatus(category=c, budget=round(a * 1.1 / 500) * 500 or 500, spent=a))
                                          ).props("flat dense no-caps size=sm").classes("ft-mint")

        body()
    return None
