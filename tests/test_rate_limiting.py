#!/usr/bin/env python3
"""
🚨 Rate Limiting Test Suite (App-TestClient)
===========================================

Runs rate limiting checks directly against the Flask test client so the
suite works in CI without a live server.
"""

import concurrent.futures

import pytest

from src.app import app


@pytest.fixture(autouse=True)
def reset_rate_limits(client):
    """Ensure each test starts with a clean rate limiter state."""
    client.post('/api/rate-limiting/reset')


def test_rate_limiting_status(client):
    response = client.get('/api/rate-limiting/status')
    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert "data" in data
    assert "rate_limiting" in data["data"]

    rules = data["data"]["rate_limiting"]["rules"]
    expected_rules = {
        "api_general", "api_strict", "config_changes",
        "music_library", "spotify_api", "status_check"
    }

    assert expected_rules.issubset(rules.keys())
    for rule_name in expected_rules:
        rule = rules[rule_name]
        assert "requests_per_window" in rule
        assert "limit_type" in rule


def test_status_check_rate_limit(client):
    responses = [client.get('/sleep_status') for _ in range(10)]
    assert all(resp.status_code == 200 for resp in responses)


def test_config_change_rate_limit(client):
    payload = {
        "time": "07:00",
        "enabled": "true"
    }

    responses = [client.post('/save_alarm', data=payload) for _ in range(5)]
    success_codes = {200, 302}
    assert all(resp.status_code in success_codes for resp in responses)


def test_concurrent_requests():
    """Simulate concurrent requests by spawning fresh clients per thread."""

    def make_request() -> int:
        with app.test_client() as local_client:
            return local_client.get('/sleep_status').status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: make_request(), range(20)))

    success_count = sum(1 for code in results if code == 200)
    assert success_count >= 18


def test_rate_limiting_reset(client):
    for _ in range(5):
        client.get('/sleep_status')

    initial_stats = client.get('/api/rate-limiting/status').get_json()
    initial_total = initial_stats["data"]["rate_limiting"]["statistics"]["global_stats"]["total_requests"]
    assert initial_total >= 5

    reset_response = client.post('/api/rate-limiting/reset')
    assert reset_response.status_code == 200

    final_stats = client.get('/api/rate-limiting/status').get_json()
    final_global = final_stats["data"]["rate_limiting"]["statistics"]["global_stats"]
    final_storage = final_stats["data"]["rate_limiting"]["statistics"]["storage_stats"]["total_clients"]

    assert final_global["total_requests"] <= 1
    assert final_global["blocked_requests"] == 0
    assert final_storage <= 1


def test_different_algorithms(client):
    status = client.get('/api/rate-limiting/status').get_json()
    rules = status["data"]["rate_limiting"]["rules"]

    algorithms = {rule["limit_type"] for rule in rules.values()}
    assert {"sliding_window", "token_bucket"}.issubset(algorithms)
