#!/usr/bin/env python3
"""
🏗️ Service Layer Test Suite (App-TestClient)
===========================================

Exercises service layer endpoints using Flask's test client so the suite can
run without an external server.
"""

import time

import pytest

from src.app import app


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_service_health(client):
    response = client.get('/api/services/health')
    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True

    health = data["data"]["health"]
    assert health["overall_healthy"] is True
    assert health["total_services"] == health["healthy_services"] >= 4

    services = health["services"]
    for name in ["alarm", "spotify", "sleep", "system"]:
        assert name in services
        assert services[name]["healthy"] is True


def test_service_performance(client):
    response = client.get('/api/services/performance')
    assert response.status_code == 200

    data = response.get_json()
    performance = data["data"]["performance"]
    resource_usage = performance["resource_usage"]

    assert resource_usage["memory_mb"] < 200
    assert 0 <= resource_usage["cpu_percent"] <= 100


def test_service_diagnostics(client):
    response = client.get('/api/services/diagnostics')
    assert response.status_code == 200

    diagnostics = response.get_json()["data"]["diagnostics"]
    tests = diagnostics["tests"]
    assert tests
    assert all(test["status"] == "pass" for test in tests)
    assert diagnostics["summary"]["overall_status"] == "healthy"


def test_alarm_service_integration(client):
    response = client.get('/alarm_status')
    assert response.status_code == 200

    alarm = response.get_json()["data"]
    for field in ["enabled", "time", "weekdays", "alarm_volume"]:
        assert field in alarm


def test_spotify_service_integration(client):
    response = client.get('/api/spotify/auth-status')
    if response.status_code == 401:
        data = response.get_json()
        assert data["success"] is False
        assert data.get("error_code") == "AUTH_REQUIRED"
    else:
        data = response.get_json()
        assert data["success"] is True
        assert "spotify" in data["data"]


def test_sleep_service_integration(client):
    response = client.get('/sleep_status?advanced=true')
    assert response.status_code == 200

    sleep = response.get_json()["data"]["sleep"]
    for field in ["active", "remaining_time", "total_duration"]:
        assert field in sleep


def test_service_response_times(client):
    endpoints = [
        '/api/services/health',
        '/api/services/performance',
        '/alarm_status',
        '/api/spotify/auth-status',
        '/sleep_status?advanced=true'
    ]

    timings = []
    for endpoint in endpoints:
        start = time.time()
        response = client.get(endpoint)
        elapsed_ms = (time.time() - start) * 1000
        timings.append((endpoint, elapsed_ms, response.status_code))

        if endpoint != '/api/services/diagnostics':
            assert elapsed_ms < 500

    # ensure we printed for debug? maybe not necessary


def test_service_error_handling(client):
    missing = client.get('/api/services/nonexistent')
    assert missing.status_code == 404

    for endpoint in ['/api/services/health', '/api/services/performance', '/alarm_status', '/sleep_status?advanced=true']:
        response = client.get(endpoint)
        assert response.headers.get('Content-Type', '').startswith('application/json')
        data = response.get_json()
        assert 'success' in data
        assert 'timestamp' in data

