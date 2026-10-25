"""
Anomaly detection for potentially unusual transactions.

Model: scikit-learn IsolationForest, fitted per user on their own
outgoing transactions (expenses and investments), so "unusual" means
unusual *for this user*. Features cover amount, category, frequency and
timing. A robust (median/MAD) z-score per category adds an interpretable
signal and produces the human-readable reasons shown in the UI.

Labels are "Normal", "Potentially Unusual" and "High Anomaly Risk".
These are statistical flags for review. They do NOT prove fraud.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.config import settings
from app.utils.dates import utcnow
from app.utils.formatters import format_inr
from app.utils.logger import get_logger

log = get_logger("ai.fraud")

MIN_TRANSACTIONS_FOR_MODEL = 30
FEATURES = [
    "log_amount", "robust_z", "category_rarity", "day_of_week", "day_of_month",
    "same_day_count", "days_since_same_category", "share_of_month",
]
NORMAL, UNUSUAL, HIGH = "Normal", "Potentially Unusual", "High Anomaly Risk"


@dataclass
class AnomalyResult:
    transaction_id: str
    date: str
    description: str
    category: str
    amount: float
    label: str
    score: float  # 0-100, higher = more unusual relative to this user's history
    reasons: list[str] = field(default_factory=list)

    def to_alert(self) -> dict[str, Any]:
        return {
            "date": self.date, "description": self.description, "category": self.category,
            "amount": self.amount, "label": self.label, "score": self.score, "reasons": self.reasons,
        }


@dataclass
class AnomalyReport:
    results: list[AnomalyResult]
    method: str
    analyzed: int
    flagged: int

    @property
    def flagged_results(self) -> list[AnomalyResult]:
        return [r for r in self.results if r.label != NORMAL]


def merchant_key(description: str) -> str:
    """Normalize a description to a merchant key: first two alphabetic words."""
    words = [w for w in "".join(ch if ch.isalpha() else " " for ch in str(description).lower()).split() if len(w) > 1]
    return " ".join(words[:2]) or "unknown"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature matrix for outgoing transactions (Expense + Investment)."""
    out = df[df["transaction_type"].isin(["Expense", "Investment"])].copy()
    if out.empty:
        return out
    out = out.sort_values("date").reset_index(drop=True)
    out["log_amount"] = np.log1p(out["amount"])

    # Baselines (median and MAD): the merchant if it repeats (3+ times), otherwise the whole
    # category if it has 3+ transactions, otherwise all outgoing transactions.
    out["merchant"] = out["description"].map(merchant_key)
    merchant_n = out.groupby("merchant")["amount"].transform("count")
    category_n = out.groupby("category")["amount"].transform("count")

    def _mad(series: pd.Series) -> float:
        return float(np.median(np.abs(series - np.median(series))))

    m_med = out.groupby("merchant")["amount"].transform("median")
    m_mad = out.groupby("merchant")["amount"].transform(_mad)
    c_med = out.groupby("category")["amount"].transform("median")
    c_mad = out.groupby("category")["amount"].transform(_mad)
    all_med, all_mad = float(out["amount"].median()), _mad(out["amount"])

    use_merchant = merchant_n >= 3
    use_category = ~use_merchant & (category_n >= 3)
    median = np.where(use_merchant, m_med, np.where(use_category, c_med, all_med))
    mad = np.where(use_merchant, m_mad, np.where(use_category, c_mad, all_mad))
    # Fall back to a share of the median when MAD is 0 (e.g. fixed subscriptions)
    scale = np.where(mad > 0, mad * 1.4826, np.maximum(median * 0.25, 1.0))
    out["robust_z"] = (out["amount"] - median) / scale
    out["category_median"] = median
    out["baseline_is_merchant"] = use_merchant
    out["baseline_is_overall"] = ~use_merchant & ~use_category
    out["category_count"] = category_n

    counts = out["category"].value_counts(normalize=True)
    out["category_rarity"] = 1 - out["category"].map(counts)
    out["day_of_week"] = out["date"].dt.dayofweek
    out["day_of_month"] = out["date"].dt.day
    out["same_day_count"] = out.groupby(out["date"].dt.date)["amount"].transform("count")
    out["days_since_same_category"] = (
        out.groupby("category")["date"].diff().dt.days.fillna(60).clip(upper=60)
    )
    monthly_spend = out.groupby("month")["amount"].transform("sum")
    out["share_of_month"] = out["amount"] / monthly_spend.replace(0, np.nan)
    out["share_of_month"] = out["share_of_month"].fillna(0)
    return out


