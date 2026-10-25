import numpy as np
import pytest

from app.ai.cashflow_forecast import forecast_cashflow, winsorize
from app.ai.spending_predictor import predict_next_month
from app.ai.wealth_forecast import WealthInputs, loan_emi, project_wealth, required_monthly_investment
from app.services.demo_data_service import generate_records
from app.services.transaction_service import documents_to_dataframe
from app.utils.errors import ValidationError


def test_wealth_zero_return_is_simple_sum():
    p = project_wealth(WealthInputs(current_savings=10000, monthly_investment=1000, expected_return=0, years=2, inflation=0))
    assert p.final_value == 10000 + 24 * 1000
    assert p.gains == 0


def test_wealth_compounding_matches_formula():
    p = project_wealth(WealthInputs(current_savings=0, monthly_investment=10000, expected_return=12, years=10))
    r, n = 0.01, 120
    expected = 10000 * ((1 + r) ** n - 1) / r
    assert p.final_value == pytest.approx(expected, rel=1e-6)
    assert len(p.scenarios) == 3
    assert any("not" in a.lower() or "fluctuate" in a.lower() for a in p.assumptions)


def test_wealth_warns_when_investment_exceeds_surplus():
    p = project_wealth(WealthInputs(0, 50000, 10, 5, monthly_income=80000, monthly_expenses=60000))
    assert p.warnings


def test_wealth_validation():
    with pytest.raises(ValidationError):
        project_wealth(WealthInputs(0, 1000, 10, 0))


def test_required_investment_reaches_target():
    monthly = required_monthly_investment(5_000_000, 10, 12)
    p = project_wealth(WealthInputs(0, monthly, 12, 10, inflation=0))
    assert p.final_value == pytest.approx(5_000_000, rel=1e-3)


def test_emi_formula():
    assert loan_emi(1_200_000, 9, 5) == pytest.approx(24910, abs=5)
    assert loan_emi(12000, 0, 1) == 1000


def test_cashflow_forecast_shapes_and_ranges():
    df = documents_to_dataframe(generate_records(months=12, seed=5))
    fc = forecast_cashflow(df, 6)
    assert len(fc.months) == len(fc.balance) == 6
    assert all(lo <= v <= hi for lo, v, hi in zip(fc.balance_low, fc.balance, fc.balance_high))
    assert fc.method.startswith("Linear trend")
    assert fc.assumptions


def test_cashflow_short_history_uses_moving_average():
    df = documents_to_dataframe(generate_records(months=3, seed=5))
    fc = forecast_cashflow(df, 3)
    assert fc.method == "3-month moving average"


def test_cashflow_empty_returns_none():
    assert forecast_cashflow(documents_to_dataframe([]), 6) is None


def test_winsorize_caps_spikes():
    capped = winsorize(np.array([50, 52, 48, 51, 200.0]))
    assert capped.max() < 200


def test_spending_prediction_fallback_without_model():
    df = documents_to_dataframe(generate_records(months=8, seed=9))
    pred = predict_next_month(df, use_model=False)
    assert pred.low <= pred.predicted <= pred.high
    assert "Moving average" in pred.method
    assert pred.category_forecast
