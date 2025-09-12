"""
SpotiPi Main Application
Flask web application with new modular structure
"""

import os
import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import logging
import threading
import time

# Import from new structure - use relative imports since we're in src/
from .config import load_config, save_config
from .core.alarm import execute_alarm
from .core.scheduler import WeekdayScheduler, AlarmTimeValidator
from .utils.logger import setup_logger, setup_logging
from .utils.validation import validate_alarm_config, validate_sleep_config, validate_volume_only, ValidationError
from .version import get_app_info, VERSION
from .utils.translations import get_translations, get_user_language
from .api.spotify import (
    get_access_token, get_devices, get_playlists, get_user_library,
    start_playback, stop_playback, resume_playback, toggle_playback,
    set_volume, get_current_track, get_current_spotify_volume,
    get_playback_status
)
from .utils.token_cache import get_token_cache_info, log_token_cache_performance
from .utils.thread_safety import get_config_stats, invalidate_config_cache
from .utils.rate_limiting import rate_limit, get_rate_limiter, add_rate_limit_headers
from .services.service_manager import get_service_manager, get_service
from .core.sleep import (
    start_sleep_timer, stop_sleep_timer, get_sleep_status,
    save_sleep_settings
)

# Initialize Flask app with correct paths
project_root = Path(__file__).parent.parent  # Go up from src/ to project root
template_dir = project_root / "templates"
static_dir = project_root / "static"

app = Flask(__name__, 
           template_folder=str(template_dir), 
           static_folder=str(static_dir))

# Secure secret key generation
import secrets
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Setup logging
setup_logging()
logger = setup_logger("spotipi")

# Initialize rate limiter with default rules
rate_limiter = get_rate_limiter()

# Initialize service manager
service_manager = get_service_manager()

@app.after_request
def after_request(response):
    """Add CORS headers to all responses with environment-aware policy"""
    # Allow broad CORS in development; restrict via env in production
    allowed_origins = os.getenv('SPOTIPI_CORS_ORIGINS')
    if allowed_origins:
        origin = request.headers.get('Origin', '')
        allowed = [o.strip() for o in allowed_origins.split(',') if o.strip()]
        if origin in allowed:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
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
                return jsonify({
                    "success": False,
                    "error": str(e),
                    "message": "An internal error occurred"
                }), 500
            else:
                # For HTML requests, redirect to main page with error
                session['error_message'] = str(e)
                return redirect(url_for('index'))
    return wrapper

# =====================================
# 🕐 Background Alarm Scheduler
# =====================================

def alarm_scheduler():
    """Background thread to check alarms every minute"""
    logger = setup_logger('alarm_scheduler')
    logger.info("⏰ Alarm scheduler thread started")
    
    while True:
        try:
            current_time = time.strftime('%H:%M')
            logger.debug(f"⏰ Checking alarm at {current_time}")
            
            config = load_config()
            if config.get("enabled", False):
                logger.debug(f"✅ Alarm enabled, checking time...")
                execute_alarm()
            else:
                logger.debug("❌ Alarm disabled, skipping check")
                
        except Exception as e:
            logger.error(f"Error in alarm scheduler: {e}")
        
        time.sleep(60)

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
        't': template_t,  # Translation function with parameter support
        'lang': user_language,  # Add language variable
        'weekday_scheduler': WeekdayScheduler,
        'static_css_path': '/static/css/',
        'static_js_path': '/static/js/',
        'static_icons_path': '/static/icons/',
        'now': datetime.datetime.now()  # Add current time for templates
    }

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

# =====================================
# 🔧 API Routes - Alarm Management
# =====================================

