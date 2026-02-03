"""
🚨 Error Handlers
Centralized HTTP error handling for API and browser routes.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict

from flask import Flask, render_template, request

from ..config import load_config
from ..utils.translations import get_translations, get_user_language, t_api
from ..version import VERSION, get_app_info
from .helpers import api_error


def _build_template_context(config: Dict[str, Any], *, error_message: str) -> Dict[str, Any]:
    user_language = get_user_language(request)
    translations = get_translations(user_language)

    def template_t(key, **kwargs):
        from ..utils.translations import t
        return t(key, user_language, **kwargs)

    feature_flags = {
        "sleep_timer": config.get("feature_sleep", False),
        "music_library": config.get("feature_library", True),
    }

    return {
        "error_message": error_message,
        "config": config,
        "devices": [],
        "playlists": [],
        "next_alarm_info": "",
        "sleep_status": {},
        "initial_state": {},
        "feature_flags": feature_flags,
        "t": template_t,
        "translations": translations,
        "lang": user_language,
        "now": datetime.datetime.now(),
        "app_info": get_app_info(),
        "version": VERSION,
    }


def register_error_handlers(app: Flask) -> None:
    """Register shared error handlers on the Flask app."""

    @app.errorhandler(404)
    def not_found_error(_error):  # type: ignore[unused-argument]
        if request.path.startswith("/api/") or request.is_json:
            return api_error(
                t_api("page_not_found", request),
                status=404,
                error_code="not_found",
            )
        config = {}
        try:
            config = load_config()
        except Exception:
            config = {}
        context = _build_template_context(config, error_message=t_api("page_not_found"))
        return render_template("index.html", **context), 404

    @app.errorhandler(500)
    def internal_error(_error):  # type: ignore[unused-argument]
        if request.path.startswith("/api/") or request.is_json:
            return api_error(
                t_api("internal_server_error_page", request),
                status=500,
                error_code="internal_error",
            )
        config = {}
        try:
            config = load_config()
        except Exception:
            config = {}
        context = _build_template_context(config, error_message=t_api("internal_server_error_page"))
        return render_template("index.html", **context), 500
