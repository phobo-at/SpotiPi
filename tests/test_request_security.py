from __future__ import annotations

import base64

from src.utils.rate_limiting import RateLimitRule, SimpleRateLimiter


def _basic_auth_headers(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _remote_request() -> dict[str, str]:
    return {"REMOTE_ADDR": "10.0.0.42"}


def _public_request() -> dict[str, str]:
    return {"REMOTE_ADDR": "8.8.8.8"}


def test_private_network_protected_route_is_allowed_without_admin_auth(client):
    response = client.get("/api/settings/spotify", environ_overrides=_remote_request())

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True


def test_public_protected_route_is_blocked_without_admin_auth(client):
    response = client.get("/api/settings/spotify", environ_overrides=_public_request())

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error_code"] == "admin_auth_required"


def test_remote_protected_route_accepts_basic_auth_and_persists_session(client, monkeypatch):
    monkeypatch.setenv("SPOTIPI_ADMIN_PASSWORD", "correct horse battery staple")

    response = client.get(
        "/api/settings",
        headers=_basic_auth_headers("spotipi", "correct horse battery staple"),
        environ_overrides=_public_request(),
    )

    assert response.status_code == 200

    follow_up = client.get("/api/settings/spotify", environ_overrides=_public_request())
    assert follow_up.status_code == 200


def test_public_settings_page_challenges_invalid_basic_auth(client, monkeypatch):
    monkeypatch.setenv("SPOTIPI_ADMIN_PASSWORD", "expected-secret")

    response = client.get(
        "/settings",
        headers=_basic_auth_headers("spotipi", "wrong-secret"),
        environ_overrides=_public_request(),
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith('Basic realm="SpotiPi Admin"')


def test_public_api_returns_json_error_without_basic_auth_challenge(client, monkeypatch):
    monkeypatch.setenv("SPOTIPI_ADMIN_PASSWORD", "expected-secret")

    response = client.get(
        "/api/settings",
        environ_overrides=_public_request(),
    )

    assert response.status_code == 403
    assert "WWW-Authenticate" not in response.headers
    payload = response.get_json()
    assert payload["error_code"] == "admin_auth_required"


def test_cross_site_post_is_rejected_even_with_valid_admin_auth(client, monkeypatch):
    monkeypatch.setenv("SPOTIPI_ADMIN_PASSWORD", "csrf-test-secret")

    response = client.post(
        "/api/settings/cache/clear",
        headers={
            **_basic_auth_headers("spotipi", "csrf-test-secret"),
            "Origin": "https://evil.example",
        },
        environ_overrides=_public_request(),
    )

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error_code"] == "invalid_origin"


def test_remote_cli_request_without_origin_is_allowed_with_basic_auth(client, monkeypatch):
    monkeypatch.setenv("SPOTIPI_ADMIN_PASSWORD", "cli-secret")

    response = client.post(
        "/api/rate-limiting/reset",
        headers=_basic_auth_headers("spotipi", "cli-secret"),
        environ_overrides=_public_request(),
    )

    assert response.status_code == 200


def test_default_cors_does_not_allow_suffix_host_match(client):
    response = client.get("/healthz", headers={"Origin": "http://evilspotipi.local"})

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


def test_default_cors_allows_exact_default_host(client):
    response = client.get("/healthz", headers={"Origin": "http://spotipi.local:3000"})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://spotipi.local:3000"


def test_rate_limiter_ignores_spoofed_forwarded_for_by_default(app):
    limiter = SimpleRateLimiter()
    limiter.add_rule(RateLimitRule("strict_test", 2, 60.0, 30.0))

    for forwarded_for in ("198.51.100.10", "198.51.100.11"):
        with app.test_request_context(
            "/healthz",
            headers={"X-Forwarded-For": forwarded_for},
            environ_overrides={"REMOTE_ADDR": "10.0.0.10"},
        ):
            status = limiter.check_rate_limit("strict_test")
            assert status.is_blocked is False

    with app.test_request_context(
        "/healthz",
        headers={"X-Forwarded-For": "198.51.100.12"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.10"},
    ):
        blocked = limiter.check_rate_limit("strict_test")

    assert blocked.is_blocked is True


def test_rate_limiter_can_trust_configured_proxy_headers(app, monkeypatch):
    monkeypatch.setenv("SPOTIPI_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("SPOTIPI_TRUSTED_PROXIES", "10.0.0.10")

    limiter = SimpleRateLimiter()
    limiter.add_rule(RateLimitRule("strict_test", 2, 60.0, 30.0))

    with app.test_request_context(
        "/healthz",
        headers={"X-Forwarded-For": "198.51.100.20"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.10"},
    ):
        first = limiter.check_rate_limit("strict_test")

    with app.test_request_context(
        "/healthz",
        headers={"X-Forwarded-For": "198.51.100.21"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.10"},
    ):
        second = limiter.check_rate_limit("strict_test")

    with app.test_request_context(
        "/healthz",
        headers={"X-Forwarded-For": "198.51.100.20"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.10"},
    ):
        third = limiter.check_rate_limit("strict_test")

    assert first.is_blocked is False
    assert second.is_blocked is False
    assert third.is_blocked is False
