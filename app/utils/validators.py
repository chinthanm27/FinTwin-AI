"""Input validation helpers shared by services."""

from __future__ import annotations

import re
from datetime import date, datetime

from app.utils.errors import ValidationError

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MAX_AMOUNT = 1_000_000_000  # ₹100 crore sanity cap


def validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or len(email) > 254 or not EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address.")
    return email


def validate_full_name(name: str) -> str:
    name = " ".join((name or "").split())
    if len(name) < 2:
        raise ValidationError("Full name must be at least 2 characters.")
    if len(name) > 80:
        raise ValidationError("Full name must be at most 80 characters.")
    if not re.match(r"^[A-Za-zÀ-ɏऀ-ॿ .'\-]+$", name):
        raise ValidationError("Full name can contain letters, spaces, dots, hyphens and apostrophes.")
    return name


def validate_password(password: str) -> str:
    """Password policy: 8+ chars, letters and digits, max 72 bytes (bcrypt limit)."""
    password = password or ""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if len(password.encode("utf-8")) > 72:
        raise ValidationError("Password must be at most 72 bytes.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one letter and one number.")
    return password


def validate_amount(amount: float | int | str | None, allow_zero: bool = False) -> float:
    try:
        value = float(str(amount).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        raise ValidationError("Amount must be a number.") from None
    if value != value:  # NaN
        raise ValidationError("Amount must be a number.")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValidationError("Amount must be greater than zero.")
    if value > MAX_AMOUNT:
        raise ValidationError("Amount is unrealistically large.")
    return round(value, 2)


def validate_date(value: date | datetime | str | None) -> datetime:
    """Return a timezone-naive datetime at midnight. Rejects far-future dates."""
    if value is None or value == "":
        raise ValidationError("Date is required.")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip()[:10])
        except ValueError:
            raise ValidationError("Date must be in YYYY-MM-DD format.") from None
    parsed = datetime(parsed.year, parsed.month, parsed.day)
    if parsed.year < 1990:
        raise ValidationError("Date is too far in the past.")
    if (parsed - datetime.now()).days > 366:
        raise ValidationError("Date cannot be more than a year in the future.")
    return parsed


def clean_text(value: str | None, max_length: int = 200) -> str:
    """Strip control characters and collapse whitespace."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", value or "")
    text = " ".join(text.split())
    return text[:max_length]
