"""Landing statistics strip: concrete facts about what the product does."""

from __future__ import annotations

from nicegui import ui

FACTS = [
    ("7", "factors behind a health score you can audit"),
    ("3", "machine-learning models trained on your history"),
    ("CSV + PDF", "bank statements parsed and auto-categorised"),
    ("0", "bank passwords asked for, ever"),
]


def stats_strip() -> None:
    with ui.element("section").classes("w-full px-4 sm:px-8 pb-6"):
        with ui.element("div").classes(
            "max-w-[1200px] mx-auto grid grid-cols-2 lg:grid-cols-4 border-y"
        ).style("border-color:var(--line)"):
            for i, (value, label) in enumerate(FACTS):
                border = "lg:border-l" if i else ""
                with ui.column().classes(f"gap-1 py-6 px-5 {border}").style("border-color:var(--line)"):
                    ui.label(value).classes("ft-num text-3xl font-bold")
                    ui.label(label).classes("text-sm ft-muted")
