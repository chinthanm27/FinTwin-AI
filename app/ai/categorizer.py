"""
Rule-based transaction categorization.

Matches merchant / keyword patterns in a transaction description and
returns (category, transaction_type, confidence). Rules are ordered:
more specific patterns come first. Designed so an ML/NLP classifier can
replace `categorize()` later without changing callers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (regex, category, type)
RULES: list[tuple[str, str, str]] = [
    # Income
    (r"\bsalary\b|\bpayroll\b|\bsal cr\b", "Salary", "Income"),
    (r"\binterest (credit|cr|earned)\b|\bint\.? ?cr\b|\bdividend\b", "Investment", "Income"),
    (r"\brefund\b|\bcashback\b|\breversal\b", "Other", "Income"),
    (r"\bfreelance\b|\bupi/cr\b|\bimps/cr\b|\bneft/cr\b", "Other", "Income"),
    # Investment
    (r"\bsip\b|\bmutual fund\b|\bgroww\b|\bzerodha\b|\bupstox\b|\bkuvera\b|\bcoin by zerodha\b"
     r"|\bppf\b|\bnps\b|\bfixed deposit\b|\b(fd|rd) (booking|opening)\b|\bsmallcase\b|\bequity\b",
     "Investment", "Investment"),
    # Expenses
    (r"\binsurance\b|\blic\b|\bpolicybazaar\b|\bhdfc ergo\b|\bicici lombard\b|\bstar health\b|\bpremium\b",
     "Insurance", "Expense"),
    (r"\brent\b|\blandlord\b|\bnobroker\b|\bhouse rent\b|\bmaintenance charges\b", "Rent", "Expense"),
    (r"\bswiggy\b|\bzomato\b|\bdomino'?s\b|\bpizza\b|\bmcdonald'?s\b|\bkfc\b|\bstarbucks\b|\bcafe\b"
     r"|\brestaurant\b|\bbigbasket\b|\bblinkit\b|\bzepto\b|\binstamart\b|\bgrocer(y|ies)\b|\bdmart\b|\bfood\b",
     "Food", "Expense"),
    (r"\buber\b|\bola\b|\brapido\b|\bmetro\b|\bpetrol\b|\bdiesel\b|\bfuel\b|\bindian oil\b|\bhpcl\b|\bbpcl\b"
     r"|\bfastag\b|\bparking\b|\birctc\b|\bredbus\b|\bcab\b|\bauto\b", "Transport", "Expense"),
    (r"\bmakemytrip\b|\bgoibibo\b|\bcleartrip\b|\boyo\b|\bairbnb\b|\bindigo\b|\bair india\b|\bvistara\b"
     r"|\bhotel\b|\bflight\b|\btrip booking\b", "Travel", "Expense"),
    (r"\bnetflix\b|\bspotify\b|\bprime video\b|\bhotstar\b|\bdisney\b|\bbookmyshow\b|\bpvr\b|\binox\b"
     r"|\bmovie\b|\bgaming\b|\bsteam\b|\bplaystation\b|\byoutube premium\b", "Entertainment", "Expense"),
    (r"\belectricity\b|\bbescom\b|\btata power\b|\bmseb\b|\bwater bill\b|\bgas bill\b|\bbroadband\b"
     r"|\bjio\b|\bairtel\b|\bvi\b|\bvodafone\b|\bbsnl\b|\bpostpaid\b|\brecharge\b|\bdth\b|\bbill\b",
     "Bills", "Expense"),
    (r"\bapollo\b|\bpharmacy\b|\bpharmeasy\b|\b1mg\b|\bnetmeds\b|\bhospital\b|\bclinic\b|\bpracto\b"
     r"|\bdoctor\b|\bdiagnostic\b|\blab test\b|\bmedical\b", "Healthcare", "Expense"),
    (r"\budemy\b|\bcoursera\b|\bbyju'?s\b|\bunacademy\b|\bschool fee\b|\bcollege fee\b|\btuition\b"
     r"|\bcourse\b|\bbooks?\b|\bexam fee\b", "Education", "Expense"),
    (r"\bamazon\b|\bflipkart\b|\bmyntra\b|\bajio\b|\bnykaa\b|\bmeesho\b|\bcroma\b|\breliance digital\b"
     r"|\bdecathlon\b|\bikea\b|\bshopping\b|\bmall\b|\bstore\b", "Shopping", "Expense"),
]

_COMPILED = [(re.compile(pattern, re.IGNORECASE), cat, ttype) for pattern, cat, ttype in RULES]


@dataclass
class CategoryPrediction:
    category: str
    transaction_type: str
    confidence: float
    matched: str | None = None


def categorize(description: str, hint_type: str | None = None) -> CategoryPrediction:
    """Predict the category for a description.

    hint_type: if the bank statement says the row is a credit (Income) or
    debit (Expense), conflicting rules are skipped.
    """
    text = (description or "").lower()
    for regex, category, ttype in _COMPILED:
        match = regex.search(text)
        if not match:
            continue
        if hint_type == "Expense" and ttype == "Income":
            continue
        if hint_type == "Income" and ttype in {"Expense", "Investment"}:
            continue
        return CategoryPrediction(category, ttype, 0.9, match.group(0))
    if hint_type == "Income":
        return CategoryPrediction("Other", "Income", 0.4)
    return CategoryPrediction("Other", hint_type or "Expense", 0.3)
