"""
SpotiPi Main Application
Flask web application with new modular structure
"""

import os
import datetime
import uuid
from threading import Thread
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from functools import wraps
import logging
import threading
import time
from urllib.parse import urlparse

# Import from new structure - use relative imports since we're in src/
from .config import load_config, save_config
from .core.alarm import execute_alarm
from .core.scheduler import WeekdayScheduler, AlarmTimeValidator
from .core.alarm_scheduler import start_alarm_scheduler as start_event_alarm_scheduler
from .utils.logger import setup_logger, setup_logging
from .utils.validation import validate_alarm_config, validate_sleep_config, validate_volume_only, ValidationError
from .version import get_app_info, VERSION
from .utils.translations import get_translations, get_user_language, t_api
from .utils.library_utils import compute_library_hash, prepare_library_payload, slim_collection
from .constants import ALARM_TRIGGER_WINDOW_MINUTES
from .api.spotify import (
    get_access_token, get_devices, get_playlists, get_user_library,
    start_playback, stop_playback, resume_playback, toggle_playback, toggle_playback_fast,
    set_volume, get_current_track, get_current_spotify_volume,
    get_playback_status, get_combined_playback, _spotify_request,
    get_saved_albums, get_user_saved_tracks, get_followed_artists
)
from .utils.token_cache import get_token_cache_info, log_token_cache_performance
from .utils.thread_safety import get_config_stats, invalidate_config_cache
from .utils.rate_limiting import rate_limit, get_rate_limiter, add_rate_limit_headers
from .utils.cache_migration import get_cache_migration_layer
from .services.service_manager import get_service_manager, get_service
from .core.sleep import (
    start_sleep_timer, stop_sleep_timer, get_sleep_status,
    save_sleep_settings
)

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

# Secure secret key generation
import secrets
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Setup logging
setup_logging()
logger = setup_logger("spotipi")

# Initialize cache migration layer
cache_migration = get_cache_migration_layer(project_root)

# Initialize rate limiter with default rules
rate_limiter = get_rate_limiter()

# Initialize service manager
service_manager = get_service_manager()

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
        response.headers['Access-Control-Allow-Origin'] = '*'

    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'

    # ---- Optional gzip compression ----
    try:
        enable_compress = (
            not LOW_POWER_MODE and
            os.getenv('SPOTIPI_ENABLE_GZIP', '1') in ('1', 'true', 'yes')
        )
        accept_encoding = request.headers.get('Accept-Encoding', '')
        already_encoded = response.headers.get('Content-Encoding')
        is_json = response.mimetype == 'application/json'
        size_threshold = int(os.getenv('SPOTIPI_GZIP_MIN_BYTES', '2048'))
        if (enable_compress and 'gzip' in accept_encoding and not already_encoded and is_json \
                and response.status_code not in (204, 304) and response.direct_passthrough is False):
            data = response.get_data()
            if len(data) >= size_threshold:
                import gzip, io
                buf = io.BytesIO()
                with gzip.GzipFile(mode='wb', fileobj=buf) as gz:
                    gz.write(data)
                compressed = buf.getvalue()
                response.set_data(compressed)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = str(len(compressed))
                # Ensure caches differentiate
                vary = response.headers.get('Vary') or ''
                if 'Accept-Encoding' not in vary:
                    response.headers['Vary'] = (vary + ', Accept-Encoding').strip(', ')
    except Exception as gzip_err:
        logging.debug(f"Compression skipped: {gzip_err}")

    return response

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
    config = load_config()
    
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
        'translations': translations,
        't': template_t,
        'lang': user_language,
        'weekday_scheduler': WeekdayScheduler,
        'static_css_path': '/static/css/',
        'static_js_path': '/static/js/',
        'static_icons_path': '/static/icons/',
        'now': datetime.datetime.now()
    }

