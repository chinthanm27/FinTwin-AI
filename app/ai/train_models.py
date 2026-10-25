"""
Generate synthetic datasets and (re)train the global spending model.

Run from the project root:

    python -m app.ai.train_models

Outputs
- datasets/sample_transactions.csv   synthetic multi-user training data
- datasets/sample_bank_statement.csv a statement you can try on the upload page
- trained_models/spending_model.joblib
Per-user anomaly and forecast models are fitted automatically inside the app.
"""

from __future__ import annotations

import json

import pandas as pd

from app.ai import spending_predictor
from app.config import settings
from app.services.demo_data_service import generate_population
from app.services.statement_service import SAMPLE_CSV


def main() -> None:
    settings.datasets_dir.mkdir(parents=True, exist_ok=True)
    population = generate_population()
    df = pd.DataFrame(population)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df.to_csv(settings.datasets_dir / "sample_transactions.csv", index=False)
    (settings.datasets_dir / "sample_bank_statement.csv").write_text(SAMPLE_CSV, encoding="utf-8")
    print(f"Wrote {len(df):,} synthetic transactions for {df['user_id'].nunique()} users.")

    spending_predictor.reset_cache()
    bundle = spending_predictor.train_global_model(population)
    print(f"Spending model selected: {bundle['model_name']}")
    print(json.dumps(bundle["metrics"], indent=2))


if __name__ == "__main__":
    main()
