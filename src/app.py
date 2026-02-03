"""
SpotiPi Main Application
Flask web application with new modular structure
"""

import datetime
import logging
import os
import secrets
import time
from pathlib import Path
from threading import Thread
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from flask import (Flask, Response, g, request)
from flask_compress import Compress

from .api.spotify import (get_access_token, get_combined_playback, get_devices,
                          get_user_library)
# Import from new structure - use relative imports since we're in src/
from .config import load_config
from .core.alarm_scheduler import \
    start_alarm_scheduler as start_event_alarm_scheduler
from .services.service_manager import get_service
from .utils.cache_migration import get_cache_migration_layer
from .utils.async_snapshot import AsyncSnapshot
from .utils.logger import setup_logger, setup_logging
from .utils.perf_monitor import perf_monitor
from .utils.translations import get_translations, get_user_language
from .utils.wsgi_logging import TidyRequestHandler
from .version import VERSION, get_app_info
from .routes.errors import register_error_handlers
from .routes.alarm import alarm_bp
from .routes.cache import cache_bp
from .routes.devices import devices_bp, init_snapshots as init_devices_snapshots
from .routes.health import health_bp, init_snapshots as init_health_snapshots
from .routes.main import main_bp, init_snapshots as init_main_snapshots
from .routes.music import music_bp
from .routes.playback import playback_bp
from .routes.services import services_bp
from .routes.sleep import sleep_bp

# Initialize Flask app with correct paths
project_root = Path(__file__).parent.parent  # Go up from src/ to project root
template_dir = project_root / "templates"
static_dir = project_root / "static"

# Detect low power mode (e.g. Pi Zero) to tailor runtime features
LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')

app: Flask | None = None
logger = logging.getLogger("spotipi")
cache_migration = None
_dashboard_snapshot = None
_playback_snapshot = None
_devices_snapshot = None


def _configure_app(app: Flask) -> None:
    """Apply runtime configuration to the Flask app."""
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


