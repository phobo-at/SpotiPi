"""
Application factory for SpotiPi.

Provides a stable factory entrypoint while preserving the existing
`src.app` module for backward compatibility.
"""

from __future__ import annotations

from .app import app as _app


def create_app():
    """Return the configured Flask application."""
    return _app


__all__ = ["create_app"]

