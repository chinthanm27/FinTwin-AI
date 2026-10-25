"""Forecasts: /forecast (cash flow, spending prediction, wealth scenarios)"""

from __future__ import annotations

from nicegui import ui

from app.ai.cashflow_forecast import forecast_cashflow
from app.ai.financial_twin import FinancialTwin
from app.ai.spending_predictor import predict_next_month
from app.ai.wealth_forecast import WealthInputs, project_wealth
from app.auth.session import current_user, login_redirect
from app.components import charts
from app.components.app_shell import app_shell
from app.components.dashboard_cards import (
    assumptions_box,
    empty_state,
    kpi_card,
    page_header,
    panel,
    stat_row,
)
from app.database import insight_repository
from app.services import analytics_service
from app.services.transaction_service import transactions_dataframe
from app.styles.theme import COLORS
from app.utils.errors import ValidationError
from app.utils.formatters import format_inr, format_inr_compact, month_label


@ui.page("/forecast", title="Forecast · FinTwin AI")
def forecast_page():
    user = current_user()
    if user is None:
        return login_redirect("/forecast")

    with app_shell(user, "forecast"):
        page_header("Forecast", "Projections from your own history. Every number here is an estimate with its "
                                "assumptions listed, not a guarantee.")
        df = transactions_dataframe(user.id)
        profile = insight_repository.get_profile(user.id)
        twin = FinancialTwin.from_dataframe(df, profile)
        monthly = analytics_service.monthly_overview(df)
        history = analytics_service.completed_months(monthly)

        with ui.tabs().classes("w-full justify-start").props("inline-label no-caps active-color=primary indicator-color=primary align=left") as tabs:
            t_cash = ui.tab("Cash flow", icon="waterfall_chart")
            t_spend = ui.tab("Spending", icon="insights")
            t_wealth = ui.tab("Wealth scenarios", icon="trending_up")

        with ui.tab_panels(tabs, value=t_cash).classes("w-full bg-transparent").props("animated"):
            # ---------------------------------------------------------------- cash flow
            with ui.tab_panel(t_cash).classes("p-0 gap-4"):
                horizon = {"months": 6}

                @ui.refreshable
                def cash_section() -> None:
                    fc = forecast_cashflow(df, horizon["months"], user_id=user.id)
                    if fc is None or history.empty:
                        with panel():
                            empty_state("Not enough history", "Cash-flow forecasts need at least one completed month "
                                        "of transactions.", "query_stats")
                        return
                    insight_repository.save_prediction(user.id, "cashflow", fc.to_dict())
                    with ui.element("div").classes("grid gap-3 grid-cols-2 lg:grid-cols-4 w-full"):
                        kpi_card("Tracked cash today", format_inr_compact(fc.starting_balance), "account_balance",
                                 COLORS["sky"])
                        kpi_card(f"Projected in {horizon['months']} months", format_inr_compact(fc.balance[-1]),
                                 "auto_awesome", COLORS["iris"],
                                 f"Range {format_inr_compact(fc.balance_low[-1])} to {format_inr_compact(fc.balance_high[-1])}")
                        kpi_card("Avg projected income", format_inr_compact(sum(fc.income.values) / len(fc.months)),
                                 "south_west", COLORS["mint"])
                        kpi_card("Avg projected expenses", format_inr_compact(sum(fc.expense.values) / len(fc.months)),
                                 "north_east", COLORS["coral"])
                    with panel("Tracked cash: recorded and projected",
                               "Mint is what happened. The dashed iris line is your twin's projection with an 80% range.",
                               right=lambda: ui.toggle({3: "3M", 6: "6M", 12: "12M"}, value=horizon["months"],
                                                       on_change=lambda e: (horizon.update(months=e.value),
                                                                            cash_section.refresh())).props(
                                   "dense no-caps unelevated rounded toggle-color=primary toggle-text-color=dark")):
                        charts.render(charts.twin_forecast(history, fc.months, fc.balance, fc.balance_low,
                                                           fc.balance_high, "cash", "cumulative_balance", 330))
                    with ui.element("div").classes("grid gap-4 lg:grid-cols-[1.5fr_1fr] w-full"):
                        with panel("Projected income, expenses and savings", fc.method):
                            charts.render(charts.multi_forecast(fc, 300))
                        with panel("Month by month"):
                            for m, inc, exp, bal in zip(fc.months, fc.income.values, fc.expense.values, fc.balance):
                                with ui.row().classes("w-full justify-between no-wrap py-1 border-b").style(
                                        "border-color:var(--line)"):
                                    ui.label(month_label(m)).classes("text-sm font-semibold w-16")
                                    ui.label(f"+{format_inr_compact(inc)}").classes("text-xs ft-mint ft-num")
                                    ui.label(f"−{format_inr_compact(exp)}").classes("text-xs ft-coral ft-num")
                                    ui.label(format_inr_compact(bal)).classes("text-sm ft-num font-semibold")
                    assumptions_box(fc.assumptions)

                cash_section()

            # ---------------------------------------------------------------- spending
            with ui.tab_panel(t_spend).classes("p-0 gap-4"):
                prediction = predict_next_month(df) if not df.empty else None
                if prediction is None:
                    with panel():
                        empty_state("Not enough history", "Spending predictions need at least one completed month "
                                    "of expenses.", "insights")
                else:
                    insight_repository.save_prediction(user.id, "spending", prediction.to_dict())
                    spent_now = float(monthly[monthly["month"] == prediction.month]["expense"].sum()) if not monthly.empty else 0.0
                    with ui.element("div").classes("grid gap-3 grid-cols-2 lg:grid-cols-4 w-full"):
                        kpi_card(f"Estimated {month_label(prediction.month)} spend", format_inr_compact(prediction.predicted),
                                 "auto_awesome", COLORS["iris"],
                                 f"Likely {format_inr_compact(prediction.low)}–{format_inr_compact(prediction.high)}")
                        kpi_card("Spent so far", format_inr_compact(spent_now), "north_east", COLORS["amber"],
                                 f"{spent_now / prediction.predicted * 100:.0f}% of estimate" if prediction.predicted else "")
                        kpi_card("3-month average", format_inr_compact(prediction.baseline), "show_chart", COLORS["muted"])
                        kpi_card("History used", f"{prediction.history_months} months", "history", COLORS["sky"],
                                 prediction.method)
                    with ui.element("div").classes("grid gap-4 lg:grid-cols-[1.5fr_1fr] w-full"):
                        with panel("Recorded vs estimated spending", "The diamond marks what you've spent this month so far"):
                            charts.render(charts.spending_estimate(history, prediction, spent_now, 300))
                        with panel("Typical monthly spend by category", "Median of your recent months"):
                            if prediction.category_forecast:
                                for cat, val in list(prediction.category_forecast.items())[:8]:
                                    stat_row(cat, format_inr(val))
                            else:
                                ui.label("No category history yet.").classes("ft-muted text-sm")
                    metrics = prediction.model_metrics or {}
                    if metrics.get("holdout_mae_ratio"):
                        with panel("How the model was chosen",
                                   f"Trained on {metrics.get('users', 0)} synthetic users · {metrics.get('train_rows', 0)} training "
                                   f"and {metrics.get('test_rows', 0)} hold-out months"):
                            ui.label("Each candidate predicts next month's spending relative to the recent average. "
                                     "Lower error is better. A machine-learning model is used only if it beats both "
                                     "simple baselines on months it never saw.").classes("text-sm ft-muted")
                            for name, mae in sorted(metrics["holdout_mae_ratio"].items(), key=lambda kv: kv[1]):
                                chosen = name == prediction.method
                                with ui.row().classes("w-full items-center justify-between no-wrap py-1"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label(name).classes("text-sm" + (" font-semibold" if chosen else ""))
                                        if chosen:
                                            ui.label("In use").classes("ft-chip ft-chip-mint")
                                    ui.label(f"±{mae * 100:.1f}% average error").classes("text-sm ft-num ft-muted")
                            ui.label(f"Typical error on hold-out months: about {format_inr(metrics.get('holdout_mae_rupees', 0))}."
                                     ).classes("text-xs ft-faint")

            # ---------------------------------------------------------------- wealth
            with ui.tab_panel(t_wealth).classes("p-0 gap-4"):
                s = twin.state
                inputs = {
                    "current_savings": round(max(0.0, s.current_balance) + s.total_invested, -3),
                    "monthly_investment": round(s.avg_investment or 5000, -2),
                    "expected_return": profile.expected_annual_return,
                    "years": 10,
                    "monthly_income": round(s.avg_income, -2),
                    "monthly_expenses": round(s.avg_expense, -2),
                    "annual_step_up": 0.0,
                    "inflation": 6.0,
                }
                with ui.element("div").classes("grid gap-4 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] w-full"):
                    with panel("Scenario inputs", "Pre-filled from your data. Change anything."):
                        fields = [
                            ("current_savings", "Current savings & investments (₹)", 1000),
                            ("monthly_investment", "Monthly investment (₹)", 500),
                            ("expected_return", "Expected annual return (%)", 0.5),
                            ("years", "Duration (years)", 1),
                            ("annual_step_up", "Yearly step-up in investment (%)", 1),
                            ("inflation", "Inflation (%)", 0.5),
                            ("monthly_income", "Monthly income (₹)", 1000),
                            ("monthly_expenses", "Monthly expenses (₹)", 1000),
                        ]
                        for key, label, step in fields:
                            ui.number(label, value=inputs[key], step=step, min=0,
                                      on_change=lambda e, k=key: (inputs.update({k: e.value or 0}), wealth_result.refresh())
                                      ).props("outlined dark dense debounce=300").classes("w-full")

                    @ui.refreshable
                    def wealth_result() -> None:
                        try:
                            projection = project_wealth(WealthInputs(
                                current_savings=float(inputs["current_savings"] or 0),
                                monthly_investment=float(inputs["monthly_investment"] or 0),
                                expected_return=float(inputs["expected_return"] or 0),
                                years=int(inputs["years"] or 1),
                                monthly_income=float(inputs["monthly_income"] or 0),
                                monthly_expenses=float(inputs["monthly_expenses"] or 0),
                                annual_step_up=float(inputs["annual_step_up"] or 0),
                                inflation=float(inputs["inflation"] or 0),
                            ))
                        except ValidationError as exc:
                            with panel():
                                empty_state("Check the inputs", exc.message, "edit_note")
                            return
                        with ui.column().classes("w-full gap-4"):
                            with ui.element("div").classes("grid gap-3 grid-cols-2 xl:grid-cols-4 w-full"):
                                kpi_card("Projected value", format_inr_compact(projection.final_value), "auto_awesome",
                                         COLORS["iris"], f"After {inputs['years']} years at {inputs['expected_return']}%")
                                kpi_card("Total invested", format_inr_compact(projection.total_invested), "savings",
                                         COLORS["muted"])
                                kpi_card("Estimated growth", format_inr_compact(projection.gains), "trending_up",
                                         COLORS["mint"])
                                kpi_card("In today's money", format_inr_compact(projection.real_final_value), "price_change",
                                         COLORS["sky"], f"Adjusted for {inputs['inflation']}% inflation")
                            for warning in projection.warnings:
                                with ui.row().classes("w-full items-center gap-2 p-3 rounded-xl ft-chip-amber no-wrap").style(
                                        "border:1px solid"):
                                    ui.icon("warning_amber", size="18px")
                                    ui.label(warning).classes("text-sm")
                            with panel("Projected growth under three return assumptions",
                                       "Not a guarantee: real returns vary year to year and can be negative"):
                                charts.render(charts.wealth_chart(projection, 340))
                            assumptions_box(projection.assumptions)

                    wealth_result()
    return None
