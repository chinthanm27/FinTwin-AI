"""Queries for the users collection."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import users_collection
from app.models.user import User
from app.utils.dates import utcnow
from app.utils.errors import ValidationError


def to_object_id(value: str | ObjectId | None) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def create_user(user: User) -> User:
    try:
        result = users_collection().insert_one(user.to_document())
    except DuplicateKeyError:
        raise ValidationError("An account with this email already exists.") from None
    user.id = str(result.inserted_id)
    return user


def find_by_email(email: str) -> User | None:
    doc = users_collection().find_one({"email": email.strip().lower()})
    return User.from_document(doc) if doc else None


def find_by_id(user_id: str) -> User | None:
    oid = to_object_id(user_id)
    if oid is None:
        return None
    doc = users_collection().find_one({"_id": oid})
    return User.from_document(doc) if doc else None


def update_user(user_id: str, fields: dict[str, Any]) -> None:
    oid = to_object_id(user_id)
    if oid is None:
        return
    allowed = {k: v for k, v in fields.items() if k in {"full_name", "password_hash", "last_login_at"}}
    if allowed:
        users_collection().update_one({"_id": oid}, {"$set": allowed})


def touch_last_login(user_id: str) -> None:
    update_user(user_id, {"last_login_at": utcnow()})


def delete_user(user_id: str) -> None:
    oid = to_object_id(user_id)
    if oid is not None:
        users_collection().delete_one({"_id": oid})
