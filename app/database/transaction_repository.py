"""
Queries for the transactions collection.

Every function takes user_id and filters by it, so one user's records
can never be read, changed or deleted by another user.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.database.mongodb import transactions_collection
from app.database.user_repository import to_object_id
from app.models.transaction import Transaction
from app.utils.dates import utcnow

SORT_FIELDS = {"date", "amount", "category", "transaction_type", "description", "created_at"}


def insert_transaction(tx: Transaction) -> Transaction:
    result = transactions_collection().insert_one(tx.to_document())
    tx.id = str(result.inserted_id)
    return tx


def insert_many(transactions: list[Transaction]) -> int:
    if not transactions:
        return 0
    result = transactions_collection().insert_many([t.to_document() for t in transactions])
    return len(result.inserted_ids)


def get_transaction(user_id: str, transaction_id: str) -> Transaction | None:
    oid = to_object_id(transaction_id)
    if oid is None:
        return None
    doc = transactions_collection().find_one({"_id": oid, "user_id": user_id})
    return Transaction.from_document(doc) if doc else None


def build_query(
    user_id: str,
    search: str | None = None,
    transaction_type: str | None = None,
    category: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"user_id": user_id}
    if transaction_type:
        query["transaction_type"] = transaction_type
    if category:
        query["category"] = category
    if start_date or end_date:
        date_q: dict[str, Any] = {}
        if start_date:
            date_q["$gte"] = start_date
        if end_date:
            date_q["$lte"] = end_date
        query["date"] = date_q
    if search:
        pattern = re.escape(search.strip()[:60])
        query["$or"] = [
            {"description": {"$regex": pattern, "$options": "i"}},
            {"category": {"$regex": pattern, "$options": "i"}},
        ]
    return query


def get_transactions(
    user_id: str,
    search: str | None = None,
    transaction_type: str | None = None,
    category: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort_by: str = "date",
    descending: bool = True,
    limit: int = 0,
) -> list[Transaction]:
    query = build_query(user_id, search, transaction_type, category, start_date, end_date)
    sort_field = sort_by if sort_by in SORT_FIELDS else "date"
    direction = DESCENDING if descending else ASCENDING
    cursor = transactions_collection().find(query).sort([(sort_field, direction), ("_id", direction)])
    if limit:
        cursor = cursor.limit(limit)
    return [Transaction.from_document(d) for d in cursor]


def get_all_documents(user_id: str) -> list[dict[str, Any]]:
    """Raw documents (for analytics dataframes)."""
    return list(
        transactions_collection().find(
            {"user_id": user_id},
            {"_id": 1, "date": 1, "category": 1, "transaction_type": 1, "amount": 1, "description": 1, "source": 1},
        )
    )


def update_transaction(user_id: str, transaction_id: str, fields: dict[str, Any]) -> bool:
    oid = to_object_id(transaction_id)
    if oid is None:
        return False
    allowed_keys = {"date", "category", "transaction_type", "amount", "description"}
    update = {k: v for k, v in fields.items() if k in allowed_keys}
    update["updated_at"] = utcnow()
    result = transactions_collection().update_one({"_id": oid, "user_id": user_id}, {"$set": update})
    return result.matched_count == 1


def delete_transaction(user_id: str, transaction_id: str) -> bool:
    oid = to_object_id(transaction_id)
    if oid is None:
        return False
    result = transactions_collection().delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count == 1


def delete_all_for_user(user_id: str) -> int:
    return transactions_collection().delete_many({"user_id": user_id}).deleted_count


def count_for_user(user_id: str) -> int:
    return transactions_collection().count_documents({"user_id": user_id})


def find_existing_keys(user_id: str, start: datetime, end: datetime) -> set[tuple[str, float, str]]:
    """(date, amount, normalized description) keys used for duplicate detection."""
    keys: set[tuple[str, float, str]] = set()
    cursor = transactions_collection().find(
        {"user_id": user_id, "date": {"$gte": start, "$lte": end}},
        {"date": 1, "amount": 1, "description": 1},
    )
    for doc in cursor:
        keys.add(duplicate_key(doc["date"], doc["amount"], doc.get("description", "")))
    return keys


def duplicate_key(date: datetime, amount: float, description: str) -> tuple[str, float, str]:
    normalized = re.sub(r"[^a-z0-9]", "", (description or "").lower())[:40]
    return (date.strftime("%Y-%m-%d"), round(float(amount), 2), normalized)
