"""
FinTwin AI design system.

Palette
- ink      #070D1A  page background (deep navy, not black)
- panel    #0E1628  raised surfaces
- mint     #3EE6B0  money in, growth, primary actions
- iris     #8B7CFF  the AI twin: projections, scenarios, copilot
- sky      #4CC2FF  investments
- amber    #F6B94C  attention
- coral    #FF6B81  money out, risk

Type: Sora for display and figures, Manrope for reading text.
The one signature element is the "twin line": recorded history in mint
that continues as a dashed iris projection. Everything else stays quiet.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

COLORS: dict[str, str] = {
    "ink": "#070D1A",
    "panel": "#0E1628",
    "panel_2": "#131D33",
    "line": "rgba(148, 163, 200, 0.14)",
    "text": "#E7ECF6",
    "muted": "#8C98B5",
    "faint": "#5E6A86",
    "mint": "#3EE6B0",
    "iris": "#8B7CFF",
    "sky": "#4CC2FF",
    "amber": "#F6B94C",
    "coral": "#FF6B81",
}

TYPE_COLORS: dict[str, str] = {"Income": COLORS["mint"], "Expense": COLORS["coral"], "Investment": COLORS["sky"]}

# Ordered categorical palette for charts (validated for contrast on the dark panel)
CHART_SEQUENCE: list[str] = [
    "#3EE6B0", "#8B7CFF", "#4CC2FF", "#F6B94C", "#FF6B81",
    "#5FD3C7", "#B79CFF", "#FF9F6E", "#9AD86B", "#E88BD8", "#7FA6FF", "#C9C26B", "#8C98B5",
]

TONE_COLORS: dict[str, str] = {
    "positive": COLORS["mint"],
    "info": COLORS["iris"],
    "warning": COLORS["amber"],
    "negative": COLORS["coral"],
}

LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,"
         "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD")
LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1D00-1DBF,U+1E00-1E9F,"
             "U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF")


def _font_faces() -> str:
    """Self-hosted fonts (app/assets/fonts, SIL OFL) so the UI works offline and loads no third-party CSS."""
    rules = []
    for family, slug, weights in (("Sora", "sora", (400, 600, 700, 800)), ("Manrope", "manrope", (400, 500, 600, 700))):
        for weight in weights:
            for subset, unicode_range in (("latin", LATIN), ("latin-ext", LATIN_EXT)):
                rules.append(
                    f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};font-display:swap;"
                    f"src:url('/assets/fonts/{slug}-{subset}-{weight}-normal.woff2') format('woff2');"
                    f"unicode-range:{unicode_range};}}"
                )
    return "\n".join(rules)


GLOBAL_CSS = """
<style>
{font_faces}
:root {
  --ink:#070D1A; --panel:#0E1628; --panel-2:#131D33; --line:rgba(148,163,200,.14); --line-strong:rgba(148,163,200,.26);
  --text:#E7ECF6; --muted:#8C98B5; --faint:#5E6A86;
  --mint:#3EE6B0; --iris:#8B7CFF; --sky:#4CC2FF; --amber:#F6B94C; --coral:#FF6B81;
  --radius-lg:20px; --radius-md:14px; --radius-sm:10px;
}
html, body { background: var(--ink) !important; color: var(--text); }
body {
  font-family: 'Manrope', system-ui, sans-serif; font-size: 15px; line-height: 1.55;
  -webkit-font-smoothing: antialiased; font-feature-settings: "tnum" 1;
}
body::before {
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:
    radial-gradient(1100px 600px at 85% -10%, rgba(139,124,255,.13), transparent 60%),
    radial-gradient(900px 520px at -10% 10%, rgba(62,230,176,.09), transparent 60%);
}
.q-layout, .q-page-container, .nicegui-content { position: relative; z-index: 1; }
.nicegui-content { padding: 0 !important; }
h1, h2, h3, .ft-display { font-family: 'Sora', sans-serif; letter-spacing: -0.02em; }
.ft-num { font-family: 'Sora', sans-serif; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.ft-muted { color: var(--muted); }
.ft-faint { color: var(--faint); }
.ft-mint { color: var(--mint); } .ft-iris { color: var(--iris); } .ft-sky { color: var(--sky); }
.ft-amber { color: var(--amber); } .ft-coral { color: var(--coral); }

/* Surfaces */
.ft-glass {
  background: linear-gradient(180deg, rgba(22,32,56,.72), rgba(14,22,40,.72));
  border: 1px solid var(--line); border-radius: var(--radius-lg);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
}
.ft-panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-lg); }
.ft-tile { background: rgba(19,29,51,.7); border: 1px solid var(--line); border-radius: var(--radius-md); }
.ft-divider { height:1px; background: var(--line); width:100%; }

