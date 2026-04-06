"""Request security helpers for admin auth, CSRF/origin checks, and proxy safety."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
from typing import Iterable
from urllib.parse import urlparse

from flask import Request, session
from werkzeug.security import check_password_hash

_ADMIN_SESSION_KEY = "spotipi_admin_authenticated"
_ADMIN_SESSION_FINGERPRINT_KEY = "spotipi_admin_fingerprint"

_PROTECTED_PATH_PREFIXES = (
    "/api/settings",
    "/api/cache",
    "/api/services",
    "/api/rate-limiting",
    "/api/thread-safety",
    "/api/token-cache",
)
_PROTECTED_EXACT_PATHS = {
    "/settings",
    "/api/devices/refresh",
    "/api/spotify/health",
    "/api/spotify/profile",
    "/debug/language",
}
_STATEFUL_GET_PATHS = {
    "/api/devices/refresh",
    "/api/settings/spotify/oauth/start",
    "/api/settings/spotify/oauth/callback",
}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_ip(value: str | None) -> ipaddress._BaseAddress | None:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _parse_proxy_entries(entries: str) -> list[ipaddress._BaseNetwork | ipaddress._BaseAddress]:
    parsed: list[ipaddress._BaseNetwork | ipaddress._BaseAddress] = []
    for raw_entry in entries.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                parsed.append(ipaddress.ip_network(entry, strict=False))
            else:
                parsed.append(ipaddress.ip_address(entry))
        except ValueError:
            continue
    return parsed


def _ip_in_entries(
    candidate: str | None,
    entries: Iterable[ipaddress._BaseNetwork | ipaddress._BaseAddress],
) -> bool:
    ip_value = _parse_ip(candidate)
    if ip_value is None:
        return False
    for entry in entries:
        if isinstance(entry, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            if ip_value == entry:
                return True
        elif ip_value in entry:
            return True
    return False


def get_effective_client_ip(request_obj: Request) -> str:
    """Resolve the client IP without trusting proxy headers by default."""
    remote_addr = request_obj.remote_addr or "127.0.0.1"

    if not _env_flag("SPOTIPI_TRUST_PROXY_HEADERS", default=False):
        return remote_addr

    trusted_proxies = _parse_proxy_entries(os.getenv("SPOTIPI_TRUSTED_PROXIES", ""))
    if not trusted_proxies or not _ip_in_entries(remote_addr, trusted_proxies):
        return remote_addr

    forwarded_for = request_obj.headers.get("X-Forwarded-For", "")
    for candidate in forwarded_for.split(","):
        candidate_ip = candidate.strip()
        if _parse_ip(candidate_ip) is not None:
            return candidate_ip

    return remote_addr


def is_loopback_request(request_obj: Request) -> bool:
    client_ip = _parse_ip(get_effective_client_ip(request_obj))
    return bool(client_ip and client_ip.is_loopback)


def matches_origin(origin: str, allowed_entry: str) -> bool:
    """Check if a request origin matches an allowed CORS entry."""
    if not allowed_entry:
        return False

    allowed_entry = allowed_entry.strip()
    if allowed_entry == "*":
        return True

    if origin == "null":
        return allowed_entry.lower() == "null"

    if not origin:
        return False

    parsed_origin = urlparse(origin)
    origin_host = parsed_origin.hostname
    origin_port = parsed_origin.port or (443 if parsed_origin.scheme == "https" else 80)

    if "://" not in allowed_entry:
        host, _, port = allowed_entry.partition(":")
        if host and host.lower() == (origin_host or "").lower():
            if not port:
                return True
            try:
                return int(port) == origin_port
            except ValueError:
                return False
        return False

    parsed_allowed = urlparse(allowed_entry)

    if parsed_allowed.scheme and parsed_allowed.scheme != parsed_origin.scheme:
        return False

    if parsed_allowed.hostname and parsed_allowed.hostname.lower() != (origin_host or "").lower():
        return False

    allowed_port = parsed_allowed.port or (
        443 if parsed_allowed.scheme == "https" else 80 if parsed_allowed.scheme == "http" else None
    )
    if parsed_allowed.port and allowed_port != origin_port:
        return False

    return True


def resolve_cors_allow_origin(request_obj: Request, request_origin: str | None = None) -> str | None:
    """Resolve the concrete Access-Control-Allow-Origin value for this request."""
    request_origin = request_origin if request_origin is not None else request_obj.headers.get("Origin")
    if not request_origin:
        return None

    allowed_origins_env = os.getenv("SPOTIPI_CORS_ORIGINS", "")
    if allowed_origins_env.strip():
        allowed_entries = [entry.strip() for entry in allowed_origins_env.split(",") if entry.strip()]
        if any(entry == "*" for entry in allowed_entries):
            return request_origin
        if request_origin == "null" and any(entry.lower() == "null" for entry in allowed_entries):
            return "null"
        if any(matches_origin(request_origin, entry) for entry in allowed_entries):
            return request_origin
        return None

    default_host = os.getenv("SPOTIPI_DEFAULT_HOST", "spotipi.local").strip()
    if matches_origin(request_origin, request_obj.host):
        return request_origin
    if default_host and matches_origin(request_origin, default_host):
        return request_origin
    return None


def has_admin_auth_config() -> bool:
    return bool(os.getenv("SPOTIPI_ADMIN_PASSWORD") or os.getenv("SPOTIPI_ADMIN_PASSWORD_HASH"))


def get_admin_realm() -> str:
    return "SpotiPi Admin"


def _admin_username() -> str:
    return os.getenv("SPOTIPI_ADMIN_USERNAME", "spotipi").strip() or "spotipi"


def _admin_fingerprint() -> str:
    secret_material = os.getenv("SPOTIPI_ADMIN_PASSWORD_HASH") or os.getenv("SPOTIPI_ADMIN_PASSWORD") or ""
    digest = hashlib.sha256()
    digest.update(_admin_username().encode("utf-8"))
    digest.update(b":")
    digest.update(secret_material.encode("utf-8"))
    return digest.hexdigest()


def clear_admin_session() -> None:
    session.pop(_ADMIN_SESSION_KEY, None)
    session.pop(_ADMIN_SESSION_FINGERPRINT_KEY, None)


def is_admin_session_authenticated() -> bool:
    if not has_admin_auth_config():
        clear_admin_session()
        return False

    authenticated = bool(session.get(_ADMIN_SESSION_KEY))
    fingerprint = session.get(_ADMIN_SESSION_FINGERPRINT_KEY)
    if authenticated and fingerprint == _admin_fingerprint():
        return True

    if authenticated:
        clear_admin_session()
    return False


def _validate_admin_password(candidate_password: str) -> bool:
    password_hash = os.getenv("SPOTIPI_ADMIN_PASSWORD_HASH", "").strip()
    if password_hash:
        try:
            return check_password_hash(password_hash, candidate_password)
        except ValueError:
            return False

    expected_password = os.getenv("SPOTIPI_ADMIN_PASSWORD", "")
    return bool(expected_password) and hmac.compare_digest(candidate_password, expected_password)


def authenticate_admin_request(request_obj: Request) -> bool:
    """Validate admin credentials from session or HTTP Basic auth."""
    if is_admin_session_authenticated():
        return True

    if not has_admin_auth_config():
        return False

    auth = request_obj.authorization
    if auth is None or (auth.type or "").lower() != "basic":
        return False

    if not hmac.compare_digest(auth.username or "", _admin_username()):
        return False

    if not _validate_admin_password(auth.password or ""):
        return False

    session[_ADMIN_SESSION_KEY] = True
    session[_ADMIN_SESSION_FINGERPRINT_KEY] = _admin_fingerprint()
    session.modified = True
    return True


def is_protected_request(request_obj: Request) -> bool:
    """Return True for admin/sensitive endpoints that require local-or-auth access."""
    if request_obj.method not in _SAFE_METHODS:
        return True

    path = request_obj.path
    if path in _PROTECTED_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _PROTECTED_PATH_PREFIXES)


def requires_same_origin_protection(request_obj: Request) -> bool:
    return request_obj.method not in _SAFE_METHODS or request_obj.path in _STATEFUL_GET_PATHS


def is_same_origin_submission(request_obj: Request) -> bool:
    """Validate browser request metadata for state-changing requests."""
    if not requires_same_origin_protection(request_obj):
        return True

    sec_fetch_site = (request_obj.headers.get("Sec-Fetch-Site") or "").strip().lower()
    if sec_fetch_site == "cross-site":
        return False

    origin = request_obj.headers.get("Origin")
    if origin:
        if origin == "null":
            return False
        return resolve_cors_allow_origin(request_obj, request_origin=origin) == origin

    referer = request_obj.headers.get("Referer")
    if referer:
        parsed_referer = urlparse(referer)
        if not parsed_referer.scheme or not parsed_referer.netloc:
            return False
        referer_origin = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
        return resolve_cors_allow_origin(request_obj, request_origin=referer_origin) == referer_origin

    if sec_fetch_site in {"same-origin", "same-site", "none"}:
        return True

    if is_loopback_request(request_obj):
        return True

    return bool(request_obj.authorization)
