"""Header notification bell with budget and anomaly alerts."""

from __future__ import annotations

from nicegui import ui

from app.services.insight_service import notifications
from app.styles.theme import TONE_COLORS


def notification_bell(user_id: str) -> None:
    items = notifications(user_id)
    actionable = [i for i in items if i["level"] != "info"]
    with ui.button(icon="notifications_none").props("flat round dense").classes("text-white") as button:
        button.props('aria-label="Notifications"')
        if actionable:
            ui.badge(str(len(actionable)), color="negative").props("floating rounded")
        with ui.menu().classes("w-80 max-w-[90vw]"):
            with ui.column().classes("p-3 gap-2 w-full"):
                ui.label("Notifications").classes("ft-display text-sm font-semibold px-1")
                if not items:
                    ui.label("You're all caught up.").classes("text-sm ft-muted px-1 py-2")
                for item in items:
                    color = TONE_COLORS.get(
                        {"negative": "negative", "warning": "warning"}.get(item["level"], "info"), TONE_COLORS["info"]
                    )
                    with ui.link(target=item.get("link", "/dashboard")).classes(
                        "no-underline w-full rounded-xl p-2 hover:bg-white/5"
                    ).style("color:inherit"):
                        with ui.row().classes("gap-3 no-wrap items-start"):
                            ui.icon(item.get("icon", "info"), size="18px").style(f"color:{color}")
                            with ui.column().classes("gap-0"):
                                ui.label(item["title"]).classes("text-sm font-semibold")
                                ui.label(item["text"]).classes("text-xs ft-muted")
