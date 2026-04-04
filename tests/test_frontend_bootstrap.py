from __future__ import annotations

import json
import re


def _extract_bootstrap(html: str) -> dict:
    match = re.search(
        r'<script id="spotipi-bootstrap" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match, "Missing frontend bootstrap payload"
    return json.loads(match.group(1))


def test_index_bootstrap_contains_dashboard_settings_and_defaults(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    bootstrap = _extract_bootstrap(html)

    assert bootstrap["language"] in {"de", "en"}
    assert "dashboard" in bootstrap
    assert "settings" in bootstrap
    assert "sleep_defaults" in bootstrap
    assert bootstrap["app"]["initial_surface"] == "home"

    dashboard = bootstrap["dashboard"]
    assert "alarm" in dashboard
    assert "sleep" in dashboard
    assert "playback_status" in dashboard
    assert "hydration" in dashboard


def test_settings_route_opens_settings_surface(client):
    response = client.get("/settings")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    bootstrap = _extract_bootstrap(html)

    assert bootstrap["app"]["initial_surface"] == "settings"


def test_index_route_sets_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "img-src 'self' https: data:" in csp
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_music_library_route_redirects_to_shell(client):
    response = client.get("/music_library", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers.get("Location", "").endswith("/")
