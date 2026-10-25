"""Transaction data model and reference values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.utils.dates import utcnow
from app.utils.errors import ValidationError
from app.utils.validators import clean_text, validate_amount, validate_date

TRANSACTION_TYPES: list[str] = ["Income", "Expense", "Investment"]

CATEGORIES: list[str] = [
    "Salary",
    "Food",
    "Shopping",
    "Transport",
    "Bills",
    "Entertainment",
    "Investment",
    "Healthcare",
    "Education",
    "Rent",
    "Travel",
    "Insurance",
    "Other",
]

# Categories that make sense for each type (used to guide the UI)
CATEGORIES_BY_TYPE: dict[str, list[str]] = {
    "Income": ["Salary", "Investment", "Other"],
    "Expense": [c for c in CATEGORIES if c not in {"Salary", "Investment"}],
    "Investment": ["Investment", "Insurance", "Other"],
}

EXPENSE_CATEGORIES: list[str] = CATEGORIES_BY_TYPE["Expense"]

CATEGORY_ICONS: dict[str, str] = {
    "Salary": "payments",
    "Food": "restaurant",
    "Shopping": "shopping_bag",
    "Transport": "directions_car",
    "Bills": "receipt_long",
    "Entertainment": "movie",
    "Investment": "trending_up",
    "Healthcare": "local_hospital",
    "Education": "school",
    "Rent": "home",
    "Travel": "flight",
    "Insurance": "verified_user",
    "Other": "category",
}


@dataclass
class Transaction:
    """A single financial transaction owned by one user."""

    user_id: str
    date: datetime
    category: str
    transaction_type: str
    amount: float
    description: str = ""
    source: str = "manual"
    id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(
        cls,
        user_id: str,
        date: Any,
        category: str,
        transaction_type: str,
        amount: Any,
        description: str = "",
        source: str = "manual",
    ) -> "Transaction":
        """Validate raw input and build a Transaction."""
        if not user_id:
            raise ValidationError("A transaction must belong to a user.")
        if transaction_type not in TRANSACTION_TYPES:
            raise ValidationError(f"Type must be one of: {', '.join(TRANSACTION_TYPES)}.")
        if category not in CATEGORIES:
            raise ValidationError("Choose a valid category.")
        return cls(
            user_id=str(user_id),
            date=validate_date(date),
            category=category,
            transaction_type=transaction_type,
            amount=validate_amount(amount),
            description=clean_text(description, 200),
            source=clean_text(source, 40) or "manual",
        )

    def to_document(self) -> dict[str, Any]:
        doc = {
            "user_id": self.user_id,
            "date": self.date,
            "category": self.category,
            "transaction_type": self.transaction_type,
            "amount": float(self.amount),
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return doc

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> "Transaction":
        return cls(
            id=str(doc.get("_id")) if doc.get("_id") is not None else None,
            user_id=str(doc["user_id"]),
            date=doc["date"],
            category=doc.get("category", "Other"),
            transaction_type=doc.get("transaction_type", "Expense"),
            amount=float(doc.get("amount", 0)),
            description=doc.get("description", ""),
            source=doc.get("source", "manual"),
            created_at=doc.get("created_at") or utcnow(),
            updated_at=doc.get("updated_at") or utcnow(),
        )

    def to_row(self) -> dict[str, Any]:
        """Flat dict used by UI tables."""
        return {
            "id": self.id,
            "date": self.date.strftime("%Y-%m-%d"),
            "category": self.category,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "description": self.description,
            "source": self.source,
        }
