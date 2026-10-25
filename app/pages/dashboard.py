"""Dashboard: /dashboard"""

from __future__ import annotations

from datetime import datetime

from nicegui import ui

from app.auth.session import current_user, login_redirect
from app.components import charts
from app.components.app_shell import app_shell
from app.components.dashboard_cards import (
    empty_state,
    insight_item,
    kpi_card,
    page_header,
    panel,
    progress_bar,
)
from app.components.onboarding import onboarding_panel
from app.components.transaction_form import open_transaction_dialog
from app.components.transaction_table import recent_list
from app.models.user import User
from app.services import transaction_service
from app.services.analytics_service import PERIODS
from app.services.insight_service import build_dashboard
from app.styles.theme import COLORS
from app.utils.formatters import format_inr, format_inr_compact

STATUS_COLORS = {"ok": COLORS["mint"], "warning": COLORS["amber"], "exceeded": COLORS["coral"]}


def _greeting(user: User) -> str:
    hour = datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    return f"Good {part}, {user.first_name}"


@ui.page("/dashboard", title="Dashboard · FinTwin AI")
def dashboard_page(welcome: str = ""):
    user = current_user()
    if user is None:
        return login_redirect("/dashboard")
    state = {"period": "6M"}

    with app_shell(user, "dashboard"):
        if welcome:
            ui.notify(f"Welcome to FinTwin AI, {user.first_name}!", type="positive")

        @ui.refreshable
        def body() -> None:
            ctx = build_dashboard(user.id, state["period"])

            def actions() -> None:
                if ctx.has_data:
                    ui.toggle({k: k for k in PERIODS}, value=state["period"],
                              on_change=lambda e: (state.update(period=e.value), body.refresh())).props(
                        "dense no-caps unelevated rounded toggle-color=primary toggle-text-color=dark"
                    ).classes("ft-tile").tooltip("Period")
                ui.button("Add transaction", icon="add",
                          on_click=lambda: open_transaction_dialog(user.id, body.refresh)).classes("ft-btn-primary").props("color=none text-color=none")

            page_header(_greeting(user),
                        f"Financial overview · {PERIODS[state['period']].lower()}" if ctx.has_data else
                        "Your financial overview will appear here.", actions)

            if not ctx.has_data:
                onboarding_panel(user.id, body.refresh)
                return

            s = ctx.summary
            health = ctx.health
            with ui.element("div").classes("grid gap-3 grid-cols-2 md:grid-cols-3 xl:grid-cols-6 w-full"):
                kpi_card("Tracked balance", format_inr_compact(ctx.all_time.balance), "account_balance",
                         COLORS["sky"], "Income − expenses − investments, all time")
                kpi_card("Income", format_inr_compact(s.income), "south_west", COLORS["mint"],
                         f"{s.transaction_count} transactions")
                kpi_card("Expenses", format_inr_compact(s.expenses), "north_east", COLORS["coral"],
                         f"{s.expenses / s.income * 100:.0f}% of income" if s.income else "No income recorded",
                         "negative" if s.income and s.expenses > s.income else "muted")
                kpi_card("Savings", format_inr_compact(s.savings), "savings", COLORS["mint"],
                         f"{s.savings_rate:.1f}% savings rate",
                         "positive" if s.savings_rate >= 20 else "warning" if s.savings_rate >= 0 else "negative")
                kpi_card("Investments", format_inr_compact(s.investments), "trending_up", COLORS["sky"],
                         "Contributions in period")
                kpi_card("Health indicator", f"{health.score}/100" if health.available else "—", "monitor_heart",
                         health.color, health.band)

            with ui.element("div").classes("grid gap-4 xl:grid-cols-3 w-full"):
                with ui.element("div").classes("xl:col-span-2"):
                    with panel("Cash flow", "Net cash flow each month and tracked cash over time"):
                        charts.render(charts.cash_flow(ctx.monthly, 300))
                with panel("AI financial insights", "Generated from your data by your twin",
                           right=lambda: ui.button("Ask twin", icon="auto_awesome",
                                                   on_click=lambda: ui.navigate.to("/ai-twin")).props(
                               "flat dense no-caps").classes("ft-iris")):
                    for insight in ctx.insights:
                        insight_item(insight)

            with ui.element("div").classes("grid gap-4 xl:grid-cols-3 w-full"):
                with ui.element("div").classes("xl:col-span-2"):
                    with panel("Income vs expenses", "Monthly totals by type"):
                        charts.render(charts.income_vs_expenses(ctx.monthly, 300))
                with panel("Spending by category", PERIODS[state["period"]]):
                    if ctx.categories.empty:
                        empty_state("No expenses", "Expenses in this period will appear here.", "donut_large")
                    else:
                        charts.render(charts.category_donut(ctx.categories, 300))

            with ui.element("div").classes("grid gap-4 lg:grid-cols-2 w-full"):
                with panel("Savings trend", "Savings (income − expenses) and savings rate"):
                    charts.render(charts.savings_trend(ctx.monthly, 270))
                with panel("Investment trend", "Monthly contributions and running total"):
                    charts.render(charts.investment_trend(ctx.monthly, 270))

            with ui.element("div").classes("grid gap-4 xl:grid-cols-3 w-full"):
                with ui.element("div").classes("xl:col-span-2"):
                    with panel("Recent transactions",
                               right=lambda: ui.button("View all", on_click=lambda: ui.navigate.to("/transactions")).props(
                                   "flat dense no-caps").classes("ft-mint")):
                        recent_list(transaction_service.recent_transactions(user.id, 7))
                with panel("Budgets this month",
                           right=lambda: ui.button("Manage", on_click=lambda: ui.navigate.to("/budget")).props(
                               "flat dense no-caps").classes("ft-mint")):
                    if not ctx.budgets:
                        empty_state("No budgets yet", "Set monthly limits to get early warnings.",
                                    "account_balance_wallet",
                                    lambda: ui.button("Create budgets", on_click=lambda: ui.navigate.to("/budget")).classes(
                                        "ft-btn-ghost").props("color=none text-color=none"))
                    for b in ctx.budgets[:6]:
                        with ui.column().classes("w-full gap-1.5"):
                            with ui.row().classes("w-full justify-between no-wrap"):
                                ui.label(b.category).classes("text-sm font-semibold")
                                ui.label(f"{format_inr(b.spent)} / {format_inr(b.budget)}").classes("text-xs ft-muted ft-num")
                            progress_bar(b.percent_used, STATUS_COLORS[b.status])

        body()
    return None
