"""Date helpers used across services and AI modules."""

from __future__ import annotations

from datetime import date, datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (MongoDB stores naive UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today() -> datetime:
    """Today at midnight (local time), naive."""
    d = date.today()
    return datetime(d.year, d.month, d.day)


def month_start(value: datetime | date | None = None) -> datetime:
    value = value or date.today()
    return datetime(value.year, value.month, 1)


def add_months(value: datetime, months: int) -> datetime:
    """Shift a datetime by whole months, clamping the day to the month length."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    days_in_month = [31, 29 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return value.replace(year=year, month=month, day=min(value.day, days_in_month))


def period_key(value: datetime | date) -> str:
    """'YYYY-MM' month key."""
    return f"{value.year:04d}-{value.month:02d}"
