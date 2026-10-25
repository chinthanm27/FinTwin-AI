"""Landing 'dashboard preview' rendered from real analytics on synthetic demo data."""

from __future__ import annotations

from functools import lru_cache

from nicegui import ui

from app.components import charts
from app.services import analytics_service
from app.services.demo_data_service import PersonaParams, generate_records
from app.services.transaction_service import documents_to_dataframe
from app.styles.theme import COLORS
from app.utils.formatters import format_inr_compact


@lru_cache(maxsize=1)
def _demo_analytics():
    df = documents_to_dataframe(generate_records(months=8, seed=2026, params=PersonaParams(inject_anomalies=False)))
    monthly = analytics_service.monthly_overview(df)
    return analytics_service.compute_summary(df), monthly.tail(6), analytics_service.category_breakdown(df)


def dashboard_preview() -> None:
    summary, monthly, categories = _demo_analytics()
    with ui.element("section").classes("w-full px-4 sm:px-8 py-16").props("id=preview"):
        with ui.column().classes("max-w-[1200px] mx-auto gap-8"):
            with ui.row().classes("w-full items-end justify-between gap-4 wrap"):
                with ui.column().classes("gap-2 max-w-xl"):
                    ui.html("<h2 style='font-size:clamp(1.8rem,3.4vw,2.6rem);line-height:1.1;margin:0;font-weight:700'>"
                            "One screen for where you stand.</h2>", sanitize=False)
                    ui.label("This preview is computed live from a fictional demo profile, exactly as your own "
                             "dashboard will be.").classes("ft-muted")
                ui.label("Demo data").classes("ft-chip ft-chip-amber")
            with ui.column().classes("ft-glass p-3 sm:p-4 w-full gap-3"):
                with ui.row().classes("items-center gap-1.5 px-2 pt-1"):
                    for c in ("#FF6B81", "#F6B94C", "#3EE6B0"):
                        ui.element("div").classes("w-2.5 h-2.5 rounded-full").style(f"background:{c}")
                    ui.label("fintwin.local/dashboard").classes("text-xs ft-faint ml-3")
                with ui.element("div").classes("grid gap-3 grid-cols-2 lg:grid-cols-4 w-full"):
                    for label, value, color in [
                        ("Income", summary.income, COLORS["mint"]), ("Expenses", summary.expenses, COLORS["coral"]),
                        ("Invested", summary.investments, COLORS["sky"]), ("Savings rate", None, COLORS["iris"]),
                    ]:
                        with ui.column().classes("ft-tile p-4 gap-1"):
                            ui.label(label).classes("ft-kpi-label")
                            text = f"{summary.savings_rate:.1f}%" if value is None else format_inr_compact(value)
                            ui.label(text).classes("ft-kpi-value").style(f"color:{color}" if value is None else "")
                with ui.element("div").classes("grid gap-3 lg:grid-cols-[1.6fr_1fr] w-full"):
                    with ui.column().classes("ft-tile p-4 gap-2"):
                        ui.label("Income vs expenses").classes("text-sm font-semibold")
                        charts.render(charts.income_vs_expenses(monthly, 260))
                    with ui.column().classes("ft-tile p-4 gap-2"):
                        ui.label("Spending by category").classes("text-sm font-semibold")
                        charts.render(charts.category_donut(categories, 260))
