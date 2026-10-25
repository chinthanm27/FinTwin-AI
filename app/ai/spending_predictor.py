"""
Next-month spending prediction.

Approach
--------
Monthly expenses are turned into *scale-free* features (each lag divided
by the user's recent 3-month average), so one model trained on many
synthetic users generalises to any income level. Two candidate models are
trained (Random Forest, Gradient Boosting) and evaluated on a time-based
hold-out (each user's most recent months). The model with the lower MAE
is selected only if it beats both naive baselines (3-month average and
6-month median);
otherwise the baseline itself is used. The bundle is saved with joblib to
trained_models/spending_model.joblib.

Prediction output is an *estimate* with a range derived from the
validation error, never a guarantee.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from app.config import settings
from app.services import analytics_service
from app.services.transaction_service import documents_to_dataframe
from app.utils.dates import month_start, period_key, utcnow
from app.utils.logger import get_logger

log = get_logger("ai.spending")

MODEL_FILE = "spending_model.joblib"
FEATURES = [
    "lag1_ratio", "lag2_ratio", "lag3_ratio", "mean6_ratio", "median6_ratio", "income_ratio",
    "count_ratio", "trend", "volatility", "month_sin", "month_cos",
]
WINDOW = 6
MIN_MONTHS_FOR_MODEL = WINDOW


@dataclass
class SpendingPrediction:
    month: str
    predicted: float
    low: float
    high: float
    method: str
    baseline: float
    history_months: int
    category_forecast: dict[str, float] = field(default_factory=dict)
    model_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month, "predicted": self.predicted, "low": self.low, "high": self.high,
            "method": self.method, "baseline": self.baseline, "history_months": self.history_months,
            "category_forecast": self.category_forecast, "model_metrics": self.model_metrics,
        }


def _feature_row(exp: np.ndarray, inc: np.ndarray, cnt: np.ndarray, target_month: int) -> dict[str, float] | None:
    """Build scale-free features from the 6 months preceding the target month."""
    base = float(np.mean(exp[-3:]))
    if base <= 0:
        return None
    count_base = float(np.mean(cnt[-3:])) or 1.0
    return {
        "lag1_ratio": exp[-1] / base,
        "lag2_ratio": exp[-2] / base,
        "lag3_ratio": exp[-3] / base,
        "mean6_ratio": float(np.mean(exp)) / base,
        "median6_ratio": float(np.median(exp)) / base,
        "income_ratio": inc[-1] / base,
        "count_ratio": cnt[-1] / count_base,
        "trend": (exp[-1] - exp[-3]) / base,
        "volatility": float(np.std(exp)) / base,
        "month_sin": float(np.sin(2 * np.pi * target_month / 12)),
        "month_cos": float(np.cos(2 * np.pi * target_month / 12)),
    }


def build_training_frame(monthly: pd.DataFrame, group: str = "user") -> pd.DataFrame:
    """Rolling windows over one user's completed monthly series -> feature rows with target ratio."""
    rows = []
    exp = monthly["expense"].to_numpy(dtype=float)
    inc = monthly["income"].to_numpy(dtype=float)
    cnt = monthly["transactions"].to_numpy(dtype=float)
    months = monthly["month"].tolist()
    for t in range(WINDOW, len(monthly)):
        target_month = int(months[t][5:7])
        feats = _feature_row(exp[t - WINDOW:t], inc[t - WINDOW:t], cnt[t - WINDOW:t], target_month)
        if feats is None:
            continue
        base = float(np.mean(exp[t - 3:t]))
        rows.append({**feats, "target_ratio": exp[t] / base, "group": group, "position": t, "base": base})
    return pd.DataFrame(rows)


def train_global_model(population: list[dict[str, Any]], holdout_months: int = 3) -> dict[str, Any]:
    """Train and evaluate candidate models on a synthetic multi-user population."""
    frames = []
    df_all = pd.DataFrame(population)
    for user_id, user_rows in df_all.groupby("user_id"):
        user_df = documents_to_dataframe(user_rows.drop(columns=["user_id"]).to_dict("records"))
        monthly = analytics_service.completed_months(analytics_service.monthly_overview(user_df))
        frame = build_training_frame(monthly, str(user_id))
        if not frame.empty:
            frame["is_test"] = frame["position"] >= frame["position"].max() - holdout_months + 1
            frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    train, test = data[~data["is_test"]], data[data["is_test"]]
    x_train, y_train = train[FEATURES], train["target_ratio"]
    x_test, y_test = test[FEATURES], test["target_ratio"]

    candidates = {
        # Shallow trees and robust (absolute-error) loss: personal spending is noisy and spiky,
        # and the evaluation metric is MAE.
        "Random Forest": RandomForestRegressor(n_estimators=300, max_depth=5, min_samples_leaf=15, max_features=0.6,
                                               random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(loss="absolute_error", n_estimators=300, max_depth=2,
                                                       learning_rate=0.03, subsample=0.7, random_state=42),
    }
    baseline_mae = float(mean_absolute_error(y_test, np.ones(len(y_test))))
    median_mae = float(mean_absolute_error(y_test, x_test["median6_ratio"]))
    results: dict[str, float] = {
        "3-month average (baseline)": round(baseline_mae, 4),
        "6-month median (baseline)": round(median_mae, 4),
    }
    fitted = {}
    for name, model in candidates.items():
        model.fit(x_train, y_train)
        mae = float(mean_absolute_error(y_test, model.predict(x_test)))
        results[name] = round(mae, 4)
        fitted[name] = model
        log.info("Spending model %s: hold-out MAE (ratio) = %.4f", name, mae)

    best_name = min(fitted, key=lambda n: results[n])
    use_model = results[best_name] < min(baseline_mae, median_mae)
    best_baseline = "6-month median (baseline)" if median_mae < baseline_mae else "3-month average (baseline)"
    chosen_name = best_name if use_model else best_baseline
    if use_model:  # refit the winner on all data
        fitted[best_name].fit(data[FEATURES], data["target_ratio"])

    # MAE in rupees on the hold-out set, for interpretability
    test_base = test["base"].to_numpy()
    if use_model:
        test_pred = fitted[best_name].predict(x_test)
    elif chosen_name.startswith("6-month"):
        test_pred = x_test["median6_ratio"].to_numpy()
    else:
        test_pred = np.ones(len(y_test))
    rupee_mae = float(np.mean(np.abs(test_pred - y_test) * test_base))

    bundle = {
        "model": fitted[best_name] if use_model else None,
        "model_name": chosen_name,
        "features": FEATURES,
        "metrics": {
            "holdout_mae_ratio": results,
            "chosen_mae_ratio": results[chosen_name],
            "holdout_mae_rupees": round(rupee_mae, 0),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "users": int(data["group"].nunique()),
        },
        "trained_at": utcnow().isoformat(),
        "version": 2,
    }
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, settings.models_dir / MODEL_FILE)
    log.info("Saved spending model bundle (%s)", chosen_name)
    return bundle


