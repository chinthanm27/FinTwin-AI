"""Landing hero with the signature twin line."""

from __future__ import annotations

from nicegui import ui

TWIN_SVG = """
<svg viewBox="0 0 600 340" role="img" aria-label="Recorded balance continuing as a projected twin line with a likely range"
     style="width:100%;height:auto;display:block">
  <defs>
    <linearGradient id="mintFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3EE6B0" stop-opacity=".22"/><stop offset="100%" stop-color="#3EE6B0" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <g stroke="rgba(148,163,200,.09)" stroke-width="1">
    <line x1="20" y1="70" x2="580" y2="70"/><line x1="20" y1="140" x2="580" y2="140"/>
    <line x1="20" y1="210" x2="580" y2="210"/><line x1="20" y1="280" x2="580" y2="280"/>
  </g>
  <path d="M20 262 C60 250 80 255 110 238 S160 236 190 214 S240 222 270 196 S310 176 330 168 L330 300 L20 300 Z"
        fill="url(#mintFill)" class="ft-draw-late"/>
  <path class="ft-draw" d="M20 262 C60 250 80 255 110 238 S160 236 190 214 S240 222 270 196 S310 176 330 168"
        fill="none" stroke="#3EE6B0" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="330" y1="46" x2="330" y2="300" stroke="rgba(231,236,246,.25)" stroke-dasharray="3 5"/>
  <text x="336" y="58" fill="#8C98B5" font-family="Manrope" font-size="12">Today</text>
  <path class="ft-draw-late" d="M330 168 C380 150 420 120 470 104 S550 66 580 54 L580 128 C540 140 500 150 470 158 S380 178 330 168 Z"
        fill="rgba(139,124,255,.16)"/>
  <path class="ft-draw-late" d="M330 168 C380 152 420 132 470 122 S550 94 580 88"
        fill="none" stroke="#8B7CFF" stroke-width="3" stroke-dasharray="8 7" stroke-linecap="round"/>
  <circle cx="330" cy="168" r="6" fill="#070D1A" stroke="#3EE6B0" stroke-width="3" class="ft-draw-late"/>
  <g class="ft-draw-late" font-family="Manrope" font-size="12" font-weight="600">
    <rect x="34" y="276" width="78" height="24" rx="12" fill="rgba(62,230,176,.12)" stroke="rgba(62,230,176,.35)"/>
    <text x="48" y="292" fill="#3EE6B0">Recorded</text>
    <rect x="452" y="160" width="114" height="24" rx="12" fill="rgba(139,124,255,.12)" stroke="rgba(139,124,255,.4)"/>
    <text x="466" y="176" fill="#B9AEFF">Twin projection</text>
  </g>
</svg>
"""


def hero() -> None:
    with ui.element("section").classes("w-full px-4 sm:px-8 pt-28 sm:pt-32 pb-16"):
        with ui.element("div").classes("max-w-[1200px] mx-auto grid gap-12 lg:grid-cols-[1.05fr_1fr] items-center"):
            with ui.column().classes("gap-6 items-start"):
                ui.label("For people who want to see a decision before they make it").classes("ft-chip ft-chip-iris")
                ui.html(
                    "<h1 style='font-size:clamp(2.4rem,5.6vw,4.3rem);line-height:1.02;font-weight:800;margin:0'>"
                    "Your money,<br>with a twin that<br>runs the what‑ifs.</h1>",
                    sanitize=False,
                )
                ui.label(
                    "FinTwin AI learns from your own transactions, scores your financial health, flags spending "
                    "that doesn't look like you, and simulates choices like a car, a raise or a new goal "
                    "before you commit to them."
                ).classes("text-lg ft-muted max-w-xl")
                with ui.row().classes("gap-3 wrap"):
                    ui.button("Create your twin", on_click=lambda: ui.navigate.to("/register")).classes(
                        "ft-btn-primary text-base px-6 py-2.5"
                    ).props("color=none text-color=none")
                    ui.button("See how it works", on_click=lambda: ui.navigate.to("#how")).classes("ft-btn-ghost text-base").props("color=none text-color=none")
                ui.label("Runs on your machine with your own MongoDB. No bank logins required.").classes(
                    "text-sm ft-faint"
                )

            with ui.column().classes("ft-glass p-5 sm:p-6 gap-4 w-full"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label("Net worth path").classes("text-sm ft-muted")
                        ui.label("₹6.8L → ₹11.2L").classes("ft-num text-2xl font-bold")
                    ui.label("12-month projection").classes("ft-chip")
                ui.html(TWIN_SVG, sanitize=False).classes("w-full")
                with ui.row().classes("ft-tile p-3 w-full gap-3 no-wrap items-start ft-draw-late"):
                    ui.icon("auto_awesome", size="20px").classes("ft-iris mt-0.5")
                    with ui.column().classes("gap-1"):
                        ui.label("“Can I afford a ₹15 lakh car next year?”").classes("text-sm font-semibold")
                        ui.label(
                            "With 20% down, the EMI would be about ₹24,900, which is 25% of your income. "
                            "Your twin calls that a stretch, and shows what would make it comfortable."
                        ).classes("text-xs ft-muted")
