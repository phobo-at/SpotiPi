#!/usr/bin/env python3
"""
🏗️ Service Layer Test Suite (App-TestClient)
===========================================

Exercises service layer endpoints using Flask's test client so the suite can
run without an external server.
"""

import time


def test_service_health(client):
    response = client.get('/api/services/health')
    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True

    health = data["data"]["health"]
    total = health["total_services"]
    healthy = health["healthy_services"]

    assert total >= 4
    assert 0 <= healthy <= total
    assert health["overall_healthy"] == (healthy == total)

    services = health["services"]
    for name in ["alarm", "spotify", "sleep", "system"]:
        assert name in services
        entry = services[name]
        assert "healthy" in entry
        assert "status" in entry
        if entry["healthy"]:
            status_value = entry.get("status_summary") or entry["status"].get("status")
            if isinstance(status_value, str):
                assert status_value.lower() in {"healthy", "ok"}


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
    for field in ["enabled", "time", "alarm_volume", "next_alarm"]:
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


def test_toggle_play_pause_failure_propagates(client, monkeypatch):
    monkeypatch.setattr('src.app.get_access_token', lambda: 'token')

    def _fake_toggle(token):
        assert token == 'token'
        return {'success': False, 'error': 'No active device'}

    monkeypatch.setattr('src.app.toggle_playback_fast', _fake_toggle)

    response = client.post('/toggle_play_pause')
    assert response.status_code == 503

    data = response.get_json()
    assert data['success'] is False
    assert data.get('error_code') == 'playback_toggle_failed'
    assert data.get('message') == 'No active device'


def test_dashboard_status_endpoint(client, monkeypatch):
    # Force predictable responses
    monkeypatch.setattr('src.app.get_access_token', lambda: None)

    response = client.get('/api/dashboard/status')
    assert response.status_code == 200

    payload = response.get_json()
    assert payload['success'] is True

    data = payload['data']
    assert isinstance(data, dict)
    assert 'alarm' in data
    assert 'sleep' in data
    assert 'playback' in data
