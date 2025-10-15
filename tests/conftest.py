"""Shared pytest fixtures for the SpotiPi test suite."""

from __future__ import annotations

import pytest

from src.app import app as flask_app


@pytest.fixture(scope="session", autouse=True)
def configure_app() -> None:
    """Put the Flask app into testing mode once for the test session."""
    flask_app.config.update({"TESTING": True})


@pytest.fixture
def client():
    """Provide a fresh Flask test client for each test."""
    with flask_app.test_client() as test_client:
        yield test_client
