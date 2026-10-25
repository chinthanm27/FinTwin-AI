"""Queries for the budgets collection (always scoped by user_id)."""

from __future__ import annotations

from app.database.mongodb import budgets_collection
from app.database.user_repository import to_object_id
from app.models.budget import Budget
from app.utils.dates import utcnow


def upsert_budget(budget: Budget) -> None:
    """Create or update the budget for (user, category)."""
    budgets_collection().update_one(
        {"user_id": budget.user_id, "category": budget.category},
        {
            "$set": {"monthly_limit": float(budget.monthly_limit), "updated_at": utcnow()},
            "$setOnInsert": {"created_at": utcnow()},
        },
        upsert=True,
    )


def get_budgets(user_id: str) -> list[Budget]:
    return [Budget.from_document(d) for d in budgets_collection().find({"user_id": user_id}).sort("category", 1)]


def delete_budget(user_id: str, budget_id: str) -> bool:
    oid = to_object_id(budget_id)
    if oid is None:
        return False
    return budgets_collection().delete_one({"_id": oid, "user_id": user_id}).deleted_count == 1


def delete_all_for_user(user_id: str) -> int:
    return budgets_collection().delete_many({"user_id": user_id}).deleted_count
