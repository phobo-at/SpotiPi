"""Tests for the performance monitor's bounded route map."""

from __future__ import annotations

from src.utils.perf_monitor import PerfMonitor


def test_route_map_is_bounded_under_high_cardinality_keys():
    """A high-cardinality key source must not grow the route map without bound.

    Regression guard: unmatched/404 requests used to be keyed on the raw URL path,
    so scanner/crawler traffic allocated a permanent RouteMetrics per distinct path.
    """
    monitor = PerfMonitor()

    for i in range(PerfMonitor._MAX_ROUTES + 100):
        monitor.record_request(f"/scan/{i}", 0.01, method="GET", status=404)

    snapshot = monitor.snapshot()
    route_keys = [key for key in snapshot if key != "OVERALL"]

    # Bounded to the cap plus the single shared overflow bucket.
    assert len(route_keys) <= PerfMonitor._MAX_ROUTES + 1
    assert "<overflow>" in snapshot
    # Overflowed requests are still counted (folded into the overflow bucket).
    assert snapshot["<overflow>"]["count"] >= 1