@app.route("/save_alarm", methods=["POST"])
@api_error_handler
@rate_limit("config_changes")
def save_alarm():
    """Save alarm settings with comprehensive input validation"""
    try:
        # Validate all alarm inputs using centralized validation
        validated_data = validate_alarm_config(request.form)
        
        # Load current config and update with validated data
        config = load_config()
        config.update(validated_data)
        
        # Additional business logic validation
        if config["time"] and not AlarmTimeValidator.validate_time_format(config["time"]):
            return jsonify({
                "success": False,
                "message": "Invalid time format. Please use HH:MM format."
            }), 400
        
        # Save configuration
        success = save_config(config)
        if not success:
            return jsonify({
                "success": False,
                "message": "Failed to save configuration"
            }), 500
        
        # Log the changes
        weekdays_info = f", Weekdays={WeekdayScheduler.format_weekdays_display(config['weekdays'])}" if config.get('weekdays') else " (daily)"
        logging.info(f"Alarm settings saved: Active={config['enabled']}, Time={config['time']}, Volume={config['alarm_volume']}%{weekdays_info}")
        
        return jsonify({
            "success": True,
            "message": "Alarm settings saved successfully",
            "config": {
                "enabled": config["enabled"],
                "time": config["time"],
                "alarm_volume": config["alarm_volume"],
                "weekdays": config["weekdays"],
                "weekdays_display": WeekdayScheduler.format_weekdays_display(config["weekdays"])
            }
        })
        
    except ValidationError as e:
        logging.warning(f"Alarm validation error: {e.field_name} - {e.message}")
        return jsonify({
            "success": False,
            "message": f"Invalid {e.field_name}: {e.message}",
            "field": e.field_name
        }), 400
    except Exception as e:
        logging.exception("Error saving alarm configuration")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500

@app.route("/alarm_status")
@api_error_handler
@rate_limit("status_check")
def alarm_status():
    """Get current alarm status with weekday information"""
    config = load_config()
    
    next_alarm_time = ""
    if config.get("enabled") and config.get("time"):
        next_alarm_time = AlarmTimeValidator.format_time_until_alarm(
            config["time"], 
            config.get("weekdays", [])
        )
    
    return jsonify({
        "enabled": config.get("enabled", False),
        "time": config.get("time", "07:00"),
        "alarm_volume": config.get("alarm_volume", 50),
        "weekdays": config.get("weekdays", []),
        "weekdays_display": WeekdayScheduler.format_weekdays_display(config.get("weekdays", [])),
        "next_alarm": next_alarm_time,
        "playlist_uri": config.get("playlist_uri", ""),
        "device_name": config.get("device_name", "")
    })

# =====================================
# 🎵 API Routes - Music & Playback
# =====================================

