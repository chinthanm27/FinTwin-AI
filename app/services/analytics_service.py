"""
Financial analytics computed from the user's transaction DataFrame.

Definitions (shown in the UI as well):
- Income        = sum of Income transactions
- Expenses      = sum of Expense transactions
- Investments   = sum of Investment transactions
- Savings       = Income - Expenses
- Savings rate  = Savings / Income x 100
- Current balance (tracked cash) = Income - Expenses - Investments
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from app.utils.dates import add_months, month_start, period_key, today

PERIODS: dict[str, str] = {
    "1M": "This month",
    "3M": "Last 3 months",
    "6M": "Last 6 months",
    "12M": "Last 12 months",
    "ALL": "All time",
}


@dataclass
class FinancialSummary:
    income: float = 0.0
    expenses: float = 0.0
    investments: float = 0.0
    savings: float = 0.0
    savings_rate: float = 0.0
    balance: float = 0.0
    transaction_count: int = 0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def filter_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Keep rows within the selected period (relative to the current month)."""
    if df.empty or period == "ALL":
        return df
    months = {"1M": 1, "3M": 3, "6M": 6, "12M": 12}.get(period, 0)
    if not months:
        return df
    start = add_months(month_start(), -(months - 1))
    return df[df["date"] >= pd.Timestamp(start)]


def compute_summary(df: pd.DataFrame) -> FinancialSummary:
    if df.empty:
        return FinancialSummary()
    by_type = df.groupby("transaction_type")["amount"].sum()
    income = float(by_type.get("Income", 0.0))
    expenses = float(by_type.get("Expense", 0.0))
    investments = float(by_type.get("Investment", 0.0))
    savings = income - expenses
    savings_rate = (savings / income * 100) if income > 0 else 0.0
    return FinancialSummary(
        income=round(income, 2),
        expenses=round(expenses, 2),
        investments=round(investments, 2),
        savings=round(savings, 2),
        savings_rate=round(savings_rate, 2),
        balance=round(income - expenses - investments, 2),
        transaction_count=int(len(df)),
    )


def monthly_overview(df: pd.DataFrame, fill_gaps: bool = True) -> pd.DataFrame:
    """One row per month: income, expense, investment, savings, net cash flow, cumulative series."""
    columns = ["month", "income", "expense", "investment", "savings", "net_cash_flow",
               "savings_rate", "cumulative_balance", "cumulative_investment", "transactions"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    pivot = df.pivot_table(index="month", columns="transaction_type", values="amount", aggfunc="sum", fill_value=0.0)
    counts = df.groupby("month").size()
    for col in ("Income", "Expense", "Investment"):
        if col not in pivot.columns:
            pivot[col] = 0.0
    if fill_gaps:
        first = pd.Period(pivot.index.min(), freq="M")
        last = max(pd.Period(pivot.index.max(), freq="M"), pd.Period(period_key(today()), freq="M"))
        full_index = [str(p) for p in pd.period_range(first, last, freq="M")]
        pivot = pivot.reindex(full_index, fill_value=0.0)
        counts = counts.reindex(full_index, fill_value=0)
    out = pd.DataFrame(
        {
            "month": pivot.index,
            "income": pivot["Income"].values,
            "expense": pivot["Expense"].values,
            "investment": pivot["Investment"].values,
        }
    )
    out["savings"] = out["income"] - out["expense"]
    out["net_cash_flow"] = out["income"] - out["expense"] - out["investment"]
    out["savings_rate"] = np.where(out["income"] > 0, out["savings"] / out["income"].replace(0, np.nan) * 100, 0.0)
    out["savings_rate"] = out["savings_rate"].fillna(0.0)
    out["cumulative_balance"] = out["net_cash_flow"].cumsum()
    out["cumulative_investment"] = out["investment"].cumsum()
    out["transactions"] = counts.values
    return out.reset_index(drop=True)


def completed_months(monthly: pd.DataFrame) -> pd.DataFrame:
    """Drop the current (incomplete) month for model training and averages."""
    if monthly.empty:
        return monthly
    current = period_key(today())
    return monthly[monthly["month"] != current].reset_index(drop=True)


def category_breakdown(df: pd.DataFrame, transaction_type: str = "Expense") -> pd.DataFrame:
    sub = df[df["transaction_type"] == transaction_type] if not df.empty else df
    if sub.empty:
        return pd.DataFrame(columns=["category", "amount", "share"])
    grouped = sub.groupby("category")["amount"].sum().sort_values(ascending=False).reset_index()
    total = grouped["amount"].sum()
    grouped["share"] = grouped["amount"] / total * 100 if total else 0.0
    return grouped


def month_over_month(df: pd.DataFrame) -> dict[str, float]:
    """Expense change of the last completed month vs the month before, per category."""
    if df.empty:
        return {}
    expenses = df[df["transaction_type"] == "Expense"]
    if expenses.empty:
        return {}
    this_month = period_key(today())
    prev1 = period_key(add_months(month_start(), -1))
    prev2 = period_key(add_months(month_start(), -2))
    current_key = this_month if (expenses["month"] == this_month).any() and today().day >= 20 else prev1
    previous_key = prev1 if current_key == this_month else prev2
    a = expenses[expenses["month"] == current_key].groupby("category")["amount"].sum()
    b = expenses[expenses["month"] == previous_key].groupby("category")["amount"].sum()
    changes = {}
    for category in set(a.index) | set(b.index):
        changes[category] = float(a.get(category, 0.0) - b.get(category, 0.0))
    return changes


def average_monthly(monthly: pd.DataFrame, column: str, months: int = 6) -> float:
    """Average of a monthly column over the last N completed months that have any activity."""
    done = completed_months(monthly)
    if done.empty:
        done = monthly
    if done.empty:
        return 0.0
    active = done[done["transactions"] > 0].tail(months)
    if active.empty:
        return 0.0
    return float(active[column].mean())


def current_month_expenses_by_category(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    key = period_key(today())
    sub = df[(df["month"] == key) & (df["transaction_type"] == "Expense")]
    return {k: float(v) for k, v in sub.groupby("category")["amount"].sum().items()}
