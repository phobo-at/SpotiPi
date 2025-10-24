"""
SpotiPi Main Application
Flask web application with new modular structure
"""

import copy
import datetime
import logging
import os
import secrets
import threading
import time
import uuid
from functools import wraps
from pathlib import Path
from threading import Thread
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from flask import (Flask, Response, g, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_compress import Compress

from .api.spotify import (get_access_token, get_combined_playback, get_devices,
                          get_followed_artists, get_playlists,
                          get_saved_albums, get_user_library,
                          get_user_saved_tracks)
# Import from new structure - use relative imports since we're in src/
from .config import load_config
from .core.alarm_scheduler import \
    start_alarm_scheduler as start_event_alarm_scheduler
from .core.scheduler import AlarmTimeValidator
from .services.service_manager import get_service, get_service_manager
from .utils.cache_migration import get_cache_migration_layer
from .utils.library_utils import compute_library_hash, prepare_library_payload
from .utils.logger import setup_logger, setup_logging
from .utils.perf_monitor import perf_monitor
from .utils.rate_limiting import get_rate_limiter, rate_limit
from .utils.thread_safety import get_config_stats, invalidate_config_cache
from .utils.token_cache import (get_token_cache_info,
                                log_token_cache_performance)
from .utils.translations import get_translations, get_user_language, t_api
from .utils.wsgi_logging import TidyRequestHandler
from .version import VERSION, get_app_info

# Initialize Flask app with correct paths
project_root = Path(__file__).parent.parent  # Go up from src/ to project root
template_dir = project_root / "templates"
static_dir = project_root / "static"

# Detect low power mode (e.g. Pi Zero) to tailor runtime features
LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')

app = Flask(
    __name__,
    template_folder=str(template_dir),
    static_folder=str(static_dir),
    static_url_path='/static'
)

# Optimize template handling for low-power environments
app.config['TEMPLATES_AUTO_RELOAD'] = not LOW_POWER_MODE
app.jinja_env.auto_reload = not LOW_POWER_MODE

app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

app.config.setdefault('COMPRESS_REGISTER', True)
app.config.setdefault('COMPRESS_ALGORITHM', os.getenv('SPOTIPI_COMPRESS_ALGO', 'gzip'))
app.config.setdefault(
    'COMPRESS_MIMETYPES',
    (
        'text/html',
        'text/css',
        'text/javascript',
        'application/javascript',
        'application/json',
        'application/xml',
        'image/svg+xml',
    ),
)
try:
    app.config['COMPRESS_LEVEL'] = max(1, min(9, int(os.getenv('SPOTIPI_COMPRESS_LEVEL', '6'))))
except ValueError:
    app.config['COMPRESS_LEVEL'] = 6
try:
    app.config['COMPRESS_MIN_SIZE'] = max(256, int(os.getenv('SPOTIPI_COMPRESS_MIN_BYTES', '1024')))
except ValueError:
    app.config['COMPRESS_MIN_SIZE'] = 1024

if not LOW_POWER_MODE:
    try:
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = int(os.getenv('SPOTIPI_STATIC_CACHE_SECONDS', str(31536000)))
    except ValueError:
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000

compress = Compress()
compress.init_app(app)

# Setup logging
setup_logging()
logger = setup_logger("spotipi")

# Initialize cache migration layer
cache_migration = get_cache_migration_layer(project_root)

# Initialize rate limiter with default rules
rate_limiter = get_rate_limiter()

# Initialize service manager
service_manager = get_service_manager()

_default_dashboard_ttl = 1.5 if LOW_POWER_MODE else 0.75
_default_playback_status_ttl = 1.5 if LOW_POWER_MODE else 0.75

try:
    DASHBOARD_CACHE_TTL = max(
        0.1,
        float(os.getenv("SPOTIPI_STATUS_CACHE_SECONDS", str(_default_dashboard_ttl))),
    )
except ValueError:
    DASHBOARD_CACHE_TTL = _default_dashboard_ttl

try:
    PLAYBACK_STATUS_CACHE_TTL = max(
        0.1,
        float(os.getenv("SPOTIPI_PLAYBACK_STATUS_CACHE_SECONDS", str(_default_playback_status_ttl))),
    )
except ValueError:
    PLAYBACK_STATUS_CACHE_TTL = _default_playback_status_ttl

class AsyncSnapshot:
    """Thread-safe helper for asynchronously refreshed snapshots."""

    def __init__(self, name: str, ttl: float, *, min_retry: float = 0.75):
        self._name = name
        self._ttl = max(0.1, float(ttl))
        self._min_retry = max(0.1, float(min_retry))
        self._lock = threading.Lock()
        self._data: Any | None = None
        self._expires_at: float = 0.0
        self._refreshing: bool = False
        self._last_refresh: float = 0.0
        self._last_error: Optional[str] = None
        self._last_error_at: float = 0.0
        self._pending_reason: Optional[str] = None
        self._next_refresh_allowed: float = 0.0

    def snapshot(self) -> tuple[Any | None, Dict[str, Any]]:
        """Return a deep copy of the cached data with metadata."""
        now = time.time()
        with self._lock:
            data_copy = copy.deepcopy(self._data) if self._data is not None else None
            meta = {
                "fresh": data_copy is not None and now < self._expires_at,
                "pending": data_copy is None or now >= self._expires_at,
                "refreshing": self._refreshing,
                "age": (now - self._last_refresh) if self._last_refresh else None,
                "last_refresh": self._last_refresh,
                "last_error": self._last_error,
                "last_error_at": self._last_error_at,
                "pending_reason": self._pending_reason,
                "ttl": self._ttl,
                "has_data": data_copy is not None,
                "next_refresh_allowed": self._next_refresh_allowed,
            }
        return data_copy, meta

    def mark_stale(self) -> None:
        """Force the snapshot to be considered stale."""
        with self._lock:
            self._expires_at = 0.0

    def set(self, payload: Any) -> None:
        """Store a payload immediately, bypassing fetcher logic."""
        now = time.time()
        with self._lock:
            self._data = copy.deepcopy(payload)
            self._last_refresh = now
            self._expires_at = now + self._ttl if self._ttl > 0 else now
            self._last_error = None
            self._last_error_at = 0.0
            self._pending_reason = None
            self._refreshing = False

    def schedule_refresh(self, fetcher: Callable[[], Any], *, force: bool = False, reason: str = "api") -> bool:
        """Trigger an asynchronous refresh if needed."""
        now = time.time()
        with self._lock:
            if self._refreshing:
                return False
            if not force:
                if self._data is not None and now < self._expires_at:
                    return False
                if self._data is None and now < self._next_refresh_allowed:
                    return False
            self._refreshing = True
            self._pending_reason = reason
            self._next_refresh_allowed = now + self._min_retry

        def _runner():
            snapshot_logger = logging.getLogger("spotipi.snapshot")
            try:
                payload = fetcher()
                refreshed_at = time.time()
                with self._lock:
                    self._data = copy.deepcopy(payload)
                    self._last_refresh = refreshed_at
                    self._expires_at = refreshed_at + self._ttl if self._ttl > 0 else refreshed_at
                    self._last_error = None
                    self._last_error_at = 0.0
                    self._pending_reason = None
            except Exception as exc:
                snapshot_logger.warning("Async snapshot %s refresh failed: %s", self._name, exc)
                with self._lock:
                    self._last_error = str(exc)
                    self._last_error_at = time.time()
            finally:
                with self._lock:
                    self._refreshing = False

        threading.Thread(
            target=_runner,
            name=f"{self._name}-snapshot-refresh",
            daemon=True
        ).start()
        return True


_dashboard_snapshot = AsyncSnapshot(
    "dashboard",
    DASHBOARD_CACHE_TTL,
    min_retry=1.2 if LOW_POWER_MODE else 0.6
)

try:
    DEVICE_SNAPSHOT_TTL = max(
        3.0,
        float(os.getenv("SPOTIPI_DEVICE_SNAPSHOT_SECONDS", os.getenv("SPOTIPI_DEVICE_TTL", "6")))
    )
except (TypeError, ValueError):
    DEVICE_SNAPSHOT_TTL = 8.0 if LOW_POWER_MODE else 5.0

_playback_snapshot = AsyncSnapshot(
    "playback",
    PLAYBACK_STATUS_CACHE_TTL,
    min_retry=0.8 if LOW_POWER_MODE else 0.4
)
_devices_snapshot = AsyncSnapshot(
    "devices",
    DEVICE_SNAPSHOT_TTL,
    min_retry=1.5 if LOW_POWER_MODE else 0.75
)

_VALID_LIBRARY_SECTIONS = ("playlists", "albums", "tracks", "artists")
_SECTION_LOADERS = {
    "playlists": get_playlists,
    "albums": get_saved_albums,
    "tracks": get_user_saved_tracks,
    "artists": get_followed_artists,
}


def _parse_library_sections(raw: Optional[str], *, default: Optional[list[str]] = None, ensure_default_on_empty: bool = False) -> list[str]:
    """Parse and validate comma separated sections parameter."""
    if raw is None:
        return list(default or [])
    items = [s.strip() for s in raw.split(",") if s.strip()]
    filtered = [s for s in items if s in _VALID_LIBRARY_SECTIONS]
    if not filtered and ensure_default_on_empty:
        return list(default or ["playlists"])
    return filtered


def _load_music_library_data(token: str, *, sections: list[str], force_refresh: bool) -> Dict[str, Any]:
    """Load music library data (full or sections) via cache migration layer."""
    if sections:
        return cache_migration.get_library_sections_cached(
            token=token,
            sections=sections,
            section_loaders=_SECTION_LOADERS,
            force_refresh=force_refresh,
        )
    return cache_migration.get_full_library_cached(
        token=token,
        loader_func=get_user_library,
        force_refresh=force_refresh,
    )


def _build_library_response(
    token: str,
    *,
    sections: list[str],
    force_refresh: bool,
    want_fields: Optional[str],
    if_modified: Optional[str],
    request_obj,
) -> Response:
    """Create a unified music library response with shared headers."""
    raw_library = _load_music_library_data(token, sections=sections, force_refresh=force_refresh)
    basic_view = want_fields == "basic"
    payload = prepare_library_payload(raw_library, basic=basic_view, sections=sections or None)
    hash_val = payload.get("hash") or compute_library_hash(payload)

    if if_modified and if_modified == hash_val:
        resp = Response(status=304)
        resp.headers["ETag"] = hash_val
        resp.headers["X-MusicLibrary-Hash"] = hash_val
        return resp

    is_offline = bool(payload.get("offline_mode"))
    cached_sections = payload.get("cached_sections") if sections else None
    cached_flag = payload.get("cached") if not sections else None

    cached_complete = False
    if sections:
        if isinstance(cached_sections, dict):
            cached_complete = all(cached_sections.get(sec, False) for sec in sections)
        else:
            cached_sections = {sec: False for sec in sections}
    else:
        cached_complete = bool(cached_flag)

    if is_offline:
        message = "ok (offline cache)"
    elif sections and not cached_complete:
        message = t_api("ok_partial", request_obj)
    elif cached_complete:
        message = "ok (cached)"
    else:
        message = "ok (fresh)"

    resp = api_response(True, data=payload, message=message)
    resp.headers["X-MusicLibrary-Hash"] = hash_val
    resp.headers["ETag"] = hash_val
    if basic_view:
        resp.headers["X-Data-Fields"] = "basic"
    return resp


def _build_playback_snapshot(token: Optional[str], *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    snapshot_ts = timestamp or _iso_timestamp_now()
    if not token:
        return {
            "status": "auth_required",
            "playback": None,
            "fetched_at": snapshot_ts
        }
    try:
        playback = get_combined_playback(token)
        status = "ok" if playback else "empty"
        return {
            "status": status,
            "playback": playback,
            "fetched_at": snapshot_ts
        }
    except Exception as exc:
        logger.debug("Playback snapshot error: %s", exc)
        return {
            "status": "error",
            "playback": None,
            "error": str(exc),
            "fetched_at": snapshot_ts
        }


def _build_devices_snapshot(token: Optional[str], *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    snapshot_ts = timestamp or _iso_timestamp_now()
    if not token:
        return {
            "status": "auth_required",
            "devices": [],
            "cache": {},
            "fetched_at": snapshot_ts
        }
    try:
        devices = get_devices(token) or []
        cache_info = cache_migration.get_device_cache_info(token) or {}
        return {
            "status": "ok" if devices else "empty",
            "devices": devices,
            "cache": cache_info,
            "fetched_at": snapshot_ts
        }
    except Exception as exc:
        logger.debug("Device snapshot error: %s", exc)
        return {
            "status": "error",
            "devices": [],
            "error": str(exc),
            "cache": {},
            "fetched_at": snapshot_ts
        }


def _refresh_playback_snapshot() -> Dict[str, Any]:
    token = get_access_token()
    payload = _build_playback_snapshot(token)
    if payload.get("status") == "ok":
        _playback_snapshot.set(payload)
    return payload


def _refresh_devices_snapshot() -> Dict[str, Any]:
    token = get_access_token()
    payload = _build_devices_snapshot(token)
    if payload.get("status") in {"ok", "empty"}:
        _devices_snapshot.set(payload)
    return payload


def _refresh_dashboard_snapshot() -> Dict[str, Any]:
    token = get_access_token()
    snapshot_ts = _iso_timestamp_now()
    playback_payload = _build_playback_snapshot(token, timestamp=snapshot_ts)
    devices_payload = _build_devices_snapshot(token, timestamp=snapshot_ts)
    if playback_payload.get("status") in {"ok", "empty"}:
        _playback_snapshot.set(playback_payload)
    if devices_payload.get("status") in {"ok", "empty"}:
        _devices_snapshot.set(devices_payload)
    return {
        "playback": playback_payload,
        "devices": devices_payload,
        "fetched_at": snapshot_ts
    }


def _normalise_snapshot_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fresh": bool(meta.get("fresh")),
        "pending": bool(meta.get("pending")),
        "refreshing": bool(meta.get("refreshing")),
        "has_data": bool(meta.get("has_data")),
        "last_refresh": meta.get("last_refresh"),
        "last_error": meta.get("last_error"),
        "last_error_at": meta.get("last_error_at"),
        "pending_reason": meta.get("pending_reason"),
        "ttl": meta.get("ttl"),
    }


@app.before_request
def _perf_before_request():
    """Capture request start timestamp for perf monitoring."""
    try:
        g.perf_started = time.perf_counter()
        g.perf_route = request.endpoint or request.path
        g.perf_method = request.method
        g.perf_recorded = False
    except Exception:
        g.perf_started = None


def _matches_origin(origin: str, allowed_entry: str) -> bool:
    """Check if a request origin matches an allowed CORS entry."""
    if not allowed_entry:
        return False

    allowed_entry = allowed_entry.strip()
    if allowed_entry == '*':
        return True

    if origin == 'null':
        # Allow explicit "null" entries for local file / PWA contexts
        return allowed_entry.lower() == 'null'

    if not origin:
        return False

    parsed_origin = urlparse(origin)
    origin_host = parsed_origin.hostname
    origin_port = parsed_origin.port or (443 if parsed_origin.scheme == 'https' else 80)

    # Allow host entries without scheme ("example.com" or "example.com:5000")
    if '://' not in allowed_entry:
        host, _, port = allowed_entry.partition(':')
        if host and host.lower() == (origin_host or '').lower():
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

    if parsed_allowed.hostname and (parsed_allowed.hostname.lower() != (origin_host or '').lower()):
        return False

    allowed_port = parsed_allowed.port or (
        443 if parsed_allowed.scheme == 'https' else 80 if parsed_allowed.scheme == 'http' else None
    )

    if parsed_allowed.port and allowed_port != origin_port:
        return False

    return True


@app.after_request
def after_request(response: Response):
    """Add CORS headers + (optional) gzip compression & cache related headers."""
    # ---- CORS ----
    allowed_origins_env = os.getenv('SPOTIPI_CORS_ORIGINS')
    request_origin = request.headers.get('Origin')

    if allowed_origins_env:
        allowed_entries = [entry.strip() for entry in allowed_origins_env.split(',') if entry.strip()]

        if any(entry == '*' for entry in allowed_entries):
            acao_value = request_origin or '*'
            response.headers['Access-Control-Allow-Origin'] = acao_value
            if request_origin:
                response.headers.setdefault('Vary', 'Origin')
        elif request_origin and any(_matches_origin(request_origin, entry) for entry in allowed_entries):
            response.headers['Access-Control-Allow-Origin'] = request_origin
            response.headers.setdefault('Vary', 'Origin')
        elif request_origin == 'null' and any(entry.lower() == 'null' for entry in allowed_entries):
            response.headers['Access-Control-Allow-Origin'] = 'null'
    else:
        default_origin = os.getenv('SPOTIPI_DEFAULT_ORIGIN', 'http://spotipi.local')
        if request_origin and _matches_origin(request_origin, default_origin):
            response.headers['Access-Control-Allow-Origin'] = request_origin
            response.headers.setdefault('Vary', 'Origin')
        else:
            response.headers['Access-Control-Allow-Origin'] = default_origin
            response.headers.setdefault('Vary', 'Origin')

    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'

    # ---- Static asset caching ----
    try:
        if request.path.startswith(app.static_url_path):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    except Exception:
        pass

    # ---- Performance instrumentation ----
    try:
        start = getattr(g, 'perf_started', None)
        if start is not None:
            duration = time.perf_counter() - start
            route_name = getattr(g, 'perf_route', request.endpoint or request.path)
            method = getattr(g, 'perf_method', request.method)
            perf_monitor.record_request(
                route_name,
                duration,
                method=method,
                status=response.status_code,
                path=request.path,
            )
            g.perf_recorded = True
    except Exception as perf_err:
        logging.debug(f"Perf monitor skipped: {perf_err}")

    return response


@app.teardown_request
def _perf_teardown(exception):
    """Ensure timings are recorded even if after_request was skipped."""
    try:
        if getattr(g, 'perf_recorded', False):
            return
        start = getattr(g, 'perf_started', None)
        if start is None:
            return
        duration = time.perf_counter() - start
        route_name = getattr(g, 'perf_route', request.endpoint or request.path)
        method = getattr(g, 'perf_method', request.method if request else 'UNKNOWN')
        status = 500 if exception else 200
        perf_monitor.record_request(
            route_name,
            duration,
            method=method,
            status=status,
            path=request.path if request else route_name,
        )
        g.perf_recorded = True
    except Exception as perf_err:
        logging.debug(f"Perf teardown skipped: {perf_err}")

def api_error_handler(func):
    """Decorator for consistent API error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.exception(f"Error in {func.__name__}")
            if request.is_json or request.path.startswith('/api/'):
                return api_response(False, message=t_api("an_internal_error_occurred", request), status=500, error_code="unhandled_exception")
            session['error_message'] = str(e)
            return redirect(url_for('index'))
    return wrapper

## Legacy minute-based alarm_scheduler removed; replaced by event-driven version in core.alarm_scheduler

@app.context_processor
def inject_global_vars():
    """Inject global variables into all templates"""
    if hasattr(g, 'current_config'):
        config = g.current_config
    else:
        config = load_config()
        g.current_config = config
    sleep_service = get_service("sleep")
    sleep_status_result = sleep_service.get_sleep_status()
    if sleep_status_result.success:
        sleep_status_payload = (sleep_status_result.data or {}).get("raw_status") or sleep_status_result.data
    else:
        sleep_status_payload = {
            "active": False,
            "error": sleep_status_result.message,
            "error_code": sleep_status_result.error_code or "sleep_status_error"
        }
    
    # Get user language from current request
    user_language = get_user_language(request)
    translations = get_translations(user_language)
    
    # Create a translation function that supports parameters
    def template_t(key, **kwargs):
        from .utils.translations import t
        return t(key, user_language, **kwargs)
    
    return {
        'app_version': VERSION,
        'app_info': get_app_info(),
        'current_config': config,
        'sleep_status': sleep_status_payload,
        'translations': translations,
        't': template_t,
        'lang': user_language,
        'static_css_path': '/static/css/',
        'static_js_path': '/static/js/',
        'static_icons_path': '/static/icons/',
        'now': datetime.datetime.now()
    }

# Unified API response helper


def _iso_timestamp_now() -> str:
    """Return ISO 8601 timestamp in UTC with a trailing Z."""
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    return now_utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


def api_response(success: bool, *, data: Any | None = None, message: str = "", status: int = 200, error_code: str | None = None):
    req_id = str(uuid.uuid4())
    timestamp = _iso_timestamp_now()
    payload = {
        "success": success,
        "timestamp": timestamp,
        "request_id": req_id
    }
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if error_code:
        payload["error_code"] = error_code
    resp = jsonify(payload)
    resp.status_code = status
    # Correlation headers
    resp.headers['X-Request-ID'] = req_id
    resp.headers['X-Response-Timestamp'] = timestamp
    return resp

# =====================================
# 🏠 Main Routes
# =====================================

@app.route("/")
@api_error_handler
def index():
    """Main page with alarm and sleep interface"""
    if hasattr(g, 'current_config'):
        config = g.current_config
    else:
        config = load_config()
        g.current_config = config

    initial_volume = config.get('volume', 50)
    try:
        initial_volume = max(0, min(100, int(initial_volume)))
    except (TypeError, ValueError):
        initial_volume = 50
    
    # Data is now loaded asynchronously via JavaScript to improve initial page load time.
    # We pass empty placeholders to the template.
    devices = []
    playlists = []
    current_track = None
    
    # Calculate next alarm time
    next_alarm_info = ""
    if config.get('enabled') and config.get('time'):
        try:
            next_alarm_info = AlarmTimeValidator.format_time_until_alarm(config['time'])
        except Exception:
            next_alarm_info = "Next alarm calculation error"
    
    # Get user language from request
    user_language = get_user_language(request)
    translations = get_translations(user_language)
    
    # Create a translation function that supports parameters  
    def template_t(key, **kwargs):
        from .utils.translations import t
        return t(key, user_language, **kwargs)

    dashboard_snapshot, dashboard_meta = _dashboard_snapshot.snapshot()
    playback_snapshot, playback_meta = _playback_snapshot.snapshot()
    devices_snapshot, devices_meta = _devices_snapshot.snapshot()

    initial_state = {
        'dashboard': dashboard_snapshot,
        'dashboard_meta': _normalise_snapshot_meta(dashboard_meta),
        'playback': playback_snapshot,
        'playback_meta': _normalise_snapshot_meta(playback_meta),
        'devices': devices_snapshot,
        'devices_meta': _normalise_snapshot_meta(devices_meta)
    }
    
    sleep_service_index = get_service("sleep")
    sleep_status_result_index = sleep_service_index.get_sleep_status()
    if sleep_status_result_index.success:
        sleep_status_initial = (sleep_status_result_index.data or {}).get("raw_status") or sleep_status_result_index.data
    else:
        sleep_status_initial = {
            "active": False,
            "error": sleep_status_result_index.message,
            "error_code": sleep_status_result_index.error_code or "sleep_status_error"
        }

    template_data = {
        'config': config,
        'devices': devices,
        'playlists': playlists,
        'current_track': current_track,
        'next_alarm_info': next_alarm_info,
        'initial_volume': initial_volume,
        'error_message': session.pop('error_message', None),
        'success_message': session.pop('success_message', None),
        'sleep_status': sleep_status_initial,
        # Add missing template variables
        'now': datetime.datetime.now(),
        't': template_t,  # Translation function with parameter support
        'lang': user_language,
        'translations': translations,
        'initial_state': initial_state,
        'low_power': LOW_POWER_MODE
    }
    
    return render_template('index.html', **template_data)

# Background warmup (runs once after startup) to prefetch devices. On Pi Zero
# we keep the warmup lightweight (devices + playback cache only).
if not hasattr(app, '_warmup_started'):
    def _warmup_fetch():
        try:
            logging.info("🌅 Warmup: starting background prefetch")
            token = get_access_token()
            if not token:
                logging.info("🌅 Warmup: no token available yet (user not authenticated)")
                return
            snapshot_ts = _iso_timestamp_now()
            devices_payload = {"status": "pending", "devices": [], "fetched_at": snapshot_ts}
            playback_payload = {"status": "pending", "playback": None, "fetched_at": snapshot_ts}
            try:
                devices_payload = _build_devices_snapshot(token, timestamp=snapshot_ts)
                _devices_snapshot.set(devices_payload)
                logging.info(
                    "🌅 Warmup: devices snapshot status=%s (count=%s)",
                    devices_payload.get("status"),
                    len(devices_payload.get("devices") or [])
                )
            except Exception as e:
                logging.info(f"🌅 Warmup: device snapshot error: {e}")
                devices_payload = {"status": "error", "devices": [], "error": str(e), "fetched_at": snapshot_ts}
            try:
                playback_payload = _build_playback_snapshot(token, timestamp=snapshot_ts)
                _playback_snapshot.set(playback_payload)
                if playback_payload.get("status") == "ok":
                    logging.info("🌅 Warmup: playback snapshot primed")
            except Exception as e:
                logging.debug(f"🌅 Warmup: playback snapshot error: {e}")
                playback_payload = {"status": "error", "playback": None, "error": str(e), "fetched_at": snapshot_ts}

            _dashboard_snapshot.set({
                "playback": playback_payload,
                "devices": devices_payload,
                "fetched_at": snapshot_ts
            })

            if not LOW_POWER_MODE:
                try:
                    cache_migration.get_full_library_cached(token, get_user_library, force_refresh=True)
                    logging.info("🌅 Warmup: music library prefetched into cache")
                except Exception as e:
                    logging.info(f"🌅 Warmup: library fetch error: {e}")
        except Exception as e:
            logging.info(f"🌅 Warmup: unexpected error: {e}")
    try:
        Thread(target=_warmup_fetch, daemon=True).start()
        app._warmup_started = True
    except Exception as e:
        logging.info(f"🌅 Warmup: could not start: {e}")

# =====================================
# 🔧 API Routes - Alarm Management
# =====================================

@app.route("/save_alarm", methods=["POST"])
@api_error_handler
@rate_limit("config_changes")
def save_alarm():
    """Save alarm settings with comprehensive input validation"""
    alarm_service = get_service("alarm")
    result = alarm_service.save_alarm_settings(request.form)

    if result.success:
        return api_response(True, data=result.data, message=t_api("alarm_settings_saved", request))

    error_code = (result.error_code or "internal_error").lower()
    message = result.message or t_api("internal_error_saving", request)

    if error_code == "time_format":
        return api_response(False, message=t_api("invalid_time_format", request), status=400, error_code="time_format")
    if error_code == "save_failed":
        return api_response(False, message=t_api("failed_save_config", request), status=500, error_code="save_failed")
    if error_code in {"alarm_time", "volume", "alarm_volume", "playlist_uri", "device_name"}:
        logger.warning("Alarm validation error (%s): %s", error_code, message)
        return api_response(False, message=message, status=400, error_code=error_code)

    logger.error("Error saving alarm configuration via service: %s", message)
    return api_response(False, message=t_api("internal_error_saving", request), status=500, error_code="internal_error")

@app.route("/alarm_status")
@api_error_handler
@rate_limit("status_check")
def alarm_status():
    """Get alarm status - supports both basic and advanced modes"""
    advanced_mode = request.args.get('advanced', 'false').lower() == 'true'

    alarm_service = get_service("alarm")
    result = alarm_service.get_alarm_status()

    if not result.success:
        logger.error("Failed to load alarm status via service: %s", result.message)
        return api_response(
            False,
            message=result.message or t_api("alarm_status_error", request),
            status=400,
            error_code=result.error_code or "alarm_status_error"
        )

    alarm_data = result.data or {}

    if advanced_mode:
        return api_response(True, data={
            "timestamp": result.timestamp.isoformat(),
            "alarm": alarm_data,
            "mode": "advanced"
        })

    payload = {
        "enabled": bool(alarm_data.get("enabled", False)),
        "time": alarm_data.get("time") or "07:00",
        "alarm_volume": alarm_data.get("alarm_volume", alarm_data.get("volume", 50)),
        "next_alarm": alarm_data.get("next_alarm", ""),
        "playlist_uri": alarm_data.get("playlist_uri", ""),
        "device_name": alarm_data.get("device_name", ""),
        "mode": "basic"
    }
    return api_response(True, data=payload)


@app.route("/api/dashboard/status")
@api_error_handler
@rate_limit("status_check")
def api_dashboard_status():
    """Aggregate dashboard status (alarm, sleep, playback) in a single response."""
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _dashboard_snapshot.mark_stale()
        _playback_snapshot.mark_stale()
        _devices_snapshot.mark_stale()

    dashboard_data, dashboard_meta = _dashboard_snapshot.snapshot()
    playback_data, playback_meta = _playback_snapshot.snapshot()
    devices_data, devices_meta = _devices_snapshot.snapshot()

    if force_refresh or dashboard_meta["pending"]:
        _dashboard_snapshot.schedule_refresh(
            _refresh_dashboard_snapshot,
            force=force_refresh,
            reason="api.dashboard"
        )

    # Only trigger dedicated snapshot refreshers if the combined dashboard one is not already running.
    if (force_refresh or playback_meta["pending"]) and not dashboard_meta.get("refreshing"):
        _playback_snapshot.schedule_refresh(
            _refresh_playback_snapshot,
            force=force_refresh,
            reason="api.dashboard.playback"
        )
    if (force_refresh or devices_meta["pending"]) and not dashboard_meta.get("refreshing"):
        _devices_snapshot.schedule_refresh(
            _refresh_devices_snapshot,
            force=force_refresh,
            reason="api.dashboard.devices"
        )

    config = load_config()
    next_alarm_time = ""
    if config.get("enabled") and config.get("time"):
        try:
            next_alarm_time = AlarmTimeValidator.format_time_until_alarm(config["time"])
        except Exception:
            next_alarm_time = "Next alarm calculation error"

    alarm_payload = {
        "enabled": config.get("enabled", False),
        "time": config.get("time", "07:00"),
        "alarm_volume": config.get("alarm_volume", 50),
        "next_alarm": next_alarm_time,
        "playlist_uri": config.get("playlist_uri", ""),
        "device_name": config.get("device_name", "")
    }

    sleep_service = get_service("sleep")
    sleep_result = sleep_service.get_sleep_status()
    if sleep_result.success:
        sleep_payload = (sleep_result.data or {}).get("raw_status") or sleep_result.data
    else:
        sleep_payload = {
            "active": False,
            "error": sleep_result.message,
            "error_code": sleep_result.error_code or "sleep_status_error"
        }

    playback_payload = {}
    playback_status = "pending"
    playback_error = None
    if playback_data:
        playback_payload = playback_data.get("playback") or {}
        playback_status = playback_data.get("status", "unknown")
        playback_error = playback_data.get("error")
    elif dashboard_data:
        dash_playback = dashboard_data.get("playback", {})
        if isinstance(dash_playback, dict):
            playback_payload = dash_playback.get("playback") or {}
            playback_status = dash_playback.get("status", playback_status)
            playback_error = dash_playback.get("error")

    devices_payload = []
    devices_status = "pending"
    devices_cache = {}
    if devices_data:
        devices_payload = devices_data.get("devices") or []
        devices_status = devices_data.get("status", "unknown")
        devices_cache = devices_data.get("cache") or {}
    elif dashboard_data:
        dash_devices = dashboard_data.get("devices", {})
        if isinstance(dash_devices, dict):
            devices_payload = dash_devices.get("devices") or []
            devices_status = dash_devices.get("status", devices_status)
            devices_cache = dash_devices.get("cache") or {}

    hydration_meta = {
        "dashboard": _normalise_snapshot_meta(dashboard_meta),
        "playback": _normalise_snapshot_meta(playback_meta),
        "devices": _normalise_snapshot_meta(devices_meta),
    }

    response_payload = {
        "timestamp": _iso_timestamp_now(),
        "alarm": alarm_payload,
        "sleep": sleep_payload,
        "playback": playback_payload or {},
        "playback_status": playback_status,
        "devices": devices_payload,
        "devices_meta": {
            "status": devices_status,
            "cache": devices_cache,
            "fetched_at": devices_data.get("fetched_at") if devices_data else None
        },
        "hydration": hydration_meta
    }

    if playback_error:
        response_payload["playback_error"] = playback_error

    # Determine a meaningful HTTP status: pending requests should return 202 to indicate work in progress.
    status_code = 200
    if hydration_meta["playback"]["pending"] or hydration_meta["devices"]["pending"]:
        status_code = 202
    elif playback_status == "error":
        status_code = 503

    return api_response(True, data=response_payload, status=status_code)

# =====================================
# 🎵 API Routes - Music & Playback
# =====================================

@app.route("/api/music-library")
@api_error_handler
@rate_limit("spotify_api")
def api_music_library():
    """API endpoint for music library data with unified caching"""
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')

    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    want_fields = request.args.get('fields')
    if_modified = request.headers.get('If-None-Match')
    raw_sections = request.args.get('sections')
    requested_sections = _parse_library_sections(raw_sections, ensure_default_on_empty=True)

    try:
        return _build_library_response(
            token,
            sections=requested_sections,
            force_refresh=force_refresh,
            want_fields=want_fields,
            if_modified=if_modified,
            request_obj=request,
        )
    except Exception:
        logging.exception("Error loading music library")
        if not requested_sections:
            fallback_data = cache_migration.get_offline_fallback()
            if fallback_data:
                resp_data = prepare_library_payload(fallback_data, basic=False)
                hash_val = resp_data["hash"]
                resp = api_response(True, data=resp_data, message=t_api("served_offline_cache", request))
                resp.headers['X-MusicLibrary-Hash'] = hash_val
                resp.headers['ETag'] = hash_val
                return resp

        return api_response(False, message=t_api("spotify_unavailable", request), status=503, error_code="spotify_unavailable")

@app.route("/api/music-library/sections")
@api_error_handler
@rate_limit("spotify_api")
def api_music_library_sections():
    """Load only requested music library sections with unified caching.

    Query params:
        sections: comma separated list (playlists,albums,tracks,artists)
        refresh: force bypass cache if '1' or 'true'
        fields: 'basic' for slimmed down response
    """
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")

    sections = _parse_library_sections(request.args.get('sections', 'playlists'), default=['playlists'], ensure_default_on_empty=True)
    force = request.args.get('refresh') in ('1', 'true', 'yes')
    want_fields = request.args.get('fields')
    if_modified = request.headers.get('If-None-Match')

    try:
        return _build_library_response(
            token,
            sections=sections,
            force_refresh=force,
            want_fields=want_fields,
            if_modified=if_modified,
            request_obj=request,
        )

    except Exception as e:
        logging.exception("Error loading partial music library")
        return api_response(False, message=str(e), status=500, error_code="music_library_partial_error")

@app.route("/api/artist-top-tracks/<artist_id>")
@api_error_handler
@rate_limit("spotify_api")
def api_artist_top_tracks(artist_id):
    """API endpoint for artist top tracks"""
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        from .api.spotify import get_artist_top_tracks
        tracks = get_artist_top_tracks(token, artist_id)
        
        return api_response(True, data={"artist_id": artist_id, "tracks": tracks, "total": len(tracks)})
        
    except Exception as e:
        logging.exception("Error loading artist top tracks")
        return api_response(False, message=f"Failed to load artist top tracks: {str(e)}", status=500, error_code="artist_tracks_failed")

@app.route("/api/token-cache/status")
@rate_limit("status_check")
def get_token_cache_status():
    """📊 Get token cache performance and status information."""
    try:
        cache_info = get_token_cache_info()
        return api_response(True, data={"cache_info": cache_info})
    except Exception as e:
        logging.error(f"❌ Error getting token cache status: {e}")
        return api_response(False, message=f"Error getting cache status: {str(e)}", status=500, error_code="cache_status_error")

@app.route("/api/thread-safety/status")
@rate_limit("status_check")
def get_thread_safety_status():
    """📊 Get thread safety status and statistics."""
    try:
        stats = get_config_stats()
        return api_response(True, data={"thread_safety_stats": stats})
    except Exception as e:
        logging.error(f"❌ Error getting thread safety status: {e}")
        return api_response(False, message=f"Error getting thread safety status: {str(e)}", status=500, error_code="thread_safety_error")

@app.route("/api/thread-safety/invalidate-cache", methods=["POST"])
def invalidate_thread_safe_cache():
    """🗑️ Force invalidation of thread-safe config cache."""
    try:
        invalidate_config_cache()
        return jsonify({
            "success": True,
            "message": "Config cache invalidated successfully"
        })
    except Exception as e:
        logging.error(f"❌ Error invalidating cache: {e}")
        return jsonify({
            "success": False,
            "message": f"Error invalidating cache: {str(e)}"
        }), 500

@app.route("/api/token-cache/performance")
def log_token_performance():
    """📈 Log token cache performance summary."""
    try:
        log_token_cache_performance()
        return jsonify({
            "success": True,
            "message": "Performance summary logged to console"
        })
    except Exception as e:
        logging.error(f"❌ Error logging token performance: {e}")
        return jsonify({
            "success": False,
            "message": f"Error logging performance: {str(e)}"
        }), 500

@app.route("/playback_status")
@api_error_handler
@rate_limit("spotify_api")
def playback_status():
    """Get current Spotify playback status"""
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _playback_snapshot.mark_stale()

    playback_data, meta = _playback_snapshot.snapshot()

    if force_refresh or meta["pending"]:
        _playback_snapshot.schedule_refresh(
            _refresh_playback_snapshot,
            force=force_refresh,
            reason="api.playback"
        )

    payload = playback_data.get("playback") if playback_data else {}
    status_flag = playback_data.get("status") if playback_data else "pending"
    response_payload = {
        "timestamp": _iso_timestamp_now(),
        "playback": payload or {},
        "status": status_flag,
        "hydration": _normalise_snapshot_meta(meta)
    }
    if playback_data and playback_data.get("error"):
        response_payload["error"] = playback_data["error"]

    status_code = 200
    if response_payload["hydration"]["pending"] or status_flag in {"pending", "auth_required"}:
        status_code = 202
    elif status_flag == "error":
        status_code = 503

    return api_response(True, data=response_payload, status=status_code)


@app.route("/api/devices")
@api_error_handler
@rate_limit("status_check")
def api_devices():
    """Return cached Spotify devices without blocking on network calls."""
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _devices_snapshot.mark_stale()

    devices_data, meta = _devices_snapshot.snapshot()

    if force_refresh or meta["pending"]:
        _devices_snapshot.schedule_refresh(
            _refresh_devices_snapshot,
            force=force_refresh,
            reason="api.devices"
        )

    payload = {
        "timestamp": _iso_timestamp_now(),
        "devices": devices_data.get("devices") if devices_data else [],
        "status": devices_data.get("status") if devices_data else "pending",
        "cache": devices_data.get("cache") if devices_data else {},
        "hydration": _normalise_snapshot_meta(meta)
    }
    if devices_data and devices_data.get("error"):
        payload["error"] = devices_data["error"]

    status_code = 200
    if payload["hydration"]["pending"] or payload["status"] in {"pending", "auth_required"}:
        status_code = 202
    elif payload["status"] == "error":
        status_code = 503

    return api_response(True, data=payload, status=status_code)

@app.route("/api/spotify/health")
@rate_limit("status_check")
def api_spotify_health():
    """Quick health check for Spotify connectivity (DNS, TLS reachability)."""
    try:
        from .api.spotify import spotify_network_health
        health = spotify_network_health()
        http_code = 200 if health.get("ok") else 503
        return api_response(health.get("ok", False), data=health, status=http_code, message=t_api("ok", request) if health.get("ok") else "degraded", error_code=None if health.get("ok") else "spotify_degraded")
    except Exception as e:
        logging.exception("Error running Spotify health check")
        return jsonify({
            "ok": False,
            "error": "HEALTH_CHECK_FAILED",
            "message": str(e)
        }), 500

# =====================================
# 🩺 Health/Readiness & Metrics
# =====================================

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "version": str(VERSION)})

@app.route("/readyz")
def readyz():
    try:
        # Basic checks: config loaded, rate limiter running
        _ = load_config()
        stats = rate_limiter.get_statistics()
        return jsonify({
            "ok": True,
            "rate_limiter": {"total_requests": stats.get('global_stats', {}).get('total_requests', 0)}
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503

@app.route("/metrics")
def metrics():
    # Minimal Prometheus-style exposition
    try:
        stats = rate_limiter.get_statistics()
        cache_info = get_token_cache_info()
        lines = []
        lines.append("# HELP spotipi_requests_total Total requests seen by rate limiter")
        lines.append("# TYPE spotipi_requests_total counter")
        lines.append(f"spotipi_requests_total {stats.get('global_stats', {}).get('total_requests', 0)}")
        lines.append("# HELP spotipi_cache_hits Token cache hits")
        lines.append("# TYPE spotipi_cache_hits counter")
        hits = cache_info.get('cache_metrics', {}).get('cache_hits', 0) if isinstance(cache_info, dict) else 0
        lines.append(f"spotipi_cache_hits {hits}")
        lines.append("# HELP spotipi_cache_misses Token cache misses")
        lines.append("# TYPE spotipi_cache_misses counter")
        misses = cache_info.get('cache_metrics', {}).get('cache_misses', 0) if isinstance(cache_info, dict) else 0
        lines.append(f"spotipi_cache_misses {misses}")
        return ("\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"})
    except Exception:
        return ("spotipi_up 0\n", 200, {"Content-Type": "text/plain; version=0.0.4"})

@app.route("/toggle_play_pause", methods=["POST"])
@api_error_handler
def toggle_play_pause():
    """Toggle Spotify play/pause - optimized for immediate response"""
    spotify_service = get_service("spotify")
    result = spotify_service.toggle_playback_fast()

    if result.success:
        return api_response(True, data=result.data, message=t_api("ok", request))

    error_code = result.error_code or "playback_toggle_failed"
    status = 503 if error_code == "playback_toggle_failed" else 500
    message = result.message or "Playback toggle failed"

    if error_code == "auth_required":
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")

    payload = result.data if isinstance(result.data, dict) else {"result": result.data}
    return api_response(False, data=payload, message=message, status=status, error_code=error_code)

@app.route("/volume", methods=["POST"])
@api_error_handler
def volume_endpoint():
    """Volume endpoint - only sets Spotify volume (no config save)"""
    spotify_service = get_service("spotify")
    result = spotify_service.set_volume_from_form(request.form)

    if result.success:
        volume = (result.data or {}).get("volume")
        message = f"Volume set to {volume}" if volume is not None else t_api("ok", request)
        return api_response(True, data=result.data, message=message)

    error_code = result.error_code or "volume_set_failed"
    message = result.message or t_api("volume_set_failed", request)

    if error_code == "auth_required":
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    if error_code == "volume":
        logger.warning("Volume validation error: %s", message)
        return api_response(False, message=message, status=400, error_code="volume")

    return api_response(False, message=t_api("volume_set_failed", request), status=500, error_code=error_code)

# =====================================
# 😴 API Routes - Sleep Timer
# =====================================

@app.route("/sleep_status")
@api_error_handler
@rate_limit("status_check")
def sleep_status_api():
    """Get sleep timer status - supports both basic and advanced modes"""
    advanced_mode = request.args.get('advanced', 'false').lower() == 'true'

    sleep_service = get_service("sleep")
    result = sleep_service.get_sleep_status()

    if not result.success:
        logger.error("Failed to load sleep status via service: %s", result.message)
        return api_response(
            False,
            message=result.message or t_api("sleep_status_error", request),
            status=500,
            error_code=result.error_code or "sleep_status_error"
        )

    if advanced_mode:
        return api_response(True, data={
            "timestamp": result.timestamp.isoformat(),
            "sleep": {k: v for k, v in (result.data or {}).items() if k != "raw_status"},
            "mode": "advanced"
        })

    legacy_payload = (result.data or {}).get("raw_status")
    if legacy_payload is None:
        legacy_payload = result.data
    return api_response(True, data=legacy_payload or {})

@app.route("/sleep", methods=["POST"])
@api_error_handler
@rate_limit("config_changes")
def start_sleep():
    """Start sleep timer with comprehensive input validation"""
    sleep_service = get_service("sleep")
    result = sleep_service.start_sleep_timer(request.form)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
    if request.is_json or is_ajax:
        if result.success:
            return api_response(True, message=result.message or "Sleep timer started")

        error_code = (result.error_code or "sleep_start_failed")
        status = 400 if error_code in {"duration", "sleep_volume", "playlist_uri", "device_name"} else 500
        message = result.message or t_api("failed_start_sleep", request)
        return api_response(False, message=message, status=status, error_code=error_code)

    if result.success:
        session['success_message'] = result.message or "Sleep timer started"
    else:
        session['error_message'] = result.message or "Failed to start sleep timer"
    return redirect(url_for('index'))

@app.route("/stop_sleep", methods=["POST"])
@api_error_handler
@rate_limit("api_general")
def stop_sleep():
    """Stop active sleep timer"""
    sleep_service = get_service("sleep")
    result = sleep_service.stop_sleep_timer()
    success = result.success

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
    if request.is_json or is_ajax:
        message = t_api("sleep_stopped", request) if success else (result.message or "Failed to stop sleep timer")
        return api_response(
            success,
            message=message,
            status=200 if success else 500,
            error_code=None if success else (result.error_code or "sleep_stop_failed")
        )

    if success:
        session['success_message'] = result.message or "Sleep timer stopped"
    else:
        session['error_message'] = result.message or "Failed to stop sleep timer"
    return redirect(url_for('index'))

# =====================================
# 🎵 Music Library & Standalone Routes
# =====================================

@app.route("/music_library")
@api_error_handler
@rate_limit("spotify_api")
def music_library():
    """Standalone music library browser"""
    token = get_access_token()
    devices = get_devices(token) if token else []
    
    return render_template('music_library.html', 
                         devices=devices,
                         has_token=bool(token))

@app.route("/play", methods=["POST"])
@api_error_handler
def play_endpoint():
    """Unified playback endpoint - supports both JSON and form data"""
    spotify_service = get_service("spotify")

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        result = spotify_service.start_playback_from_payload(payload, payload_type="json")
    else:
        result = spotify_service.start_playback_from_payload(request.form, payload_type="form")

    if result.success:
        return api_response(True, message=t_api("playback_started", request))

    error_code = (result.error_code or "playback_start_failed")
    message = result.message or t_api("failed_start_playback", request)

    if error_code == "auth_required":
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    if error_code in {"missing_context_uri", "missing_uri", "missing_device"}:
        translations = {
            "missing_context_uri": t_api("missing_context_uri", request),
            "missing_uri": t_api("missing_uri", request),
            "missing_device": t_api("missing_device", request)
        }
        return api_response(False, message=translations[error_code], status=400, error_code=error_code)
    if error_code == "no_devices":
        return api_response(False, message=t_api("no_devices", request), status=404, error_code="no_devices")
    if error_code == "device_not_found":
        device_name = ""
        if isinstance(result.data, dict):
            device_name = result.data.get("device_name", "")
        return api_response(False, message=t_api("device_not_found", request, name=device_name), status=404, error_code="device_not_found")

    status = 503 if error_code == "playlists_unavailable" else 500
    return api_response(False, message=message, status=status, error_code=error_code)

# =====================================
# 📱 Utility Routes
# =====================================

@app.route("/debug/language")
def debug_language():
    """Debug endpoint to check language detection"""
    user_language = get_user_language(request)
    translations = get_translations(user_language)
    
    return {
        "detected_language": user_language,
        "accept_language_header": request.headers.get('Accept-Language', 'Not found'),
        "sample_translation": translations.get('app_title', 'Translation not found'),
        "all_headers": dict(request.headers)
    }

# =====================================
# 🚨 Error Handlers
# =====================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors by rendering a minimal error page"""
    return render_template('index.html', 
                         error_message=t_api("page_not_found"),
                         config={},
                         devices=[],
                         playlists=[],
                         next_alarm_info="",
                         sleep_status={},
                         initial_state={}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors by rendering a minimal error page"""
    return render_template('index.html', 
                         error_message=t_api("internal_server_error_page"),
                         config={},
                         devices=[],
                         playlists=[],
                         next_alarm_info="",
                         sleep_status={},
                         initial_state={}), 500

# =====================================
# 🚀 Application Startup
# =====================================

def start_alarm_scheduler():  # backward compatibility alias
    start_event_alarm_scheduler()

# =====================================
# �️ Cache Management API
# =====================================

@app.route("/api/cache/status")
@rate_limit("status_check")
def get_cache_status():
    """📊 Get unified cache performance and statistics."""
    try:
        stats = cache_migration.get_cache_statistics()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "cache_system": {
                "type": "unified",
                "status": "active",
                **stats
            }
        })
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return api_response(False, message=str(e), status=500, error_code="cache_status_error")

@app.route("/api/cache/invalidate", methods=["POST"])
@rate_limit("config_changes")
def invalidate_cache():
    """🗑️ Invalidate all cache data."""
    try:
        count = cache_migration.invalidate_all_cache()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "invalidated_entries": count
        }, message=f"Successfully invalidated {count} cache entries")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return api_response(False, message=str(e), status=500, error_code="cache_invalidate_error")

@app.route("/api/cache/invalidate/music-library", methods=["POST"])
@rate_limit("config_changes") 
def invalidate_music_library_cache():
    """🎵 Invalidate only music library cache data."""
    try:
        count = cache_migration.invalidate_music_library()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "invalidated_entries": count
        }, message=f"Successfully invalidated {count} music library cache entries")
    except Exception as e:
        logger.error(f"Error invalidating music library cache: {e}")
        return api_response(False, message=str(e), status=500, error_code="music_cache_invalidate_error")

@app.route("/api/cache/invalidate/devices", methods=["POST"])
@rate_limit("config_changes")
def invalidate_device_cache():
    """📱 Invalidate only device cache data."""
    try:
        count = cache_migration.invalidate_devices()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "invalidated_entries": count
        }, message=f"Successfully invalidated {count} device cache entries")
    except Exception as e:
        logger.error(f"Error invalidating device cache: {e}")
        return api_response(False, message=str(e), status=500, error_code="device_cache_invalidate_error")

# =====================================
# �🚨 Rate Limiting Management API
# =====================================

@app.route("/api/rate-limiting/status")
@rate_limit("status_check") 
def get_rate_limiting_status():
    """📊 Get rate limiting status and statistics."""
    try:
        stats = rate_limiter.get_stats()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "rate_limiting": stats
        })
    except Exception as e:
        logger.error(f"Error getting rate limiting status: {e}")
        return api_response(False, message=str(e), status=500, error_code="rate_limit_status_error")

@app.route("/api/rate-limiting/reset", methods=["POST"])
@rate_limit("config_changes")
def reset_rate_limiting():
    """🔄 Reset rate limiting statistics and storage."""
    try:
        rate_limiter.reset()
        return api_response(True, data={"timestamp": datetime.datetime.now().isoformat()}, message="Rate limiting data reset successfully")
    except Exception as e:
        logger.error(f"Error resetting rate limiting: {e}")
        return api_response(False, message=str(e), status=500, error_code="rate_limit_reset_error")

# =====================================
# 🏗️ Service Layer API Endpoints
# =====================================

@app.route("/api/services/health")
@rate_limit("status_check")
def api_services_health():
    """📊 Get health status of all services."""
    try:
        result = service_manager.health_check_all()
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "health": result.data})
        else:
            return api_response(False, message=result.message, status=500, error_code=result.error_code or "services_health_error")
            
    except Exception as e:
        logger.error(f"Error in services health check: {e}")
        return api_response(False, message=str(e), status=500, error_code="services_health_exception")

@app.route("/api/services/performance")
@rate_limit("status_check")
def api_services_performance():
    """📈 Get performance overview of all services."""
    try:
        result = service_manager.get_performance_overview()
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "performance": result.data})
        else:
            return api_response(False, message=result.message, status=500, error_code=result.error_code or "services_performance_error")
            
    except Exception as e:
        logger.error(f"Error getting performance overview: {e}")
        return api_response(False, message=str(e), status=500, error_code="services_performance_exception")

@app.route("/api/services/diagnostics")
@rate_limit("status_check")
def api_services_diagnostics():
    """🔧 Run comprehensive system diagnostics."""
    try:
        result = service_manager.run_diagnostics()
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "diagnostics": result.data})
        else:
            return api_response(False, message=result.message, status=500, error_code=result.error_code or "services_diagnostics_error")
            
    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        return api_response(False, message=str(e), status=500, error_code="services_diagnostics_exception")


@app.route("/api/perf/metrics")
@rate_limit("status_check")
def api_perf_metrics():
    """📈 Expose recent performance timings for bench scripts."""
    try:
        metrics = perf_monitor.snapshot()
        payload = {
            "timestamp": _iso_timestamp_now(),
            "metrics": metrics
        }
        return api_response(True, data=payload)
    except Exception as e:
        logger.error(f"Error collecting perf metrics: {e}")
        return api_response(False, message=str(e), status=500, error_code="perf_metrics_error")

# =====================================
# ⏱️ Alarm Manual Trigger Endpoint
# =====================================

@app.route("/api/alarm/execute", methods=["POST"])
@rate_limit("config_changes")
def api_alarm_execute():
    """Manually execute the alarm immediately.

    Useful for debugging on the Raspberry Pi when checking playlist/device
    configuration or verifying logging. Returns JSON with success flag.
    """
    alarm_service = get_service("alarm")
    result = alarm_service.execute_alarm_now()

    if result.success:
        return api_response(True, data={"executed": True}, message=result.message or "Alarm executed")

    logger.error("Alarm execution failed: %s", result.message)
    return api_response(
        False,
        data={"executed": False},
        message=result.message or "Alarm conditions not met or failed",
        status=400,
        error_code="alarm_not_executed"
    )

@app.route("/api/spotify/auth-status")
@rate_limit("spotify_api")
def api_spotify_auth_status():
    """🎵 Get Spotify authentication status via service layer."""
    try:
        spotify_service = get_service("spotify")
        result = spotify_service.get_authentication_status()
        
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "spotify": result.data})
        else:
            return api_response(False, message=result.message, status=401 if result.error_code == "AUTH_REQUIRED" else 500, error_code=result.error_code or "spotify_auth_error")
            
    except Exception as e:
        logger.error(f"Error getting Spotify auth status: {e}")
        return api_response(False, message=str(e), status=500, error_code="spotify_auth_exception")

@app.route("/api/spotify/devices")
@api_error_handler
@rate_limit("spotify_api")
def api_spotify_devices():
    """API endpoint for getting available Spotify devices."""
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _devices_snapshot.mark_stale()

    devices_data, meta = _devices_snapshot.snapshot()
    if force_refresh or meta["pending"]:
        _devices_snapshot.schedule_refresh(
            _refresh_devices_snapshot,
            force=force_refresh,
            reason="api.spotify.devices"
        )

    cache_info = devices_data.get("cache") if devices_data else {}
    ts_value = cache_info.get('timestamp') if isinstance(cache_info, dict) else None
    last_updated_iso = None
    if ts_value:
        try:
            last_updated_iso = datetime.datetime.fromtimestamp(
                float(ts_value),
                tz=datetime.timezone.utc
            ).isoformat()
        except (TypeError, ValueError, OSError):
            last_updated_iso = None
    elif devices_data and devices_data.get("fetched_at"):
        last_updated_iso = devices_data["fetched_at"]

    payload = {
        "devices": devices_data.get("devices") if devices_data else [],
        "cache": cache_info or {},
        "lastUpdated": ts_value,
        "lastUpdatedIso": last_updated_iso,
        "status": devices_data.get("status") if devices_data else "pending",
        "hydration": _normalise_snapshot_meta(meta)
    }

    status_code = 200
    if payload["hydration"]["pending"] or payload["status"] in {"pending", "auth_required"}:
        status_code = 202
    elif payload["status"] == "error":
        status_code = 503

    return api_response(True, data=payload, status=status_code)

@app.route("/api/devices/refresh")
@api_error_handler
def api_devices_refresh():
    """Fast device refresh endpoint - bypasses cache for immediate updates."""
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        cache_migration.invalidate_devices()
        devices = get_devices(token)
        cache_info = cache_migration.get_device_cache_info(token)
        payload = {
            "devices": devices if devices else [],
            "cache": cache_info or {},
            "lastUpdated": cache_info.get('timestamp') if cache_info else None,
            "stale": bool(cache_info.get('stale')) if cache_info else False,
            "timestamp": time.time()
        }
        if cache_info and cache_info.get('timestamp'):
            try:
                payload['lastUpdatedIso'] = datetime.datetime.fromtimestamp(
                    cache_info['timestamp'], tz=datetime.timezone.utc
                ).isoformat()
            except (TypeError, ValueError, OSError):
                pass
        logging.info(f"🔄 Fast device refresh: {len(payload['devices'])} devices loaded")

        snapshot_payload = {
            "status": "ok" if payload["devices"] else "empty",
            "devices": payload["devices"],
            "cache": cache_info or {},
            "fetched_at": _iso_timestamp_now()
        }
        _devices_snapshot.set(snapshot_payload)

        return api_response(True, data=payload)
    except Exception as e:
        logging.error(f"❌ Error in device refresh: {e}")
        return api_response(False, message=str(e), status=503, error_code="device_refresh_error")

# =====================================
# 🚀 Application Runner
# =====================================

def run_app(host="0.0.0.0", port=5001, debug=False):
    """Run the Flask app with event-driven alarm scheduler."""
    start_event_alarm_scheduler()
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        request_handler=TidyRequestHandler,
    )

# Do not start scheduler at import time to avoid duplicate threads in WSGI

if __name__ == "__main__":
    logging.info(f"🎵 Starting {get_app_info()}")
    logging.info(f"📁 Project root: {project_root}")
    logging.info(f"⚙️ Config loaded: {bool(load_config())}")

    # Development vs Production
    config = load_config()
    debug_mode = config.get("debug", False)
    port = int(os.getenv("PORT", 5000))

    # Start with new event-driven scheduler
    run_app(host="0.0.0.0", port=port, debug=debug_mode)
