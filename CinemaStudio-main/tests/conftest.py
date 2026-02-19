"""
conftest.py — Pytest fixtures for Coffee-with-Cinema tests.
"""

import os
import tempfile
import pytest
from app import create_app


@pytest.fixture
def app():
    """Create a test Flask app with an in-memory SQLite database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    test_config = {
        "TESTING": True,
        "DATABASE": db_path,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "SESSION_COOKIE_SECURE": False,
    }

    application = create_app(test_config)

    yield application

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Return a test client for the app."""
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    """Return a client with a username set in the session."""
    with client.session_transaction() as sess:
        sess["username"] = "testuser"
    return client