@app.route("/api/music-library")
@api_error_handler
@rate_limit("spotify_api")
def api_music_library():
    """API endpoint for music library data"""
    # Simple in-memory TTL cache to reduce load
    if not hasattr(api_music_library, '_cache'):
        api_music_library._cache = { 'data': None, 'ts': 0 }
    cache_ttl = int(os.getenv('SPOTIPI_MUSIC_CACHE_TTL', '600'))
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')

    token = get_access_token()
    if not token:
        return jsonify({
            "error": "401",
            "message": "Spotify authentication required"
        }), 401
    
    try:
        # Serve from in-memory cache when fresh
        now = time.time()
        if not force_refresh and api_music_library._cache['data'] and (now - api_music_library._cache['ts'] < cache_ttl):
            cached = api_music_library._cache['data']
            return jsonify({
                "success": True,
                "cached": True,
                "total": cached.get("total", 0),
                "playlists": cached.get("playlists", []),
                "albums": cached.get("albums", []),
                "tracks": cached.get("tracks", []),
                "artists": cached.get("artists", [])
            })

        # Get comprehensive music library
        library_data = get_user_library(token)
        api_music_library._cache = { 'data': library_data, 'ts': now }

        # Persist a lightweight cache to serve when Spotify is unreachable
        try:
            from .utils.simple_cache import write_json_cache
            cache_path = str(project_root / "logs" / "music_library_cache.json")
            write_json_cache(cache_path, library_data)
        except Exception as cache_err:
            logging.debug(f"Could not write music library cache: {cache_err}")

        return jsonify({
            "success": True,
            "total": library_data.get("total", 0),
            "playlists": library_data.get("playlists", []),
            "albums": library_data.get("albums", []),
            "tracks": library_data.get("tracks", []),
            "artists": library_data.get("artists", [])
        })
        
    except Exception as e:
        logging.exception("Error loading music library")
        # Try to serve last known good cache as a graceful fallback
        if api_music_library._cache['data']:
            cached = api_music_library._cache['data']
            return jsonify({
                "success": True,
                "cached": True,
                "total": cached.get("total", 0),
                "playlists": cached.get("playlists", []),
                "albums": cached.get("albums", []),
                "tracks": cached.get("tracks", []),
                "artists": cached.get("artists", []),
                "message": "Served in-memory cached library due to Spotify connectivity issue"
            })

        try:
            from .utils.simple_cache import read_json_cache
            cache_path = str(project_root / "logs" / "music_library_cache.json")
            cached = read_json_cache(cache_path)
            if cached:
                return jsonify({
                    "success": True,
                    "cached": True,
                    "total": cached.get("total", 0),
                    "playlists": cached.get("playlists", []),
                    "albums": cached.get("albums", []),
                    "tracks": cached.get("tracks", []),
                    "artists": cached.get("artists", []),
                    "message": "Served cached music library due to Spotify connectivity issue"
                })
        except Exception as cache_err:
            logging.debug(f"Could not read music library cache: {cache_err}")

        return jsonify({
            "error": "503",
            "message": "Spotify unavailable: failed to load music library"
        }), 503

@app.route("/api/artist-top-tracks/<artist_id>")
@api_error_handler
@rate_limit("spotify_api")
def api_artist_top_tracks(artist_id):
    """API endpoint for artist top tracks"""
    token = get_access_token()
    if not token:
        return jsonify({
            "error": "401",
            "message": "Spotify authentication required"
        }), 401
    
    try:
        from .api.spotify import get_artist_top_tracks
        tracks = get_artist_top_tracks(token, artist_id)
        
        return jsonify({
            "success": True,
            "artist_id": artist_id,
            "tracks": tracks,
            "total": len(tracks)
        })
        
    except Exception as e:
        logging.exception("Error loading artist top tracks")
        return jsonify({
            "error": "500",
            "message": f"Failed to load artist top tracks: {str(e)}"
        }), 500

@app.route("/api/token-cache/status")
@rate_limit("status_check")
def get_token_cache_status():
    """📊 Get token cache performance and status information."""
    try:
        cache_info = get_token_cache_info()
        return jsonify({
            "success": True,
            "cache_info": cache_info
        })
    except Exception as e:
        logging.error(f"❌ Error getting token cache status: {e}")
        return jsonify({
            "success": False,
            "message": f"Error getting cache status: {str(e)}"
        }), 500

@app.route("/api/thread-safety/status")
@rate_limit("status_check")
def get_thread_safety_status():
    """📊 Get thread safety status and statistics."""
    try:
        stats = get_config_stats()
        return jsonify({
            "success": True,
            "thread_safety_stats": stats
        })
    except Exception as e:
        logging.error(f"❌ Error getting thread safety status: {e}")
        return jsonify({
            "success": False,
            "message": f"Error getting thread safety status: {str(e)}"
        }), 500

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
        return jsonify({"error": "401", "message": "Authentication required"})
    
    try:
        status = get_playback_status(token)
        if status:
            # Add current track information to playback status
            current_track = get_current_track(token)
            status['current_track'] = current_track
            return jsonify(status)
        else:
            return jsonify({"error": "No active playback"})
    except Exception as e:
        logging.exception("Error getting playback status")
        # Return a proper service-unavailable status so the UI can degrade gracefully
        return jsonify({"error": "503", "message": str(e)}), 503

