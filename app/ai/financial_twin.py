"""
AI Financial Twin: a data-driven model of one user's finances.

The twin summarises *actual* transaction history (and optional profile
facts) into a state, then simulates what-if scenarios on top of it:
affordability, salary or expense changes, savings over time, and goal-
based investing. Every answer:
- uses only the user's real data (nothing is invented),
- lists what data is missing when it matters,
- states its assumptions, and
- presents results as estimates, not guarantees.

The twin is deterministic and works offline. The Copilot can optionally
pass the twin's context and analysis to an LLM for a conversational reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.ai.wealth_forecast import loan_emi, required_monthly_investment
from app.models.financial_profile import FinancialProfile
from app.services import analytics_service
from app.services.health_service import HealthReport, compute_health
from app.utils.formatters import format_inr, format_inr_compact

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "eighteen": 18, "twenty": 20,
}
UNIT_MULTIPLIERS = {
    "k": 1e3, "thousand": 1e3, "l": 1e5, "lac": 1e5, "lacs": 1e5, "lakh": 1e5, "lakhs": 1e5,
    "cr": 1e7, "crore": 1e7, "crores": 1e7,
}
AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|lac|crores?|cr|thousand|k|l)?\b(?!\s*(?:%|percent|years?|yrs?|months?))",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", re.IGNORECASE)
DURATION_RE = re.compile(r"(\d+(?:\.\d+)?|" + "|".join(WORD_NUMBERS) + r")\s*(years?|yrs?|months?)", re.IGNORECASE)

DISCLAIMER = "Estimates based on your recorded data and stated assumptions; not financial advice."


# ---------------------------------------------------------------- parsing
def parse_amounts(text: str) -> list[float]:
    """Extract rupee amounts like ₹15 lakh, 2.5L, 10,000, 50k, 1 crore."""
    amounts = []
    for match in AMOUNT_RE.finditer(text):
        number, unit = match.group(1), (match.group(2) or "").lower()
        try:
            value = float(number.replace(",", ""))
        except ValueError:
            continue
        has_currency = bool(re.match(r"\s*(₹|rs|inr)", match.group(0), re.IGNORECASE))
        if not unit and not has_currency and value < 100:
            continue  # bare small numbers are usually durations/counts
        amounts.append(value * UNIT_MULTIPLIERS.get(unit, 1.0))
    return amounts


def parse_percent(text: str) -> float | None:
    match = PERCENT_RE.search(text)
    return float(match.group(1)) if match else None


def parse_months(text: str) -> int | None:
    lowered = text.lower()
    if "next year" in lowered or "a year" in lowered or "one year" in lowered:
        return 12
    if "next month" in lowered:
        return 1
    match = DURATION_RE.search(lowered)
    if not match:
        return None
    raw, unit = match.group(1), match.group(2)
    value = WORD_NUMBERS.get(raw, None) or float(raw)
    return int(round(value * 12)) if unit.startswith("y") else int(round(value))


# ---------------------------------------------------------------- state
@dataclass
class TwinAnswer:
    title: str
    text: str
    intent: str
    assumptions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def as_markdown(self) -> str:
        parts = [self.text]
        if self.missing:
            parts.append("**Missing data:** " + "; ".join(self.missing))
        if self.assumptions:
            parts.append("**Assumptions:**\n\n" + "\n".join(f"- {a}" for a in self.assumptions))
        parts.append(f"_{DISCLAIMER}_")
        return "\n\n".join(parts)


@dataclass
class TwinState:
    months_of_data: int = 0
    avg_income: float = 0.0
    avg_expense: float = 0.0
    avg_investment: float = 0.0
    income_std: float = 0.0
    savings_std: float = 0.0
    current_balance: float = 0.0
    total_invested: float = 0.0
    savings_rate: float = 0.0
    emergency_fund: float | None = None
    monthly_debt: float | None = None
    expected_return: float = 10.0
    goals: list[dict[str, Any]] = field(default_factory=list)
    top_categories: list[tuple[str, float]] = field(default_factory=list)
    category_changes: dict[str, float] = field(default_factory=dict)
    health_score: int | None = None
    health_band: str = ""

    @property
    def avg_savings(self) -> float:
        """Income minus expenses (part of this is invested)."""
        return self.avg_income - self.avg_expense

    @property
    def monthly_surplus(self) -> float:
        """Cash left after expenses and investments."""
        return self.avg_income - self.avg_expense - self.avg_investment

    @property
    def has_data(self) -> bool:
        return self.months_of_data > 0 and self.avg_income > 0


class FinancialTwin:
    """Simulates scenarios from the user's own financial state."""

    def __init__(self, state: TwinState, health: HealthReport | None = None) -> None:
        self.state = state
        self.health = health

    # ---------------------------------------------------------- construction
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, profile: FinancialProfile | None = None) -> "FinancialTwin":
        monthly = analytics_service.monthly_overview(df)
        done = analytics_service.completed_months(monthly)
        done = done[done["transactions"] > 0].tail(6) if not done.empty else done
        if done.empty and not monthly.empty:
            done = monthly[monthly["transactions"] > 0].tail(6)
        state = TwinState(expected_return=profile.expected_annual_return if profile else 10.0)
        if profile:
            state.emergency_fund = profile.emergency_fund
            state.monthly_debt = profile.monthly_debt_payment
            state.goals = [g.to_dict() for g in profile.goals]
        health = None
        if not done.empty:
            state.months_of_data = len(done)
            state.avg_income = float(done["income"].mean())
            state.avg_expense = float(done["expense"].mean())
            state.avg_investment = float(done["investment"].mean())
            state.income_std = float(done["income"].std(ddof=0))
            state.savings_std = float((done["income"] - done["expense"]).std(ddof=0))
            state.current_balance = float(monthly["net_cash_flow"].sum())
            state.total_invested = float(monthly["investment"].sum())
            state.savings_rate = (state.avg_savings / state.avg_income * 100) if state.avg_income else 0.0
            recent_months = done["month"].tolist()
            exp = df[(df["transaction_type"] == "Expense") & (df["month"].isin(recent_months))]
            if not exp.empty:
                cats = exp.groupby("category")["amount"].sum() / len(recent_months)
                state.top_categories = [(k, float(v)) for k, v in cats.sort_values(ascending=False).items()]
            state.category_changes = analytics_service.month_over_month(df)
            health = compute_health(df, profile)
            state.health_score = health.score
            state.health_band = health.band
        return cls(state, health)

    # ---------------------------------------------------------- simulation
    def simulate(
        self,
        months: int,
        income_change_pct: float = 0.0,
        expense_change_abs: float = 0.0,
        expense_change_pct: float = 0.0,
        extra_monthly_investment: float = 0.0,
        one_time_expense: float = 0.0,
    ) -> dict[str, Any]:
        s = self.state
        income = s.avg_income * (1 + income_change_pct / 100)
        expense = s.avg_expense * (1 + expense_change_pct / 100) + expense_change_abs
        investment = s.avg_investment + extra_monthly_investment
        r = s.expected_return / 100 / 12
        cash = s.current_balance - one_time_expense
        invested = s.total_invested
        timeline = []
        for m in range(1, months + 1):
            cash += income - expense - investment
            invested = invested * (1 + r) + investment
            timeline.append({"month": m, "cash": round(cash), "invested": round(invested),
                             "net_worth": round(cash + invested)})
        surplus = income - expense - investment
        return {
            "monthly_income": round(income),
            "monthly_expense": round(expense),
            "monthly_investment": round(investment),
            "monthly_surplus": round(surplus),
            "savings_rate": round((income - expense) / income * 100, 1) if income else 0.0,
            "timeline": timeline,
            "final_cash": timeline[-1]["cash"] if timeline else round(cash),
            "final_invested": timeline[-1]["invested"] if timeline else round(invested),
            "final_net_worth": timeline[-1]["net_worth"] if timeline else round(cash + invested),
        }

    def baseline_vs(self, months: int, **changes: float) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.simulate(months), self.simulate(months, **changes)

    # ---------------------------------------------------------- scenarios
    def affordability(self, price: float, months: int = 12, loan_rate: float = 9.0,
                      loan_years: int = 5, down_payment_pct: float = 20.0) -> TwinAnswer:
        s = self.state
        sim = self.simulate(months)
        reserve_note = None
        if s.emergency_fund is None:
            reserve = 3 * s.avg_expense
            reserve_note = f"{format_inr(reserve)} (3 months of expenses) is kept aside as a safety buffer."
        else:
            reserve = 0.0
        projected_cash = sim["final_cash"]
        usable = projected_cash - reserve
        down_payment = price * down_payment_pct / 100
        loan = price - down_payment
        emi = loan_emi(loan, loan_rate, loan_years)
        emi_share = emi / s.avg_income * 100 if s.avg_income else 100.0
        existing_debt = s.monthly_debt or 0.0
        total_emi_share = (emi + existing_debt) / s.avg_income * 100 if s.avg_income else 100.0
        surplus_after_emi = s.monthly_surplus - emi
        needed_per_month = max(0.0, (price + reserve - s.current_balance) / months)

        if usable >= price:
            verdict = "Likely affordable in cash"
            detail = (f"Your twin projects about **{format_inr(projected_cash)}** in tracked cash in {months} months, "
                      f"enough to pay **{format_inr(price)}** outright and keep your buffer.")
        elif usable >= down_payment and emi_share <= 15 and total_emi_share <= 40 and surplus_after_emi > 0:
            verdict = "Affordable with a loan"
            detail = (f"You'd likely have the **{format_inr(down_payment)}** down payment ({down_payment_pct:.0f}%). "
                      f"A loan of {format_inr(loan)} at {loan_rate:.0f}% for {loan_years} years means an EMI of about "
                      f"**{format_inr(emi)}/month** ({emi_share:.0f}% of income), leaving roughly "
                      f"{format_inr(surplus_after_emi)} of monthly surplus.")
        elif usable >= down_payment and emi_share <= 25 and surplus_after_emi > 0:
            verdict = "Possible, but a stretch"
            detail = (f"The down payment looks reachable, but an EMI of about **{format_inr(emi)}/month** would take "
                      f"{emi_share:.0f}% of your income (a common comfort limit for vehicle loans is 10–15%).")
        else:
            verdict = "Not affordable on current numbers"
            detail = (f"Projected usable cash in {months} months is about **{format_inr(max(usable, 0))}**, and an EMI of "
                      f"{format_inr(emi)} would leave {format_inr(surplus_after_emi)} a month. To buy it in cash you'd need "
                      f"to set aside about **{format_inr(needed_per_month)}/month**, versus your current surplus of "
                      f"{format_inr(s.monthly_surplus)}.")
        text = (f"### {verdict}\n\n{detail}\n\n"
                f"| | Amount |\n|---|---|\n"
                f"| Average monthly income | {format_inr(s.avg_income)} |\n"
                f"| Average monthly expenses | {format_inr(s.avg_expense)} |\n"
                f"| Monthly surplus after investing | {format_inr(s.monthly_surplus)} |\n"
                f"| Tracked cash today | {format_inr(s.current_balance)} |\n"
                f"| Projected cash in {months} months | {format_inr(projected_cash)} |\n"
                f"| Estimated EMI (if financed) | {format_inr(emi)} |")
        assumptions = [
            f"Income and spending continue at your {s.months_of_data}-month averages.",
            f"Loan option: {down_payment_pct:.0f}% down, {loan_rate:.0f}% interest, {loan_years}-year tenure.",
            "Existing investments are not sold to fund the purchase.",
        ]
        if reserve_note:
            assumptions.append(reserve_note)
        missing = []
        if s.monthly_debt is None:
            missing.append("existing loan EMIs (set them in Settings for a more accurate check)")
        return TwinAnswer("Affordability check", text, "affordability", assumptions, missing,
                          {"verdict": verdict, "emi": round(emi), "projected_cash": projected_cash, "price": price})

    def income_change(self, pct: float, months: int = 12) -> TwinAnswer:
        base, new = self.baseline_vs(months, income_change_pct=pct)
        s = self.state
        diff = new["final_net_worth"] - base["final_net_worth"]
        direction = "increases" if pct >= 0 else "decreases"
        text = (f"### If your income {direction} by {abs(pct):.0f}%\n\n"
                f"Monthly income moves from **{format_inr(s.avg_income)}** to **{format_inr(new['monthly_income'])}**. "
                f"With spending unchanged, your savings rate goes from {s.savings_rate:.1f}% to "
                f"**{new['savings_rate']:.1f}%**.\n\n"
                f"Over {months} months your projected net worth (cash + investments) changes by about "
                f"**{format_inr(diff, sign=True)}**, to {format_inr(new['final_net_worth'])}.\n\n"
                f"Tip: decide in advance how much of any raise goes to investments, so lifestyle costs "
                f"don't absorb it.")
        return TwinAnswer("Income scenario", text, "income_change",
                          [f"Expenses stay at your {s.months_of_data}-month average.",
                           f"Investments grow at an assumed {s.expected_return:.0f}% a year."],
                          [], {"baseline": base, "scenario": new})

    def expense_change(self, amount: float | None = None, pct: float | None = None, months: int = 12) -> TwinAnswer:
        s = self.state
        changes = {"expense_change_abs": amount or 0.0, "expense_change_pct": pct or 0.0}
        base, new = self.baseline_vs(months, **changes)
        delta = new["monthly_expense"] - s.avg_expense
        label = format_inr(abs(amount)) if amount else f"{abs(pct or 0):.0f}%"
        direction = "increase" if delta >= 0 else "decrease"
        warning = ""
        if new["monthly_surplus"] < 0:
            runway = s.current_balance / abs(new["monthly_surplus"]) if s.current_balance > 0 else 0
            warning = (f"\n\n**Warning:** your monthly surplus turns negative ({format_inr(new['monthly_surplus'])}). "
                       f"At that rate tracked cash would last about {runway:.0f} months unless you reduce investments "
                       f"or other spending.")
        text = (f"### If expenses {direction} by {label}\n\n"
                f"Monthly expenses go from **{format_inr(s.avg_expense)}** to **{format_inr(new['monthly_expense'])}**. "
                f"Your savings rate moves from {s.savings_rate:.1f}% to **{new['savings_rate']:.1f}%**, and the "
                f"monthly surplus after investing becomes **{format_inr(new['monthly_surplus'])}**.\n\n"
                f"Over {months} months that's a difference of about "
                f"**{format_inr(new['final_net_worth'] - base['final_net_worth'], sign=True)}** in net worth.{warning}")
        return TwinAnswer("Expense scenario", text, "expense_change",
                          [f"Income stays at your {s.months_of_data}-month average.",
                           "Investment contributions stay the same."], [], {"baseline": base, "scenario": new})

    def savings_projection(self, months: int = 12) -> TwinAnswer:
        s = self.state
        expected = s.avg_savings * months
        spread = s.savings_std * np.sqrt(months) * 1.28
        invest_part = s.avg_investment * months
        text = (f"### Projected savings over {months} months\n\n"
                f"At your current pace you could save about **{format_inr(expected)}** "
                f"(likely range {format_inr(max(0, expected - spread))} to {format_inr(expected + spread)}).\n\n"
                f"Of that, about {format_inr(invest_part)} goes into investments at your average of "
                f"{format_inr(s.avg_investment)}/month, and {format_inr(expected - invest_part)} stays as cash.\n\n"
                f"Your current savings rate is **{s.savings_rate:.1f}%**.")
        return TwinAnswer("Savings projection", text, "savings",
                          [f"Based on your last {s.months_of_data} completed month(s).",
                           "Savings = income minus expenses; range reflects your month-to-month variation."],
                          [], {"expected": round(expected)})

    def goal_investment(self, target: float | None, months: int | None, goal_name: str | None = None) -> TwinAnswer:
        s = self.state
        missing = []
        if target is None and s.goals:
            g = s.goals[0]
            target, months, goal_name = g["target_amount"], int(round(g["target_years"] * 12)), g["name"]
        if target is None:
            missing.append("goal amount (e.g. 'reach ₹50 lakh in 10 years') or a goal saved in Settings")
        if months is None:
            missing.append("timeline for the goal")
        if missing:
            return TwinAnswer("Goal planning", "I need a little more information to plan this goal.",
                              "goal", [], missing)
        years = months / 12
        rates = [max(s.expected_return - 3, 0), s.expected_return, s.expected_return + 3]
        needed = [required_monthly_investment(target, years, r) for r in rates]
        gap = needed[1] - s.avg_investment
        name = f" for **{goal_name}**" if goal_name else ""
        if gap <= 0:
            fit = f"Your current average investment of {format_inr(s.avg_investment)}/month already covers this."
        elif gap <= s.monthly_surplus:
            fit = (f"That's {format_inr(gap)} more than you invest today, which fits within your monthly surplus "
                   f"of {format_inr(s.monthly_surplus)}.")
        else:
            fit = (f"That's {format_inr(gap)} more than you invest today and more than your monthly surplus of "
                   f"{format_inr(s.monthly_surplus)}, so you may need a longer timeline, a step-up plan, or lower expenses.")
        text = (f"### Investing to reach {format_inr_compact(target)} in {years:g} years{name}\n\n"
                f"You'd need to invest about **{format_inr(needed[1])}/month** at an assumed "
                f"{rates[1]:.0f}% annual return.\n\n"
                f"| Assumed return | Monthly investment needed |\n|---|---|\n"
                + "\n".join(f"| {r:.0f}% | {format_inr(n)} |" for r, n in zip(rates, needed))
                + f"\n\n{fit}")
        return TwinAnswer("Goal planning", text, "goal",
                          ["Monthly compounding; no step-up; taxes and fees excluded.",
                           "Existing investments are not counted toward this goal."],
                          [], {"monthly_needed": round(needed[1])})

    def spending_breakdown(self) -> TwinAnswer:
        s = self.state
        if not s.top_categories:
            return TwinAnswer("Spending", "No expense transactions found yet.", "spending", [], ["expense transactions"])
        rows = "\n".join(
            f"| {cat} | {format_inr(val)} | {val / s.avg_expense * 100:.0f}% |" for cat, val in s.top_categories[:6]
        )
        rising = sorted(((c, v) for c, v in s.category_changes.items() if v > 0), key=lambda kv: -kv[1])[:2]
        rising_text = ""
        if rising:
            rising_text = "\n\nRising fastest vs the previous month: " + ", ".join(
                f"**{c}** (+{format_inr(v)})" for c, v in rising) + "."
        top, top_val = s.top_categories[0]
        text = (f"### Where your money goes (monthly average)\n\n| Category | Avg / month | Share |\n|---|---|---|\n{rows}"
                f"{rising_text}\n\nCutting **{top}** by 10% would free about {format_inr(top_val * 0.1)} a month "
                f"({format_inr(top_val * 1.2)} a year).")
        return TwinAnswer("Spending breakdown", text, "spending",
                          [f"Averages over your last {s.months_of_data} completed month(s)."])

    def health_answer(self) -> TwinAnswer:
        h = self.health
        if not h or not h.available:
            return TwinAnswer("Financial health", "There isn't enough data for a health score yet.", "health", [],
                              ["at least one month of income and expenses"])
        weakest = sorted(h.factors, key=lambda f: f.score)[:2]
        tips = "\n".join(f"- **{f.name}** ({f.value_text}): {f.tip}" for f in weakest)
        text = (f"### Health indicator: about {h.score}/100 ({h.band})\n\n"
                f"Your two weakest factors and what would help most:\n\n{tips}\n\n"
                f"See the Financial Health page for the full breakdown.")
        return TwinAnswer("Financial health", text, "health", h.notes)

    def emergency_answer(self) -> TwinAnswer:
        s = self.state
        target = 6 * s.avg_expense
        if s.emergency_fund is None:
            have, missing = max(0.0, s.current_balance), ["emergency fund amount (set it in Settings)"]
        else:
            have, missing = s.emergency_fund, []
        gap = max(0.0, target - have)
        months_to_fill = gap / s.monthly_surplus if s.monthly_surplus > 0 else None
        fill = (f"At your current surplus that takes about **{months_to_fill:.0f} months**."
                if months_to_fill else "Your current monthly surplus isn't positive, so this needs a budget change first.")
        text = (f"### Emergency fund\n\nA common target is 6 months of expenses: **{format_inr(target)}**. "
                f"You have about {format_inr(have)} ({have / s.avg_expense if s.avg_expense else 0:.1f} months).\n\n"
                + (f"Gap: **{format_inr(gap)}**. {fill}" if gap > 0 else "You've reached the 6-month target."))
        return TwinAnswer("Emergency fund", text, "emergency", [], missing)

    def overview(self) -> TwinAnswer:
        s = self.state
        text = (f"### Your financial twin at a glance\n\n"
                f"- Average monthly income: **{format_inr(s.avg_income)}**\n"
                f"- Average monthly expenses: **{format_inr(s.avg_expense)}**\n"
                f"- Average monthly investing: **{format_inr(s.avg_investment)}**\n"
                f"- Savings rate: **{s.savings_rate:.1f}%**\n"
                f"- Tracked cash: **{format_inr(s.current_balance)}**, total invested: **{format_inr(s.total_invested)}**\n"
                + (f"- Health indicator: **{s.health_score}/100** ({s.health_band})\n" if s.health_score is not None else "")
                + "\nTry asking: *Can I afford a ₹15 lakh car next year?*, *What if my salary increases by 20%?*, "
                  "*How much can I save in one year?*, *What if my expenses increase by ₹10,000?*, or "
                  "*How much should I invest monthly to reach ₹50 lakh in 10 years?*")
        return TwinAnswer("Overview", text, "overview", [f"Averages over your last {s.months_of_data} month(s)."])

    # ---------------------------------------------------------- router
    def answer(self, question: str) -> TwinAnswer:
        q = (question or "").strip()
        lowered = q.lower()
        if not self.state.has_data:
            return TwinAnswer(
                "Not enough data",
                "Your twin doesn't have enough financial history yet to answer that reliably.",
                "no_data", [],
                ["income and expense transactions (add them, upload a statement, or load demo data)"],
            )
        amounts = parse_amounts(q)
        pct = parse_percent(q)
        months = parse_months(q)

        if re.search(r"\b(afford|buy|purchase|get a)\b", lowered) and amounts:
            return self.affordability(max(amounts), months or 12)
        if re.search(r"\b(salary|income|raise|hike|increment|pay)\b", lowered) and (pct is not None or amounts):
            if pct is None and amounts and self.state.avg_income:
                pct = amounts[0] / self.state.avg_income * 100
            sign = -1 if re.search(r"\b(decrease|drop|cut|fall|reduce|lose|loss)\b", lowered) else 1
            return self.income_change(sign * (pct or 0), months or 12)
        if re.search(r"\b(expense|expenses|spending|spend|costs?|rent|emi)\b", lowered) and \
                re.search(r"\b(increase|rise|go up|goes up|more|decrease|reduce|cut|drop|less|lower)\b", lowered) and \
                (pct is not None or amounts):
            sign = -1 if re.search(r"\b(decrease|reduce|cut|drop|less|lower)\b", lowered) else 1
            if amounts:
                return self.expense_change(amount=sign * amounts[0], months=months or 12)
            return self.expense_change(pct=sign * (pct or 0), months=months or 12)
        if re.search(r"\binvest\b", lowered) and re.search(r"\b(goal|reach|target|corpus|accumulate|build)\b", lowered) \
                or re.search(r"how much should i invest", lowered):
            return self.goal_investment(max(amounts) if amounts else None, months)
        if re.search(r"\b(save|saving|savings)\b", lowered) and (months or "how much" in lowered):
            return self.savings_projection(months or 12)
        if re.search(r"overspend|spend(ing)? (the )?most|top categor|where .*(money|spend)|biggest expense|cut (back|down)|category", lowered):
            return self.spending_breakdown()
        if re.search(r"\b(health|score|doing financially|how am i doing)\b", lowered):
            return self.health_answer()
        if re.search(r"\bemergency\b", lowered):
            return self.emergency_answer()
        return self.overview()

    # ---------------------------------------------------------- context & insights
    def context_summary(self) -> str:
        """Plain-text financial context for an LLM. Contains no personal identifiers."""
        s = self.state
        lines = [
            f"Months of data analysed: {s.months_of_data}",
            f"Average monthly income: {format_inr(s.avg_income)}",
            f"Average monthly expenses: {format_inr(s.avg_expense)}",
            f"Average monthly investments: {format_inr(s.avg_investment)}",
            f"Savings rate: {s.savings_rate:.1f}%",
            f"Monthly surplus after investing: {format_inr(s.monthly_surplus)}",
            f"Tracked cash balance: {format_inr(s.current_balance)}",
            f"Total invested (contributions): {format_inr(s.total_invested)}",
            f"Emergency fund: {format_inr(s.emergency_fund) if s.emergency_fund is not None else 'not provided'}",
            f"Monthly loan EMIs: {format_inr(s.monthly_debt) if s.monthly_debt is not None else 'not provided'}",
            f"Assumed annual investment return: {s.expected_return:.1f}%",
            f"Health indicator: {s.health_score}/100 ({s.health_band})" if s.health_score is not None else "Health indicator: unavailable",
            "Top expense categories (monthly avg): " + ", ".join(f"{c} {format_inr(v)}" for c, v in s.top_categories[:6]),
        ]
        if s.goals:
            lines.append("Goals: " + "; ".join(f"{g['name']} {format_inr(g['target_amount'])} in {g['target_years']:g} years" for g in s.goals))
        return "\n".join(lines)

    def key_insights(self, spending_prediction: Any = None, open_alerts: int = 0,
                     budget_alerts: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
        """Short, data-backed insights for the dashboard."""
        s = self.state
        insights: list[dict[str, str]] = []
        if not s.has_data:
            return [{"tone": "info", "icon": "lightbulb", "title": "Your twin is waiting for data",
                     "text": "Add transactions, upload a bank statement, or load demo data to unlock insights."}]
        if s.savings_rate >= 30:
            insights.append({"tone": "positive", "icon": "savings", "title": f"Strong savings rate: {s.savings_rate:.0f}%",
                             "text": "You keep more than 30% of income. Consider directing extra surplus to goals."})
        elif s.savings_rate >= 10:
            insights.append({"tone": "info", "icon": "savings", "title": f"Savings rate {s.savings_rate:.0f}%",
                             "text": f"Reaching 30% would mean saving {format_inr(s.avg_income * 0.3 - s.avg_savings)} more a month."})
        else:
            insights.append({"tone": "warning", "icon": "savings", "title": f"Low savings rate: {s.savings_rate:.0f}%",
                             "text": "Expenses are using most of your income. Review your largest categories."})
        rising = sorted(((c, v) for c, v in s.category_changes.items() if v > 0), key=lambda kv: -kv[1])
        if rising and rising[0][1] > 500:
            c, v = rising[0]
            insights.append({"tone": "warning", "icon": "trending_up", "title": f"{c} spending rose by {format_inr(v)}",
                             "text": "Compared with the previous month. Check whether this was a one-off."})
        if spending_prediction is not None:
            diff = spending_prediction.predicted - s.avg_expense
            insights.append({"tone": "info", "icon": "insights", "title": f"Estimated spend this month: {format_inr_compact(spending_prediction.predicted)}",
                             "text": f"{'Above' if diff > 0 else 'Below'} your average by {format_inr(abs(diff))} "
                                     f"· method: {spending_prediction.method}."})
        if budget_alerts:
            insights.append({"tone": "negative" if any(a["level"] == "negative" for a in budget_alerts) else "warning",
                             "icon": "account_balance_wallet", "title": budget_alerts[0]["title"],
                             "text": budget_alerts[0]["text"]})
        if open_alerts:
            insights.append({"tone": "warning", "icon": "policy", "title": f"{open_alerts} transaction(s) to review",
                             "text": "Flagged as unusual for your spending pattern. This is not proof of fraud."})
        if s.avg_investment <= 0:
            insights.append({"tone": "info", "icon": "trending_up", "title": "No regular investing detected",
                             "text": "Even a small monthly SIP builds the habit and compounds over time."})
        return insights[:5]
