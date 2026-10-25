"""
Synthetic demo data.

Generates realistic (but entirely fictional) Indian personal-finance
transactions. Used for:
- the "Load demo data" button, so the app can be explored instantly
- datasets/sample_transactions.csv and global ML model training
No real personal financial information is used anywhere.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from app.database import transaction_repository
from app.models.transaction import Transaction
from app.utils.dates import add_months, month_start, today


@dataclass
class PersonaParams:
    salary: float = 85000
    rent: float = 22000
    sip: float = 10000
    food_level: float = 1.0
    shopping_level: float = 1.0
    travel_trips_per_year: int = 2
    raise_pct: float = 8.0
    lifestyle_creep: float = 0.8  # % growth per month in discretionary spending
    inject_anomalies: bool = True


def _seed_for(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def _day(rng: np.random.Generator, month: datetime, low: int = 1, high: int = 28) -> datetime:
    return month.replace(day=int(rng.integers(low, high + 1)))


def generate_records(
    months: int = 12,
    seed: int = 42,
    params: PersonaParams | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return a list of transaction dicts covering `months` months up to `end` (default today)."""
    p = params or PersonaParams()
    rng = np.random.default_rng(seed)
    end = end or today()
    first_month = add_months(month_start(end), -(months - 1))
    records: list[dict[str, Any]] = []

    def add(date: datetime, category: str, ttype: str, amount: float, description: str) -> None:
        if date <= end and amount > 0:
            records.append({
                "date": date,
                "category": category,
                "transaction_type": ttype,
                "amount": round(float(amount), 0),
                "description": description,
            })

    for i in range(months):
        m = add_months(first_month, i)
        # Realistic structure: festive season (Diwali, Oct-Nov) and year-end spending,
        # plus gradual lifestyle creep in discretionary categories.
        festive = 2.2 if m.month in (10, 11) else 1.4 if m.month == 12 else 1.0
        creep = 1 + p.lifestyle_creep / 100 * i
        salary = p.salary * (1 + p.raise_pct / 100) if i >= months // 2 else p.salary
        add(m.replace(day=1), "Salary", "Income", salary, "SALARY CREDIT - NIMBUS TECH PVT LTD")
        if rng.random() < 0.3:
            add(_day(rng, m, 10, 25), "Other", "Income", rng.integers(6, 20) * 1000, "UPI/CR/Freelance design project")
        if rng.random() < 0.25:
            add(_day(rng, m, 10, 28), "Investment", "Income", rng.integers(300, 1800), "Interest credit - savings account")

        add(m.replace(day=2), "Rent", "Expense", p.rent, "NEFT - Monthly house rent")
        add(m.replace(day=5), "Investment", "Investment", p.sip, "SIP - Groww Nifty 50 index fund")
        if rng.random() < 0.35:
            add(_day(rng, m, 8, 26), "Investment", "Investment", rng.integers(3, 15) * 1000, "Zerodha - equity purchase")

        add(_day(rng, m, 6, 12), "Bills", "Expense", rng.integers(1100, 2600), "BESCOM electricity bill")
        add(_day(rng, m, 3, 8), "Bills", "Expense", 999, "Jio Fiber broadband")
        add(_day(rng, m, 10, 15), "Bills", "Expense", 599, "Airtel postpaid mobile")

        for _ in range(int(rng.integers(10, 17) * p.food_level * creep * (1.2 if festive > 1 else 1.0))):
            merchant = rng.choice(["Swiggy order", "Zomato order", "Swiggy Instamart", "Cafe Coffee Day", "Domino's Pizza"])
            add(_day(rng, m), "Food", "Expense", rng.integers(180, 750), str(merchant))
        for _ in range(int(rng.integers(2, 4))):
            add(_day(rng, m), "Food", "Expense", rng.integers(1400, 3600), "BigBasket groceries")

        for _ in range(int(rng.integers(6, 11))):
            merchant = rng.choice(["Uber trip", "Ola ride", "Rapido bike taxi"])
            add(_day(rng, m), "Transport", "Expense", rng.integers(90, 560), str(merchant))
        add(_day(rng, m, 1, 10), "Transport", "Expense", 500, "Namma Metro card recharge")
        if rng.random() < 0.6:
            add(_day(rng, m), "Transport", "Expense", rng.integers(1500, 2600), "Indian Oil petrol")

        for _ in range(int(rng.integers(1, 5) * p.shopping_level * festive * creep)):
            merchant = rng.choice(["Amazon.in order", "Flipkart order", "Myntra fashion", "Decathlon sports"])
            add(_day(rng, m), "Shopping", "Expense", rng.integers(400, 4200), str(merchant))

        add(_day(rng, m, 1, 6), "Entertainment", "Expense", 649, "Netflix subscription")
        add(_day(rng, m, 1, 6), "Entertainment", "Expense", 119, "Spotify premium")
        if rng.random() < 0.5:
            add(_day(rng, m), "Entertainment", "Expense", rng.integers(400, 1300), "BookMyShow movie tickets")

        if rng.random() < 0.5:
            add(_day(rng, m), "Healthcare", "Expense", rng.integers(250, 1600), "Apollo Pharmacy")
        if rng.random() < 0.15:
            add(_day(rng, m), "Healthcare", "Expense", rng.integers(800, 2500), "Practo doctor consultation")
        if rng.random() < 0.2:
            add(_day(rng, m), "Education", "Expense", rng.integers(450, 3500), "Udemy online course")
        if i % 3 == 0:
            add(_day(rng, m, 15, 20), "Insurance", "Expense", 6200, "LIC premium payment")

    # Trips cluster around holidays (May, October-December)
    month_weights = np.array([3.0 if add_months(first_month, k).month in (5, 10, 11, 12) else 1.0 for k in range(months)])
    trips = sorted(rng.choice(range(months), size=min(p.travel_trips_per_year * months // 12, months), replace=False,
                              p=month_weights / month_weights.sum()))
    for t in trips:
        m = add_months(first_month, int(t))
        add(_day(rng, m, 8, 24), "Travel", "Expense", rng.integers(7000, 24000), "MakeMyTrip flight booking")
        add(_day(rng, m, 8, 24), "Travel", "Expense", rng.integers(3000, 12000), "OYO hotel stay")

    if p.inject_anomalies and months >= 8:
        # A few deliberately unusual transactions so anomaly detection has something to find
        a1 = add_months(first_month, months - 5)
        add(_day(rng, a1, 10, 20), "Shopping", "Expense", 64999, "Croma electronics - card purchase")
        a2 = add_months(first_month, months - 8)
        add(_day(rng, a2, 5, 25), "Other", "Expense", 30000, "ATM cash withdrawal - unknown location")
        a3 = add_months(first_month, months - 2)
        add(_day(rng, a3, 5, 25), "Entertainment", "Expense", 18500, "International online gaming purchase")

    records.sort(key=lambda r: r["date"])
    return records


def load_demo_data(user_id: str, months: int = 12) -> int:
    """Insert demo transactions for the user. Returns the number inserted."""
    records = generate_records(months=months, seed=_seed_for(user_id))
    txs = [
        Transaction.create(user_id, r["date"], r["category"], r["transaction_type"], r["amount"], r["description"], "demo")
        for r in records
    ]
    return transaction_repository.insert_many(txs)


def remove_demo_data(user_id: str) -> int:
    from app.database.mongodb import transactions_collection

    return transactions_collection().delete_many({"user_id": user_id, "source": "demo"}).deleted_count


def generate_population(users: int = 80, months: int = 24, seed: int = 7) -> list[dict[str, Any]]:
    """Synthetic multi-user dataset for training global models."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for u in range(users):
        params = PersonaParams(
            salary=float(rng.integers(35, 220) * 1000),
            rent=float(rng.integers(8, 45) * 1000),
            sip=float(rng.integers(0, 30) * 1000),
            food_level=float(rng.uniform(0.6, 1.6)),
            shopping_level=float(rng.uniform(0.5, 2.0)),
            travel_trips_per_year=int(rng.integers(0, 5)),
            raise_pct=float(rng.uniform(0, 15)),
            lifestyle_creep=float(rng.uniform(-0.5, 2.0)),
            inject_anomalies=False,
        )
        for r in generate_records(months=months, seed=seed * 1000 + u, params=params):
            rows.append({"user_id": f"synthetic_user_{u:03d}", **r})
    return rows
