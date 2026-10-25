"""
Assembles everything the dashboard and AI pages need in one pass, so a
page load reads MongoDB once and every widget uses the same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.ai.cashflow_forecast import CashflowForecast, forecast_cashflow
from app.ai.financial_twin import FinancialTwin
from app.ai.spending_predictor import SpendingPrediction, predict_next_month
from app.database import insight_repository
from app.models.budget import BudgetStatus
from app.models.financial_profile import FinancialProfile
from app.services import analytics_service, budget_service, fraud_service
from app.services.analytics_service import FinancialSummary
from app.services.health_service import HealthReport, compute_health
from app.services.transaction_service import transactions_dataframe
from app.utils.logger import get_logger

log = get_logger("insights")


@dataclass
class DashboardContext:
    df: pd.DataFrame
    period: str
    summary: FinancialSummary
    all_time: FinancialSummary
    monthly: pd.DataFrame
    categories: pd.DataFrame
    health: HealthReport
    profile: FinancialProfile
    budgets: list[BudgetStatus] = field(default_factory=list)
    budget_alerts: list[dict[str, Any]] = field(default_factory=list)
    prediction: SpendingPrediction | None = None
    open_alerts: int = 0
    insights: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return not self.df.empty


def build_dashboard(user_id: str, period: str = "6M", with_ml: bool = True) -> DashboardContext:
    df = transactions_dataframe(user_id)
    profile = insight_repository.get_profile(user_id)
    period_df = analytics_service.filter_period(df, period)
    monthly_all = analytics_service.monthly_overview(df)
    monthly = analytics_service.monthly_overview(period_df) if not period_df.empty else monthly_all.head(0)
    budgets = budget_service.budget_status(user_id, df)
    budget_alerts = budget_service.budget_alerts(budgets)
    prediction = None
    if with_ml and not df.empty:
        try:
            prediction = predict_next_month(df)
        except Exception as exc:  # ML must never break the dashboard
            log.warning("Spending prediction failed: %s", exc)
    open_alerts = fraud_service.open_alert_count(user_id) if not df.empty else 0
    twin = FinancialTwin.from_dataframe(df, profile)
    return DashboardContext(
        df=df,
        period=period,
        summary=analytics_service.compute_summary(period_df),
        all_time=analytics_service.compute_summary(df),
        monthly=monthly,
        categories=analytics_service.category_breakdown(period_df),
        health=twin.health or compute_health(df, profile),
        profile=profile,
        budgets=budgets,
        budget_alerts=budget_alerts,
        prediction=prediction,
        open_alerts=open_alerts,
        insights=twin.key_insights(prediction, open_alerts, budget_alerts),
    )


def build_forecast(user_id: str, horizon: int = 6) -> tuple[CashflowForecast | None, SpendingPrediction | None, pd.DataFrame]:
    df = transactions_dataframe(user_id)
    forecast = forecast_cashflow(df, horizon, user_id=user_id)
    prediction = predict_next_month(df) if not df.empty else None
    if forecast is not None:
        insight_repository.save_prediction(user_id, "cashflow", forecast.to_dict())
    if prediction is not None:
        insight_repository.save_prediction(user_id, "spending", prediction.to_dict())
    return forecast, prediction, df


def notifications(user_id: str) -> list[dict[str, Any]]:
    """Items for the header notification panel."""
    items: list[dict[str, Any]] = []
    try:
        df = transactions_dataframe(user_id)
        statuses = budget_service.budget_status(user_id, df)
        for alert in budget_service.budget_alerts(statuses):
            items.append({**alert, "icon": "account_balance_wallet", "link": "/budget"})
        count = fraud_service.open_alert_count(user_id)
        if count:
            items.append({"level": "warning", "icon": "policy", "link": "/fraud",
                          "title": f"{count} unusual transaction(s)",
                          "text": "Review flagged transactions on the Fraud Detection page."})
        if df.empty:
            items.append({"level": "info", "icon": "rocket_launch", "link": "/transactions",
                          "title": "Get started", "text": "Add your first transaction or load demo data."})
    except Exception as exc:
        log.warning("Notifications unavailable: %s", exc)
    return items
