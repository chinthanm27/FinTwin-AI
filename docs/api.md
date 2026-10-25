# Routes and internal service API

FinTwin AI is a server-rendered NiceGUI app; it has no public REST API. This page documents the UI routes and the Python service functions pages call, which are also the natural boundary for a future REST layer.

## UI routes

| Route | Auth | Purpose |
|---|---|---|
| `/` | public | Landing page |
| `/register` | public | Create account |
| `/login?next=/path` | public | Log in (redirects only to known internal paths) |
| `/logout` | any | End session |
| `/dashboard` | required | Overview, charts, insights |
| `/transactions` | required | CRUD, search, filter, sort, export |
| `/budget` | required | Budgets and alerts |
| `/financial-health` | required | Health indicator |
| `/forecast` | required | Cash flow, spending, wealth scenarios |
| `/fraud` | required | Anomaly review |
| `/ai-twin` | required | Scenario simulator and Copilot |
| `/upload` | required | Bank statement import |
| `/reports` | required | Reports and exports |
| `/settings` | required | Profile, goals, security, data |
| `/assets/*` | public | Static files (fonts) |

## Services (all user-scoped)

### `app.services.auth_service`
- `register_user(full_name, email, password, confirm_password) -> User`
- `authenticate(email, password) -> User` (raises `AuthenticationError`; rate-limited)
- `change_password(user_id, current, new, confirm)`
- `update_name(user_id, full_name) -> str`
- `delete_account(user_id, password)`

### `app.services.transaction_service`
- `add_transaction(user_id, date, category, transaction_type, amount, description="", source="manual") -> Transaction`
- `update_transaction(user_id, transaction_id, data: dict)`
- `delete_transaction(user_id, transaction_id)`
- `list_transactions(user_id, search=None, transaction_type=None, category=None, start_date=None, end_date=None, sort_by="date", descending=True, limit=0) -> list[Transaction]`
- `transactions_dataframe(user_id) -> pandas.DataFrame`
- `export_csv(transactions) -> bytes`

### `app.services.analytics_service` (pure functions on DataFrames)
- `compute_summary(df) -> FinancialSummary`
- `monthly_overview(df) -> DataFrame`
- `category_breakdown(df, transaction_type="Expense") -> DataFrame`
- `filter_period(df, "1M"|"3M"|"6M"|"12M"|"ALL")`

### `app.services.budget_service`
- `set_budget(user_id, category, monthly_limit)`, `delete_budget(user_id, budget_id)`
- `budget_status(user_id, df=None) -> list[BudgetStatus]`, `budget_alerts(statuses)`, `budget_totals(statuses)`
- `apply_suggested_budgets(user_id, averages)`

### `app.services.health_service`
- `compute_health(df, profile) -> HealthReport`

### `app.services.fraud_service`
- `scan_user(user_id, df=None) -> AnomalyReport`
- `get_alerts(user_id, status=None)`, `set_status(user_id, alert_id, status)`

### `app.services.statement_service`
- `process_statement(user_id, file_name, data: bytes) -> ParsedStatement`
- `import_rows(user_id, rows) -> int`

### `app.services.report_service`
- `build_report(user_id, user_name, period) -> FinancialReport`
- `render_html(report) -> str`

### `app.services.insight_service`
- `build_dashboard(user_id, period) -> DashboardContext`
- `build_forecast(user_id, horizon) -> (CashflowForecast, SpendingPrediction, DataFrame)`
- `notifications(user_id) -> list[dict]`

### AI
- `app.ai.copilot.ask(user_id, question) -> CopilotReply`
- `app.ai.financial_twin.FinancialTwin.from_dataframe(df, profile).answer(question) -> TwinAnswer`
- `app.ai.spending_predictor.predict_next_month(df) -> SpendingPrediction | None`
- `app.ai.fraud_detector.detect_anomalies(df, user_id=None) -> AnomalyReport`
- `app.ai.cashflow_forecast.forecast_cashflow(df, horizon) -> CashflowForecast | None`
- `app.ai.wealth_forecast.project_wealth(WealthInputs) -> WealthProjection`
