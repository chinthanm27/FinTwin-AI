"""Registration, login, password change and account deletion."""

from __future__ import annotations

import threading
import time

from app.auth.security import hash_password, verify_password
from app.database import budget_repository, insight_repository, transaction_repository, user_repository
from app.models.user import User
from app.utils.errors import AuthenticationError, ValidationError
from app.utils.logger import get_logger
from app.utils.validators import validate_email, validate_full_name, validate_password

log = get_logger("auth")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300

_failed: dict[str, list[float]] = {}
_failed_lock = threading.Lock()


def _recent_failures(email: str) -> list[float]:
    now = time.time()
    with _failed_lock:
        attempts = [t for t in _failed.get(email, []) if now - t < LOCKOUT_SECONDS]
        _failed[email] = attempts
        return attempts


def _record_failure(email: str) -> None:
    with _failed_lock:
        _failed.setdefault(email, []).append(time.time())


def _clear_failures(email: str) -> None:
    with _failed_lock:
        _failed.pop(email, None)


def reset_rate_limits() -> None:
    """Testing helper."""
    with _failed_lock:
        _failed.clear()


def register_user(full_name: str, email: str, password: str, confirm_password: str) -> User:
    full_name = validate_full_name(full_name)
    email = validate_email(email)
    validate_password(password)
    if password != confirm_password:
        raise ValidationError("Passwords do not match.")
    if user_repository.find_by_email(email):
        raise ValidationError("An account with this email already exists.")
    user = User(full_name=full_name, email=email, password_hash=hash_password(password))
    user = user_repository.create_user(user)
    log.info("Registered user %s", user.id)
    return user


def authenticate(email: str, password: str) -> User:
    email = (email or "").strip().lower()
    if not email or not password:
        raise AuthenticationError("Enter your email and password.")
    if len(_recent_failures(email)) >= MAX_FAILED_ATTEMPTS:
        raise AuthenticationError("Too many failed attempts. Try again in 5 minutes.")
    user = user_repository.find_by_email(email)
    if user is None or not verify_password(password, user.password_hash):
        _record_failure(email)
        raise AuthenticationError("Invalid email or password.")
    _clear_failures(email)
    user_repository.touch_last_login(user.id)
    log.info("User %s logged in", user.id)
    return user


def change_password(user_id: str, current_password: str, new_password: str, confirm_password: str) -> None:
    user = user_repository.find_by_id(user_id)
    if user is None:
        raise AuthenticationError("Your session is no longer valid. Log in again.")
    if not verify_password(current_password, user.password_hash):
        raise ValidationError("Current password is incorrect.")
    validate_password(new_password)
    if new_password != confirm_password:
        raise ValidationError("New passwords do not match.")
    user_repository.update_user(user_id, {"password_hash": hash_password(new_password)})


def update_name(user_id: str, full_name: str) -> str:
    full_name = validate_full_name(full_name)
    user_repository.update_user(user_id, {"full_name": full_name})
    return full_name


def delete_account(user_id: str, password: str) -> None:
    """Delete the user and every record that belongs to them."""
    user = user_repository.find_by_id(user_id)
    if user is None or not verify_password(password, user.password_hash):
        raise ValidationError("Password is incorrect.")
    transaction_repository.delete_all_for_user(user_id)
    budget_repository.delete_all_for_user(user_id)
    insight_repository.delete_all_for_user(user_id)
    user_repository.delete_user(user_id)
    log.info("Deleted account %s", user_id)
