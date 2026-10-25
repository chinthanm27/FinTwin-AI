"""Shared fixtures: every test runs against a fresh in-memory MongoDB (mongomock)."""

from __future__ import annotations

import dataclasses

import mongomock
import pytest

from app.database import mongodb
from app.services import auth_service, statement_service


@pytest.fixture(autouse=True)
def mock_db():
    db = mongomock.MongoClient()["fintwin_test"]
    mongodb.use_database(db)
    auth_service.reset_rate_limits()
    yield db
    mongodb.use_database(None)


@pytest.fixture
def user():
    return auth_service.register_user("Test User", "test@example.com", "Passw0rd!", "Passw0rd!")


@pytest.fixture
def other_user():
    return auth_service.register_user("Other Person", "other@example.com", "Secret123", "Secret123")


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    """Keep uploads written by tests out of app/uploads."""
    patched = dataclasses.replace(statement_service.settings, uploads_dir=tmp_path / "uploads")
    monkeypatch.setattr(statement_service, "settings", patched)
