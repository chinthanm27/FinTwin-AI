"""Budget data model and budget status calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.utils.dates import utcnow
from app.models.transaction import EXPENSE_CATEGORIES
from app.utils.errors import ValidationError
from app.utils.validators import validate_amount

WARNING_THRESHOLD = 80.0  # percent used that triggers "approaching"


@dataclass
class Budget:
    user_id: str
    category: str
    monthly_limit: float
    id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(cls, user_id: str, category: str, monthly_limit: Any) -> "Budget":
        if category not in EXPENSE_CATEGORIES:
            raise ValidationError("Budgets can only be set for expense categories.")
        return cls(user_id=str(user_id), category=category, monthly_limit=validate_amount(monthly_limit))

    def to_document(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "category": self.category,
            "monthly_limit": float(self.monthly_limit),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> "Budget":
        return cls(
            id=str(doc["_id"]),
            user_id=str(doc["user_id"]),
            category=doc["category"],
            monthly_limit=float(doc["monthly_limit"]),
            created_at=doc.get("created_at") or utcnow(),
            updated_at=doc.get("updated_at") or utcnow(),
        )


@dataclass
class BudgetStatus:
    """Budget vs actual for the current month."""

    category: str
    budget: float
    spent: float
    budget_id: str | None = None

    @property
    def remaining(self) -> float:
        return self.budget - self.spent

    @property
    def percent_used(self) -> float:
        if self.budget <= 0:
            return 0.0
        return self.spent / self.budget * 100

    @property
    def status(self) -> str:
        """'ok', 'warning' (>= 80 %), or 'exceeded' (> 100 %)."""
        if self.percent_used > 100:
            return "exceeded"
        if self.percent_used >= WARNING_THRESHOLD:
            return "warning"
        return "ok"
