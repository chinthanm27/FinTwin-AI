"""Settings: /settings (profile, financial details, goals, security, data)"""

from __future__ import annotations

from nicegui import run, ui

from app.ai.llm_provider import provider_status
from app.auth.session import current_user, end_session, login_redirect, update_session_name
from app.components.app_shell import app_shell, notify_error
from app.components.dashboard_cards import page_header, panel, stat_row
from app.components.onboarding import load_demo
from app.database import insight_repository
from app.database.mongodb import check_connection
from app.models.financial_profile import FinancialGoal
from app.services import auth_service, demo_data_service, statement_service
from app.utils.formatters import format_inr


@ui.page("/settings", title="Settings · FinTwin AI")
def settings_page():
    user = current_user()
    if user is None:
        return login_redirect("/settings")

    with app_shell(user, "settings"):
        page_header("Settings", "Your profile, the financial details your twin can't infer, and your data.")
        profile = insight_repository.get_profile(user.id)

        with ui.element("div").classes("grid gap-4 xl:grid-cols-2 w-full items-start"):
            # ---------------------------------------------------------- financial details
            with panel("Financial details", "Used by the health score and your twin. Leave blank if unknown."):
                emergency = ui.number("Emergency fund saved (₹)", value=profile.emergency_fund, min=0, step=1000).props(
                    "outlined dark clearable").classes("w-full")
                debt = ui.number("Monthly loan EMIs (₹)", value=profile.monthly_debt_payment, min=0, step=500).props(
                    "outlined dark clearable").classes("w-full")
                with ui.row().classes("w-full gap-3 no-wrap"):
                    ret = ui.number("Expected annual return (%)", value=profile.expected_annual_return, min=0, max=30,
                                    step=0.5).props("outlined dark").classes("flex-1")
                    risk = ui.select(["Conservative", "Moderate", "Aggressive"], value=profile.risk_profile,
                                     label="Risk profile").props("outlined dark").classes("flex-1")

                def save_details() -> None:
                    try:
                        profile.emergency_fund = float(emergency.value) if emergency.value not in (None, "") else None
                        profile.monthly_debt_payment = float(debt.value) if debt.value not in (None, "") else None
                        value = float(ret.value or 10)
                        if not 0 <= value <= 30:
                            ui.notify("Expected return must be between 0% and 30%.", type="negative")
                            return
                        profile.expected_annual_return = value
                        profile.risk_profile = risk.value
                        insight_repository.save_profile(profile)
                        ui.notify("Financial details saved", type="positive")
                    except Exception as exc:
                        notify_error(exc)

                ui.button("Save details", on_click=save_details).classes("ft-btn-primary self-end").props("color=none text-color=none")

            # ---------------------------------------------------------- goals
            with panel("Goals", "Your twin uses these when you ask how much to invest"):
                @ui.refreshable
                def goals_list() -> None:
                    if not profile.goals:
                        ui.label("No goals yet.").classes("text-sm ft-muted")
                    for i, g in enumerate(profile.goals):
                        with ui.row().classes("w-full items-center justify-between ft-tile px-4 py-2 no-wrap"):
                            with ui.column().classes("gap-0"):
                                ui.label(g.name).classes("text-sm font-semibold")
                                ui.label(f"{format_inr(g.target_amount)} in {g.target_years:g} years").classes(
                                    "text-xs ft-muted")
                            ui.button(icon="delete_outline", on_click=lambda idx=i: remove_goal(idx)).props(
                                'flat round dense color=negative aria-label="Remove goal"')

                def remove_goal(idx: int) -> None:
                    profile.goals.pop(idx)
                    insight_repository.save_profile(profile)
                    goals_list.refresh()

                goals_list()
                with ui.row().classes("w-full gap-2 items-start"):
                    g_name = ui.input("Goal", placeholder="e.g. House down payment").props("outlined dark dense").classes(
                        "flex-[2] min-w-[140px]")
                    g_amount = ui.number("Target (₹)", min=0, step=10000).props("outlined dark dense").classes(
                        "flex-1 min-w-[110px]")
                    g_years = ui.number("Years", min=0.5, max=50, step=0.5, value=5).props("outlined dark dense").classes(
                        "w-24")

                def add_goal() -> None:
                    try:
                        goal = FinancialGoal.create(g_name.value, g_amount.value, g_years.value)
                    except Exception as exc:
                        notify_error(exc)
                        return
                    if len(profile.goals) >= 10:
                        ui.notify("You can save up to 10 goals.", type="warning")
                        return
                    profile.goals.append(goal)
                    insight_repository.save_profile(profile)
                    g_name.value, g_amount.value = "", None
                    goals_list.refresh()
                    ui.notify("Goal added", type="positive")

                ui.button("Add goal", icon="add", on_click=add_goal).classes("ft-btn-ghost self-end").props("color=none text-color=none")

            # ---------------------------------------------------------- profile & security
            with panel("Profile & security"):
                name = ui.input("Full name", value=user.full_name).props("outlined dark").classes("w-full")
                ui.input("Email", value=user.email).props("outlined dark readonly").classes("w-full")

                def save_name() -> None:
                    try:
                        new_name = auth_service.update_name(user.id, name.value)
                        update_session_name(new_name)
                        ui.notify("Name updated", type="positive")
                    except Exception as exc:
                        notify_error(exc)

                ui.button("Save name", on_click=save_name).classes("ft-btn-ghost self-end").props("color=none text-color=none")
                ui.element("div").classes("ft-divider")
                ui.label("Change password").classes("text-sm font-semibold")
                current_pw = ui.input("Current password", password=True, password_toggle_button=True).props(
                    "outlined dark dense").classes("w-full")
                new_pw = ui.input("New password", password=True, password_toggle_button=True).props(
                    "outlined dark dense").classes("w-full")
                confirm_pw = ui.input("Confirm new password", password=True, password_toggle_button=True).props(
                    "outlined dark dense").classes("w-full")

                async def change_pw() -> None:
                    try:
                        await run.io_bound(auth_service.change_password, user.id, current_pw.value, new_pw.value,
                                           confirm_pw.value)
                    except Exception as exc:
                        notify_error(exc)
                        return
                    current_pw.value = new_pw.value = confirm_pw.value = ""
                    ui.notify("Password changed", type="positive")

                ui.button("Change password", on_click=change_pw).classes("ft-btn-ghost self-end").props("color=none text-color=none")

            # ---------------------------------------------------------- data & system
            with panel("Data & system"):
                db_ok, db_text = check_connection()
                llm_on, llm_text = provider_status()
                stat_row("Database", db_text, "ft-mint" if db_ok else "ft-coral")
                stat_row("AI Copilot", llm_text, "ft-mint" if llm_on else "ft-muted")
                ui.element("div").classes("ft-divider")
                with ui.row().classes("w-full gap-2 wrap"):
                    ui.button("Load demo data", icon="science",
                              on_click=lambda: load_demo(user.id, lambda: ui.navigate.to("/dashboard"))).classes(
                        "ft-btn-ghost").props("color=none text-color=none")

                    def remove_demo() -> None:
                        try:
                            count = demo_data_service.remove_demo_data(user.id)
                            ui.notify(f"Removed {count} demo transactions", type="positive")
                        except Exception as exc:
                            notify_error(exc)

                    ui.button("Remove demo data", icon="remove_circle_outline", on_click=remove_demo).classes(
                        "ft-btn-ghost").props("color=none text-color=none")

                    def remove_uploads() -> None:
                        try:
                            count = statement_service.delete_user_uploads(user.id)
                            ui.notify(f"Deleted {count} uploaded statement file(s)", type="positive")
                        except Exception as exc:
                            notify_error(exc)

                    ui.button("Delete uploaded files", icon="folder_delete", on_click=remove_uploads).classes(
                        "ft-btn-ghost").props("color=none text-color=none")

                ui.element("div").classes("ft-divider")
                ui.label("Delete account").classes("text-sm font-semibold ft-coral")
                ui.label("Permanently deletes your account, transactions, budgets, alerts, conversations and reports.").classes(
                    "text-xs ft-muted")

                def confirm_delete() -> None:
                    with ui.dialog() as dialog, ui.card().classes("ft-dialog p-6 gap-4 w-[420px] max-w-[95vw]"):
                        ui.label("Delete your account?").classes("ft-display text-lg font-semibold")
                        ui.label("This can't be undone. Enter your password to confirm.").classes("text-sm ft-muted")
                        pw = ui.input("Password", password=True, password_toggle_button=True).props(
                            "outlined dark").classes("w-full")

                        async def do_delete() -> None:
                            try:
                                await run.io_bound(auth_service.delete_account, user.id, pw.value)
                                statement_service.delete_user_uploads(user.id)
                            except Exception as exc:
                                notify_error(exc)
                                return
                            end_session()
                            ui.navigate.to("/")

                        with ui.row().classes("w-full justify-end gap-2"):
                            ui.button("Cancel", on_click=dialog.close).classes("ft-btn-ghost").props("color=none text-color=none")
                            ui.button("Delete account", icon="delete_forever", on_click=do_delete).classes(
                                "ft-btn-danger").props("color=none text-color=none")
                    dialog.open()

                ui.button("Delete account", icon="delete_forever", on_click=confirm_delete).classes("ft-btn-danger self-start").props("color=none text-color=none")
    return None
