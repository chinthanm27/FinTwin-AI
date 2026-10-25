"""
Queries for financial_profiles, predictions, fraud_alerts,
ai_conversations and reports. All functions are scoped by user_id.
"""

from __future__ import annotations

from typing import Any

from pymongo import DESCENDING

from app.database.mongodb import (
    conversations_collection,
    fraud_alerts_collection,
    predictions_collection,
    profiles_collection,
    reports_collection,
)
from app.database.user_repository import to_object_id
from app.models.financial_profile import FinancialProfile
from app.utils.dates import utcnow


# ---------------- Financial profiles ----------------
def get_profile(user_id: str) -> FinancialProfile:
    doc = profiles_collection().find_one({"user_id": user_id})
    return FinancialProfile.from_document(doc, user_id)


def save_profile(profile: FinancialProfile) -> None:
    profile.updated_at = utcnow()
    profiles_collection().update_one(
        {"user_id": profile.user_id}, {"$set": profile.to_document()}, upsert=True
    )


# ---------------- Predictions ----------------
def save_prediction(user_id: str, kind: str, payload: dict[str, Any]) -> None:
    predictions_collection().insert_one(
        {"user_id": user_id, "kind": kind, "payload": payload, "created_at": utcnow()}
    )
    # Keep only the 20 most recent predictions of each kind per user
    old = list(
        predictions_collection()
        .find({"user_id": user_id, "kind": kind}, {"_id": 1})
        .sort("created_at", DESCENDING)
        .skip(20)
    )
    if old:
        predictions_collection().delete_many({"_id": {"$in": [d["_id"] for d in old]}})


def latest_prediction(user_id: str, kind: str) -> dict[str, Any] | None:
    doc = predictions_collection().find_one(
        {"user_id": user_id, "kind": kind}, sort=[("created_at", DESCENDING)]
    )
    return doc


# ---------------- Fraud alerts ----------------
def upsert_fraud_alert(user_id: str, transaction_id: str, alert: dict[str, Any]) -> None:
    fraud_alerts_collection().update_one(
        {"user_id": user_id, "transaction_id": transaction_id},
        {
            "$set": {**alert, "updated_at": utcnow()},
            "$setOnInsert": {"status": "open", "created_at": utcnow()},
        },
        upsert=True,
    )


def get_fraud_alerts(user_id: str, status: str | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"user_id": user_id}
    if status:
        query["status"] = status
    return list(fraud_alerts_collection().find(query).sort("score", DESCENDING))


def set_fraud_alert_status(user_id: str, alert_id: str, status: str) -> bool:
    oid = to_object_id(alert_id)
    if oid is None or status not in {"open", "reviewed", "dismissed"}:
        return False
    result = fraud_alerts_collection().update_one(
        {"_id": oid, "user_id": user_id}, {"$set": {"status": status, "updated_at": utcnow()}}
    )
    return result.matched_count == 1


def remove_stale_alerts(user_id: str, keep_transaction_ids: set[str]) -> None:
    """Delete open alerts whose transactions are no longer flagged (keeps reviewed ones)."""
    fraud_alerts_collection().delete_many(
        {"user_id": user_id, "status": "open", "transaction_id": {"$nin": list(keep_transaction_ids)}}
    )


def count_open_alerts(user_id: str) -> int:
    return fraud_alerts_collection().count_documents({"user_id": user_id, "status": "open"})


# ---------------- AI conversations ----------------
def add_message(user_id: str, role: str, content: str, meta: dict[str, Any] | None = None) -> None:
    conversations_collection().insert_one(
        {"user_id": user_id, "role": role, "content": content, "meta": meta or {}, "created_at": utcnow()}
    )


def get_messages(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    docs = list(
        conversations_collection().find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)
    )
    return list(reversed(docs))


def clear_messages(user_id: str) -> None:
    conversations_collection().delete_many({"user_id": user_id})


# ---------------- Reports ----------------
def save_report_record(user_id: str, period: str, summary: dict[str, Any]) -> None:
    reports_collection().insert_one(
        {"user_id": user_id, "period": period, "summary": summary, "created_at": utcnow()}
    )


def get_report_records(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    return list(reports_collection().find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit))


# ---------------- Cleanup ----------------
def delete_all_for_user(user_id: str) -> None:
    for collection in (
        profiles_collection(),
        predictions_collection(),
        fraud_alerts_collection(),
        conversations_collection(),
        reports_collection(),
    ):
        collection.delete_many({"user_id": user_id})
