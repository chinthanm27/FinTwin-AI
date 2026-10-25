"""
Cash-flow forecast: future income, expenses, savings and cash balance.

Deliberately simple and interpretable:
- With 6+ completed months: average of a linear trend (least squares on
  the last 12 months) and a 3-month moving average. The trend captures
  direction (e.g. a raise), the moving average keeps it grounded.
- With 1-5 months: moving average only.
An ~80 % band is derived from the historical residual spread.
ARIMA-style models are not used because a few months of personal data
cannot support them reliably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from app.config import settings
from app.services import analytics_service
from app.utils.dates import add_months, month_start, period_key, utcnow
from app.utils.logger import get_logger

log = get_logger("ai.cashflow")

Z_80 = 1.28


@dataclass
class SeriesForecast:
    values: list[float]
    low: list[float]
    high: list[float]
    slope_per_month: float


@dataclass
class CashflowForecast:
    months: list[str]
    income: SeriesForecast
    expense: SeriesForecast
    investment: SeriesForecast
    savings: list[float]
    balance: list[float]
    balance_low: list[float]
    balance_high: list[float]
    starting_balance: float
    method: str
    history_months: int
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "months": self.months,
            "income": self.income.values,
            "expense": self.expense.values,
            "investment": self.investment.values,
            "savings": self.savings,
            "balance": self.balance,
            "method": self.method,
            "history_months": self.history_months,
        }


def winsorize(history: np.ndarray) -> np.ndarray:
    """Cap one-off spikes (e.g. a large purchase) at median ± 2.5 MAD so they don't distort the trend."""
    if len(history) < 4:
        return history
    median = float(np.median(history))
    mad = float(np.median(np.abs(history - median))) * 1.4826
    if mad == 0:
        return history
    return np.clip(history, median - 2.5 * mad, median + 2.5 * mad)


def _forecast_series(history: np.ndarray, horizon: int) -> SeriesForecast:
    history = winsorize(np.asarray(history, dtype=float))
    n = len(history)
    ma = float(np.mean(history[-3:]))
    if n >= 6:
        recent = history[-12:]
        x = np.arange(len(recent)).reshape(-1, 1)
        reg = LinearRegression().fit(x, recent)
        future_x = np.arange(len(recent), len(recent) + horizon).reshape(-1, 1)
        trend = reg.predict(future_x)
        values = 0.5 * trend + 0.5 * ma
        residual = recent - reg.predict(x)
        sigma = float(np.std(residual)) if len(residual) > 1 else ma * 0.1
        slope = float(reg.coef_[0]) * 0.5
    else:
        values = np.full(horizon, ma)
        sigma = float(np.std(history)) if n > 1 else ma * 0.15
        slope = 0.0
    values = np.maximum(values, 0.0)
    widen = np.sqrt(np.arange(1, horizon + 1))  # uncertainty grows with distance
    low = np.maximum(values - Z_80 * sigma * widen, 0.0)
    high = values + Z_80 * sigma * widen
    return SeriesForecast(
        values=[round(float(v)) for v in values],
        low=[round(float(v)) for v in low],
        high=[round(float(v)) for v in high],
        slope_per_month=round(slope, 2),
    )


def forecast_cashflow(df: pd.DataFrame, horizon: int = 6, user_id: str | None = None) -> CashflowForecast | None:
    monthly = analytics_service.monthly_overview(df)
    done = analytics_service.completed_months(monthly)
    done = done[done["transactions"] > 0]
    if done.empty:
        return None
    n = len(done)
    income = _forecast_series(done["income"].to_numpy(dtype=float), horizon)
    expense = _forecast_series(done["expense"].to_numpy(dtype=float), horizon)
    investment = _forecast_series(done["investment"].to_numpy(dtype=float), horizon)

    start_balance = float(monthly["net_cash_flow"].sum()) if not monthly.empty else 0.0
    months = [period_key(add_months(month_start(), i + 1)) for i in range(horizon)]
    savings = [round(i - e) for i, e in zip(income.values, expense.values)]
    net = np.array(income.values) - np.array(expense.values) - np.array(investment.values)
    balance = start_balance + np.cumsum(net)
    net_low = np.array(income.low) - np.array(expense.high) - np.array(investment.values)
    net_high = np.array(income.high) - np.array(expense.low) - np.array(investment.values)

    method = "Linear trend + 3-month moving average" if n >= 6 else "3-month moving average"
    assumptions = [
        f"Based on {n} completed month(s) of your transactions.",
        "Income, expenses and investments continue their recent pattern.",
        "Range shows roughly 80% of outcomes if past variability repeats.",
        "One-off spikes (e.g. a single large purchase) are capped so they don't distort the trend.",
        "Balance means tracked cash: income minus expenses and investments.",
    ]
    if n < 6:
        assumptions.append("Fewer than 6 months of history, so no trend is applied.")

    if user_id:
        try:
            path = settings.models_dir / "users" / user_id
            path.mkdir(parents=True, exist_ok=True)
            joblib.dump(
                {"method": method, "history_months": n, "income_slope": income.slope_per_month,
                 "expense_slope": expense.slope_per_month, "trained_at": utcnow().isoformat()},
                path / "forecast_model.joblib",
            )
        except OSError as exc:
            log.warning("Could not save forecast model: %s", exc)

    return CashflowForecast(
        months=months,
        income=income,
        expense=expense,
        investment=investment,
        savings=savings,
        balance=[round(float(b)) for b in balance],
        balance_low=[round(float(b)) for b in start_balance + np.cumsum(net_low)],
        balance_high=[round(float(b)) for b in start_balance + np.cumsum(net_high)],
        starting_balance=round(start_balance),
        method=method,
        history_months=n,
        assumptions=assumptions,
    )