@app.route("/api/spotify/health")
@rate_limit("status_check")
def api_spotify_health():
    """Quick health check for Spotify connectivity (DNS, TLS reachability)."""
    try:
        from .api.spotify import spotify_network_health
        health = spotify_network_health()
        http_code = 200 if health.get("ok") else 503
        return jsonify(health), http_code
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
    """Toggle Spotify play/pause"""
    token = get_access_token()
    if not token:
        return jsonify({"error": "401"}), 401
    
    result = toggle_playback(token)
    return jsonify(result)

@app.route("/volume", methods=["POST"])
@api_error_handler
def set_volume_endpoint():
    """Set Spotify volume with input validation"""
    token = get_access_token()
    if not token:
        return jsonify({"error": "401"}), 401
    
    try:
        # Validate volume input
        volume = validate_volume_only(request.form)
        
        success = set_volume(token, volume)
        if success:
            return jsonify({"success": True, "volume": volume})
        else:
            return jsonify({"error": "Failed to set volume"}), 500
            
    except ValidationError as e:
        logging.warning(f"Volume validation error: {e.field_name} - {e.message}")
        return jsonify({
            "error": f"Invalid {e.field_name}: {e.message}",
            "field": e.field_name
        }), 400

# =====================================
# 😴 API Routes - Sleep Timer
# =====================================

@app.route("/sleep_status")
@api_error_handler
@rate_limit("status_check")
def sleep_status_api():
    """Get current sleep timer status"""
    return jsonify(get_sleep_status())

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
                return jsonify({
                    "success": True,
                    "message": f"Sleep timer started for {validated_data['duration_minutes']} minutes"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Failed to start sleep timer"
                })
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
            return jsonify({
                "success": False, 
                "message": error_msg,
                "field": e.field_name
            }), 400
        else:
            session['error_message'] = error_msg
            return redirect(url_for('index'))
    except Exception as e:
        error_msg = f"Error starting sleep timer: {str(e)}"
        logging.exception("Error starting sleep timer")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept', '').find('application/json') != -1
        if request.is_json or is_ajax:
            return jsonify({"success": False, "message": error_msg}), 500
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
        return jsonify({
            "success": success,
            "message": "Sleep timer stopped" if success else "Failed to stop sleep timer"
        })
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

@app.route("/start_playback", methods=["POST"])
@api_error_handler
def start_playback_endpoint():
    """Start playback for music library"""
    token = get_access_token()
    if not token:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        data = request.get_json()
        context_uri = data.get("context_uri")
        device_id = data.get("device_id")
        
        if not context_uri:
            return jsonify({"error": "Missing context_uri"}), 400
        
        success = start_playback(token, device_id, context_uri)
        
        if success:
            return jsonify({"success": True, "message": "Playback started"})
        else:
            return jsonify({"error": "Failed to start playback"}), 500
            
    except Exception as e:
        logging.exception("Error starting playback")
        return jsonify({"error": str(e)}), 500

@app.route("/play", methods=["POST"])
@api_error_handler
def play_endpoint():
    """Play music on specified device - simplified endpoint for frontend"""
    token = get_access_token()
    if not token:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        # Handle form-encoded data (from frontend)
        device_name = request.form.get('device_name')
        uri = request.form.get('uri')
        
        if not uri:
            return jsonify({"error": "Missing URI"}), 400
        
        if not device_name:
            return jsonify({"error": "Missing device name"}), 400
        
        # Get devices to find device_id from device_name
        devices = get_devices(token)
        if not devices:
            return jsonify({"error": "No devices available"}), 404
        
        # Find device by name
        target_device = None
        for device in devices:
            if device['name'] == device_name:
                target_device = device
                break
        
        if not target_device:
            return jsonify({"error": f"Device '{device_name}' not found"}), 404
        
        # Start playback
        success = start_playback(token, target_device['id'], uri)
        
        if success:
            return jsonify({"success": True, "message": "Playback started"})
        else:
            return jsonify({"error": "Failed to start playback"}), 500
            
    except Exception as e:
        logging.exception("Error in play endpoint")
        return jsonify({"error": str(e)}), 500

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