# Unified API response helper
from typing import Any
def api_response(success: bool, *, data: Any | None = None, message: str = "", status: int = 200, error_code: str | None = None):
    req_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
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
    config = load_config()
    
    # Data is now loaded asynchronously via JavaScript to improve initial page load time.
    # We pass empty placeholders to the template.
    devices = []
    playlists = []
    current_track = None
    
    # Format weekdays for display
    weekdays_display = WeekdayScheduler.format_weekdays_display(config.get('weekdays', []))
    
    # Calculate next alarm time
    next_alarm_info = ""
    if config.get('enabled') and config.get('time'):
        try:
            next_alarm_info = AlarmTimeValidator.format_time_until_alarm(
                config['time'], 
                config.get('weekdays', [])
            )
        except Exception:
            next_alarm_info = "Next alarm calculation error"
    
    # Get user language from request
    user_language = get_user_language(request)
    translations = get_translations(user_language)
    
    # Create a translation function that supports parameters  
    def template_t(key, **kwargs):
        from .utils.translations import t
        return t(key, user_language, **kwargs)
    
    template_data = {
        'config': config,
        'devices': devices,
        'playlists': playlists,
        'current_track': current_track,
        'weekdays_display': weekdays_display,
        'next_alarm_info': next_alarm_info,
        'error_message': session.pop('error_message', None),
        'success_message': session.pop('success_message', None),
        'sleep_status': get_sleep_status(),
        # Add missing template variables
        'now': datetime.datetime.now(),
        't': template_t,  # Translation function with parameter support
        'lang': user_language,
        'translations': translations
    }
    
    return render_template('index.html', **template_data)

# Background warmup (runs once after startup) to prefetch devices and music library
# Skip on low-power devices like Pi Zero W to avoid CPU/RAM spikes at boot.
if not LOW_POWER_MODE and not hasattr(app, '_warmup_started'):
    def _warmup_fetch():
        try:
            logging.info("🌅 Warmup: starting background prefetch")
            token = get_access_token()
            if not token:
                logging.info("🌅 Warmup: no token available yet (user not authenticated)")
                return
            try:
                devs = cache_migration.get_devices_cached(token, get_devices, force_refresh=True)
                logging.info(f"🌅 Warmup: cached {len(devs)} devices")
            except Exception as e:
                logging.info(f"🌅 Warmup: device fetch error: {e}")
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
    try:
        validated_data = validate_alarm_config(request.form)
        config = load_config()
        config.update(validated_data)
        if config["time"] and not AlarmTimeValidator.validate_time_format(config["time"]):
            return api_response(False, message=t_api("invalid_time_format", request), status=400, error_code="time_format")
        if not save_config(config):
            return api_response(False, message=t_api("failed_save_config", request), status=500, error_code="save_failed")
        weekdays_info = WeekdayScheduler.format_weekdays_display(config.get('weekdays', []))
        logging.info(
            "Alarm settings saved: Active=%s Time=%s Volume=%s%% Weekdays=%s",
            config['enabled'], config['time'], config['alarm_volume'], weekdays_info or 'daily'
        )
        return api_response(True, data={
            "enabled": config["enabled"],
            "time": config["time"],
            "alarm_volume": config["alarm_volume"],
            "weekdays": config["weekdays"],
            "weekdays_display": weekdays_info
        }, message=t_api("alarm_settings_saved", request))
    except ValidationError as e:
        logging.warning("Alarm validation error: %s - %s", e.field_name, e.message)
        return api_response(False, message=f"Invalid {e.field_name}: {e.message}", status=400, error_code=e.field_name)
    except Exception:
        logging.exception("Error saving alarm configuration")
        return api_response(False, message=t_api("internal_error_saving", request), status=500, error_code="internal_error")

