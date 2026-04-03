from typing import Optional

# Helper to assert unified response shape

def assert_api_envelope(resp, *, expect_success: Optional[bool] = None):
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


def test_music_library_sections_contract(client):
    resp = client.get('/api/music-library/sections?sections=playlists')
    if resp.status_code == 401:
        data = resp.get_json()
        assert data.get('error_code') == 'auth_required'
        return
    if resp.status_code == 304:
        assert resp.headers.get('ETag')
        assert resp.headers.get('X-MusicLibrary-Hash')
        return
    data = assert_api_envelope(resp, expect_success=True)
    payload = data['data']
    assert payload.get('partial') is True
    assert 'sections' in payload
    assert resp.headers.get('X-MusicLibrary-Hash')
    if resp.headers.get('X-Data-Fields') == 'basic':
        # ensure slimmed payload only contains whitelisted keys
        for coll in ('playlists', 'albums', 'tracks', 'artists'):
            for item in payload.get(coll, []):
                assert set(item.keys()).issubset({'uri', 'name', 'image_url', 'track_count', 'type', 'artist'})


def test_playback_status_no_token(client, monkeypatch):
    monkeypatch.setattr('src.routes.health.get_access_token', lambda: None)
    resp = client.get('/playback_status')
    assert resp.status_code == 202
    data = assert_api_envelope(resp, expect_success=True)
    assert 'data' in data and isinstance(data['data'], dict)
    assert data['data'].get('status') in {'pending', 'auth_required'}
    assert data['data'].get('hydration', {}).get('pending') in {True, False}


def test_debug_language_route_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr('src.routes.main.DEBUG_ROUTES_ENABLED', False)
    resp = client.get('/debug/language')
    assert resp.status_code == 404
    data = assert_api_envelope(resp, expect_success=False)
    assert data.get('error_code') == 'not_found'


def test_debug_language_route_whitelists_headers(client, monkeypatch):
    monkeypatch.setattr('src.routes.main.DEBUG_ROUTES_ENABLED', True)
    resp = client.get(
        '/debug/language',
        headers={
            'Accept-Language': 'de-AT,de;q=0.9',
            'Authorization': 'Bearer secret-token',
            'Cookie': 'session=secret-cookie',
            'User-Agent': 'pytest-agent'
        }
    )
    assert resp.status_code == 200
    data = assert_api_envelope(resp, expect_success=True)
    payload = data['data']
    assert 'all_headers' not in payload
    headers = payload.get('request_headers', {})
    assert headers.get('Accept-Language') == 'de-AT,de;q=0.9'
    assert headers.get('User-Agent') == 'pytest-agent'
    assert 'Authorization' not in headers
    assert 'Cookie' not in headers


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
        'alarm_volume': '55'
    })
    data = assert_api_envelope(resp, expect_success=True)
    payload = data['data']
    assert payload['time'] == '07:30'
    assert 'next_alarm' in payload


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


def test_volume_endpoint_validation(client):
    resp = client.post('/volume', data={'volume': '999'})
    data = resp.get_json()
    if resp.status_code == 401:
        assert data.get('error_code') == 'auth_required'
        return
    assert resp.status_code == 400
    assert data['success'] is False
    assert data.get('error_code') == 'volume'
