"""AI Financial Twin and Copilot: /ai-twin"""

from __future__ import annotations

from nicegui import ui

from app.ai.financial_twin import FinancialTwin
from app.auth.session import current_user, login_redirect
from app.components import charts
from app.components.ai_copilot import copilot_chat
from app.components.app_shell import app_shell
from app.components.dashboard_cards import assumptions_box, empty_state, page_header, panel, stat_row
from app.components.onboarding import onboarding_panel
from app.database import insight_repository
from app.services.transaction_service import transactions_dataframe
from app.utils.formatters import format_inr, format_inr_compact


@ui.page("/ai-twin", title="AI Twin · FinTwin AI")
def ai_twin_page():
    user = current_user()
    if user is None:
        return login_redirect("/ai-twin")

    with app_shell(user, "twin"):
        page_header("Your AI financial twin",
                    "A model of your finances built from your real transactions. Move the sliders to simulate a "
                    "decision, or ask the Copilot in plain English.")
        df = transactions_dataframe(user.id)
        twin = FinancialTwin.from_dataframe(df, insight_repository.get_profile(user.id))
        s = twin.state
        if not s.has_data:
            onboarding_panel(user.id, lambda: ui.navigate.reload())
            return None

        with ui.element("div").classes("grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] w-full items-start"):
            with ui.column().classes("gap-4 w-full min-w-0"):
                with panel("What your twin knows", f"Averages of your last {s.months_of_data} completed month(s)"):
                    with ui.element("div").classes("grid sm:grid-cols-2 gap-x-8 w-full"):
                        stat_row("Monthly income", format_inr(s.avg_income), "ft-mint")
                        stat_row("Monthly expenses", format_inr(s.avg_expense), "ft-coral")
                        stat_row("Monthly investing", format_inr(s.avg_investment), "ft-sky")
                        stat_row("Surplus after investing", format_inr(s.monthly_surplus))
                        stat_row("Savings rate", f"{s.savings_rate:.1f}%")
                        stat_row("Tracked cash", format_inr(s.current_balance))
                        stat_row("Total invested", format_inr(s.total_invested))
                        stat_row("Health indicator", f"{s.health_score}/100" if s.health_score is not None else "—")
                    missing = []
                    if s.emergency_fund is None:
                        missing.append("emergency fund")
                    if s.monthly_debt is None:
                        missing.append("loan EMIs")
                    if not s.goals:
                        missing.append("goals")
                    if missing:
                        with ui.row().classes("w-full items-center gap-2 no-wrap"):
                            ui.icon("info", size="16px").classes("ft-amber")
                            ui.label(f"Not provided yet: {', '.join(missing)}. Answers say when this matters.").classes(
                                "text-xs ft-muted")
                            ui.button("Add", on_click=lambda: ui.navigate.to("/settings")).props(
                                "flat dense no-caps size=sm").classes("ft-mint ml-auto")

                sim = {"income": 0, "expense": 0, "invest": 0, "months": 12}
                with panel("Scenario simulator", "Your twin's net worth (cash + investments) under your changes"):
                    with ui.element("div").classes("grid sm:grid-cols-2 gap-x-6 gap-y-2 w-full"):
                        def slider(label: str, key: str, minimum: float, maximum: float, step: float, fmt) -> None:
                            with ui.column().classes("gap-0 w-full"):
                                with ui.row().classes("w-full justify-between"):
                                    ui.label(label).classes("text-xs ft-muted")
                                    value_label = ui.label(fmt(sim[key])).classes("text-xs font-semibold ft-num")
                                ui.slider(min=minimum, max=maximum, step=step, value=sim[key],
                                          on_change=lambda e: (sim.update({key: e.value}),
                                                               value_label.set_text(fmt(e.value)),
                                                               result.refresh())).props("color=secondary")

                        slider("Income change", "income", -50, 100, 5, lambda v: f"{v:+.0f}%")
                        slider("Monthly expense change", "expense", -30000, 50000, 1000,
                               lambda v: ("+" if v > 0 else "") + format_inr(v))
                        slider("Extra monthly investment", "invest", 0, 50000, 1000, lambda v: format_inr(v))
                        slider("Horizon", "months", 3, 60, 3, lambda v: f"{int(v)} months")

                    @ui.refreshable
                    def result() -> None:
                        months = int(sim["months"])
                        base = twin.simulate(months)
                        scen = twin.simulate(months, income_change_pct=sim["income"],
                                             expense_change_abs=sim["expense"],
                                             extra_monthly_investment=sim["invest"])
                        diff = scen["final_net_worth"] - base["final_net_worth"]
                        with ui.element("div").classes("grid grid-cols-3 gap-2 w-full"):
                            for label, value, cls in [
                                ("Net worth, current path", format_inr_compact(base["final_net_worth"]), ""),
                                ("Net worth, scenario", format_inr_compact(scen["final_net_worth"]), "ft-iris"),
                                ("Difference", ("+" if diff >= 0 else "") + format_inr_compact(diff),
                                 "ft-mint" if diff >= 0 else "ft-coral"),
                            ]:
                                with ui.column().classes("ft-tile p-3 gap-0"):
                                    ui.label(label).classes("text-[11px] ft-muted")
                                    ui.label(value).classes(f"ft-num text-lg font-bold {cls}")
                        charts.render(charts.scenario_chart(base, scen, 260))
                        if scen["monthly_surplus"] < 0:
                            with ui.row().classes("w-full items-center gap-2 p-3 rounded-xl ft-chip-coral no-wrap").style(
                                    "border:1px solid"):
                                ui.icon("warning_amber", size="18px")
                                ui.label(f"Monthly surplus turns negative ({format_inr(scen['monthly_surplus'])}). "
                                         "Cash would shrink each month.").classes("text-sm")
                        else:
                            ui.label(f"Scenario savings rate {scen['savings_rate']:.1f}% · monthly surplus "
                                     f"{format_inr(scen['monthly_surplus'])}").classes("text-xs ft-muted")

                    result()
                assumptions_box([
                    "Starts from your recent monthly averages and current tracked cash.",
                    f"Investments compound at {s.expected_return:.0f}% a year (change this in Settings).",
                    "Changes apply from next month and stay constant. Real life is lumpier.",
                ])

            copilot_chat(user.id)
    return None