@app.route("/alarm_status")
@api_error_handler
@rate_limit("status_check")
def alarm_status():
    """Get alarm status - supports both basic and advanced modes"""
    config = load_config()
    advanced_mode = request.args.get('advanced', 'false').lower() == 'true'
    
    if advanced_mode:
        # Advanced status via service layer
        try:
            alarm_service = get_service("alarm")
            result = alarm_service.get_alarm_status()
            
            if result.success:
                return api_response(True, data={
                    "timestamp": result.timestamp.isoformat(), 
                    "alarm": result.data,
                    "mode": "advanced"
                })
            else:
                return api_response(False, message=result.message, status=400, 
                                  error_code=result.error_code or "alarm_status_error")
        except Exception as e:
            logger.error(f"Error getting advanced alarm status: {e}")
            return api_response(False, message=str(e), status=500, 
                              error_code="alarm_status_exception")
    else:
        # Basic status (legacy format)
        next_alarm_time = ""
        if config.get("enabled") and config.get("time"):
            next_alarm_time = AlarmTimeValidator.format_time_until_alarm(
                config["time"], 
                config.get("weekdays", [])
            )
        return api_response(True, data={
            "enabled": config.get("enabled", False),
            "time": config.get("time", "07:00"),
            "alarm_volume": config.get("alarm_volume", 50),
            "weekdays": config.get("weekdays", []),
            "weekdays_display": WeekdayScheduler.format_weekdays_display(config.get("weekdays", [])),
            "next_alarm": next_alarm_time,
            "playlist_uri": config.get("playlist_uri", ""),
            "device_name": config.get("device_name", ""),
            "mode": "basic"
        })


