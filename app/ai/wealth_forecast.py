"""
Wealth projection scenario calculator.

Projects how savings and regular investments could grow with monthly
compounding at an assumed annual return, plus an optional yearly step-up
in the monthly investment. Three scenarios (assumed return -3 %, as
entered, +3 %) illustrate sensitivity. All outputs are projections under
stated assumptions, never guaranteed returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.utils.errors import ValidationError


@dataclass
class WealthInputs:
    current_savings: float
    monthly_investment: float
    expected_return: float  # annual %, e.g. 10
    years: int
    monthly_income: float = 0.0
    monthly_expenses: float = 0.0
    annual_step_up: float = 0.0  # % increase of monthly investment each year
    inflation: float = 6.0  # annual %

    def validate(self) -> None:
        if self.current_savings < 0 or self.monthly_investment < 0:
            raise ValidationError("Savings and investment cannot be negative.")
        if not -10 <= self.expected_return <= 30:
            raise ValidationError("Expected return should be between -10% and 30% a year.")
        if not 1 <= self.years <= 50:
            raise ValidationError("Duration must be between 1 and 50 years.")
        if not 0 <= self.annual_step_up <= 50:
            raise ValidationError("Step-up must be between 0% and 50%.")
        if not 0 <= self.inflation <= 20:
            raise ValidationError("Inflation must be between 0% and 20%.")


@dataclass
class WealthProjection:
    years: list[int]
    invested: list[float]
    value: list[float]
    real_value: list[float]
    final_value: float
    total_invested: float
    gains: float
    real_final_value: float
    scenarios: dict[str, list[float]] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_value": self.final_value, "total_invested": self.total_invested, "gains": self.gains,
            "real_final_value": self.real_final_value, "years": self.years, "value": self.value,
        }


def _simulate(inputs: WealthInputs, annual_return: float) -> tuple[list[float], list[float]]:
    """Return (value at end of each year, cumulative contributions)."""
    r = annual_return / 100 / 12
    value = inputs.current_savings
    invested = inputs.current_savings
    monthly = inputs.monthly_investment
    values, contributions = [], []
    for year in range(1, inputs.years + 1):
        for _ in range(12):
            value = value * (1 + r) + monthly
            invested += monthly
        values.append(value)
        contributions.append(invested)
        monthly *= 1 + inputs.annual_step_up / 100
    return values, contributions


def project_wealth(inputs: WealthInputs) -> WealthProjection:
    inputs.validate()
    values, invested = _simulate(inputs, inputs.expected_return)
    real = [v / ((1 + inputs.inflation / 100) ** (i + 1)) for i, v in enumerate(values)]
    scenarios = {
        f"Conservative ({inputs.expected_return - 3:.0f}%)": [round(v) for v in _simulate(inputs, inputs.expected_return - 3)[0]],
        f"Expected ({inputs.expected_return:.0f}%)": [round(v) for v in values],
        f"Optimistic ({inputs.expected_return + 3:.0f}%)": [round(v) for v in _simulate(inputs, inputs.expected_return + 3)[0]],
    }
    warnings = []
    if inputs.monthly_income and inputs.monthly_expenses:
        surplus = inputs.monthly_income - inputs.monthly_expenses
        if inputs.monthly_investment > surplus:
            warnings.append(
                f"Planned investment exceeds your monthly surplus of ₹{surplus:,.0f} (income minus expenses)."
            )
    assumptions = [
        f"Assumed {inputs.expected_return:.1f}% annual return, compounded monthly.",
        f"Monthly investment {'grows by ' + format(inputs.annual_step_up, '.0f') + '% each year' if inputs.annual_step_up else 'stays constant'}.",
        f"Inflation of {inputs.inflation:.1f}% a year is used for today's-money values.",
        "Returns are smooth and constant; real markets fluctuate and can fall.",
        "Taxes, fees and withdrawals are not included.",
    ]
    final = values[-1]
    return WealthProjection(
        years=list(range(1, inputs.years + 1)),
        invested=[round(v) for v in invested],
        value=[round(v) for v in values],
        real_value=[round(v) for v in real],
        final_value=round(final),
        total_invested=round(invested[-1]),
        gains=round(final - invested[-1]),
        real_final_value=round(real[-1]),
        scenarios=scenarios,
        assumptions=assumptions,
        warnings=warnings,
    )


def required_monthly_investment(target: float, years: float, annual_return: float, current: float = 0.0) -> float:
    """Monthly amount needed to reach `target` in `years` at `annual_return` (no step-up)."""
    months = max(1, int(round(years * 12)))
    r = annual_return / 100 / 12
    future_current = current * (1 + r) ** months
    remaining = max(0.0, target - future_current)
    if remaining == 0:
        return 0.0
    if r == 0:
        return remaining / months
    return remaining * r / ((1 + r) ** months - 1)


def loan_emi(principal: float, annual_rate: float, years: float) -> float:
    """Standard reducing-balance EMI."""
    n = max(1, int(round(years * 12)))
    r = annual_rate / 100 / 12
    if principal <= 0:
        return 0.0
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
