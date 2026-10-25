"""User data model. The password hash never leaves the auth layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.utils.dates import utcnow


@dataclass
class User:
    full_name: str
    email: str
    password_hash: str = field(repr=False)
    id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    last_login_at: datetime | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "email": self.email,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> "User":
        return cls(
            id=str(doc["_id"]),
            full_name=doc.get("full_name", ""),
            email=doc.get("email", ""),
            password_hash=doc.get("password_hash", ""),
            created_at=doc.get("created_at") or utcnow(),
            last_login_at=doc.get("last_login_at"),
        )

    def public_dict(self) -> dict[str, Any]:
        """Safe representation for sessions and UI (no password hash)."""
        return {"id": self.id, "full_name": self.full_name, "email": self.email}

    @property
    def first_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else "there"

    @property
    def initials(self) -> str:
        parts = [p for p in self.full_name.split(" ") if p]
        return "".join(p[0] for p in parts[:2]).upper() or "U"
