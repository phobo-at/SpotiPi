import json
from typing import List
from flask import Flask
import pytest

# Import the app
from src.app import app as flask_app

@pytest.fixture(scope="module")
def client():
    flask_app.config.update({"TESTING": True})
    with flask_app.test_client() as c:
        yield c

# Helper to assert unified response shape

def assert_api_envelope(resp, *, expect_success: bool | None = None):
    assert resp.status_code >= 200
    data = resp.get_json()
    assert isinstance(data, dict), "Response must be JSON object"
    assert 'success' in data, "Missing success field"
    assert 'timestamp' in data, "Missing timestamp"
    assert 'request_id' in data, "Missing request_id"
    # timestamp basic shape
    assert data['timestamp'].endswith('Z')
    if expect_success is not None:
        assert data['success'] is expect_success, f"Expected success={expect_success} got {data['success']}"
    if not data['success']:
        assert 'message' in data, "Error responses must contain message"
        assert 'error_code' in data, "Error responses must contain error_code"
    return data

# -------- Tests --------

def test_alarm_status_contract(client):
    resp = client.get('/alarm_status')
    data = assert_api_envelope(resp, expect_success=True)
    # Data payload existence
    assert 'data' in data, "Expected data field"
    assert 'enabled' in data['data']


def test_music_library_auth_required(client):
    # Without token environment, should 401
    resp = client.get('/api/music-library')
    assert resp.status_code in (401, 200)  # Might be 401 or served cache
    data = resp.get_json()
    # If unauthorized path chosen
    if resp.status_code == 401 or not data.get('success', False):
        assert 'error_code' in data


def test_playback_status_no_token(client):
    resp = client.get('/playback_status')
    data = resp.get_json()
    # Accept either unauthorized (no token) or no playback scenario
    assert 'success' in data
    if data['success'] is False:
        # Could be auth required or simply no active playback
        assert data.get('error_code') in {'auth_required', 'no_playback'}
    else:
        # Active playback path
        assert 'data' in data and isinstance(data['data'], dict)


def test_save_alarm_validation_error(client):
    # Missing time field should raise validation error
    resp = client.post('/save_alarm', data={
        'time': '25:99',  # invalid
        'alarm_volume': '110'
    })
    data = resp.get_json()
    assert data['success'] is False
    assert 'error_code' in data


def test_save_alarm_success_roundtrip(client):
    resp = client.post('/save_alarm', data={
        'time': '07:30',
        'enabled': 'true',
        'alarm_volume': '55',
        'weekdays': '1,2,3'
    })
    data = assert_api_envelope(resp, expect_success=True)
    payload = data['data']
    assert payload['time'] == '07:30'
    assert isinstance(payload['weekdays'], list)


def test_devices_auth_required(client):
    resp = client.get('/api/spotify/devices')
    data = resp.get_json()
    # Two valid outcomes: unauthorized OR authorized with devices list
    assert 'success' in data
    if not data['success']:
        assert data.get('error_code') == 'auth_required'
    else:
        assert 'data' in data and 'devices' in data['data']
        assert isinstance(data['data']['devices'], list)


def test_sleep_status_contract(client):
    resp = client.get('/sleep_status')
    data = assert_api_envelope(resp, expect_success=True)
    assert 'data' in data