def _reasons(row: pd.Series, avg_monthly_spend: float) -> list[str]:
    reasons = []
    if row["category_median"] > 0 and row["amount"] >= 3 * row["category_median"] and row["robust_z"] > 3:
        multiple = row["amount"] / row["category_median"]
        if row["baseline_is_merchant"]:
            what = "payment to this merchant"
        elif row["baseline_is_overall"]:
            what = "outgoing transaction"
        else:
            what = f"{row['category']} transaction"
        reasons.append(f"{multiple:.1f}× your typical {what} ({format_inr(row['category_median'])}).")
    if row["category_count"] <= 2:
        reasons.append(f"{row['category']} is a category you rarely spend in.")
    if avg_monthly_spend > 0 and row["amount"] > 0.25 * avg_monthly_spend:
        reasons.append(f"Equals {row['amount'] / avg_monthly_spend * 100:.0f}% of an average month's outgoing spend.")
    if row["same_day_count"] >= 6:
        reasons.append(f"{int(row['same_day_count'])} outgoing transactions on the same day.")
    if not reasons:
        reasons.append("Combination of amount, timing and category differs from your usual pattern.")
    return reasons


def detect_anomalies(df: pd.DataFrame, user_id: str | None = None, save_model: bool = True) -> AnomalyReport:
    feats = build_features(df)
    if feats.empty:
        return AnomalyReport([], "No outgoing transactions", 0, 0)

    avg_monthly_spend = float(feats.groupby("month")["amount"].sum().mean())

    if len(feats) >= MIN_TRANSACTIONS_FOR_MODEL:
        scaler = StandardScaler()
        x = scaler.fit_transform(feats[FEATURES])
        model = IsolationForest(n_estimators=300, contamination=0.02, random_state=42)
        model.fit(x)
        raw = -model.decision_function(x)  # higher = more anomalous
        is_outlier = model.predict(x) == -1
        method = "Isolation Forest + robust z-score"
        if save_model and user_id:
            path = settings.models_dir / "users" / user_id
            path.mkdir(parents=True, exist_ok=True)
            joblib.dump(
                {"model": model, "scaler": scaler, "features": FEATURES, "trained_at": utcnow().isoformat(),
                 "samples": int(len(feats))},
                path / "fraud_model.joblib",
            )
    else:
        raw = feats["robust_z"].clip(lower=0).to_numpy(dtype=float)
        is_outlier = raw > 3.5
        method = "Robust z-score rules (limited history)"

    ranks = pd.Series(raw).rank(pct=True).to_numpy() * 100
    p75_amount = float(feats["amount"].quantile(0.75))
    results: list[AnomalyResult] = []
    for i, row in feats.iterrows():
        z = float(row["robust_z"])
        big = row["category_median"] > 0 and row["amount"] >= 3 * row["category_median"]
        material = row["amount"] >= p75_amount  # ignore tiny amounts, however rare
        if is_outlier[i] and z > 4 and big and ranks[i] >= 98 and row["share_of_month"] > 0.1:
            label = HIGH
        elif not material:
            label = NORMAL
        elif is_outlier[i] and ((z > 3 and big) or (z > 2 and row["share_of_month"] > 0.25)):
            label = UNUSUAL
        elif z > 8 and big:
            label = UNUSUAL
        else:
            label = NORMAL
        results.append(AnomalyResult(
            transaction_id=str(row.get("id", i)),
            date=row["date"].strftime("%Y-%m-%d"),
            description=row.get("description", ""),
            category=row["category"],
            amount=float(row["amount"]),
            label=label,
            score=round(float(ranks[i]), 1),
            reasons=_reasons(row, avg_monthly_spend) if label != NORMAL else [],
        ))
    flagged = sum(1 for r in results if r.label != NORMAL)
    log.info("Anomaly scan: %d analysed, %d flagged (%s)", len(results), flagged, method)
    return AnomalyReport(results, method, len(results), flagged)
