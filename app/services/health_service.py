"""
Financial Health Score: a transparent, heuristic 0-100 indicator.

Each factor gets a 0-100 sub-score from a simple, documented rule and a
fixed weight. The overall score is the weighted average, rounded to the
nearest 5 to avoid implying false precision. This is an application-
generated indicator, not a credit score or professional assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.models.financial_profile import FinancialProfile
from app.services import analytics_service

BANDS = [
    (0, 30, "Needs attention", "#FF6B7A"),
    (31, 60, "Fair", "#F5B84B"),
    (61, 80, "Good", "#7C8CFF"),
    (81, 100, "Excellent", "#3EE6B0"),
]


@dataclass
class HealthFactor:
    key: str
    name: str
    weight: float
    score: float
    value_text: str
    rule: str
    tip: str
    estimated: bool = False


@dataclass
class HealthReport:
    score: int | None
    band: str
    color: str
    factors: list[HealthFactor] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    months_analyzed: int = 0

    @property
    def available(self) -> bool:
        return self.score is not None


def _clamp(value: float) -> float:
    return float(max(0.0, min(100.0, value)))


def band_for(score: int) -> tuple[str, str]:
    for low, high, label, color in BANDS:
        if low <= score <= high:
            return label, color
    return "Needs attention", "#FF6B7A"


def compute_health(df: pd.DataFrame, profile: FinancialProfile | None = None, months: int = 6) -> HealthReport:
    monthly = analytics_service.monthly_overview(df)
    done = analytics_service.completed_months(monthly)
    done = done[done["transactions"] > 0].tail(months) if not done.empty else done
    if done.empty and not monthly.empty:
        done = monthly[monthly["transactions"] > 0].tail(months)
    if done.empty or done["income"].sum() <= 0:
        return HealthReport(
            score=None,
            band="Not enough data",
            color="#8A96B3",
            notes=["Add at least one month of income and expense transactions to calculate a score."],
        )

    notes: list[str] = []
    income = float(done["income"].sum())
    expense = float(done["expense"].sum())
    avg_income = float(done["income"].mean())
    avg_expense = float(done["expense"].mean())
    n = len(done)
    if n < 3:
        notes.append(f"Based on only {n} month(s) of data, so treat the score as a rough first look.")

    factors: list[HealthFactor] = []

    # 1. Savings rate: 30 %+ of income saved earns full marks
    savings_rate = (income - expense) / income * 100
    factors.append(HealthFactor(
        "savings_rate", "Savings rate", 0.20, _clamp(savings_rate / 30 * 100),
        f"{savings_rate:.1f}% of income",
        "Full marks at 30% or more of income saved; zero at 0% or below.",
        "Automate a transfer to savings on salary day so saving happens before spending.",
    ))

    # 2. Expense ratio: 50 % or less is ideal, 100 %+ scores zero
    expense_ratio = expense / income * 100
    factors.append(HealthFactor(
        "expense_ratio", "Expense ratio", 0.15, _clamp((100 - expense_ratio) / 50 * 100),
        f"{expense_ratio:.1f}% of income spent",
        "Full marks at 50% or less of income spent; zero at 100% or more.",
        "Review your two largest categories first; they usually hold the biggest savings.",
    ))

    # 3. Emergency fund: 6 months of expenses earns full marks
    estimated = False
    if profile and profile.emergency_fund is not None:
        fund = float(profile.emergency_fund)
    else:
        fund = max(0.0, float(monthly["net_cash_flow"].sum()))
        estimated = True
        notes.append("Emergency fund not set in Settings, so tracked cash balance is used as an estimate.")
    months_covered = fund / avg_expense if avg_expense > 0 else 6.0
    factors.append(HealthFactor(
        "emergency_fund", "Emergency fund", 0.20, _clamp(months_covered / 6 * 100),
        f"{months_covered:.1f} months of expenses",
        "Full marks at 6 or more months of expenses set aside.",
        "Build toward 6 months of expenses in a liquid account before increasing risky investments.",
        estimated,
    ))

    # 4. Debt burden: EMI/loan payments as share of income; 0 % full marks, 50 %+ zero
    if profile and profile.monthly_debt_payment is not None:
        debt_ratio = float(profile.monthly_debt_payment) / avg_income * 100 if avg_income else 0.0
        debt_estimated = False
    else:
        debt_ratio = 0.0
        debt_estimated = True
        notes.append("Monthly debt payments not set in Settings, so debt burden assumes no loans.")
    factors.append(HealthFactor(
        "debt_burden", "Debt burden", 0.15, _clamp((50 - debt_ratio) / 50 * 100),
        f"{debt_ratio:.1f}% of income on EMIs",
        "Full marks with no EMIs; zero when EMIs take 50% or more of income.",
        "Prioritise repaying high-interest debt such as credit cards and personal loans.",
        debt_estimated,
    ))

    # 5. Investment consistency: share of months with any investment
    invest_months = int((done["investment"] > 0).sum())
    factors.append(HealthFactor(
        "investment_consistency", "Investment consistency", 0.10, _clamp(invest_months / n * 100),
        f"Invested in {invest_months} of {n} months",
        "Share of analysed months that include at least one investment.",
        "A small monthly SIP done every month beats a large one done occasionally.",
    ))

    # 6. Cash-flow stability: share of months with positive net cash flow
    positive = int((done["income"] - done["expense"] > 0).sum())
    factors.append(HealthFactor(
        "cash_flow_stability", "Cash-flow stability", 0.10, _clamp(positive / n * 100),
        f"{positive} of {n} months cash-flow positive",
        "Share of analysed months where income exceeded expenses.",
        "Keep a buffer for irregular costs (insurance, travel) so they don't create negative months.",
    ))

    # 7. Spending stability: coefficient of variation of monthly expenses
    cv = float(done["expense"].std(ddof=0) / avg_expense) if avg_expense > 0 and n > 1 else 0.0
    factors.append(HealthFactor(
        "spending_stability", "Spending stability", 0.10, _clamp((0.6 - cv) / 0.6 * 100),
        f"Monthly spend varies ±{cv * 100:.0f}%",
        "Full marks when monthly spending barely varies; zero at ±60% variation or more.",
        "Spread big annual expenses across months with a sinking fund.",
    ))

    raw = sum(f.score * f.weight for f in factors) / sum(f.weight for f in factors)
    score = int(np.clip(round(raw / 5) * 5, 0, 100))
    label, color = band_for(score)
    for f in factors:
        f.score = round(f.score)
    return HealthReport(score=score, band=label, color=color, factors=factors, notes=notes, months_analyzed=n)


def weakest_factors(report: HealthReport, count: int = 2) -> list[HealthFactor]:
    return sorted(report.factors, key=lambda f: f.score)[:count]
