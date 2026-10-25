"""Password hashing with bcrypt. Plain-text passwords are never stored."""

from __future__ import annotations

import bcrypt

BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Return a bcrypt hash (salted) for the given password."""
    data = password.encode("utf-8")
    if len(data) > 72:
        raise ValueError("Password exceeds bcrypt's 72-byte limit.")
    return bcrypt.hashpw(data, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time comparison of a password with a stored bcrypt hash."""
    if not password or not password_hash:
        return False
    data = password.encode("utf-8")
    if len(data) > 72:
        return False
    try:
        return bcrypt.checkpw(data, password_hash.encode("utf-8"))
    except ValueError:
        return False