@app.route("/api/dashboard/status")
@api_error_handler
@rate_limit("status_check")
def api_dashboard_status():
    """Aggregate dashboard status (alarm, sleep, playback) in a single response."""
    config = load_config()

    next_alarm_time = ""
    if config.get("enabled") and config.get("time"):
        next_alarm_time = AlarmTimeValidator.format_time_until_alarm(
            config["time"],
            config.get("weekdays", [])
        )

    alarm_payload = {
        "enabled": config.get("enabled", False),
        "time": config.get("time", "07:00"),
        "alarm_volume": config.get("alarm_volume", 50),
        "weekdays": config.get("weekdays", []),
        "weekdays_display": WeekdayScheduler.format_weekdays_display(config.get("weekdays", [])),
        "next_alarm": next_alarm_time,
        "playlist_uri": config.get("playlist_uri", ""),
        "device_name": config.get("device_name", "")
    }

    sleep_payload = get_sleep_status()

    playback_payload = {}
    token = get_access_token()
    if token:
        try:
            playback_payload = get_combined_playback(token) or {}
        except Exception as playback_err:
            logger.debug("Dashboard playback aggregation failed: %s", playback_err)
    else:
        playback_payload = {"auth_required": True}

    response_payload = {
        "timestamp": datetime.datetime.utcnow().isoformat() + 'Z',
        "alarm": alarm_payload,
        "sleep": sleep_payload,
        "playback": playback_payload
    }

    return api_response(True, data=response_payload)

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
    
    try:
        want_fields = request.args.get('fields')  # "basic" -> slim lists
        if_modified = request.headers.get('If-None-Match')  # ETag header
        raw_sections = request.args.get('sections')
        valid_sections = {"playlists", "albums", "tracks", "artists"}
        requested_sections = []
        if raw_sections is not None:
            requested_sections = [s.strip() for s in raw_sections.split(',') if s.strip()]
            requested_sections = [s for s in requested_sections if s in valid_sections]
            if not requested_sections:
                requested_sections = ['playlists']

        if requested_sections:
            section_loaders = {
                'playlists': get_playlists,
                'albums': get_saved_albums,
                'tracks': get_user_saved_tracks,
                'artists': get_followed_artists
            }

            library_data = cache_migration.get_library_sections_cached(
                token=token,
                sections=requested_sections,
                section_loaders=section_loaders,
                force_refresh=force_refresh
            )
        else:
            # Use unified cache system instead of legacy _cache attribute
            library_data = cache_migration.get_full_library_cached(
                token=token,
                loader_func=get_user_library,
                force_refresh=force_refresh
            )

        # Compute hash for ETag/conditional requests
        hash_val = compute_library_hash(library_data)
        
        # Conditional request short-circuit
        if if_modified and if_modified == hash_val:
            resp = Response(status=304)
            resp.headers['ETag'] = hash_val
            resp.headers['X-MusicLibrary-Hash'] = hash_val
            return resp

        # Prepare response payload
        resp_data = prepare_library_payload(library_data, basic=want_fields == 'basic')
        is_offline = library_data.get("offline_mode", False)

        if requested_sections:
            resp_data['partial'] = True
            resp_data['sections'] = library_data.get('sections', requested_sections)
            resp_data['cached_sections'] = library_data.get('cached', {})
            cached_flags = library_data.get('cached', {})
            is_cached = all(cached_flags.get(sec, False) for sec in requested_sections)
        else:
            is_cached = library_data.get("cached", False)
        
        # Determine response message
        if is_offline:
            message = "ok (offline cache)"
        elif requested_sections and not is_cached:
            message = t_api("ok_partial", request)
        elif is_cached:
            message = "ok (cached)"
        else:
            message = "ok (fresh)"

        resp = api_response(True, data=resp_data, message=message)
        resp.headers['X-MusicLibrary-Hash'] = hash_val
        resp.headers['ETag'] = hash_val
        
        if want_fields == 'basic':
            resp.headers['X-Data-Fields'] = 'basic'
            
        return resp
        
    except Exception as e:
        logging.exception("Error loading music library")
        
        # Try offline fallback through unified cache
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

    raw_sections = request.args.get('sections', 'playlists')
    sections = [s.strip() for s in raw_sections.split(',') if s.strip()]
    force = request.args.get('refresh') in ('1', 'true', 'yes')
    
    try:
        # Import section loaders
        from .api.spotify import get_playlists, get_saved_albums, get_user_saved_tracks, get_followed_artists
        
        section_loaders = {
            'playlists': get_playlists,
            'albums': get_saved_albums,
            'tracks': get_user_saved_tracks,
            'artists': get_followed_artists
        }
        
        # Use unified cache for sections
        partial = cache_migration.get_library_sections_cached(
            token=token, 
            sections=sections, 
            section_loaders=section_loaders, 
            force_refresh=force
        )
        
        # Compute hash for ETag
        import hashlib
        def _compute_hash(data_dict):
            try:
                parts = []
                for coll in ("playlists","albums","tracks","artists"):
                    for item in data_dict.get(coll, []) or []:
                        parts.append(item.get("uri", ""))
                raw = "|".join(sorted(parts))
                return hashlib.md5(raw.encode("utf-8")).hexdigest() if raw else "0"*32
            except Exception:
                return "0"*32
        
        hash_val = _compute_hash(partial)
        partial['hash'] = hash_val
        
        # Check for conditional request
        if_modified = request.headers.get('If-None-Match')
        if if_modified and if_modified == hash_val:
            resp = Response(status=304)
            resp.headers['ETag'] = hash_val
            resp.headers['X-MusicLibrary-Hash'] = hash_val
            return resp

        # Optional slimming for basic fields
        want_fields = request.args.get('fields')
        if want_fields == 'basic':
            def _slim(items):
                allowed = {"uri","name","image_url","track_count","type","artist"}
                return [{k: it.get(k) for k in allowed if k in it} for it in (items or [])]
            
            for coll in ('playlists','albums','tracks','artists'):
                partial[coll] = _slim(partial.get(coll, []))
        
        resp = api_response(True, data=partial, message=t_api("ok_partial", request))
        resp.headers['X-MusicLibrary-Hash'] = hash_val
        resp.headers['ETag'] = hash_val
        
        if want_fields == 'basic':
            resp.headers['X-Data-Fields'] = 'basic'
            
        return resp
        
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
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        combined = get_combined_playback(token)
        if combined:
            return api_response(True, data=combined, message=t_api("ok", request))
        return api_response(False, message=t_api("no_active_playback", request), status=200, error_code="no_playback")
    except Exception as e:
        logging.exception("Error getting playback status")
        return api_response(False, message=str(e), status=503, error_code="playback_status_error")

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
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")

    result = toggle_playback_fast(token)

    if isinstance(result, dict):
        success = result.get("success", True)
        if success:
            return api_response(True, data=result, message=t_api("ok", request))

        error_message = result.get("error") or "Playback toggle failed"
        return api_response(False, data=result, message=error_message, status=503, error_code="playback_toggle_failed")

    # Fallback for unexpected return shapes
    return api_response(True, data={"result": result}, message=t_api("ok", request))

