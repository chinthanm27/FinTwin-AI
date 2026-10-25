"""FinTwin AI Copilot chat component."""

from __future__ import annotations

from nicegui import run, ui

from app.ai import copilot
from app.ai.llm_provider import provider_status
from app.components.app_shell import notify_error
from app.database import insight_repository


def _user_bubble(text: str) -> None:
    with ui.row().classes("w-full justify-end"):
        ui.label(text).classes("text-sm px-4 py-2.5 rounded-2xl rounded-br-md max-w-[85%] break-words").style(
            "background:rgba(62,230,176,.14); border:1px solid rgba(62,230,176,.3)"
        )


def _assistant_bubble(markdown: str, source: str = "") -> None:
    with ui.row().classes("w-full no-wrap gap-2 items-start"):
        with ui.element("div").classes("rounded-full p-1.5 shrink-0 mt-1").style("background:rgba(139,124,255,.16)"):
            ui.icon("auto_awesome", size="16px").classes("ft-iris")
        with ui.column().classes("ft-tile px-4 py-3 gap-1 max-w-[92%] min-w-0 overflow-x-auto"):
            ui.markdown(markdown).classes("text-sm")
            if source:
                ui.label(f"Answered by {source}").classes("text-[11px] ft-faint")


def copilot_chat(user_id: str, height: str = "560px") -> None:
    llm_on, llm_text = provider_status()
    with ui.column().classes("ft-panel w-full p-0 gap-0 overflow-hidden"):
        with ui.row().classes("w-full items-center justify-between px-5 py-4 border-b no-wrap").style(
                "border-color:var(--line)"):
            with ui.row().classes("items-center gap-3 no-wrap"):
                with ui.element("div").classes("rounded-xl p-2").style("background:rgba(139,124,255,.16)"):
                    ui.icon("auto_awesome", size="20px").classes("ft-iris")
                with ui.column().classes("gap-0"):
                    ui.label("🤖 FinTwin AI Copilot").classes("ft-display font-semibold")
                    ui.label(llm_text).classes("text-[11px] " + ("ft-mint" if llm_on else "ft-muted"))
            ui.button(icon="delete_sweep", on_click=lambda: clear()).props(
                'flat round dense aria-label="Clear conversation"').tooltip("Clear conversation")

        scroll = ui.scroll_area().classes("w-full").style(f"height:{height}")
        with scroll:
            messages = ui.column().classes("w-full gap-4 p-5")

        def render_history() -> None:
            messages.clear()
            history = insight_repository.get_messages(user_id, 40)
            with messages:
                if not history:
                    _assistant_bubble(
                        "Hi! I'm your financial twin's voice. I answer using **your recorded transactions** and tell "
                        "you when something is missing. Try one of the questions below."
                    )
                for m in history:
                    if m["role"] == "user":
                        _user_bubble(m["content"])
                    else:
                        _assistant_bubble(m["content"], m.get("meta", {}).get("source", ""))

        def clear() -> None:
            insight_repository.clear_messages(user_id)
            render_history()

        with ui.column().classes("w-full gap-3 px-5 py-4 border-t").style("border-color:var(--line)"):
            with ui.row().classes("w-full gap-2 wrap"):
                for q in copilot.SUGGESTED_QUESTIONS:
                    ui.button(q, on_click=lambda q=q: send(q)).props("outline rounded no-caps dense").classes(
                        "text-xs px-3").style("color:var(--muted); border-color:var(--line-strong)")
            with ui.row().classes("w-full gap-2 no-wrap items-center"):
                box = ui.input(placeholder="Ask about your money, e.g. 'Can I afford a ₹8 lakh trip in 2 years?'").props(
                    "outlined dark dense maxlength=500").classes("flex-grow")
                send_button = ui.button(icon="send", on_click=lambda: send(box.value)).props(
                    'round unelevated aria-label="Send"').classes("ft-btn-primary").props("color=none text-color=none")
            ui.label("Estimates for education and analysis, not financial advice.").classes("text-[11px] ft-faint")

        async def send(text: str | None) -> None:
            question = (text or "").strip()
            if not question:
                return
            box.value = ""
            with messages:
                _user_bubble(question)
                with ui.row().classes("items-center gap-2 pl-9") as typing:
                    ui.spinner("dots", size="md", color="secondary")
                    ui.label("Your twin is running the numbers…").classes("text-xs ft-muted")
            scroll.scroll_to(percent=1.0)
            send_button.props("loading")
            try:
                reply = await run.io_bound(copilot.ask, user_id, question)
            except Exception as exc:
                typing.delete()
                send_button.props(remove="loading")
                notify_error(exc)
                return
            typing.delete()
            send_button.props(remove="loading")
            with messages:
                _assistant_bubble(reply.markdown, reply.source)
            scroll.scroll_to(percent=1.0)

        box.on("keydown.enter", lambda: send(box.value))
        render_history()
        ui.timer(0.3, lambda: scroll.scroll_to(percent=1.0), once=True)