def _register_blueprints(app: Flask) -> None:
    """Register blueprints and error handlers."""
    app.register_blueprint(main_bp)
    app.register_blueprint(alarm_bp)
    app.register_blueprint(cache_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(music_bp)
    app.register_blueprint(playback_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(sleep_bp)
    register_error_handlers(app)


def _init_snapshots() -> tuple[AsyncSnapshot, AsyncSnapshot, AsyncSnapshot]:
    """Initialize snapshot helpers and return them."""
    # Adaptive cache TTLs: Longer on Pi Zero W to reduce API calls
    # Playback state changes infrequently (only on skip/pause/volume change)
    _default_dashboard_ttl = 5.0 if LOW_POWER_MODE else 1.5
    _default_playback_status_ttl = 5.0 if LOW_POWER_MODE else 1.5

    try:
        dashboard_cache_ttl = max(
            0.1,
            float(os.getenv("SPOTIPI_STATUS_CACHE_SECONDS", str(_default_dashboard_ttl))),
        )
    except ValueError:
        dashboard_cache_ttl = _default_dashboard_ttl

    try:
        playback_status_cache_ttl = max(
            0.1,
            float(os.getenv("SPOTIPI_PLAYBACK_STATUS_CACHE_SECONDS", str(_default_playback_status_ttl))),
        )
    except ValueError:
        playback_status_cache_ttl = _default_playback_status_ttl

    dashboard_snapshot = AsyncSnapshot(
        "dashboard",
        dashboard_cache_ttl,
        min_retry=1.2 if LOW_POWER_MODE else 0.6
    )

    try:
        device_snapshot_ttl = max(
            3.0,
            float(os.getenv("SPOTIPI_DEVICE_SNAPSHOT_SECONDS", os.getenv("SPOTIPI_DEVICE_TTL", "6")))
        )
    except (TypeError, ValueError):
        device_snapshot_ttl = 8.0 if LOW_POWER_MODE else 5.0

    playback_snapshot = AsyncSnapshot(
        "playback",
        playback_status_cache_ttl,
        min_retry=0.8 if LOW_POWER_MODE else 0.4
    )
    devices_snapshot = AsyncSnapshot(
        "devices",
        device_snapshot_ttl,
        min_retry=1.5 if LOW_POWER_MODE else 0.75
    )

    return dashboard_snapshot, playback_snapshot, devices_snapshot


def _register_snapshot_injections(
    dashboard_snapshot: AsyncSnapshot,
    playback_snapshot: AsyncSnapshot,
    devices_snapshot: AsyncSnapshot,
) -> None:
    """Inject snapshot references into blueprints."""
    init_devices_snapshots(playback_snapshot, devices_snapshot)
    init_health_snapshots(dashboard_snapshot, playback_snapshot, devices_snapshot)
    init_main_snapshots(dashboard_snapshot, playback_snapshot, devices_snapshot)


def _register_request_hooks(app: Flask) -> None:
    """Attach request hooks and template context."""

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
            # Default: allow same-origin and spotipi.local (with any port)
            default_host = os.getenv('SPOTIPI_DEFAULT_HOST', 'spotipi.local')
            if request_origin:
                parsed_origin = urlparse(request_origin)
                # Allow if hostname matches (ignore port difference)
                if parsed_origin.hostname and parsed_origin.hostname.endswith(default_host):
                    response.headers['Access-Control-Allow-Origin'] = request_origin
                    response.headers.setdefault('Vary', 'Origin')
                else:
                    # Fallback to default origin
                    response.headers['Access-Control-Allow-Origin'] = f'http://{default_host}'
                    response.headers.setdefault('Vary', 'Origin')
            # No Origin header = same-origin request, no CORS needed

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


def _start_warmup(
    app: Flask,
    dashboard_snapshot: AsyncSnapshot,
    playback_snapshot: AsyncSnapshot,
    devices_snapshot: AsyncSnapshot,
) -> None:
    """Start the background warmup routine once per app instance."""
    if hasattr(app, '_warmup_started'):
        return

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
                devices_snapshot.set(devices_payload)
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
                playback_snapshot.set(playback_payload)
                if playback_payload.get("status") == "ok":
                    logging.info("🌅 Warmup: playback snapshot primed")
            except Exception as e:
                logging.debug(f"🌅 Warmup: playback snapshot error: {e}")
                playback_payload = {"status": "error", "playback": None, "error": str(e), "fetched_at": snapshot_ts}

            dashboard_snapshot.set({
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


def create_app(*, start_warmup: Optional[bool] = None) -> Flask:
    """Build and configure a Flask application instance."""
    global app, logger, cache_migration, _dashboard_snapshot, _playback_snapshot, _devices_snapshot

    flask_app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
        static_url_path='/static'
    )

    _configure_app(flask_app)
    _register_blueprints(flask_app)

    setup_logging()
    logger = setup_logger("spotipi")

    cache_migration = get_cache_migration_layer(project_root)

    dashboard_snapshot, playback_snapshot, devices_snapshot = _init_snapshots()
    _dashboard_snapshot = dashboard_snapshot
    _playback_snapshot = playback_snapshot
    _devices_snapshot = devices_snapshot

    _register_snapshot_injections(dashboard_snapshot, playback_snapshot, devices_snapshot)
    _register_request_hooks(flask_app)

    if start_warmup is None:
        warmup_env = os.getenv("SPOTIPI_WARMUP", "1").strip().lower()
        start_warmup = warmup_env not in {"0", "false", "no", "off"}
        if os.getenv("PYTEST_CURRENT_TEST"):
            start_warmup = False

    if start_warmup:
        _start_warmup(flask_app, dashboard_snapshot, playback_snapshot, devices_snapshot)

    app = flask_app
    return flask_app


def get_app() -> Flask:
    """Return the current app, creating it if needed."""
    global app
    if app is None:
        app = create_app()
    return app



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


## Legacy minute-based alarm_scheduler removed; replaced by event-driven version in core.alarm_scheduler

def _iso_timestamp_now() -> str:
    """Return ISO 8601 timestamp in UTC with a trailing Z."""
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    return now_utc.isoformat(timespec="microseconds").replace("+00:00", "Z")

# =====================================
# 🚨 Error Handlers
# =====================================


# =====================================
# 🚀 Application Startup
# =====================================

def start_alarm_scheduler():  # backward compatibility alias
    start_event_alarm_scheduler()

# =====================================
# 🚀 Application Runner
# =====================================

def run_app(host="0.0.0.0", port=5001, debug=False):
    """Run the Flask app with event-driven alarm scheduler."""
    start_event_alarm_scheduler()
    flask_app = get_app()
    flask_app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        request_handler=TidyRequestHandler,
    )

# Do not start scheduler at import time to avoid duplicate threads in WSGI

if __name__ == "__main__":
    create_app()
    logging.info(f"🎵 Starting {get_app_info()}")
    logging.info(f"📁 Project root: {project_root}")
    logging.info(f"⚙️ Config loaded: {bool(load_config())}")

    # Development vs Production
    config = load_config()
    debug_mode = config.get("debug", False)
    port = int(os.getenv("PORT", 5000))

    # Start with new event-driven scheduler
    run_app(host="0.0.0.0", port=port, debug=debug_mode)
