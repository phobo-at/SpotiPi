"""Simplified rate limiting tuned for single-user LAN deployments.

The original implementation supported multiple algorithms, per-client
deques and verbose statistics.  That flexibility consumed unnecessary
CPU/RAM on Raspberry Pi Zero systems.  This module keeps the public API
but implements a lightweight sliding-window limiter with minimal state.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Dict, Optional

from flask import g, jsonify, request

LOW_POWER_MODE = os.getenv("SPOTIPI_LOW_POWER", "").lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class RateLimitRule:
    """Definition of a rate limiting rule."""

    name: str
    requests_per_window: int
    window_seconds: float
    block_duration_seconds: float
    limit_type: str = "sliding_window"
    exempt_ips: tuple[str, ...] = ()


@dataclass
class RateLimitStatus:
    """Current status result returned by the limiter."""

    requests_made: int
    requests_remaining: int
    window_reset_time: float
    is_blocked: bool
    block_expires_at: Optional[float] = None


class SimpleRateLimiter:
    """Lightweight sliding-window rate limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: Dict[str, RateLimitRule] = {}
        self._state: Dict[tuple[str, str], tuple[int, float, float]] = {}
        self._start = time.monotonic()
        self._start_wall = time.time()
        self._total_requests = 0
        self._blocked_requests = 0
        self._enabled = os.getenv("SPOTIPI_DISABLE_RATE_LIMIT", "0") != "1" and not LOW_POWER_MODE
        self._install_default_rules()

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------
    def _install_default_rules(self) -> None:
        self.add_rule(RateLimitRule("api_general", 300, 60.0, 30.0, "sliding_window"))
        self.add_rule(RateLimitRule("api_strict", 80, 60.0, 30.0, "sliding_window"))
        self.add_rule(RateLimitRule("config_changes", 60, 60.0, 30.0, "sliding_window"))
        self.add_rule(RateLimitRule("music_library", 120, 60.0, 30.0, "token_bucket"))
        self.add_rule(RateLimitRule("spotify_api", 100, 60.0, 45.0, "sliding_window"))
        self.add_rule(RateLimitRule("status_check", 200, 10.0, 30.0, "sliding_window"))

    def add_rule(self, rule: RateLimitRule) -> None:
        self._rules[rule.name] = rule

    def remove_rule(self, rule_name: str) -> bool:
        return self._rules.pop(rule_name, None) is not None

    def get_rules_summary(self) -> Dict[str, Dict[str, float]]:
        return {
            name: {
                "requests_per_window": rule.requests_per_window,
                "window_seconds": rule.window_seconds,
                "block_duration": rule.block_duration_seconds,
                "limit_type": rule.limit_type,
            }
            for name, rule in self._rules.items()
        }

    # ------------------------------------------------------------------
    # Core limiter
    # ------------------------------------------------------------------
    def _resolve_client_id(self) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr or "127.0.0.1"
        user_agent = request.headers.get("User-Agent", "")[:64]
        ua_hash = hash(user_agent) & 0xFFFF
        return f"{ip}:{ua_hash:x}"

    def check_rate_limit(self, rule_name: str, client_id: Optional[str] = None) -> RateLimitStatus:
        if not self._enabled:
            return RateLimitStatus(0, 999999, time.time() + 3600, False)

        rule = self._rules.get(rule_name)
        if not rule:
            return RateLimitStatus(0, 999999, time.time() + 3600, False)

        if client_id is None:
            client_id = self._resolve_client_id()

        client_ip = client_id.split(":", 1)[0]
        if client_ip in rule.exempt_ips:
            return RateLimitStatus(0, 999999, time.time() + 3600, False)

        now_mono = time.monotonic()
        now_wall = time.time()
        state_key = (client_id, rule.name)

        with self._lock:
            count, window_start, blocked_until = self._state.get(state_key, (0, now_mono, 0.0))

            if blocked_until > now_mono:
                self._blocked_requests += 1
                reset_seconds = max(0.0, blocked_until - now_mono)
                reset_at = now_wall + reset_seconds
                return RateLimitStatus(count, 0, reset_at, True, reset_at)

            if now_mono - window_start >= rule.window_seconds:
                count = 0
                window_start = now_mono

            count += 1
            self._total_requests += 1

            if count > rule.requests_per_window:
                blocked_until = now_mono + rule.block_duration_seconds
                self._state[state_key] = (count, window_start, blocked_until)
                self._blocked_requests += 1
                reset_at = now_wall + rule.block_duration_seconds
                return RateLimitStatus(rule.requests_per_window, 0, reset_at, True, reset_at)

            self._state[state_key] = (count, window_start, 0.0)
            remaining = max(0, rule.requests_per_window - count)
            reset_seconds = max(0.0, rule.window_seconds - (now_mono - window_start))
            reset_at = now_wall + reset_seconds
            return RateLimitStatus(count, remaining, reset_at, False, None)

    def is_request_allowed(self, rule_name: str, client_id: Optional[str] = None) -> bool:
        status = self.check_rate_limit(rule_name, client_id)
        return not status.is_blocked

    # ------------------------------------------------------------------
    # Diagnostics / control
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:  # type: ignore[override]
        with self._lock:
            uptime = time.monotonic() - self._start
            block_rate = 0.0 if self._total_requests == 0 else (self._blocked_requests / self._total_requests) * 100.0
            requests_per_second = self._total_requests / max(uptime, 1.0)

            unique_clients = {client for client, _ in self._state.keys()}
            storage_stats = {
                "total_clients": len(unique_clients),
                "tracked_entries": len(self._state),
            }

            statistics = {
                "uptime_seconds": uptime,
                "requests_per_second": requests_per_second,
                "block_rate_percent": block_rate,
                "global_stats": {
                    "total_requests": self._total_requests,
                    "blocked_requests": self._blocked_requests,
                    "start_time": self._start_wall,
                },
                "storage_stats": storage_stats,
            }

        return {
            "enabled": self._enabled,
            "statistics": statistics,
            "rules": self.get_rules_summary(),
        }

    def get_statistics(self) -> Dict[str, Any]:  # compatibility alias
        return self.get_stats()

    def reset(self) -> None:
        with self._lock:
            self._state.clear()
            self._start = time.monotonic()
            self._start_wall = time.time()
            self._total_requests = 0
            self._blocked_requests = 0

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False


_rate_limiter: Optional[SimpleRateLimiter] = None


def get_rate_limiter() -> SimpleRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SimpleRateLimiter()
    return _rate_limiter


def rate_limit(rule_name: str, error_response: Optional[Dict[str, Any]] = None):  # type: ignore[name-defined]
    """Decorator that applies rate limiting to Flask routes."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            status = limiter.check_rate_limit(rule_name)
            if status.is_blocked:
                payload = error_response or {
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please retry later.",
                }
                response = jsonify(payload)
                response.status_code = 429
                response.headers["Retry-After"] = str(
                    max(1, int(status.block_expires_at - time.time()))
                ) if status.block_expires_at else "1"
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(status.window_reset_time))
                return response

            g.rate_limit_status = status
            return func(*args, **kwargs)

        return wrapper

    return decorator


def add_rate_limit_headers(response):
    """Attach rate limit metadata to responses when available."""

    status: RateLimitStatus | None = getattr(g, "rate_limit_status", None)
    if status is not None:
        response.headers["X-RateLimit-Remaining"] = str(status.requests_remaining)
        response.headers["X-RateLimit-Reset"] = str(int(status.window_reset_time))
    return response
