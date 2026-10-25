"""Budget management and budget-vs-actual calculations."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.database import budget_repository
from app.models.budget import Budget, BudgetStatus
from app.services import analytics_service
from app.services.transaction_service import transactions_dataframe
from app.utils.dates import period_key, today

SUGGESTED_BUDGETS: dict[str, float] = {
    "Food": 8000,
    "Transport": 4000,
    "Shopping": 5000,
    "Entertainment": 3000,
    "Bills": 10000,
}


def set_budget(user_id: str, category: str, monthly_limit: Any) -> None:
    budget_repository.upsert_budget(Budget.create(user_id, category, monthly_limit))


def delete_budget(user_id: str, budget_id: str) -> bool:
    return budget_repository.delete_budget(user_id, budget_id)


def get_budgets(user_id: str) -> list[Budget]:
    return budget_repository.get_budgets(user_id)


def calculate_status(budgets: list[Budget], spent_by_category: dict[str, float]) -> list[BudgetStatus]:
    """Pure calculation: combine budgets with this month's spending."""
    statuses = [
        BudgetStatus(
            category=b.category,
            budget=float(b.monthly_limit),
            spent=round(float(spent_by_category.get(b.category, 0.0)), 2),
            budget_id=b.id,
        )
        for b in budgets
    ]
    return sorted(statuses, key=lambda s: s.percent_used, reverse=True)


def budget_status(user_id: str, df: pd.DataFrame | None = None) -> list[BudgetStatus]:
    df = df if df is not None else transactions_dataframe(user_id)
    spent = analytics_service.current_month_expenses_by_category(df)
    return calculate_status(get_budgets(user_id), spent)


def budget_totals(statuses: list[BudgetStatus]) -> dict[str, float]:
    total_budget = sum(s.budget for s in statuses)
    total_spent = sum(s.spent for s in statuses)
    return {
        "budget": total_budget,
        "spent": total_spent,
        "remaining": total_budget - total_spent,
        "percent_used": (total_spent / total_budget * 100) if total_budget else 0.0,
    }


def budget_alerts(statuses: list[BudgetStatus]) -> list[dict[str, Any]]:
    alerts = []
    for s in statuses:
        if s.status == "exceeded":
            alerts.append({
                "level": "negative",
                "title": f"{s.category} budget exceeded",
                "text": f"Spent {s.percent_used:.0f}% of this month's {s.category} budget.",
            })
        elif s.status == "warning":
            alerts.append({
                "level": "warning",
                "title": f"{s.category} budget almost used",
                "text": f"{s.percent_used:.0f}% used with days left in the month.",
            })
    return alerts


def apply_suggested_budgets(user_id: str, average_by_category: dict[str, float] | None = None) -> int:
    """Create starter budgets. Uses the user's own averages (rounded up) when available."""
    count = 0
    for category, default in SUGGESTED_BUDGETS.items():
        avg = (average_by_category or {}).get(category)
        limit = default
        if avg and avg > 0:
            limit = max(500.0, round(avg * 1.05 / 500) * 500)
        set_budget(user_id, category, limit)
        count += 1
    return count


def average_spend_by_category(df: pd.DataFrame, months: int = 3) -> dict[str, float]:
    if df.empty:
        return {}
    expenses = df[df["transaction_type"] == "Expense"]
    done_months = sorted(expenses["month"].unique())
    done_months = [m for m in done_months if m != period_key(today())][-months:]
    if not done_months:
        return {}
    sub = expenses[expenses["month"].isin(done_months)]
    return {k: float(v) / len(done_months) for k, v in sub.groupby("category")["amount"].sum().items()}