_cached_bundle: dict[str, Any] | None = None
_load_lock = threading.Lock()


def load_model(auto_train: bool = True) -> dict[str, Any] | None:
    """Load the saved model bundle; train it from synthetic data if missing."""
    if _cached_bundle is not None:
        return _cached_bundle
    with _load_lock:
        return _load_model_locked(auto_train)


def _load_model_locked(auto_train: bool) -> dict[str, Any] | None:
    global _cached_bundle
    if _cached_bundle is not None:
        return _cached_bundle
    path = settings.models_dir / MODEL_FILE
    if path.exists():
        try:
            bundle = joblib.load(path)
            if bundle.get("version") == 2 and bundle.get("features") == FEATURES:
                _cached_bundle = bundle
                return _cached_bundle
            log.info("Spending model is outdated; retraining.")
        except Exception as exc:  # corrupted / incompatible file
            log.warning("Could not load spending model (%s); retraining.", exc)
    if not auto_train:
        return None
    from app.services.demo_data_service import generate_population

    _cached_bundle = train_global_model(generate_population())
    return _cached_bundle


def reset_cache() -> None:
    global _cached_bundle
    _cached_bundle = None


def predict_next_month(df: pd.DataFrame, use_model: bool = True) -> SpendingPrediction | None:
    """Estimate the current month's total expenses from completed months."""
    monthly = analytics_service.monthly_overview(df)
    done = analytics_service.completed_months(monthly)
    done = done[done["transactions"] > 0]
    if done.empty or done["expense"].sum() <= 0:
        return None
    # The target is the first month after the completed history: the current month.
    # Its estimate can be compared with "spent so far" in the UI.
    target_key = period_key(month_start())

    exp = done["expense"].to_numpy(dtype=float)
    history = len(done)
    baseline = float(np.mean(exp[-3:]))
    category_avg = _category_typical(df, done["month"].tail(6).tolist())

    if history < MIN_MONTHS_FOR_MODEL or not use_model:
        spread = float(np.std(exp[-3:])) if history > 1 else baseline * 0.2
        return SpendingPrediction(
            month=target_key, predicted=round(baseline), low=round(max(0, baseline - spread)),
            high=round(baseline + spread), method="Moving average (limited history)", baseline=round(baseline),
            history_months=history, category_forecast=_rounded(category_avg),
        )

    bundle = load_model()
    inc = done["income"].to_numpy(dtype=float)
    cnt = done["transactions"].to_numpy(dtype=float)
    feats = _feature_row(exp[-WINDOW:], inc[-WINDOW:], cnt[-WINDOW:], int(target_key[5:7]))
    if bundle is None or bundle.get("model") is None or feats is None:
        method = bundle["model_name"] if bundle else "3-month average (baseline)"
        ratio = feats["median6_ratio"] if feats and "median" in method else 1.0
        metrics = bundle.get("metrics", {}) if bundle else {}
        mae_ratio = float(metrics.get("chosen_mae_ratio", 0.15))
    else:
        ratio = float(bundle["model"].predict(pd.DataFrame([feats])[bundle["features"]])[0])
        ratio = float(np.clip(ratio, 0.4, 2.5))
        method = bundle["model_name"]
        mae_ratio = float(bundle["metrics"]["chosen_mae_ratio"])
        metrics = bundle["metrics"]
    predicted = baseline * ratio
    margin = baseline * mae_ratio * 1.5
    return SpendingPrediction(
        month=target_key,
        predicted=round(predicted),
        low=round(max(0.0, predicted - margin)),
        high=round(predicted + margin),
        method=method,
        baseline=round(baseline),
        history_months=history,
        category_forecast=_rounded(category_avg),
        model_metrics=metrics,
    )


def _category_typical(df: pd.DataFrame, months: list[str]) -> dict[str, float]:
    """Typical monthly spend per category: median of monthly totals (robust to one-off purchases)."""
    sub = df[(df["transaction_type"] == "Expense") & (df["month"].isin(months))]
    if sub.empty or not months:
        return {}
    table = sub.pivot_table(index="month", columns="category", values="amount", aggfunc="sum", fill_value=0.0)
    table = table.reindex(months, fill_value=0.0)
    return {k: float(v) for k, v in table.median().items() if v > 0}


def _rounded(category_typical: dict[str, float]) -> dict[str, float]:
    return dict(sorted(((k, round(v)) for k, v in category_typical.items()), key=lambda kv: -kv[1]))
