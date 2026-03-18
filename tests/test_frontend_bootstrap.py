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
