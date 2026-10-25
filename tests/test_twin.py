import pytest

from app.ai.categorizer import categorize
from app.ai.financial_twin import FinancialTwin, parse_amounts, parse_months, parse_percent
from app.models.financial_profile import FinancialProfile
from app.services.demo_data_service import generate_records
from app.services.transaction_service import documents_to_dataframe


@pytest.fixture(scope="module")
def twin():
    df = documents_to_dataframe(generate_records(months=12, seed=21))
    return FinancialTwin.from_dataframe(df, FinancialProfile(user_id="u"))


@pytest.mark.parametrize("text,expected", [
    ("₹15 lakh car", [1_500_000]), ("2.5 crore", [25_000_000]), ("₹10,000 more", [10_000]),
    ("50k bike", [50_000]), ("salary up 20% in 2 years", []), ("Rs. 8L trip", [800_000]),
])
def test_parse_amounts(text, expected):
    assert parse_amounts(text) == expected


def test_parse_months_and_percent():
    assert parse_months("next year") == 12
    assert parse_months("in 18 months") == 18
    assert parse_months("in two years") == 24
    assert parse_percent("increase by 20%") == 20


@pytest.mark.parametrize("question,intent", [
    ("Can I afford a ₹15 lakh car next year?", "affordability"),
    ("What happens if my salary increases by 20%?", "income_change"),
    ("How much can I save in one year?", "savings"),
    ("What happens if my expenses increase by ₹10,000?", "expense_change"),
    ("How much should I invest monthly to reach ₹50 lakh in 10 years?", "goal"),
    ("Where am I spending the most?", "spending"),
    ("What's my financial health score?", "health"),
])
def test_intents(twin, question, intent):
    answer = twin.answer(question)
    assert answer.intent == intent
    assert "not financial advice" in answer.as_markdown()


def test_answers_use_real_numbers(twin):
    answer = twin.answer("What happens if my salary increases by 20%?")
    assert answer.data["scenario"]["monthly_income"] == pytest.approx(twin.state.avg_income * 1.2, rel=0.01)


def test_missing_data_is_reported(twin):
    answer = twin.answer("Can I afford a ₹15 lakh car next year?")
    assert any("EMI" in m for m in answer.missing)
    goal = twin.answer("How much should I invest monthly for my goal?")
    assert goal.missing


def test_no_data_twin_refuses_to_guess():
    empty = FinancialTwin.from_dataframe(documents_to_dataframe([]))
    answer = empty.answer("Can I afford a car?")
    assert answer.intent == "no_data" and answer.missing


def test_simulation_income_raise_improves_net_worth(twin):
    base, scen = twin.baseline_vs(12, income_change_pct=10)
    assert scen["final_net_worth"] > base["final_net_worth"]


@pytest.mark.parametrize("desc,category,ttype", [
    ("Swiggy order 123", "Food", "Expense"), ("UBER TRIP", "Transport", "Expense"),
    ("Amazon.in order", "Shopping", "Expense"), ("Netflix subscription", "Entertainment", "Expense"),
    ("SALARY CREDIT ACME", "Salary", "Income"), ("SIP Groww fund", "Investment", "Investment"),
    ("random text", "Other", "Expense"),
])
def test_categorizer(desc, category, ttype):
    pred = categorize(desc)
    assert (pred.category, pred.transaction_type) == (category, ttype)
