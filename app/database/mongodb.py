"""
MongoDB connection management.

- Lazily connects on first use and pings the server so failures surface
  as a friendly DatabaseUnavailableError instead of a traceback.
- Supports demo mode: MONGO_URI=mongomock://localhost uses an in-memory
  database (no MongoDB installation needed; data is lost on restart).
- Creates indexes that enforce data integrity and per-user query speed.
"""

from __future__ import annotations

import threading
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import settings
from app.utils.errors import DatabaseUnavailableError
from app.utils.logger import get_logger

log = get_logger("database")

COLLECTIONS = (
    "users",
    "transactions",
    "budgets",
    "financial_profiles",
    "predictions",
    "fraud_alerts",
    "ai_conversations",
    "reports",
)

_lock = threading.Lock()
_client: Any = None
_db: Database | None = None
_override_db: Database | None = None


def _create_client() -> Any:
    if settings.uses_mock_database:
        import mongomock  # imported lazily: only needed in demo mode / tests

        log.warning("Using in-memory mongomock database (demo mode). Data is not persisted.")
        return mongomock.MongoClient()
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000, tz_aware=False)


def _ensure_indexes(db: Database) -> None:
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.transactions.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
    db.transactions.create_index([("user_id", ASCENDING), ("category", ASCENDING)])
    db.budgets.create_index([("user_id", ASCENDING), ("category", ASCENDING)], unique=True)
    db.financial_profiles.create_index([("user_id", ASCENDING)], unique=True)
    db.predictions.create_index([("user_id", ASCENDING), ("kind", ASCENDING), ("created_at", DESCENDING)])
    db.fraud_alerts.create_index([("user_id", ASCENDING), ("transaction_id", ASCENDING)], unique=True)
    db.ai_conversations.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db.reports.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])


def get_database() -> Database:
    """Return the connected database, connecting on first use."""
    global _client, _db
    if _override_db is not None:
        return _override_db
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        try:
            client = _create_client()
            client.admin.command("ping")
            db = client[settings.database_name]
            _ensure_indexes(db)
        except PyMongoError as exc:
            log.error("MongoDB connection failed: %s", exc)
            raise DatabaseUnavailableError() from exc
        _client, _db = client, db
        log.info("Connected to MongoDB database '%s'", settings.database_name)
        return _db


def get_collection(name: str) -> Collection:
    if name not in COLLECTIONS:
        raise ValueError(f"Unknown collection: {name}")
    return get_database()[name]


def check_connection() -> tuple[bool, str]:
    """Health check used by the UI. Returns (ok, message)."""
    try:
        get_database().command("ping")
        mode = "demo (in-memory)" if settings.uses_mock_database else "MongoDB"
        return True, f"Connected · {mode}"
    except (DatabaseUnavailableError, PyMongoError) as exc:
        return False, getattr(exc, "message", DatabaseUnavailableError.user_message)


def use_database(db: Database | None) -> None:
    """Override the database (used by tests). Pass None to reset."""
    global _override_db
    _override_db = db
    if db is not None:
        _ensure_indexes(db)


# Convenience accessors (evaluated at call time, never at import time)
def users_collection() -> Collection:
    return get_collection("users")


def transactions_collection() -> Collection:
    return get_collection("transactions")


def budgets_collection() -> Collection:
    return get_collection("budgets")


def profiles_collection() -> Collection:
    return get_collection("financial_profiles")


def predictions_collection() -> Collection:
    return get_collection("predictions")


def fraud_alerts_collection() -> Collection:
    return get_collection("fraud_alerts")


def conversations_collection() -> Collection:
    return get_collection("ai_conversations")


def reports_collection() -> Collection:
    return get_collection("reports")
