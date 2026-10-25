"""Fraud / anomaly detection: /fraud"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.auth.session import current_user, login_redirect
from app.components.app_shell import app_shell, notify_error
from app.components.dashboard_cards import empty_state, kpi_card, page_header, panel
from app.services import fraud_service
from app.services.transaction_service import transactions_dataframe
from app.styles.theme import COLORS
from app.utils.formatters import format_date, format_inr

LABEL_TONES = {"High Anomaly Risk": "coral", "Potentially Unusual": "amber", "Normal": "mint"}


@ui.page("/fraud", title="Fraud Detection · FinTwin AI")
def fraud_page():
    user = current_user()
    if user is None:
        return login_redirect("/fraud")
    view = {"status": "open"}

    with app_shell(user, "fraud"):
        page_header(
            "Fraud detection",
            "Transactions that look unusual compared with your own history. A flag is a prompt to check, "
            "not proof of fraud.",
            lambda: ui.button("Scan again", icon="radar", on_click=lambda: body.refresh()).classes("ft-btn-primary").props("color=none text-color=none"),
        )

        def set_status(alert: dict[str, Any], status: str) -> None:
            try:
                fraud_service.set_status(user.id, alert["id"], status)
                ui.notify({"dismissed": "Marked as expected", "reviewed": "Marked as reviewed",
                           "open": "Reopened"}[status], type="positive")
            except Exception as exc:
                notify_error(exc)
            alerts_list.refresh()

        @ui.refreshable
        def alerts_list() -> None:
            alerts = fraud_service.get_alerts(user.id, None if view["status"] == "all" else view["status"])
            if not alerts:
                with panel():
                    messages = {
                        "open": ("Nothing to review", "No open flags. New unusual transactions will appear here."),
                        "reviewed": ("No reviewed flags", "Flags you mark as reviewed are kept here."),
                        "dismissed": ("No dismissed flags", "Flags you mark as expected are kept here."),
                        "all": ("No flags", "Nothing has been flagged yet."),
                    }
                    empty_state(*messages[view["status"]], "verified_user")
                return
            with ui.column().classes("w-full gap-3"):
                for alert in alerts:
                    tone = LABEL_TONES.get(alert.get("label"), "amber")
                    with ui.column().classes("ft-panel p-4 sm:p-5 gap-3 w-full"):
                        with ui.row().classes("w-full items-start justify-between gap-3 no-wrap"):
                            with ui.row().classes("items-start gap-3 no-wrap min-w-0"):
                                with ui.element("div").classes("rounded-xl p-2 shrink-0").style(
                                        f"background:{COLORS[tone]}1A"):
                                    ui.icon("policy", size="20px").style(f"color:{COLORS[tone]}")
                                with ui.column().classes("gap-0.5 min-w-0"):
                                    ui.label(alert.get("description") or alert.get("category")).classes(
                                        "font-semibold break-words")
                                    ui.label(f"{alert.get('category')} · {format_date(alert.get('date'))}").classes(
                                        "text-xs ft-muted")
                            with ui.column().classes("items-end gap-1 shrink-0"):
                                ui.label(format_inr(alert.get("amount"))).classes("ft-num text-lg font-bold")
                                ui.label(alert.get("label", "")).classes(f"ft-chip ft-chip-{tone}")
                        with ui.column().classes("gap-1 pl-0 sm:pl-12"):
                            for reason in alert.get("reasons", []):
                                with ui.row().classes("gap-2 no-wrap items-start"):
                                    ui.icon("arrow_right", size="18px").classes("ft-faint")
                                    ui.label(reason).classes("text-sm ft-muted")
                            ui.label(f"More unusual than {min(float(alert.get('score', 0)), 99.9):.1f}% of your outgoing "
                                     f"transactions").classes("text-xs ft-faint")
                        with ui.row().classes("w-full justify-end gap-2 wrap"):
                            status = alert.get("status", "open")
                            if status != "dismissed":
                                ui.button("Looks fine", icon="check", on_click=lambda a=alert: set_status(a, "dismissed")
                                          ).classes("ft-btn-ghost").props("color=none text-color=none").props("dense")
                            if status != "reviewed":
                                ui.button("Mark reviewed", icon="flag",
                                          on_click=lambda a=alert: set_status(a, "reviewed")).classes("ft-btn-ghost").props("color=none text-color=none").props("dense")
                            if status != "open":
                                ui.button("Reopen", icon="undo", on_click=lambda a=alert: set_status(a, "open")).props(
                                    "flat dense no-caps").classes("ft-muted")

        @ui.refreshable
        def body() -> None:
            df = transactions_dataframe(user.id)
            if df.empty:
                with panel():
                    empty_state("No transactions to scan", "Add transactions or load demo data first.", "policy",
                                lambda: ui.button("Go to transactions", on_click=lambda: ui.navigate.to("/transactions")
                                                  ).classes("ft-btn-primary").props("color=none text-color=none"))
                return
            report = fraud_service.scan_user(user.id, df)
            high = sum(1 for r in report.results if r.label == "High Anomaly Risk")
            with ui.element("div").classes("grid gap-3 grid-cols-2 lg:grid-cols-4 w-full"):
                kpi_card("Transactions analysed", str(report.analyzed), "manage_search", COLORS["sky"], "Outgoing only")
                kpi_card("Flagged", str(report.flagged), "flag", COLORS["amber"],
                         f"{report.flagged / report.analyzed * 100:.1f}% of analysed" if report.analyzed else "")
                kpi_card("High anomaly risk", str(high), "priority_high", COLORS["coral"])
                kpi_card("Open to review", str(fraud_service.open_alert_count(user.id)), "inbox", COLORS["iris"])
            with ui.row().classes("ft-tile p-3 px-4 gap-3 no-wrap items-start w-full"):
                ui.icon("model_training", size="20px").classes("ft-iris mt-0.5")
                ui.label(f"Method: {report.method}. The model learns what's normal for you (amounts per merchant and "
                         "category, frequency, timing, share of monthly spend) and scores how different each "
                         "transaction is. Recurring payments like rent stay normal.").classes("text-sm ft-muted")
            ui.toggle({"open": "Open", "reviewed": "Reviewed", "dismissed": "Looks fine", "all": "All"},
                      value=view["status"],
                      on_change=lambda e: (view.update(status=e.value), alerts_list.refresh())).props(
                "no-caps unelevated rounded toggle-color=primary toggle-text-color=dark").classes("ft-tile")
            alerts_list()

        body()
    return None