@app.route("/volume", methods=["POST"])
@api_error_handler
def volume_endpoint():
    """Volume endpoint - only sets Spotify volume (no config save)"""
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        # Validate volume input
        volume = validate_volume_only(request.form)
        
        # Set Spotify volume
        device_id = request.form.get('device_id') or None

        spotify_success = set_volume(token, volume, device_id)
        
        if spotify_success:
            return api_response(True, data={"volume": volume}, message=f"Volume set to {volume}")
        else:
            return api_response(False, message=t_api("volume_set_failed", request), status=500, 
                              error_code="volume_set_failed")
            
    except ValidationError as e:
        logging.warning(f"Volume validation error: {e.field_name} - {e.message}")
        return api_response(False, message=f"Invalid {e.field_name}: {e.message}", 
                          status=400, error_code=e.field_name)

# =====================================
# 😴 API Routes - Sleep Timer
# =====================================

@app.route("/sleep_status")
@api_error_handler
@rate_limit("status_check")
def sleep_status_api():
    """Get sleep timer status - supports both basic and advanced modes"""
    advanced_mode = request.args.get('advanced', 'false').lower() == 'true'
    
    if advanced_mode:
        # Advanced status via service layer
        try:
            sleep_service = get_service("sleep")
            result = sleep_service.get_sleep_status()
            
            if result.success:
                return api_response(True, data={
                    "timestamp": result.timestamp.isoformat(), 
                    "sleep": result.data,
                    "mode": "advanced"
                })
            else:
                return api_response(False, message=result.message, status=500, 
                                  error_code=result.error_code or "sleep_status_error")
        except Exception as e:
            logger.error(f"Error getting advanced sleep status: {e}")
            return api_response(False, message=str(e), status=500, 
                              error_code="sleep_status_exception")
    else:
        # Basic status (legacy format)
        return api_response(True, data=get_sleep_status())

@app.route("/sleep", methods=["POST"])
@api_error_handler
@rate_limit("config_changes")
def start_sleep():
    """Start sleep timer with comprehensive input validation"""
    try:
        # Validate all sleep timer inputs
        validated_data = validate_sleep_config(request.form)
        
        # Start sleep timer with validated data
        success = start_sleep_timer(**validated_data)
        
        # Return JSON for AJAX requests, redirect for form submissions
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
        if request.is_json or is_ajax:
            if success:
                return api_response(True, message=f"Sleep timer started for {validated_data['duration_minutes']} minutes")
            else:
                return api_response(False, message=t_api("failed_start_sleep", request), status=500, error_code="sleep_start_failed")
        else:
            # Traditional form submission
            if success:
                session['success_message'] = f"Sleep timer started for {validated_data['duration_minutes']} minutes"
                return redirect(url_for('index'))
            else:
                session['error_message'] = "Failed to start sleep timer"
                return redirect(url_for('index'))
                
    except ValidationError as e:
        error_msg = f"Invalid {e.field_name}: {e.message}"
        logging.warning(f"Sleep timer validation error: {e.field_name} - {e.message}")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
        if request.is_json or is_ajax:
            return api_response(False, message=error_msg, status=400, error_code=e.field_name)
        else:
            session['error_message'] = error_msg
            return redirect(url_for('index'))
    except Exception as e:
        error_msg = f"Error starting sleep timer: {str(e)}"
        logging.exception("Error starting sleep timer")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
        if request.is_json or is_ajax:
            return api_response(False, message=error_msg, status=500, error_code="sleep_start_error")
        else:
            session['error_message'] = error_msg
            return redirect(url_for('index'))

