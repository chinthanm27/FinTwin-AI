from datetime import datetime

import pandas as pd

from app.models.financial_profile import FinancialProfile
from app.services.health_service import band_for, compute_health
from app.services.transaction_service import documents_to_dataframe
from app.utils.dates import add_months, month_start


def _history(months=6, income=100000, expense=50000, invest=10000):
    docs = []
    start = add_months(month_start(), -months)
    for i in range(months):
        m = add_months(start, i)
        docs += [
            {"date": m, "category": "Salary", "transaction_type": "Income", "amount": income, "description": "s"},
            {"date": m.replace(day=3), "category": "Rent", "transaction_type": "Expense", "amount": expense, "description": "r"},
            {"date": m.replace(day=5), "category": "Investment", "transaction_type": "Investment", "amount": invest, "description": "i"},
        ]
    return documents_to_dataframe(docs)


def test_no_data_returns_unavailable():
    report = compute_health(documents_to_dataframe([]))
    assert not report.available and report.score is None


def test_healthy_profile_scores_high():
    profile = FinancialProfile(user_id="u", emergency_fund=400000, monthly_debt_payment=0)
    report = compute_health(_history(), profile)
    assert report.available
    assert report.score >= 81 and report.band == "Excellent"
    assert len(report.factors) == 7
    assert report.score % 5 == 0  # rounded to avoid false precision


def test_overspending_scores_low():
    profile = FinancialProfile(user_id="u", emergency_fund=0, monthly_debt_payment=40000)
    report = compute_health(_history(expense=110000, invest=0), profile)
    assert report.score <= 30


def test_missing_profile_is_flagged_as_estimated():
    report = compute_health(_history())
    estimated = {f.key for f in report.factors if f.estimated}
    assert {"emergency_fund", "debt_burden"} <= estimated
    assert any("not set" in n for n in report.notes)


def test_weights_sum_to_one():
    report = compute_health(_history())
    assert abs(sum(f.weight for f in report.factors) - 1.0) < 1e-9


def test_bands():
    assert band_for(25)[0] == "Needs attention"
    assert band_for(45)[0] == "Fair"
    assert band_for(70)[0] == "Good"
    assert band_for(95)[0] == "Excellent"
