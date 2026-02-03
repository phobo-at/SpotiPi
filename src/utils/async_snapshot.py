"""
Thread-safe async snapshot cache for lightweight background refreshes.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional


class AsyncSnapshot:
    """Thread-safe helper for asynchronously refreshed snapshots."""

    def __init__(self, name: str, ttl: float, *, min_retry: float = 0.75):
        self._name = name
        self._ttl = max(0.1, float(ttl))
        self._min_retry = max(0.1, float(min_retry))
        self._lock = threading.Lock()
        self._data: Any | None = None
        self._expires_at: float = 0.0
        self._refreshing: bool = False
        self._last_refresh: float = 0.0
        self._last_error: Optional[str] = None
        self._last_error_at: float = 0.0
        self._pending_reason: Optional[str] = None
        self._next_refresh_allowed: float = 0.0

    def snapshot(self) -> tuple[Any | None, Dict[str, Any]]:
        """Return a deep copy of the cached data with metadata."""
        now = time.time()
        with self._lock:
            data_copy = copy.deepcopy(self._data) if self._data is not None else None
            meta = {
                "fresh": data_copy is not None and now < self._expires_at,
                "pending": data_copy is None or now >= self._expires_at,
                "refreshing": self._refreshing,
                "age": (now - self._last_refresh) if self._last_refresh else None,
                "last_refresh": self._last_refresh,
                "last_error": self._last_error,
                "last_error_at": self._last_error_at,
                "pending_reason": self._pending_reason,
                "ttl": self._ttl,
                "has_data": data_copy is not None,
                "next_refresh_allowed": self._next_refresh_allowed,
            }
        return data_copy, meta

    def mark_stale(self) -> None:
        """Force the snapshot to be considered stale."""
        with self._lock:
            self._expires_at = 0.0

    def set(self, payload: Any) -> None:
        """Store a payload immediately, bypassing fetcher logic."""
        now = time.time()
        with self._lock:
            self._data = copy.deepcopy(payload)
            self._last_refresh = now
            self._expires_at = now + self._ttl if self._ttl > 0 else now
            self._last_error = None
            self._last_error_at = 0.0
            self._pending_reason = None
            self._refreshing = False

    def schedule_refresh(
        self,
        fetcher: Callable[[], Any],
        *,
        force: bool = False,
        reason: str = "api",
    ) -> bool:
        """Trigger an asynchronous refresh if needed."""
        now = time.time()
        with self._lock:
            if self._refreshing:
                return False
            if not force:
                if self._data is not None and now < self._expires_at:
                    return False
                if self._data is None and now < self._next_refresh_allowed:
                    return False
            self._refreshing = True
            self._pending_reason = reason
            self._next_refresh_allowed = now + self._min_retry

        def _runner():
            snapshot_logger = logging.getLogger("spotipi.snapshot")
            try:
                payload = fetcher()
                refreshed_at = time.time()
                with self._lock:
                    self._data = copy.deepcopy(payload)
                    self._last_refresh = refreshed_at
                    self._expires_at = refreshed_at + self._ttl if self._ttl > 0 else refreshed_at
                    self._last_error = None
                    self._last_error_at = 0.0
                    self._pending_reason = None
            except Exception as exc:
                snapshot_logger.warning("Async snapshot %s refresh failed: %s", self._name, exc)
                with self._lock:
                    self._last_error = str(exc)
                    self._last_error_at = time.time()
            finally:
                with self._lock:
                    self._refreshing = False

        threading.Thread(
            target=_runner,
            name=f"{self._name}-snapshot-refresh",
            daemon=True,
        ).start()
        return True

