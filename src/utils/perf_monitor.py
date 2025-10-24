#!/usr/bin/env python3
"""Lightweight performance instrumentation for SpotiPi."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, Dict, Iterable, Optional


@dataclass
class RouteMetrics:
    """Aggregated timings for a single logical route or block."""

    samples: Deque[float]
    total: float = 0.0
    count: int = 0
    slowest: float = 0.0
    last_logged: float = 0.0
    last_duration: float = 0.0
    last_status: int = 0
    lock: Lock = field(default_factory=Lock)


class PerfMonitor:
    """Collect high-resolution request and block timings."""

    def __init__(self) -> None:
        self._routes: Dict[str, RouteMetrics] = {}
        self._overall: RouteMetrics = RouteMetrics(samples=deque(maxlen=self._max_samples()))
        self._lock = Lock()
        self._logger = logging.getLogger("perf")
        self._log_interval = float(os.getenv("SPOTIPI_PERF_LOG_INTERVAL", "30"))
        self._warn_threshold = float(os.getenv("SPOTIPI_PERF_WARN_THRESHOLD", "1.5"))
        self._maxlen = self._max_samples()

    @staticmethod
    def _max_samples() -> int:
        try:
            return max(20, int(os.getenv("SPOTIPI_PERF_MAX_SAMPLES", "200")))
        except ValueError:
            return 200

    def _ensure_route(self, key: str) -> RouteMetrics:
        metrics = self._routes.get(key)
        if metrics is None:
            with self._lock:
                metrics = self._routes.get(key)
                if metrics is None:
                    metrics = RouteMetrics(samples=deque(maxlen=self._maxlen))
                    self._routes[key] = metrics
        return metrics

    def record_request(
        self,
        name: str,
        duration: float,
        *,
        method: str,
        status: int,
        path: Optional[str] = None,
    ) -> None:
        """Record a Flask request timing."""
        label = f"{method} {name}"
        metrics = self._ensure_route(label)
        self._update_metrics(metrics, duration, status)
        self._update_metrics(self._overall, duration, status)
        self._maybe_log(label, metrics, duration, path=path)

    def record_block(self, name: str, duration: float) -> None:
        """Record a named code block timing."""
        label = f"BLOCK {name}"
        metrics = self._ensure_route(label)
        self._update_metrics(metrics, duration, metrics.last_status)
        self._maybe_log(label, metrics, duration)

    def _update_metrics(self, metrics: RouteMetrics, duration: float, status: int) -> None:
        with metrics.lock:
            metrics.count += 1
            metrics.total += duration
            metrics.last_duration = duration
            metrics.last_status = status
            metrics.samples.append(duration)
            if duration > metrics.slowest:
                metrics.slowest = duration

    def _maybe_log(self, label: str, metrics: RouteMetrics, duration: float, *, path: Optional[str] = None) -> None:
        now = time.time()
        should_warn = duration >= self._warn_threshold
        with metrics.lock:
            elapsed = now - metrics.last_logged
            if not should_warn and elapsed < self._log_interval:
                return
            snapshot = self._compute_snapshot(metrics.samples)
            avg = (metrics.total / metrics.count) if metrics.count else 0.0
            message = (
                f"{label} avg={avg:.3f}s p50={snapshot['p50']:.3f}s "
                f"p95={snapshot['p95']:.3f}s latest={metrics.last_duration:.3f}s "
                f"slowest={metrics.slowest:.3f}s count={metrics.count}"
            )
            if path:
                message += f" path={path}"
            if should_warn:
                self._logger.warning(message)
            else:
                self._logger.info(message)
            metrics.last_logged = now

    @staticmethod
    def _compute_snapshot(samples: Iterable[float]) -> Dict[str, float]:
        data = list(samples)
        if not data:
            return {"p50": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        data.sort()
        return {
            "p50": PerfMonitor._percentile(data, 0.50),
            "p95": PerfMonitor._percentile(data, 0.95),
            "min": data[0],
            "max": data[-1],
        }

    @staticmethod
    def _percentile(sorted_values: Iterable[float], percentile: float) -> float:
        values = list(sorted_values)
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        index = percentile * (len(values) - 1)
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        weight = index - lower
        return values[lower] * (1 - weight) + values[upper] * weight

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Return current metrics as a JSON-serialisable dict."""
        result: Dict[str, Dict[str, float]] = {}
        for label, metrics in self._routes.items():
            with metrics.lock:
                stats = self._compute_snapshot(metrics.samples)
                avg = (metrics.total / metrics.count) if metrics.count else 0.0
                result[label] = {
                    "count": metrics.count,
                    "avg_ms": avg * 1000,
                    "p50_ms": stats["p50"] * 1000,
                    "p95_ms": stats["p95"] * 1000,
                    "min_ms": stats["min"] * 1000,
                    "max_ms": stats["max"] * 1000,
                    "latest_ms": metrics.last_duration * 1000,
                    "slowest_ms": metrics.slowest * 1000,
                    "last_status": metrics.last_status,
                }
        with self._overall.lock:
            stats = self._compute_snapshot(self._overall.samples)
            avg = (self._overall.total / self._overall.count) if self._overall.count else 0.0
            result["OVERALL"] = {
                "count": self._overall.count,
                "avg_ms": avg * 1000,
                "p50_ms": stats["p50"] * 1000,
                "p95_ms": stats["p95"] * 1000,
                "min_ms": stats["min"] * 1000,
                "max_ms": stats["max"] * 1000,
                "slowest_ms": self._overall.slowest * 1000,
            }
        return result

    @contextmanager
    def time_block(self, name: str):
        """Context manager to measure arbitrary code blocks."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.record_block(name, duration)


perf_monitor = PerfMonitor()

__all__ = ["perf_monitor"]
