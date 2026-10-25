"""Landing feature grid (bento layout: the twin gets the large tile)."""

from __future__ import annotations

from nicegui import ui

FEATURES = [
    ("account_balance_wallet", "#F6B94C", "Budgets that warn you early",
     "Set monthly limits per category. You're alerted at 80% used, not after the money is gone."),
    ("monitor_heart", "#8B7CFF", "A health score you can read",
     "Seven weighted factors, each with its own rule and tip. No black box, no false precision."),
    ("policy", "#FF6B81", "Unusual spending, flagged",
     "An Isolation Forest learns your normal pattern and highlights what doesn't fit, with reasons."),
    ("query_stats", "#4CC2FF", "Forecasts with honest ranges",
     "Cash flow, spending and long-term wealth projections, always shown with assumptions."),
    ("upload_file", "#3EE6B0", "Statements in, transactions out",
     "Upload a CSV or PDF statement. Duplicates are detected and merchants are categorised."),
]

SCENARIOS = [
    "Can I afford a ₹15 lakh car next year?",
    "What if my salary rises 20%?",
    "What if expenses go up by ₹10,000?",
    "How much should I invest for ₹50 lakh in 10 years?",
]


def feature_grid() -> None:
    with ui.element("section").classes("w-full px-4 sm:px-8 py-20").props("id=features"):
        with ui.column().classes("max-w-[1200px] mx-auto gap-10"):
            with ui.column().classes("gap-3 max-w-2xl"):
                ui.html("<h2 style='font-size:clamp(1.8rem,3.4vw,2.6rem);line-height:1.1;margin:0;font-weight:700'>"
                        "Everything a careful spreadsheet would do, and the questions it can't answer.</h2>",
                        sanitize=False)
                ui.label("Built around one idea: your past transactions are the best model of your future ones.").classes(
                    "ft-muted text-base"
                )
            with ui.element("div").classes("grid gap-4 md:grid-cols-2 lg:grid-cols-3 w-full"):
                # Large twin tile
                with ui.column().classes("ft-glass p-6 gap-4 md:col-span-2 lg:row-span-2"):
                    with ui.row().classes("items-center gap-3"):
                        with ui.element("div").classes("rounded-xl p-2.5").style("background:rgba(139,124,255,.14)"):
                            ui.icon("auto_awesome", size="24px").classes("ft-iris")
                        ui.label("The AI Financial Twin").classes("ft-display text-xl font-semibold")
                    ui.label(
                        "A model of your finances built from your real income, spending, investments and goals. "
                        "Ask it a question in plain English and it runs the scenario on your numbers, says what "
                        "it assumed, and tells you when data is missing instead of guessing."
                    ).classes("ft-muted max-w-xl")
                    with ui.column().classes("gap-2 w-full mt-2"):
                        for q in SCENARIOS:
                            with ui.row().classes("ft-tile px-4 py-3 w-full items-center gap-3 no-wrap"):
                                ui.icon("chat_bubble_outline", size="18px").classes("ft-iris")
                                ui.label(q).classes("text-sm")
                for icon, color, title, text in FEATURES:
                    with ui.column().classes("ft-panel p-5 gap-3"):
                        with ui.element("div").classes("rounded-xl p-2 self-start").style(f"background:{color}1F"):
                            ui.icon(icon, size="22px").style(f"color:{color}")
                        ui.label(title).classes("ft-display text-base font-semibold")
                        ui.label(text).classes("text-sm ft-muted")
