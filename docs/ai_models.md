# AI and machine-learning models

All models are deliberately interpretable, evaluated honestly, and presented as estimates.

## 1. Spending prediction (`app/ai/spending_predictor.py`)

**Goal:** estimate this month's total spending from completed months.

**Features** (all scale-free, so one model works at any income level; base = mean of the last 3 months):
`lag1_ratio`, `lag2_ratio`, `lag3_ratio`, `mean6_ratio`, `median6_ratio`, `income_ratio`, `count_ratio` (transaction frequency), `trend`, `volatility`, `month_sin`, `month_cos` (seasonality).
**Target:** next month's expense ÷ base.

**Training data:** a synthetic population (80 users × 24 months) from `app/services/demo_data_service.py` with realistic structure: salary raises, festive-season shopping (Oct–Nov), holiday travel, lifestyle creep. No real personal data.

**Model selection:** the last 3 months of every synthetic user are held out. Candidates:

| Candidate | Hold-out MAE (ratio) |
|---|---|
| 3-month average (baseline) | 0.159 |
| 6-month median (baseline) | 0.143 |
| Random Forest (shallow, min leaf 15) | 0.150 |
| **Gradient Boosting (absolute-error loss)** | **0.138** |

A machine-learning model is used only if it beats *both* baselines; otherwise the better baseline is used. Gradient Boosting with an absolute-error loss wins because personal spending is noisy and spiky, and the metric is MAE. The bundle (model, features, metrics, timestamp, version) is saved to `trained_models/spending_model.joblib`. If missing or outdated it is retrained automatically at startup.

**Output:** estimate, likely range (±1.5 × hold-out MAE), method used, and typical spend per category (median of recent months). Users with fewer than 6 months get a moving average instead.

## 2. Anomaly detection (`app/ai/fraud_detector.py`)

**Model:** `IsolationForest(n_estimators=300, contamination=0.02)` fitted *per user* on their outgoing transactions, so "unusual" means unusual for that person. Saved to `trained_models/users/<user_id>/fraud_model.joblib`.

**Features:** log amount; robust z-score against a baseline chosen as merchant (if seen 3+ times) → category (3+ transactions) → all outgoing spend; category rarity; day of week; day of month; same-day transaction count; days since last transaction in the category; share of monthly spend.

**Labels:**
- *High Anomaly Risk*: Isolation Forest outlier, z > 4, at least 3× the baseline, top 2 % unusualness, and over 10 % of monthly spend.
- *Potentially Unusual*: outlier with a large z-score, or a large share of monthly spend.
- *Normal*: everything else, including small amounts (below the user's 75th percentile).

Each flag carries reasons such as "27.0× your typical Shopping transaction (₹2,406)". With fewer than 30 transactions a robust z-score rule is used instead. The UI states clearly that flags are prompts to review, not proof of fraud.

## 3. Cash-flow forecast (`app/ai/cashflow_forecast.py`)

For income, expenses and investments separately:

1. Cap one-off spikes at median ± 2.5 MAD (winsorizing).
2. With 6+ months: average of a least-squares linear trend (last 12 months) and the 3-month moving average. Below 6 months: moving average only.
3. Range: ±1.28 σ of residuals (≈ 80 %), widening with √horizon.

Projected tracked cash = today's tracked cash + cumulative (income − expenses − investments). ARIMA-type models were not used because a few months of personal data can't support them reliably.

## 4. Wealth projection (`app/ai/wealth_forecast.py`)

Monthly compounding of current savings plus monthly investment, optional yearly step-up, inflation-adjusted value, and three return scenarios (expected −3 %, expected, +3 %). Also provides `required_monthly_investment` (goal planning) and `loan_emi` (reducing-balance EMI). Assumptions are always displayed.

## 5. Financial Twin (`app/ai/financial_twin.py`)

`FinancialTwin.from_dataframe` builds a state from the last 6 completed months: average income/expenses/investments, variability, tracked cash, total invested, savings rate, top categories, month-over-month changes, health score, and profile facts (emergency fund, EMIs, expected return, goals).

`simulate()` projects cash and invested value month by month under changes to income (%), expenses (₹ or %), extra investment and one-time costs.

`answer(question)` parses amounts (₹, Rs, lakh, crore, k), percentages and durations, routes to an intent and returns markdown with data, **missing information** and **assumptions**:

| Intent | Example |
|---|---|
| affordability | Can I afford a ₹15 lakh car next year? (cash vs 20 % down + EMI at 9 %/5 yrs, EMI ≤ 15 % of income guideline, safety buffer) |
| income_change | What happens if my salary increases by 20%? |
| expense_change | What happens if my expenses increase by ₹10,000? |
| savings | How much can I save in one year? |
| goal | How much should I invest monthly to reach ₹50 lakh in 10 years? |
| spending / health / emergency / overview | Where am I spending the most? etc. |

If there's no usable history, the twin says so and lists what's needed instead of guessing.

## 6. Copilot and LLM integration

`app/ai/copilot.py` pipeline: question → twin analysis → financial context (no personal identifiers) → LLM (if configured) → response, saved to `ai_conversations`.

The system prompt requires the LLM to use only the provided numbers, state missing data, avoid guarantees and product recommendations, and keep the twin's verdict. `app/ai/llm_provider.py` defines an `LLMProvider` interface and a `GeminiProvider` using the REST API (key from `.env`, sent only as a header). Any failure falls back to the twin's deterministic answer.

## 7. Categorization (`app/ai/categorizer.py`)

Ordered regex rules for common Indian merchants and patterns (Swiggy/Zomato → Food, Uber/Ola/Metro → Transport, Amazon/Flipkart → Shopping, Netflix → Entertainment, salary credits → Salary, SIP/Groww/Zerodha → Investment…), respecting debit/credit hints from statements, with a confidence score. The interface (`categorize(description, hint_type)`) lets an ML classifier replace the rules later.

## 8. Financial health score (`app/services/health_service.py`)

Heuristic, transparent indicator. Factors, rules and weights:

| Factor | Weight | Full marks | Zero |
|---|---|---|---|
| Savings rate | 20 % | ≥ 30 % | ≤ 0 % |
| Expense ratio | 15 % | ≤ 50 % of income | ≥ 100 % |
| Emergency fund | 20 % | ≥ 6 months of expenses | 0 |
| Debt burden | 15 % | no EMIs | EMIs ≥ 50 % of income |
| Investment consistency | 10 % | invested every month | never |
| Cash-flow stability | 10 % | every month positive | none |
| Spending stability | 10 % | no variation | ±60 % variation |

Weighted average, rounded to the nearest 5; bands 0–30, 31–60, 61–80, 81–100. Missing profile inputs are estimated and labelled as such.