@app.route("/save_volume", methods=["POST"])
@api_error_handler
@rate_limit("api_general")
def save_volume():
    """Save volume setting to configuration with input validation"""
    try:
        # Validate volume input
        volume = validate_volume_only(request.form)
        
        config = load_config()
        config["volume"] = volume
        
        success = save_config(config)
        return jsonify({"success": success, "volume": volume})
        
    except ValidationError as e:
        logging.warning(f"Save volume validation error: {e.field_name} - {e.message}")
        return jsonify({
            "error": f"Invalid {e.field_name}: {e.message}",
            "field": e.field_name
        }), 400

# =====================================
# 🚨 Error Handlers
# =====================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors by rendering a minimal error page"""
    return render_template('index.html', 
                         error_message="Page not found",
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
                         error_message="Internal server error",
                         config={},
                         devices=[],
                         playlists=[],
                         weekdays_display="",
                         next_alarm_info="",
                         sleep_status={}), 500

# =====================================
# 🚀 Application Startup
# =====================================

def start_alarm_scheduler():
    """Start the background alarm scheduler thread."""
    # Ensure single-flight startup
    if getattr(start_alarm_scheduler, '_started', False):
        return
    print("🚨 Starting alarm scheduler thread...")
    alarm_thread = threading.Thread(target=alarm_scheduler, daemon=True)
    alarm_thread.start()
    start_alarm_scheduler._started = True
    print("⏰ Background alarm scheduler started")

# =====================================
# 🚨 Rate Limiting Management API
# =====================================

@app.route("/api/rate-limiting/status")
@rate_limit("status_check") 
def get_rate_limiting_status():
    """📊 Get rate limiting status and statistics."""
    try:
        stats = rate_limiter.get_statistics()
        return jsonify({
            "success": True,
            "timestamp": datetime.datetime.now().isoformat(),
            "rate_limiting": {
                "enabled": True,
                "statistics": stats,
                "rules": rate_limiter.get_rules_summary()
            }
        })
    except Exception as e:
        logger.error(f"Error getting rate limiting status: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get rate limiting status",
            "message": str(e)
        }), 500

@app.route("/api/rate-limiting/reset", methods=["POST"])
@rate_limit("config_changes")
def reset_rate_limiting():
    """🔄 Reset rate limiting statistics and storage."""
    try:
        # Clear all rate limiting data
        rate_limiter._storage.clear()
        
        return jsonify({
            "success": True,
            "message": "Rate limiting data reset successfully",
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error resetting rate limiting: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to reset rate limiting",
            "message": str(e)
        }), 500

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
            return jsonify({
                "success": True,
                "timestamp": result.timestamp.isoformat(),
                "health": result.data
            })
        else:
            return jsonify({
                "success": False,
                "error": result.message,
                "error_code": result.error_code
            }), 500
            
    except Exception as e:
        logger.error(f"Error in services health check: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to check services health",
            "message": str(e)
        }), 500

@app.route("/api/services/performance")
@rate_limit("status_check")
def api_services_performance():
    """📈 Get performance overview of all services."""
    try:
        result = service_manager.get_performance_overview()
        if result.success:
            return jsonify({
                "success": True,
                "timestamp": result.timestamp.isoformat(),
                "performance": result.data
            })
        else:
            return jsonify({
                "success": False,
                "error": result.message,
                "error_code": result.error_code
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting performance overview: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get performance overview",
            "message": str(e)
        }), 500

