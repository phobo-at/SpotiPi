"""
Application factory for SpotiPi.

Provides a stable factory entrypoint while preserving the existing
`src.app` module for backward compatibility.
"""

from __future__ import annotations

from .app import create_app as _create_app


def create_app():
    """Return a freshly constructed Flask application."""
    return _create_app()


__all__ = ["create_app"]
