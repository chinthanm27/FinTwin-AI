"""Business logic for transactions: validation, CRUD, dataframes, export."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd

from app.database import transaction_repository
from app.models.transaction import CATEGORIES, TRANSACTION_TYPES, Transaction
from app.utils.dates import utcnow
from app.utils.errors import ValidationError
from app.utils.validators import clean_text, validate_amount, validate_date

DATAFRAME_COLUMNS = ["id", "date", "category", "transaction_type", "amount", "description", "source"]


def add_transaction(
    user_id: str,
    date: Any,
    category: str,
    transaction_type: str,
    amount: Any,
    description: str = "",
    source: str = "manual",
) -> Transaction:
    tx = Transaction.create(user_id, date, category, transaction_type, amount, description, source)
    return transaction_repository.insert_transaction(tx)


def update_transaction(user_id: str, transaction_id: str, data: dict[str, Any]) -> None:
    fields: dict[str, Any] = {}
    if "date" in data:
        fields["date"] = validate_date(data["date"])
    if "amount" in data:
        fields["amount"] = validate_amount(data["amount"])
    if "transaction_type" in data:
        if data["transaction_type"] not in TRANSACTION_TYPES:
            raise ValidationError("Choose a valid transaction type.")
        fields["transaction_type"] = data["transaction_type"]
    if "category" in data:
        if data["category"] not in CATEGORIES:
            raise ValidationError("Choose a valid category.")
        fields["category"] = data["category"]
    if "description" in data:
        fields["description"] = clean_text(data["description"], 200)
    if not transaction_repository.update_transaction(user_id, transaction_id, fields):
        raise ValidationError("Transaction not found.")


def delete_transaction(user_id: str, transaction_id: str) -> None:
    if not transaction_repository.delete_transaction(user_id, transaction_id):
        raise ValidationError("Transaction not found.")


def list_transactions(user_id: str, **filters: Any) -> list[Transaction]:
    return transaction_repository.get_transactions(user_id, **filters)


def recent_transactions(user_id: str, limit: int = 6) -> list[Transaction]:
    return transaction_repository.get_transactions(user_id, limit=limit)


def has_transactions(user_id: str) -> bool:
    return transaction_repository.count_for_user(user_id) > 0


def transactions_dataframe(user_id: str) -> pd.DataFrame:
    """All of the user's transactions as a typed DataFrame (empty-safe)."""
    docs = transaction_repository.get_all_documents(user_id)
    return documents_to_dataframe(docs)


def documents_to_dataframe(docs: list[dict[str, Any]]) -> pd.DataFrame:
    if not docs:
        df = pd.DataFrame(columns=DATAFRAME_COLUMNS)
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = df["amount"].astype(float)
        df["month"] = pd.Series(dtype=str)
        return df
    df = pd.DataFrame(docs)
    if "_id" in df.columns:
        df["id"] = df["_id"].astype(str)
        df = df.drop(columns=["_id"])
    for col in DATAFRAME_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col not in {"amount"} else 0.0
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).astype(float)
    df["description"] = df["description"].fillna("").astype(str)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    return df.sort_values("date").reset_index(drop=True)


def export_csv(transactions: list[Transaction]) -> bytes:
    rows = [
        {
            "date": t.date.strftime("%Y-%m-%d"),
            "type": t.transaction_type,
            "category": t.category,
            "amount": t.amount,
            "description": t.description,
            "source": t.source,
        }
        for t in transactions
    ]
    buffer = io.StringIO()
    pd.DataFrame(rows, columns=["date", "type", "category", "amount", "description", "source"]).to_csv(
        buffer, index=False
    )
    return buffer.getvalue().encode("utf-8")


def export_filename(prefix: str, extension: str) -> str:
    return f"fintwin_{prefix}_{utcnow().strftime('%Y%m%d_%H%M')}.{extension}"


def parse_date_input(value: str | None) -> datetime | None:
    """Parse optional filter dates from the UI; invalid values are ignored."""
    if not value:
        return None
    try:
        return validate_date(value)
    except ValidationError:
        return None
