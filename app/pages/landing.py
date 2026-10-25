"""Public landing page: /"""

from __future__ import annotations

from nicegui import ui

from app.auth.session import current_user
from app.components.dashboard_preview import dashboard_preview
from app.components.feature_grid import feature_grid
from app.components.hero import hero
from app.components.landing_sections import ai_features, call_to_action, footer, how_it_works
from app.components.navbar import landing_navbar
from app.components.stats import stats_strip
from app.styles.theme import apply_theme


@ui.page("/", title="FinTwin AI · Your AI financial twin")
def landing_page() -> None:
    apply_theme()
    ui.add_head_html("<style>html{scroll-behavior:smooth} section[id]{scroll-margin-top:80px}</style>")
    landing_navbar(logged_in=current_user() is not None)
    with ui.column().classes("w-full gap-0"):
        hero()
        stats_strip()
        feature_grid()
        dashboard_preview()
        how_it_works()
        ai_features()
        call_to_action()
        footer()
