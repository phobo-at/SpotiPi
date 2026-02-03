"""Shared pytest fixtures for the SpotiPi test suite."""

from __future__ import annotations

import pytest

from src.app import create_app


@pytest.fixture(scope="session")
def app():
    """Create a Flask app instance for the test session."""
    flask_app = create_app(start_warmup=False)
    flask_app.config.update({"TESTING": True})
    return flask_app


@pytest.fixture
def client(app):
    """Provide a fresh Flask test client for each test."""
    with app.test_client() as test_client:
        yield test_client
