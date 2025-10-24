#!/usr/bin/env python3
"""Centralised timezone utilities."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .thread_safety import get_thread_safe_config_manager, load_config_safe

_LOGGER = logging.getLogger("timezone")
_FALLBACK_TZ = "Europe/Vienna"


def _extract_timezone(config: Dict[str, Any] | None) -> str | None:
    if not config:
        return None
    tz_value = config.get("timezone")
    if isinstance(tz_value, str):
        tz_value = tz_value.strip()
        if tz_value:
            return tz_value
    return None


def _resolve_timezone_name() -> str:
    env_tz = os.getenv("SPOTIPI_TIMEZONE")
    if env_tz:
        return env_tz.strip()
    try:
        config = load_config_safe()
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Could not load config for timezone resolution: %s", exc)
        return _FALLBACK_TZ
    tz_name = _extract_timezone(config)
    return tz_name or _FALLBACK_TZ


@lru_cache(maxsize=1)
def get_timezone_name() -> str:
    """Return the configured timezone name with caching."""
    return _resolve_timezone_name()


@lru_cache(maxsize=8)
def _zoneinfo_cached(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def get_local_timezone() -> ZoneInfo:
    """Return a ZoneInfo instance based on configuration/env settings."""
    tz_name = get_timezone_name()
    try:
        return _zoneinfo_cached(tz_name)
    except ZoneInfoNotFoundError:
        _LOGGER.warning(
            "Unknown timezone '%s' – falling back to '%s'",
            tz_name,
            _FALLBACK_TZ,
        )
        try:
            return _zoneinfo_cached(_FALLBACK_TZ)
        except ZoneInfoNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("Fallback timezone is unavailable on this system") from exc


def invalidate_timezone_cache() -> None:
    """Clear cached timezone information (called on config change)."""
    get_timezone_name.cache_clear()


def _on_config_change(_config: Dict[str, Any]) -> None:
    """Config change listener to invalidate timezone cache when needed."""
    invalidate_timezone_cache()


try:
    get_thread_safe_config_manager().add_change_listener(_on_config_change)
except Exception as exc:  # pragma: no cover - listener is best-effort
    _LOGGER.debug("Timezone change listener registration failed: %s", exc)
