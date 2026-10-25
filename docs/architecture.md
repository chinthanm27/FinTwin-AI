# Architecture

## Layers

```text
┌──────────────────────────────────────────────────────────────┐
│ pages/        One module per route. Auth check, layout, wiring │
├──────────────────────────────────────────────────────────────┤
│ components/   Reusable UI: app shell, sidebar, KPI cards,      │
│               charts, tables, dialogs, Copilot chat            │
├──────────────────────────────────────────────────────────────┤
│ services/     Business logic: validation, analytics, budgets,  │
│               health score, statements, reports, orchestration │
├───────────────────────────────┬──────────────────────────────┤
│ database/                     │ ai/                          │
│ Connection + per-user queries │ ML models, twin, LLM adapter │
├───────────────────────────────┴──────────────────────────────┤
│ models/   Dataclasses with validation (Transaction, Budget…)  │
│ utils/    errors, validators, formatters, dates, logging      │
│ styles/   design tokens, global CSS, Plotly layout            │
└──────────────────────────────────────────────────────────────┘
```

Rules that keep it clean:

- Pages never talk to MongoDB directly; they call services.
- Every repository function that touches user data takes `user_id` and filters by it.
- AI modules work on Pandas DataFrames, so they are testable without a database.
- LLM access is isolated in `app/ai/llm_provider.py`; swapping providers touches one file.
- All imports are absolute (`from app.services import ...`) and the app runs with `python -m app.main`.

## Request flow (example: dashboard)

```text
GET /dashboard
  → pages.dashboard.dashboard_page()
      → auth.session.current_user()            # signed session, else redirect to /login
      → components.app_shell(...)              # header, sidebar, error boundary
      → services.insight_service.build_dashboard(user_id, period)
          → transaction_service.transactions_dataframe(user_id)   # one MongoDB read
          → analytics_service.compute_summary / monthly_overview / category_breakdown
          → budget_service.budget_status
          → ai.spending_predictor.predict_next_month
          → ai.financial_twin.FinancialTwin.from_dataframe → key_insights
      → components.charts.*  (Plotly)
```

## Error handling

`app_shell` is a context manager wrapping page content. It catches:

- `DatabaseUnavailableError` / `PyMongoError` → "Unable to connect to MongoDB…" card
- `FinTwinError` subclasses → their friendly message
- anything else → generic message; full traceback to `logs/fintwin.log`

Actions (buttons, dialogs) use `notify_error()` for the same mapping as toast notifications.

## Startup

`app/main.py` registers pages, serves `app/assets` at `/assets`, and on startup runs a background warm-up: database ping and loading (or training) the spending model, so the first dashboard load is fast.

## Sessions

NiceGUI's `app.storage.user` is server-side storage keyed by a browser cookie signed with `STORAGE_SECRET`. The session holds only `user_id`, name, email and login time; it expires after 7 days. Post-login redirects accept only known internal paths.

## Design system

`app/styles/theme.py` defines colour tokens (ink, panel, mint for money in/growth, iris for the AI twin, sky for investments, amber, coral), self-hosted Sora/Manrope fonts, surfaces, buttons, Quasar overrides and a shared Plotly layout with Indian-unit axis labels (₹K, ₹L, ₹Cr). The signature visual is the "twin line": recorded history in mint continuing as a dashed iris projection with a likely range.
