"""Financial reports: /reports"""

from __future__ import annotations

from nicegui import ui

from app.auth.session import current_user, login_redirect
from app.components.app_shell import app_shell, notify_error
from app.components.dashboard_cards import empty_state, kpi_card, page_header, panel, progress_bar, stat_row
from app.database import insight_repository
from app.services import report_service, transaction_service
from app.services.analytics_service import PERIODS, filter_period
from app.styles.theme import COLORS
from app.utils.formatters import format_inr, format_inr_compact, month_label

STATUS_COLORS = {"ok": COLORS["mint"], "warning": COLORS["amber"], "exceeded": COLORS["coral"]}


@ui.page("/reports", title="Reports · FinTwin AI")
def reports_page():
    user = current_user()
    if user is None:
        return login_redirect("/reports")
    state = {"period": "3M"}

    with app_shell(user, "reports"):
        def export_html() -> None:
            try:
                report = report_service.build_report(user.id, user.full_name, state["period"])
                ui.download.content(report_service.render_html(report).encode("utf-8"),
                                    transaction_service.export_filename(f"report_{state['period']}", "html"), "text/html")
                ui.notify("Report downloaded. Open it in a browser and print to save as PDF.", type="positive")
            except Exception as exc:
                notify_error(exc)

        def export_csv() -> None:
            try:
                items = transaction_service.list_transactions(user.id)
                df = transaction_service.transactions_dataframe(user.id)
                keep = set(filter_period(df, state["period"])["id"]) if not df.empty else set()
                data = transaction_service.export_csv([t for t in items if t.id in keep])
                ui.download.content(data, transaction_service.export_filename(f"transactions_{state['period']}", "csv"),
                                    "text/csv")
            except Exception as exc:
                notify_error(exc)

        def actions() -> None:
            ui.select(PERIODS, value=state["period"], label="Period",
                      on_change=lambda e: (state.update(period=e.value), body.refresh())).props(
                "outlined dark dense").classes("w-44")
            ui.button("Export CSV", icon="table_view", on_click=export_csv).classes("ft-btn-ghost").props("color=none text-color=none")
            ui.button("Download report", icon="download", on_click=export_html).classes("ft-btn-primary").props("color=none text-color=none")

        page_header("Reports", "A complete financial summary you can download, print or share.", actions)

        @ui.refreshable
        def body() -> None:
            report = report_service.build_report(user.id, user.full_name, state["period"])
            if not report.has_data:
                with panel():
                    empty_state("Nothing to report yet", "Add transactions to generate your first report.", "description")
                return
            s = report.summary
            with panel(f"Financial summary · {report.period_label}", f"Generated {report.generated_at}"):
                with ui.element("div").classes("grid gap-3 grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 w-full"):
                    kpi_card("Income", format_inr_compact(s["income"]), "south_west", COLORS["mint"])
                    kpi_card("Expenses", format_inr_compact(s["expenses"]), "north_east", COLORS["coral"])
                    kpi_card("Savings", format_inr_compact(s["savings"]), "savings", COLORS["mint"])
                    kpi_card("Savings rate", f"{s['savings_rate']:.1f}%", "percent", COLORS["iris"])
                    kpi_card("Investments", format_inr_compact(s["investments"]), "trending_up", COLORS["sky"])
                    kpi_card("Health", f"{report.health['score']}/100" if report.health["score"] is not None else "—",
                             "monitor_heart", COLORS["iris"], report.health["band"])

            with ui.element("div").classes("grid gap-4 lg:grid-cols-2 w-full"):
                with panel("Top expense categories"):
                    for c in report.top_categories:
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("w-full justify-between no-wrap"):
                                ui.label(c["category"]).classes("text-sm")
                                ui.label(f"{format_inr(c['amount'])} · {c['share']:.0f}%").classes("text-sm ft-num ft-muted")
                            progress_bar(c["share"], COLORS["iris"])
                with panel("Monthly breakdown"):
                    for m in report.monthly:
                        with ui.row().classes("w-full justify-between no-wrap py-1 border-b").style("border-color:var(--line)"):
                            ui.label(month_label(m["month"])).classes("text-sm font-semibold w-16")
                            ui.label(f"+{format_inr_compact(m['income'])}").classes("text-xs ft-mint ft-num")
                            ui.label(f"−{format_inr_compact(m['expense'])}").classes("text-xs ft-coral ft-num")
                            ui.label(format_inr_compact(m["savings"])).classes("text-sm ft-num font-semibold")

            with ui.element("div").classes("grid gap-4 lg:grid-cols-2 w-full"):
                with panel("Budget performance", "This month"):
                    if not report.budgets:
                        ui.label("No budgets set.").classes("text-sm ft-muted")
                    for b in report.budgets:
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("w-full justify-between no-wrap"):
                                ui.label(b["category"]).classes("text-sm")
                                ui.label(f"{format_inr(b['spent'])} / {format_inr(b['budget'])}").classes(
                                    "text-xs ft-num ft-muted")
                            progress_bar(b["percent"], STATUS_COLORS[b["status"]])
                with panel("Financial health factors"):
                    for f in report.health["factors"]:
                        stat_row(f"{f['name']} · {f['value']}", f"{f['score']}/100")

            with ui.element("div").classes("grid gap-4 lg:grid-cols-2 w-full"):
                with panel("Potential anomalies", "Statistical flags, not proof of fraud"):
                    if not report.anomalies:
                        ui.label("No unusual transactions flagged.").classes("text-sm ft-muted")
                    for a in report.anomalies[:6]:
                        with ui.row().classes("w-full justify-between no-wrap py-1 gap-3"):
                            with ui.column().classes("gap-0 min-w-0"):
                                ui.label(a["description"]).classes("text-sm truncate")
                                ui.label(f"{a['date']} · {a['label']}").classes("text-xs ft-muted")
                            ui.label(format_inr(a["amount"])).classes("text-sm ft-num font-semibold shrink-0")
                with panel("Forecast", report.forecast["method"] if report.forecast else "Not enough history"):
                    if report.forecast:
                        f = report.forecast
                        for m, inc, exp, bal in zip(f["months"], f["income"], f["expense"], f["balance"]):
                            with ui.row().classes("w-full justify-between no-wrap py-1"):
                                ui.label(month_label(m)).classes("text-sm font-semibold w-16")
                                ui.label(f"+{format_inr_compact(inc)}").classes("text-xs ft-mint ft-num")
                                ui.label(f"−{format_inr_compact(exp)}").classes("text-xs ft-coral ft-num")
                                ui.label(f"Cash {format_inr_compact(bal)}").classes("text-sm ft-num")

            with panel("AI recommendations", "Potential actions based on your weakest factors and recent alerts"):
                for r in report.recommendations:
                    with ui.row().classes("gap-3 no-wrap items-start"):
                        ui.icon("auto_awesome", size="18px").classes("ft-iris mt-0.5")
                        ui.label(r).classes("text-sm")

            history = insight_repository.get_report_records(user.id, 6)
            if history:
                with panel("Recently generated"):
                    for h in history:
                        with ui.row().classes("w-full justify-between no-wrap py-1"):
                            ui.label(f"{PERIODS.get(h['period'], h['period'])} · {h['created_at'].strftime('%d %b %Y, %H:%M')} UTC"
                                     ).classes("text-sm ft-muted")
                            ui.label(f"Savings {format_inr_compact(h['summary'].get('savings', 0))}").classes(
                                "text-sm ft-num")

        body()
    return None
