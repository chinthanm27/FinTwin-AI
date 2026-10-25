import pytest

from app.database import budget_repository, insight_repository, transaction_repository
from app.database.mongodb import COLLECTIONS, check_connection
from app.services import budget_service, transaction_service
from app.utils.errors import ValidationError


def test_connection_check():
    ok, _ = check_connection()
    assert ok


def test_all_collections_known():
    assert set(COLLECTIONS) == {"users", "transactions", "budgets", "financial_profiles", "predictions",
                                "fraud_alerts", "ai_conversations", "reports"}


def test_transactions_are_isolated_between_users(user, other_user):
    mine = transaction_service.add_transaction(user.id, "2026-01-01", "Food", "Expense", 100, "mine")
    transaction_service.add_transaction(other_user.id, "2026-01-01", "Food", "Expense", 999, "theirs")
    assert [t.description for t in transaction_service.list_transactions(user.id)] == ["mine"]
    assert transaction_repository.get_transaction(other_user.id, mine.id) is None


def test_cannot_modify_or_delete_another_users_transaction(user, other_user):
    mine = transaction_service.add_transaction(user.id, "2026-01-01", "Food", "Expense", 100, "mine")
    with pytest.raises(ValidationError):
        transaction_service.update_transaction(other_user.id, mine.id, {"amount": 1})
    with pytest.raises(ValidationError):
        transaction_service.delete_transaction(other_user.id, mine.id)
    assert transaction_service.list_transactions(user.id)[0].amount == 100


def test_invalid_object_id_is_handled(user):
    assert transaction_repository.get_transaction(user.id, "not-an-id") is None
    assert transaction_repository.delete_transaction(user.id, "zzz") is False


def test_budgets_isolated_and_upserted(user, other_user):
    budget_service.set_budget(user.id, "Food", 8000)
    budget_service.set_budget(user.id, "Food", 9000)
    budget_service.set_budget(other_user.id, "Food", 1000)
    mine = budget_repository.get_budgets(user.id)
    assert len(mine) == 1 and mine[0].monthly_limit == 9000


def test_profile_and_conversation_scoped(user, other_user):
    profile = insight_repository.get_profile(user.id)
    profile.emergency_fund = 50000
    insight_repository.save_profile(profile)
    assert insight_repository.get_profile(other_user.id).emergency_fund is None
    insight_repository.add_message(user.id, "user", "hello")
    assert insight_repository.get_messages(other_user.id) == []
    assert len(insight_repository.get_messages(user.id)) == 1
