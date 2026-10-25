import pytest

from app.auth.security import hash_password, verify_password
from app.services import auth_service
from app.utils.errors import AuthenticationError, ValidationError


def test_password_is_hashed_not_stored_plain(mock_db, user):
    doc = mock_db.users.find_one({"email": "test@example.com"})
    assert doc["password_hash"] != "Passw0rd!"
    assert doc["password_hash"].startswith("$2")
    assert verify_password("Passw0rd!", doc["password_hash"])


def test_hash_and_verify_roundtrip():
    hashed = hash_password("abc12345")
    assert verify_password("abc12345", hashed)
    assert not verify_password("wrong123", hashed)
    assert not verify_password("", hashed)


def test_login_success_and_case_insensitive_email(user):
    logged = auth_service.authenticate("TEST@example.com ", "Passw0rd!")
    assert logged.id == user.id


def test_login_wrong_password_gives_generic_error(user):
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        auth_service.authenticate("test@example.com", "nope12345")


def test_login_unknown_email_gives_same_error():
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        auth_service.authenticate("ghost@example.com", "whatever1")


def test_login_rate_limited_after_repeated_failures(user):
    for _ in range(auth_service.MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthenticationError):
            auth_service.authenticate("test@example.com", "bad-pass1")
    with pytest.raises(AuthenticationError, match="Too many failed attempts"):
        auth_service.authenticate("test@example.com", "Passw0rd!")


def test_duplicate_email_rejected(user):
    with pytest.raises(ValidationError, match="already exists"):
        auth_service.register_user("Someone", "test@example.com", "Another12", "Another12")


@pytest.mark.parametrize(
    "name,email,password,confirm,message",
    [
        ("A", "a@b.com", "abc12345", "abc12345", "Full name"),
        ("Valid Name", "not-an-email", "abc12345", "abc12345", "valid email"),
        ("Valid Name", "a@b.com", "short1", "short1", "at least 8"),
        ("Valid Name", "a@b.com", "lettersonly", "lettersonly", "letter and one number"),
        ("Valid Name", "a@b.com", "abc12345", "abc12346", "do not match"),
    ],
)
def test_registration_validation(name, email, password, confirm, message):
    with pytest.raises(ValidationError, match=message):
        auth_service.register_user(name, email, password, confirm)


def test_change_password(user):
    auth_service.change_password(user.id, "Passw0rd!", "NewPass99", "NewPass99")
    assert auth_service.authenticate("test@example.com", "NewPass99").id == user.id


def test_delete_account_removes_all_user_data(mock_db, user):
    from app.services import transaction_service

    transaction_service.add_transaction(user.id, "2026-01-05", "Food", "Expense", 500, "Lunch")
    auth_service.delete_account(user.id, "Passw0rd!")
    assert mock_db.users.count_documents({}) == 0
    assert mock_db.transactions.count_documents({"user_id": user.id}) == 0
