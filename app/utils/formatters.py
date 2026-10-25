"""Formatting helpers for Indian currency, percentages and dates."""

from __future__ import annotations

from datetime import date, datetime


def _indian_group(integer_part: str) -> str:
    """Group digits the Indian way: 12,34,56,789."""
    if len(integer_part) <= 3:
        return integer_part
    last3 = integer_part[-3:]
    rest = integer_part[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return ",".join(groups) + "," + last3


def format_inr(amount: float | int | None, decimals: int = 0, sign: bool = False) -> str:
    """Format a number as Indian Rupees, e.g. ₹1,23,456."""
    if amount is None:
        return "₹0"
    value = float(amount)
    negative = value < 0
    value = abs(value)
    text = f"{value:.{decimals}f}"
    integer_part, _, fraction = text.partition(".")
    grouped = _indian_group(integer_part)
    result = f"₹{grouped}" + (f".{fraction}" if decimals else "")
    if negative:
        return f"-{result}"
    if sign and value > 0:
        return f"+{result}"
    return result


def format_inr_compact(amount: float | int | None) -> str:
    """Compact rupee format: ₹950, ₹12.5K, ₹3.2L, ₹1.4Cr."""
    if amount is None:
        return "₹0"
    value = float(amount)
    negative = value < 0
    value = abs(value)
    if value >= 1e7:
        text = f"₹{value / 1e7:.2f}Cr"
    elif value >= 1e5:
        text = f"₹{value / 1e5:.2f}L"
    elif value >= 1e3:
        text = f"₹{value / 1e3:.1f}K"
    else:
        text = f"₹{value:.0f}"
    text = text.replace(".00Cr", "Cr").replace(".00L", "L").replace(".0K", "K")
    return f"-{text}" if negative else text


def format_percent(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}%"


def format_date(value: date | datetime | str | None, fmt: str = "%d %b %Y") -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(fmt)


def month_label(period: str) -> str:
    """'2026-03' -> 'Mar 26'."""
    try:
        return datetime.strptime(period, "%Y-%m").strftime("%b %y")
    except ValueError:
        return period
