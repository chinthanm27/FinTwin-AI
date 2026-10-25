"""Landing sections: how it works, AI features, call to action, footer."""

from __future__ import annotations

from nicegui import ui

STEPS = [
    ("Create an account", "Your data is stored in your own MongoDB and isolated to your login."),
    ("Bring in transactions", "Add them by hand, upload a CSV or PDF statement, or start with demo data."),
    ("Read your analysis", "Dashboard, budgets, health score, forecasts and anomaly flags update instantly."),
    ("Ask your twin", "Run what-if scenarios in plain English and get answers built on your numbers."),
]

MODELS = [
    ("insights", "Spending prediction", "Random Forest and Gradient Boosting compete against simple baselines on "
     "held-out months. The winner is used only if it's actually more accurate."),
    ("policy", "Anomaly detection", "Isolation Forest, fitted per user on amount, category, frequency and timing, "
     "with plain-language reasons for every flag."),
    ("query_stats", "Cash-flow forecast", "A linear trend blended with a 3-month moving average, robust to one-off "
     "spikes, with an 80% range."),
    ("auto_awesome", "Financial Twin + Copilot", "A deterministic scenario engine on your data. Connect Gemini to "
     "make it conversational. It is only allowed to use your numbers."),
]


def how_it_works() -> None:
    with ui.element("section").classes("w-full px-4 sm:px-8 py-20").props("id=how"):
        with ui.column().classes("max-w-[1200px] mx-auto gap-10"):
            ui.html("<h2 style='font-size:clamp(1.8rem,3.4vw,2.6rem);line-height:1.1;margin:0;font-weight:700'>"
                    "From first transaction to first answer in four steps.</h2>", sanitize=False)
            with ui.element("div").classes("grid gap-4 sm:grid-cols-2 lg:grid-cols-4 w-full"):
                for i, (title, text) in enumerate(STEPS, start=1):
                    with ui.column().classes("gap-3 pt-5 border-t-2").style(
                        f"border-color:{'var(--mint)' if i == 1 else 'var(--line-strong)'}"
                    ):
                        ui.label(f"Step {i}").classes("text-sm font-semibold ft-mint")
                        ui.label(title).classes("ft-display text-lg font-semibold")
                        ui.label(text).classes("text-sm ft-muted")


def ai_features() -> None:
    with ui.element("section").classes("w-full px-4 sm:px-8 py-20").props("id=ai"):
        with ui.element("div").classes("max-w-[1200px] mx-auto grid gap-10 lg:grid-cols-2 items-start"):
            with ui.column().classes("gap-6"):
                ui.html("<h2 style='font-size:clamp(1.8rem,3.4vw,2.6rem);line-height:1.1;margin:0;font-weight:700'>"
                        "Machine learning that shows its working.</h2>", sanitize=False)
                ui.label("Every model reports how it was evaluated and what it assumed. Predictions are labelled "
                         "as estimates; anomaly flags are prompts to review, never accusations.").classes("ft-muted")
                with ui.column().classes("gap-4 w-full"):
                    for icon, title, text in MODELS:
                        with ui.row().classes("gap-4 no-wrap items-start"):
                            with ui.element("div").classes("rounded-xl p-2 shrink-0").style("background:rgba(139,124,255,.12)"):
                                ui.icon(icon, size="20px").classes("ft-iris")
                            with ui.column().classes("gap-0.5"):
                                ui.label(title).classes("font-semibold")
                                ui.label(text).classes("text-sm ft-muted")
            with ui.column().classes("ft-glass p-5 gap-4 w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("auto_awesome", size="18px").classes("ft-iris")
                    ui.label("FinTwin AI Copilot").classes("text-sm font-semibold")
                    ui.label("Demo conversation").classes("ft-chip ml-auto")
                with ui.row().classes("w-full justify-end"):
                    ui.label("What happens if my expenses increase by ₹10,000?").classes(
                        "text-sm px-4 py-2.5 rounded-2xl rounded-br-md max-w-[85%]"
                    ).style("background:rgba(62,230,176,.14); border:1px solid rgba(62,230,176,.3)")
                with ui.column().classes("ft-tile p-4 gap-2 max-w-[92%]"):
                    ui.label("Expenses would rise from ₹63,200 to ₹73,200 a month.").classes("text-sm font-semibold")
                    ui.label("Your savings rate drops from 31% to 20%, and the monthly surplus after investing "
                             "becomes ₹1,600. Over 12 months that's about ₹1.2L less net worth.").classes("text-sm ft-muted")
                    ui.label("Assumes income stays at your 6-month average. Missing: loan EMIs.").classes("text-xs ft-faint")
                with ui.row().classes("w-full justify-end"):
                    ui.label("Where am I spending the most?").classes(
                        "text-sm px-4 py-2.5 rounded-2xl rounded-br-md"
                    ).style("background:rgba(62,230,176,.14); border:1px solid rgba(62,230,176,.3)")
                with ui.column().classes("ft-tile p-4 gap-1 max-w-[92%]"):
                    ui.label("Rent ₹22,000 · Food ₹11,900 · Shopping ₹8,300 a month on average.").classes("text-sm")
                    ui.label("Cutting Food by 10% frees about ₹14,300 a year.").classes("text-sm ft-muted")


def call_to_action() -> None:
    with ui.element("section").classes("w-full px-4 sm:px-8 py-20"):
        with ui.column().classes("max-w-[1200px] mx-auto ft-glass p-8 sm:p-12 gap-5 items-start").style(
            "background:linear-gradient(120deg, rgba(62,230,176,.12), rgba(139,124,255,.14))"
        ):
            ui.html("<h2 style='font-size:clamp(1.8rem,3.6vw,2.8rem);line-height:1.08;margin:0;font-weight:800'>"
                    "Meet your financial twin.</h2>", sanitize=False)
            ui.label("Create an account, load demo data, and ask your first what-if in under a minute.").classes(
                "ft-muted text-lg max-w-xl"
            )
            with ui.row().classes("gap-3 wrap"):
                ui.button("Create free account", on_click=lambda: ui.navigate.to("/register")).classes(
                    "ft-btn-primary text-base px-6 py-2.5"
                ).props("color=none text-color=none")
                ui.button("Log in", on_click=lambda: ui.navigate.to("/login")).classes("ft-btn-ghost text-base").props("color=none text-color=none")


def footer() -> None:
    with ui.element("footer").classes("w-full px-4 sm:px-8 py-10 border-t").style("border-color:var(--line)"):
        with ui.row().classes("max-w-[1200px] mx-auto w-full justify-between items-start gap-6 wrap"):
            with ui.column().classes("gap-2 max-w-sm"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("💰")
                    ui.label("FinTwin AI").classes("ft-display font-bold")
                ui.label("An educational, portfolio-grade personal finance analysis app built with Python, NiceGUI, "
                         "MongoDB and scikit-learn.").classes("text-sm ft-muted")
            with ui.column().classes("gap-1"):
                ui.label("Product").classes("text-sm font-semibold")
                for label, href in [("Features", "#features"), ("How it works", "#how"), ("AI models", "#ai")]:
                    ui.link(label, href).classes("text-sm ft-muted no-underline hover:text-white")
            with ui.column().classes("gap-1"):
                ui.label("Account").classes("text-sm font-semibold")
                for label, href in [("Create account", "/register"), ("Log in", "/login")]:
                    ui.link(label, href).classes("text-sm ft-muted no-underline hover:text-white")
        ui.label("Projections, scores and anomaly flags are estimates for education and analysis. "
                 "They are not financial advice.").classes("max-w-[1200px] mx-auto block text-xs ft-faint mt-8")
