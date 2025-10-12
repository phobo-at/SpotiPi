#!/usr/bin/env python3
"""Centralised HTTP session configuration for Spotify API access."""

import logging
import os
import platform
from threading import RLock
from typing import Any, Callable, Optional, Tuple, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

TimeoutValue = Union[float, Tuple[float, float]]

_LOGGER = logging.getLogger("spotify.http")
_SESSION_LOCK = RLock()
_SESSION: Optional[requests.Session] = None
_CONFIG_LOGGED = False


def _parse_timeout_tuple() -> Tuple[float, float]:
    """Parse timeout defaults from environment variables."""
    raw = os.getenv("SPOTIPI_HTTP_TIMEOUTS")
    if raw:
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        if len(parts) == 2:
            try:
                connect = max(0.5, float(parts[0]))
                read = max(1.0, float(parts[1]))
                return connect, read
            except ValueError:
                pass

    connect_env = os.getenv("SPOTIPI_HTTP_CONNECT_TIMEOUT")
    read_env = os.getenv("SPOTIPI_HTTP_READ_TIMEOUT")
    try:
        connect = max(0.5, float(connect_env)) if connect_env else 4.0
    except ValueError:
        connect = 4.0
    try:
        read = max(1.0, float(read_env)) if read_env else 15.0
    except ValueError:
        read = 15.0
    return connect, read


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


DEFAULT_TIMEOUT: Tuple[float, float] = _parse_timeout_tuple()


def _coerce_timeout(value: TimeoutValue) -> TimeoutValue:
    """Normalise timeout values to a tuple of (connect, read)."""
    if isinstance(value, tuple):
        if len(value) == 2:
            return max(0.5, float(value[0])), max(1.0, float(value[1]))
        raise ValueError("Timeout tuples must be length 2 (connect, read)")
    numeric = max(0.5, float(value))
    return numeric, numeric


def _with_default_timeout(
    request_func: Callable[..., requests.Response],
    timeout: Tuple[float, float],
) -> Callable[..., requests.Response]:
    """Wrap session.request to inject default timeouts."""

    def wrapper(method: str, url: str, **kwargs: Any) -> requests.Response:
        provided = kwargs.get("timeout")
        if provided is None:
            kwargs["timeout"] = timeout
        else:
            try:
                kwargs["timeout"] = _coerce_timeout(provided)  # type: ignore[assignment]
            except Exception:
                kwargs["timeout"] = timeout
        return request_func(method, url, **kwargs)

    return wrapper


def _build_retry_configuration() -> Retry:
    status_forcelist = [429, 500, 502, 503, 504]
    allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    backoff = float(os.getenv("SPOTIPI_HTTP_BACKOFF_FACTOR", "0.6"))
    total = int(os.getenv("SPOTIPI_HTTP_RETRY_TOTAL", "5"))
    connect = int(os.getenv("SPOTIPI_HTTP_RETRY_CONNECT", "3"))
    read = int(os.getenv("SPOTIPI_HTTP_RETRY_READ", "4"))
    return Retry(
        total=total,
        connect=connect,
        read=read,
        backoff_factor=backoff,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
        respect_retry_after_header=True,
        raise_on_status=False,
    )


def _log_configuration(session: requests.Session) -> None:
    global _CONFIG_LOGGED
    if _CONFIG_LOGGED:
        return
    _CONFIG_LOGGED = True

    adapter = session.get_adapter("https://")
    pool_connections = getattr(adapter, "pool_connections", None)
    pool_maxsize = getattr(adapter, "pool_maxsize", None)

    _LOGGER.info(
        "HTTP session configured",
        extra={
            "http.timeout_connect": DEFAULT_TIMEOUT[0],
            "http.timeout_read": DEFAULT_TIMEOUT[1],
            "http.retry_total": adapter.max_retries.total if hasattr(adapter, "max_retries") else None,
            "http.pool_connections": pool_connections,
            "http.pool_maxsize": pool_maxsize,
        },
    )


def build_session() -> requests.Session:
    """Create a configured requests.Session with retries and timeouts."""
    session = requests.Session()

    retry = _build_retry_configuration()
    pool_connections = _int_env("SPOTIPI_HTTP_POOL_CONNECTIONS", 10)
    pool_maxsize = _int_env("SPOTIPI_HTTP_POOL_MAXSIZE", 20)
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)
    python_version = platform.python_version()
    session.headers.update(
        {
            "Connection": "keep-alive",
            "Accept": "application/json",
            "User-Agent": f"SpotiPi/1.0 (+RaspberryPi; Python {python_version}; Requests {requests.__version__})",
        }
    )
    session.trust_env = False
    session.request = _with_default_timeout(session.request, DEFAULT_TIMEOUT)

    _log_configuration(session)
    return session


def get_http_session() -> requests.Session:
    """Return the shared HTTP session, creating it if necessary."""
    global _SESSION
    if _SESSION is None:
        with _SESSION_LOCK:
            if _SESSION is None:
                _SESSION = build_session()
    return _SESSION


def set_http_session(session: requests.Session) -> None:
    """
    Override the shared HTTP session (primarily for testing).

    Args:
        session: Preconfigured session instance
    """
    global _SESSION, _CONFIG_LOGGED
    with _SESSION_LOCK:
        _SESSION = session
        _CONFIG_LOGGED = False
        _log_configuration(session)


# Eagerly instantiate for modules that import SESSION directly
SESSION = get_http_session()

__all__ = ["SESSION", "DEFAULT_TIMEOUT", "build_session", "get_http_session", "set_http_session"]
