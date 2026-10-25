import pytest

from app.models.budget import Budget, BudgetStatus
from app.services import budget_service, transaction_service
from app.utils.dates import today
from app.utils.errors import ValidationError


def test_budget_status_math():
    s = BudgetStatus(category="Food", budget=8000, spent=6800)
    assert s.remaining == 1200
    assert s.percent_used == pytest.approx(85.0)
    assert s.status == "warning"
    assert BudgetStatus("Food", 8000, 9000).status == "exceeded"
    assert BudgetStatus("Food", 8000, 1000).status == "ok"
    assert BudgetStatus("Food", 0, 100).percent_used == 0


def test_calculate_status_sorted_by_usage():
    budgets = [Budget("u", "Food", 1000), Budget("u", "Bills", 1000)]
    statuses = budget_service.calculate_status(budgets, {"Food": 200, "Bills": 900})
    assert [s.category for s in statuses] == ["Bills", "Food"]


def test_budget_uses_current_month_spending(user):
    budget_service.set_budget(user.id, "Food", 1000)
    transaction_service.add_transaction(user.id, today(), "Food", "Expense", 850, "groceries")
    transaction_service.add_transaction(user.id, "2025-01-05", "Food", "Expense", 5000, "old month")
    status = budget_service.budget_status(user.id)[0]
    assert status.spent == 850
    alerts = budget_service.budget_alerts([status])
    assert alerts and alerts[0]["level"] == "warning"


def test_budget_totals():
    totals = budget_service.budget_totals([BudgetStatus("A", 1000, 500), BudgetStatus("B", 1000, 1500)])
    assert totals == {"budget": 2000, "spent": 2000, "remaining": 0, "percent_used": 100.0}


def test_budget_rejects_income_category():
    with pytest.raises(ValidationError):
        Budget.create("u", "Salary", 1000)


def test_suggested_budgets_use_averages(user):
    count = budget_service.apply_suggested_budgets(user.id, {"Food": 12000})
    assert count == 5
    food = [b for b in budget_service.get_budgets(user.id) if b.category == "Food"][0]
    assert food.monthly_limit == 12500  # 12000 * 1.05 rounded to nearest 500