@app.route("/stop_sleep", methods=["POST"])
@api_error_handler
@rate_limit("api_general")
def stop_sleep():
    """Stop active sleep timer"""
    success = stop_sleep_timer()
    
    # Return JSON for AJAX requests, redirect for form submissions
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
    if request.is_json or is_ajax:
        return api_response(success, message=t_api("sleep_stopped", request) if success else "Failed to stop sleep timer", status=200 if success else 500, error_code=None if success else "sleep_stop_failed")
    else:
        if success:
            session['success_message'] = "Sleep timer stopped"
        else:
            session['error_message'] = "Failed to stop sleep timer"
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
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        # Support both JSON and form data for backward compatibility
        if request.is_json:
            # JSON format (legacy /start_playback)
            data = request.get_json()
            context_uri = data.get("context_uri")
            device_id = data.get("device_id")
            
            if not context_uri:
                return api_response(False, message=t_api("missing_context_uri", request), status=400, error_code="missing_context_uri")
            
            # Direct device_id usage
            success = start_playback(token, device_id, context_uri)
            
        else:
            # Form format (legacy /play)
            device_name = request.form.get('device_name')
            context_uri = request.form.get('uri')
            
            if not context_uri:
                return api_response(False, message=t_api("missing_uri", request), status=400, error_code="missing_uri")
            
            if not device_name:
                return api_response(False, message=t_api("missing_device", request), status=400, error_code="missing_device")
            
            # Get devices to find device_id from device_name
            devices = get_devices(token)
            if not devices:
                return api_response(False, message=t_api("no_devices", request), status=404, error_code="no_devices")
            
            # Find device by name
            target_device = None
            for device in devices:
                if device['name'] == device_name:
                    target_device = device
                    break
            
            if not target_device:
                return api_response(False, message=t_api("device_not_found", request, name=device_name), status=404, error_code="device_not_found")
            
            # Start playback with found device_id
            success = start_playback(token, target_device['id'], context_uri)
        
        if success:
            return api_response(True, message=t_api("playback_started", request))
        else:
            return api_response(False, message=t_api("failed_start_playback", request), status=500, error_code="playback_start_failed")
            
    except Exception as e:
        logging.exception("Error in play endpoint")
        return api_response(False, message=str(e), status=500, error_code="play_endpoint_error")

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
                         weekdays_display="",
                         next_alarm_info="",
                         sleep_status={}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors by rendering a minimal error page"""
    return render_template('index.html', 
                         error_message=t_api("internal_server_error_page"),
                         config={},
                         devices=[],
                         playlists=[],
                         weekdays_display="",
                         next_alarm_info="",
                         sleep_status={}), 500

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
        stats = rate_limiter.get_statistics()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "rate_limiting": {
                "enabled": True,
                "statistics": stats,
                "rules": rate_limiter.get_rules_summary()
            }
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
    try:
        result = execute_alarm()
        return api_response(bool(result), data={"executed": bool(result)}, message="Alarm executed" if result else "Alarm conditions not met or failed", status=200 if result else 400, error_code=None if result else "alarm_not_executed")
    except Exception as e:
        logger.error(f"Error executing alarm manually: {e}")
        return api_response(False, message=str(e), status=500, error_code="alarm_execute_error")

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
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    devices = get_devices(token)
    return api_response(True, data={"devices": devices if devices else []})

@app.route("/api/devices/refresh")
@api_error_handler
def api_devices_refresh():
    """Fast device refresh endpoint - bypasses cache for immediate updates."""
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        # Load devices directly from Spotify API (bypass cache)
        import requests
        r = _spotify_request(
            'GET',
            "https://api.spotify.com/v1/me/player/devices",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5  # Reduced timeout for fast response
        )
        
        if r.status_code == 200:
            devices = r.json().get("devices", [])
            logging.info(f"🔄 Fast device refresh: {len(devices)} devices found")
            return api_response(True, data={"devices": devices, "timestamp": time.time()})
        else:
            logging.warning(f"⚠️ Device refresh failed: {r.status_code} - {r.text}")
            return api_response(False, message="Device refresh failed", status=503, error_code="device_refresh_failed")
            
    except Exception as e:
        logging.error(f"❌ Error in device refresh: {e}")
        return api_response(False, message=str(e), status=503, error_code="device_refresh_error")

# =====================================
# 🚀 Application Runner
# =====================================

def run_app(host="0.0.0.0", port=5001, debug=False):
    """Run the Flask app with event-driven alarm scheduler."""
    start_event_alarm_scheduler()
    app.run(host=host, port=port, debug=debug, threaded=True)

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
