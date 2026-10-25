"""Runs anomaly detection and keeps fraud_alerts in sync for a user."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.ai.fraud_detector import NORMAL, AnomalyReport, detect_anomalies
from app.database import insight_repository
from app.services.transaction_service import transactions_dataframe


def scan_user(user_id: str, df: pd.DataFrame | None = None) -> AnomalyReport:
    """Detect anomalies and upsert alerts. Reviewed/dismissed alerts keep their status."""
    df = df if df is not None else transactions_dataframe(user_id)
    report = detect_anomalies(df, user_id=user_id)
    flagged_ids = set()
    for result in report.results:
        if result.label != NORMAL:
            flagged_ids.add(result.transaction_id)
            insight_repository.upsert_fraud_alert(user_id, result.transaction_id, result.to_alert())
    insight_repository.remove_stale_alerts(user_id, flagged_ids)
    insight_repository.save_prediction(user_id, "anomaly_scan", {
        "method": report.method, "analyzed": report.analyzed, "flagged": report.flagged,
    })
    return report


def get_alerts(user_id: str, status: str | None = None) -> list[dict[str, Any]]:
    alerts = insight_repository.get_fraud_alerts(user_id, status)
    for a in alerts:
        a["id"] = str(a.pop("_id"))
    return alerts


def set_status(user_id: str, alert_id: str, status: str) -> bool:
    return insight_repository.set_fraud_alert_status(user_id, alert_id, status)


def open_alert_count(user_id: str) -> int:
    return insight_repository.count_open_alerts(user_id)
