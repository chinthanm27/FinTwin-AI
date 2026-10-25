from datetime import datetime

import pytest

from app.models.transaction import Transaction
from app.services import analytics_service, transaction_service
from app.utils.errors import ValidationError


def _add(user_id, date, category, ttype, amount, desc=""):
    return transaction_service.add_transaction(user_id, date, category, ttype, amount, desc)


def test_summary_calculations(user):
    _add(user.id, "2026-03-01", "Salary", "Income", 100000)
    _add(user.id, "2026-03-03", "Rent", "Expense", 25000)
    _add(user.id, "2026-03-04", "Food", "Expense", 15000)
    _add(user.id, "2026-03-05", "Investment", "Investment", 10000)
    s = analytics_service.compute_summary(transaction_service.transactions_dataframe(user.id))
    assert s.income == 100000
    assert s.expenses == 40000
    assert s.investments == 10000
    assert s.savings == 60000
    assert s.savings_rate == pytest.approx(60.0)
    assert s.balance == 50000


def test_summary_empty_is_zero(user):
    s = analytics_service.compute_summary(transaction_service.transactions_dataframe(user.id))
    assert s.income == 0 and s.savings_rate == 0


def test_monthly_overview_fills_gaps_and_cumulates(user):
    _add(user.id, "2026-01-01", "Salary", "Income", 50000)
    _add(user.id, "2026-03-01", "Salary", "Income", 50000)
    _add(user.id, "2026-03-02", "Food", "Expense", 20000)
    monthly = analytics_service.monthly_overview(transaction_service.transactions_dataframe(user.id))
    assert list(monthly["month"][:3]) == ["2026-01", "2026-02", "2026-03"]
    assert monthly.loc[1, "income"] == 0
    assert monthly.loc[2, "cumulative_balance"] == 80000


def test_category_breakdown_shares(user):
    _add(user.id, "2026-02-01", "Food", "Expense", 300)
    _add(user.id, "2026-02-02", "Bills", "Expense", 700)
    cats = analytics_service.category_breakdown(transaction_service.transactions_dataframe(user.id))
    assert cats.iloc[0]["category"] == "Bills"
    assert cats["share"].sum() == pytest.approx(100)


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"amount": -5}, "greater than zero"),
        ({"amount": "abc"}, "must be a number"),
        ({"amount": 0}, "greater than zero"),
        ({"category": "Crypto"}, "valid category"),
        ({"transaction_type": "Gift"}, "Type must be"),
        ({"date": "31-31-2026"}, "YYYY-MM-DD"),
        ({"date": "2099-01-01"}, "future"),
    ],
)
def test_transaction_validation(kwargs, message):
    base = {"user_id": "u1", "date": "2026-01-10", "category": "Food", "transaction_type": "Expense",
            "amount": 100, "description": "ok"}
    base.update(kwargs)
    with pytest.raises(ValidationError, match=message):
        Transaction.create(**base)


def test_description_is_sanitised():
    t = Transaction.create("u1", "2026-01-10", "Food", "Expense", "1,250.50", "  Swiggy\x00  order\n ")
    assert t.description == "Swiggy order"
    assert t.amount == 1250.50
    assert t.date == datetime(2026, 1, 10)


def test_update_and_delete(user):
    t = _add(user.id, "2026-02-01", "Food", "Expense", 300, "Snacks")
    transaction_service.update_transaction(user.id, t.id, {"amount": 450, "category": "Shopping"})
    updated = transaction_service.list_transactions(user.id)[0]
    assert updated.amount == 450 and updated.category == "Shopping"
    transaction_service.delete_transaction(user.id, t.id)
    assert transaction_service.list_transactions(user.id) == []


def test_search_filter_sort(user):
    _add(user.id, "2026-02-01", "Food", "Expense", 300, "Swiggy dinner")
    _add(user.id, "2026-02-05", "Transport", "Expense", 900, "Uber airport")
    _add(user.id, "2026-02-03", "Salary", "Income", 50000, "Salary credit")
    assert [t.description for t in transaction_service.list_transactions(user.id, search="uber")] == ["Uber airport"]
    assert len(transaction_service.list_transactions(user.id, transaction_type="Expense")) == 2
    by_amount = transaction_service.list_transactions(user.id, sort_by="amount", descending=False)
    assert [t.amount for t in by_amount] == [300, 900, 50000]
    ranged = transaction_service.list_transactions(user.id, start_date=datetime(2026, 2, 2), end_date=datetime(2026, 2, 4))
    assert [t.category for t in ranged] == ["Salary"]


def test_search_regex_is_escaped(user):
    _add(user.id, "2026-02-01", "Food", "Expense", 300, "Coffee (large)")
    assert len(transaction_service.list_transactions(user.id, search="(large")) == 1
    assert transaction_service.list_transactions(user.id, search=".*") == []


def test_csv_export(user):
    _add(user.id, "2026-02-01", "Food", "Expense", 300, "Swiggy")
    data = transaction_service.export_csv(transaction_service.list_transactions(user.id)).decode()
    assert data.splitlines()[0] == "date,type,category,amount,description,source"
    assert "Swiggy" in data
