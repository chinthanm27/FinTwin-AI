"""Reusable building blocks: page headers, KPI tiles, panels, empty and error states."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from nicegui import ui

from app.styles.theme import TONE_COLORS


def page_header(title: str, subtitle: str = "", actions: Callable[[], None] | None = None) -> None:
    with ui.row().classes("w-full items-end justify-between gap-4 wrap"):
        with ui.column().classes("gap-1"):
            ui.label(title).classes("ft-display text-2xl sm:text-3xl font-bold")
            if subtitle:
                ui.label(subtitle).classes("ft-muted text-sm max-w-2xl")
        if actions:
            with ui.row().classes("items-center gap-2 wrap"):
                actions()


@contextmanager
def panel(title: str | None = None, subtitle: str | None = None, classes: str = "",
          right: Callable[[], None] | None = None) -> Iterator[ui.column]:
    """A titled surface. Yields the inner column."""
    with ui.column().classes(f"ft-panel p-5 gap-4 w-full {classes}") as col:
        if title or right:
            with ui.row().classes("w-full items-start justify-between gap-2 no-wrap"):
                with ui.column().classes("gap-0 min-w-0"):
                    if title:
                        ui.label(title).classes("ft-display text-base font-semibold")
                    if subtitle:
                        ui.label(subtitle).classes("ft-muted text-xs")
                if right:
                    with ui.row().classes("items-center gap-2 shrink-0"):
                        right()
        yield col


def kpi_card(label: str, value: str, icon: str, color: str, caption: str = "", caption_tone: str = "muted") -> None:
    with ui.column().classes("ft-tile p-4 gap-2 w-full min-w-0"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(label).classes("ft-kpi-label")
            with ui.element("div").classes("rounded-lg p-1.5").style(f"background:{color}1F"):
                ui.icon(icon, size="18px").style(f"color:{color}")
        ui.label(value).classes("ft-kpi-value truncate")
        if caption:
            tone_class = {"positive": "ft-mint", "negative": "ft-coral", "warning": "ft-amber"}.get(caption_tone, "ft-muted")
            ui.label(caption).classes(f"text-xs {tone_class}")


def chip(text: str, tone: str = "") -> ui.label:
    return ui.label(text).classes(f"ft-chip {('ft-chip-' + tone) if tone else ''}")


def progress_bar(percent: float, color: str) -> None:
    width = max(0.0, min(100.0, percent))
    with ui.element("div").classes("ft-bar"):
        ui.element("div").style(f"width:{width:.1f}%; background:{color}")


def insight_item(insight: dict[str, str]) -> None:
    color = TONE_COLORS.get(insight.get("tone", "info"), TONE_COLORS["info"])
    with ui.row().classes("w-full gap-3 no-wrap items-start py-1"):
        with ui.element("div").classes("rounded-xl p-2 shrink-0").style(f"background:{color}1A"):
            ui.icon(insight.get("icon", "lightbulb"), size="18px").style(f"color:{color}")
        with ui.column().classes("gap-0 min-w-0"):
            ui.label(insight["title"]).classes("text-sm font-semibold")
            ui.label(insight["text"]).classes("text-xs ft-muted")


def empty_state(title: str, text: str, icon: str = "inbox",
                actions: Callable[[], None] | None = None) -> None:
    with ui.column().classes("w-full items-center text-center gap-3 py-10 px-4"):
        with ui.element("div").classes("rounded-2xl p-4").style("background:rgba(139,124,255,.1)"):
            ui.icon(icon, size="32px").classes("ft-iris")
        ui.label(title).classes("ft-display text-lg font-semibold")
        ui.label(text).classes("ft-muted text-sm max-w-md")
        if actions:
            with ui.row().classes("gap-2 justify-center wrap mt-1"):
                actions()


def error_state(message: str, detail: str = "") -> None:
    with ui.column().classes("ft-panel w-full items-center text-center gap-3 py-12 px-6"):
        with ui.element("div").classes("rounded-2xl p-4").style("background:rgba(255,107,129,.1)"):
            ui.icon("cloud_off", size="34px").classes("ft-coral")
        ui.label("This page couldn't load").classes("ft-display text-lg font-semibold")
        ui.label(message).classes("text-sm max-w-lg")
        if detail:
            ui.label(detail).classes("ft-muted text-xs max-w-lg")
        ui.button("Try again", icon="refresh", on_click=lambda: ui.navigate.reload()).classes("ft-btn-ghost mt-2").props("color=none text-color=none")


def stat_row(label: str, value: str, value_class: str = "") -> None:
    with ui.row().classes("w-full justify-between items-center no-wrap gap-3 py-1"):
        ui.label(label).classes("text-sm ft-muted")
        ui.label(value).classes(f"text-sm font-semibold ft-num text-right {value_class}")


def assumptions_box(items: list[str], title: str = "Assumptions") -> None:
    with ui.column().classes("ft-tile p-4 gap-1 w-full"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("info", size="16px").classes("ft-iris")
            ui.label(title).classes("text-sm font-semibold")
        for item in items:
            ui.label(f"• {item}").classes("text-xs ft-muted")
