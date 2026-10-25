"""Financial profile: extra facts that transactions alone cannot reveal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.utils.dates import utcnow
from app.utils.errors import ValidationError
from app.utils.validators import clean_text, validate_amount


@dataclass
class FinancialGoal:
    name: str
    target_amount: float
    target_years: float

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "target_amount": self.target_amount, "target_years": self.target_years}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FinancialGoal":
        return cls(
            name=data.get("name", "Goal"),
            target_amount=float(data.get("target_amount", 0)),
            target_years=float(data.get("target_years", 1)),
        )

    @classmethod
    def create(cls, name: str, target_amount: Any, target_years: Any) -> "FinancialGoal":
        name = clean_text(name, 60)
        if not name:
            raise ValidationError("Goal name is required.")
        try:
            years = float(target_years)
        except (TypeError, ValueError):
            raise ValidationError("Years must be a number.") from None
        if not 0 < years <= 50:
            raise ValidationError("Years must be between 0 and 50.")
        return cls(name=name, target_amount=validate_amount(target_amount), target_years=years)


@dataclass
class FinancialProfile:
    """Optional, user-provided context used by health score and the twin.

    Every field is optional; when a value is missing, analyses say so
    instead of inventing a number.
    """

    user_id: str
    emergency_fund: float | None = None
    monthly_debt_payment: float | None = None
    expected_annual_return: float = 10.0
    risk_profile: str = "Moderate"
    goals: list[FinancialGoal] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utcnow)

    def to_document(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "emergency_fund": self.emergency_fund,
            "monthly_debt_payment": self.monthly_debt_payment,
            "expected_annual_return": self.expected_annual_return,
            "risk_profile": self.risk_profile,
            "goals": [g.to_dict() for g in self.goals],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_document(cls, doc: dict[str, Any] | None, user_id: str) -> "FinancialProfile":
        if not doc:
            return cls(user_id=user_id)
        return cls(
            user_id=user_id,
            emergency_fund=doc.get("emergency_fund"),
            monthly_debt_payment=doc.get("monthly_debt_payment"),
            expected_annual_return=float(doc.get("expected_annual_return") or 10.0),
            risk_profile=doc.get("risk_profile") or "Moderate",
            goals=[FinancialGoal.from_dict(g) for g in doc.get("goals") or []],
            updated_at=doc.get("updated_at") or utcnow(),
        )