@app.route("/api/services/diagnostics")
@rate_limit("status_check")
def api_services_diagnostics():
    """🔧 Run comprehensive system diagnostics."""
    try:
        result = service_manager.run_diagnostics()
        if result.success:
            return jsonify({
                "success": True,
                "timestamp": result.timestamp.isoformat(),
                "diagnostics": result.data
            })
        else:
            return jsonify({
                "success": False,
                "error": result.message,
                "error_code": result.error_code
            }), 500
            
    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to run diagnostics",
            "message": str(e)
        }), 500

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
        return jsonify({
            "success": bool(result),
            "executed": bool(result),
            "message": "Alarm executed" if result else "Alarm conditions not met or failed"
        }), 200 if result else 400
    except Exception as e:
        logger.error(f"Error executing alarm manually: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to execute alarm",
            "message": str(e)
        }), 500

@app.route("/api/alarm/advanced-status")
@rate_limit("status_check")
def api_alarm_advanced_status():
    """⏰ Get advanced alarm status via service layer."""
    try:
        alarm_service = get_service("alarm")
        result = alarm_service.get_alarm_status()
        
        if result.success:
            return jsonify({
                "success": True,
                "timestamp": result.timestamp.isoformat(),
                "alarm": result.data
            })
        else:
            return jsonify({
                "success": False,
                "error": result.message,
                "error_code": result.error_code
            }), 400
            
    except Exception as e:
        logger.error(f"Error getting advanced alarm status: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get alarm status",
            "message": str(e)
        }), 500

@app.route("/api/spotify/auth-status")
@rate_limit("spotify_api")
def api_spotify_auth_status():
    """🎵 Get Spotify authentication status via service layer."""
    try:
        spotify_service = get_service("spotify")
        result = spotify_service.get_authentication_status()
        
        if result.success:
            return jsonify({
                "success": True,
                "timestamp": result.timestamp.isoformat(),
                "spotify": result.data
            })
        else:
            return jsonify({
                "success": False,
                "error": result.message,
                "error_code": result.error_code
            }), 401 if result.error_code == "AUTH_REQUIRED" else 500
            
    except Exception as e:
        logger.error(f"Error getting Spotify auth status: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get Spotify status",
            "message": str(e)
        }), 500

@app.route("/api/sleep/advanced-status")
@rate_limit("status_check")
def api_sleep_advanced_status():
    """😴 Get advanced sleep status via service layer."""
    try:
        sleep_service = get_service("sleep")
        result = sleep_service.get_sleep_status()
        
        if result.success:
            return jsonify({
                "success": True,
                "timestamp": result.timestamp.isoformat(),
                "sleep": result.data
            })
        else:
            return jsonify({
                "success": False,
                "error": result.message,
                "error_code": result.error_code
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting advanced sleep status: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get sleep status",
            "message": str(e)
        }), 500

@app.route("/api/spotify/devices")
@api_error_handler
@rate_limit("spotify_api")
def api_spotify_devices():
    """API endpoint for getting available Spotify devices."""
    token = get_access_token()
    if not token:
        return jsonify({"error": "401", "message": "Authentication required"}), 401
    
    devices = get_devices(token)
    return jsonify(devices if devices else [])

# =====================================
# 🚀 Application Runner
# =====================================

def run_app(host="0.0.0.0", port=5001, debug=False):
    """Run the Flask app with alarm scheduler."""
    start_alarm_scheduler()
    app.run(host=host, port=port, debug=debug, threaded=True)

# Do not start scheduler at import time to avoid duplicate threads in WSGI

if __name__ == "__main__":
    print(f"🎵 Starting {get_app_info()}")
    print(f"📁 Project root: {project_root}")
    print(f"⚙️ Config loaded: {bool(load_config())}")
    
    # Development vs Production
    config = load_config()
    debug_mode = config.get("debug", False)
    port = int(os.getenv("PORT", 5000))
    
    # Use the run_app function that includes scheduler
    run_app(host="0.0.0.0", port=port, debug=debug_mode)
