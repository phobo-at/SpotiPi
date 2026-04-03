"""Lightweight thread-safe configuration helpers for SpotiPi.

The previous implementation used deep copies, read/write locks and
thread-local caches.  On constrained hardware (Pi Zero W) this caused
measurable overhead for every request.  The replacement keeps the same
public API while reducing allocations and lock contention.
"""

from __future__ import annotations

import copy
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

# Detect low-power mode for adaptive cache TTL
_LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')

# Adaptive Config Cache TTL: Longer on Pi Zero W to reduce SD-Card I/O
# Default: 30s on Pi (config changes rarely), 5s on Dev machines (faster iteration)
_DEFAULT_TTL = "30.0" if _LOW_POWER_MODE else "5.0"
_CACHE_TTL = max(0.5, float(os.getenv("SPOTIPI_CONFIG_CACHE_TTL", _DEFAULT_TTL)))


@dataclass
class ConfigTransaction:
    """Represents a configuration transaction with rollback capability."""

    original_config: Dict[str, Any]
    new_config: Dict[str, Any]


class ThreadSafeConfigManager:
    """Lightweight wrapper around the base ConfigManager.

    Uses a simple mutex and a small in-memory snapshot to avoid repeated disk
    reads while keeping behaviour predictable across threads.
    """

    def __init__(self, base_config_manager):
        self._base_manager = base_config_manager
        self._lock = threading.RLock()
        self._cache: Dict[str, Any] | None = None
        self._cache_timestamp: float = 0.0
        self._listeners: list[Callable[[Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _snapshot(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(config)

    def _deep_snapshot(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(config)

    def _cache_stale(self) -> bool:
        if self._cache is None:
            return True
        return (time.monotonic() - self._cache_timestamp) > _CACHE_TTL

    def _notify_listeners(
        self,
        config: Dict[str, Any],
        listeners: Optional[list[Callable[[Dict[str, Any]], None]]] = None
    ) -> None:
        targets = list(listeners) if listeners is not None else list(self._listeners)
        for callback in targets:
            try:
                callback(self._snapshot(config))
            except Exception:
                # Never let listener failures break config writes
                continue

    def _save_config_locked(self, snapshot: Dict[str, Any]) -> bool:
        success = self._base_manager.save_config(snapshot)
        if success:
            self._cache = self._snapshot(snapshot)
            self._cache_timestamp = time.monotonic()
        return success

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_change_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_change_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def load_config(self, use_cache: bool = True) -> Dict[str, Any]:
        with self._lock:
            if not use_cache:
                self._cache = None
            if self._cache_stale():
                config = self._base_manager.load_config()
                self._cache = self._snapshot(config)
                self._cache_timestamp = time.monotonic()
            return self._snapshot(self._cache)

    def save_config(self, config: Dict[str, Any], notify_listeners: bool = True) -> bool:
        snapshot = self._snapshot(config)
        listeners_snapshot: Optional[list[Callable[[Dict[str, Any]], None]]] = None
        with self._lock:
            success = self._save_config_locked(snapshot)
            if success and notify_listeners:
                listeners_snapshot = list(self._listeners)
        if success and notify_listeners and listeners_snapshot:
            self._notify_listeners(snapshot, listeners_snapshot)
        return success

    def get_config_value(self, key: str, default: Any = None) -> Any:
        config = self.load_config()
        return config.get(key, default)

    def set_config_value(self, key: str, value: Any) -> bool:
        return self.update_config_atomic(lambda config: {**config, key: value})

    def update_config_atomic(
        self,
        mutator: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
        notify_listeners: bool = True,
    ) -> bool:
        """Apply a config mutation atomically under one lock and one write."""
        listeners_snapshot: Optional[list[Callable[[Dict[str, Any]], None]]] = None
        updated_snapshot: Optional[Dict[str, Any]] = None

        with self._lock:
            if self._cache_stale():
                config = self._base_manager.load_config()
                self._cache = self._snapshot(config)
                self._cache_timestamp = time.monotonic()

            current = self._snapshot(self._cache or {})
            result = mutator(current)
            updated = current if result is None else result
            updated_snapshot = self._snapshot(updated)

            success = self._save_config_locked(updated_snapshot)
            if success and notify_listeners:
                listeners_snapshot = list(self._listeners)

        if success and notify_listeners and listeners_snapshot and updated_snapshot is not None:
            self._notify_listeners(updated_snapshot, listeners_snapshot)
        return success

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_timestamp = 0.0

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            age = None
            if self._cache is not None:
                age = time.monotonic() - self._cache_timestamp
            return {
                "cache_age_seconds": age,
                "listeners": len(self._listeners),
                "ttl": _CACHE_TTL,
            }

    @contextmanager
    def config_transaction(self):
        listeners_snapshot: Optional[list[Callable[[Dict[str, Any]], None]]] = None
        pending_snapshot: Optional[Dict[str, Any]] = None
        with self._lock:
            if self._cache_stale():
                config = self._base_manager.load_config()
                self._cache = self._snapshot(config)
                self._cache_timestamp = time.monotonic()

            base_snapshot = self._snapshot(self._cache or {})
            manager = _ConfigTransactionContext(self, base_snapshot)
            try:
                yield manager
            except Exception:
                manager.rollback()
                raise

            if manager.dirty:
                pending_snapshot = manager.pending_snapshot()
                success = self._save_config_locked(pending_snapshot)
                if not success:
                    raise RuntimeError("Failed to commit configuration transaction")
                listeners_snapshot = list(self._listeners)

        if listeners_snapshot and pending_snapshot is not None:
            self._notify_listeners(pending_snapshot, listeners_snapshot)


class _ConfigTransactionContext:
    """Context manager that keeps config changes atomic."""

    def __init__(self, manager: ThreadSafeConfigManager, base_snapshot: Dict[str, Any]):
        self._manager = manager
        self._original = manager._deep_snapshot(base_snapshot)
        self._pending = self._manager._deep_snapshot(self._original)
        self._dirty = False

    def load(self) -> Dict[str, Any]:
        return self._manager._deep_snapshot(self._pending)

    def save(self, config: Dict[str, Any]) -> bool:
        self._pending = self._manager._deep_snapshot(config)
        self._dirty = True
        return True

    @property
    def dirty(self) -> bool:
        return self._dirty

    def pending_snapshot(self) -> Dict[str, Any]:
        return self._manager._deep_snapshot(self._pending)

    def rollback(self) -> bool:
        self._pending = self._manager._deep_snapshot(self._original)
        self._dirty = False
        return True


_thread_safe_config_manager: Optional[ThreadSafeConfigManager] = None


def initialize_thread_safe_config(base_config_manager) -> None:
    global _thread_safe_config_manager
    _thread_safe_config_manager = ThreadSafeConfigManager(base_config_manager)


def get_thread_safe_config_manager() -> ThreadSafeConfigManager:
    if _thread_safe_config_manager is None:
        raise RuntimeError(
            "Thread-safe config manager not initialized. Call initialize_thread_safe_config() first."
        )
    return _thread_safe_config_manager


def load_config_safe() -> Dict[str, Any]:
    return get_thread_safe_config_manager().load_config()


def save_config_safe(config: Dict[str, Any]) -> bool:
    return get_thread_safe_config_manager().save_config(config)


def get_config_value_safe(key: str, default: Any = None) -> Any:
    return get_thread_safe_config_manager().get_config_value(key, default)


def set_config_value_safe(key: str, value: Any) -> bool:
    return get_thread_safe_config_manager().set_config_value(key, value)


def update_config_atomic(mutator: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]) -> bool:
    return get_thread_safe_config_manager().update_config_atomic(mutator)


def config_transaction():
    return get_thread_safe_config_manager().config_transaction()


def invalidate_config_cache() -> None:
    get_thread_safe_config_manager().invalidate_cache()


def get_config_stats() -> Dict[str, Any]:
    return get_thread_safe_config_manager().get_stats()