/* Buttons */
.ft-btn-primary.q-btn {
  background: linear-gradient(135deg, #3EE6B0 0%, #4CC2FF 100%) !important; color: #04121A !important;
  font-weight: 700; border-radius: 12px; text-transform: none; letter-spacing: 0; padding: 8px 18px;
  box-shadow: 0 8px 28px -10px rgba(62,230,176,.6);
}
.ft-btn-ghost.q-btn {
  background: rgba(255,255,255,.04) !important; color: var(--text) !important; border: 1px solid var(--line-strong);
  border-radius: 12px; text-transform: none; letter-spacing: 0; font-weight: 600; padding: 8px 18px;
}
.ft-btn-danger.q-btn { background: rgba(255,107,129,.12) !important; color: var(--coral) !important;
  border: 1px solid rgba(255,107,129,.35); border-radius: 12px; text-transform: none; font-weight: 600; }
.q-btn { text-transform: none; letter-spacing: 0; }
.q-btn:focus-visible, a:focus-visible { outline: 2px solid var(--mint); outline-offset: 2px; }

/* Chips */
.ft-chip { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:12px;
  font-weight:600; border:1px solid var(--line-strong); color: var(--muted); background: rgba(255,255,255,.03); }
.ft-chip-mint { color: var(--mint); border-color: rgba(62,230,176,.35); background: rgba(62,230,176,.08); }
.ft-chip-iris { color: var(--iris); border-color: rgba(139,124,255,.38); background: rgba(139,124,255,.10); }
.ft-chip-amber { color: var(--amber); border-color: rgba(246,185,76,.38); background: rgba(246,185,76,.10); }
.ft-chip-coral { color: var(--coral); border-color: rgba(255,107,129,.38); background: rgba(255,107,129,.10); }
.ft-chip-sky { color: var(--sky); border-color: rgba(76,194,255,.38); background: rgba(76,194,255,.10); }

/* App shell */
.ft-header { background: rgba(7,13,26,.78) !important; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--line); }
.ft-drawer { background: #0A1222 !important; border-right: 1px solid var(--line) !important; }
.ft-nav-item { display:flex; align-items:center; gap:12px; padding:10px 14px; border-radius:12px; color: var(--muted);
  font-weight:600; font-size:14px; text-decoration:none; transition: background .15s, color .15s; width:100%; }
.ft-nav-item:hover { background: rgba(255,255,255,.04); color: var(--text); }
.ft-nav-item.active { background: linear-gradient(90deg, rgba(62,230,176,.14), rgba(62,230,176,.02)); color: var(--text);
  box-shadow: inset 2px 0 0 var(--mint); }
.ft-nav-item.active .q-icon { color: var(--mint); }
.ft-content { width:100%; max-width: 1320px; margin: 0 auto; padding: 24px 28px 48px; gap: 22px; }
@media (max-width: 640px) { .ft-content { padding: 16px 14px 40px; } }

/* KPI */
.ft-kpi-label { font-size:13px; color: var(--muted); font-weight:600; }
.ft-kpi-value { font-family:'Sora',sans-serif; font-size: 26px; font-weight:700; letter-spacing:-0.03em; line-height:1.15; }
@media (max-width: 640px) { .ft-kpi-value { font-size: 22px; } }

/* Progress */
.ft-bar { height:8px; border-radius:999px; background: rgba(255,255,255,.06); overflow:hidden; width:100%; }
.ft-bar > div { height:100%; border-radius:999px; }

/* Quasar overrides */
.q-field--outlined .q-field__control { border-radius: 12px; }
.q-field--outlined .q-field__control:before { border-color: var(--line-strong) !important; }
.q-field--dark .q-field__control { background: rgba(255,255,255,.02); }
.q-table__container, .q-table__card { background: transparent !important; box-shadow:none !important; }
.q-table th { color: var(--muted) !important; font-weight: 700 !important; font-size: 12.5px !important; }
.q-table tbody td { font-size: 14px; }
.q-table--dark .q-table__bottom, .q-table--dark thead, .q-table--dark tr, .q-table--dark th, .q-table--dark td { border-color: var(--line) !important; }
.q-dialog__inner > .q-card, .ft-dialog { background: #0F182C !important; border:1px solid var(--line-strong); border-radius: var(--radius-lg) !important; }
.q-menu { background: #0F182C !important; border:1px solid var(--line-strong); border-radius: 14px !important; }
.q-tab { text-transform: none; font-weight: 600; }
.q-notification { border-radius: 12px !important; font-family: 'Manrope', sans-serif; }
.q-uploader { background: transparent !important; box-shadow: none !important; width: 100%; }
.markdown-body, .nicegui-markdown { color: var(--text); }
.nicegui-markdown table { border-collapse: collapse; margin: 8px 0; font-size: 14px; }
.nicegui-markdown th, .nicegui-markdown td { border: 1px solid var(--line-strong); padding: 6px 10px; text-align:left; }
.nicegui-markdown h3 { font-size: 18px; margin: 4px 0 10px; }
.nicegui-markdown p { margin: 0 0 10px; }
.nicegui-markdown code { background: rgba(255,255,255,.06); padding: 1px 5px; border-radius: 6px; }

/* Scrollbar */
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-thumb { background: rgba(140,152,181,.25); border-radius: 999px; border: 2px solid var(--ink); }
::-webkit-scrollbar-track { background: transparent; }

/* One orchestrated motion: the twin line draws itself on page load */
.ft-draw { stroke-dasharray: 1600; stroke-dashoffset: 1600; animation: ft-draw 2.2s cubic-bezier(.65,0,.35,1) .2s forwards; }
.ft-draw-late { opacity:0; animation: ft-fade .8s ease 1.9s forwards; }
@keyframes ft-draw { to { stroke-dashoffset: 0; } }
@keyframes ft-fade { to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .ft-draw { animation: none; stroke-dashoffset: 0; } .ft-draw-late { animation: none; opacity: 1; }
}
</style>
""".replace("{font_faces}", _font_faces())


def apply_theme() -> None:
    """Inject fonts, CSS and Quasar brand colours. Call once at the start of every page."""
    ui.add_head_html(GLOBAL_CSS)
    ui.colors(
        primary=COLORS["mint"],
        secondary=COLORS["iris"],
        accent=COLORS["sky"],
        positive=COLORS["mint"],
        negative=COLORS["coral"],
        warning=COLORS["amber"],
        info=COLORS["iris"],
        dark=COLORS["panel"],
    )


def plotly_layout(height: int = 300, **overrides: Any) -> dict[str, Any]:
    """Shared Plotly layout: transparent background, theme fonts, quiet grid."""
    layout: dict[str, Any] = {
        "height": height,
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Manrope, sans-serif", "color": COLORS["muted"], "size": 12},
        "colorway": CHART_SEQUENCE,
        "hovermode": "x unified",
        "hoverlabel": {"bgcolor": "#0F182C", "bordercolor": "rgba(148,163,200,.3)",
                       "font": {"family": "Manrope", "color": COLORS["text"]}},
        "legend": {"orientation": "h", "y": 1.12, "x": 0, "font": {"color": COLORS["muted"]}, "bgcolor": "rgba(0,0,0,0)"},
        "xaxis": {"gridcolor": "rgba(148,163,200,.07)", "zeroline": False, "linecolor": "rgba(148,163,200,.18)",
                  "tickfont": {"color": COLORS["muted"]}, "automargin": True},
        "yaxis": {"gridcolor": "rgba(148,163,200,.09)", "zeroline": False, "tickfont": {"color": COLORS["muted"]},
                  "tickprefix": "₹", "separatethousands": True, "automargin": True},
    }
    layout.update(overrides)
    return layout


PLOTLY_CONFIG: dict[str, Any] = {"displayModeBar": False, "responsive": True, "displaylogo": False}
