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
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
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
    
    # Get Spotify data
    token = get_access_token()
    devices = get_devices(token) if token else []
    playlists_data = get_playlists(token) if token else []
    current_track = get_current_track(token) if token else None
    
    # Process playlists for display
    playlists = []
    if playlists_data and 'items' in playlists_data:
        for item in playlists_data['items']:
            playlist = {
                'name': item['name'],
                'uri': item['uri'],
                'image_url': item['images'][0]['url'] if item['images'] else None,
                'track_count': item['tracks']['total'],
                'artist': item['owner']['display_name']
            }
            playlists.append(playlist)
    
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
    token = get_access_token()
    if not token:
        return jsonify({
            "error": "401",
            "message": "Spotify authentication required"
        }), 401
    
    try:
        # Get comprehensive music library
        library_data = get_user_library(token)
        
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
        return jsonify({
            "error": "500",
            "message": "Failed to load music library"
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
        return jsonify({"error": "500", "message": str(e)})

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
    print("🚨 Starting alarm scheduler thread...")
    alarm_thread = threading.Thread(target=alarm_scheduler, daemon=True)
    alarm_thread.start()
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
                "rules": {
                    rule_name: {
                        "requests_per_window": rule.requests_per_window,
                        "window_seconds": rule.window_seconds,
                        "limit_type": rule.limit_type.value,
                        "block_duration": rule.block_duration_seconds
                    } for rule_name, rule in rate_limiter._rules.items()
                }
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

# =====================================
# 🚀 Application Runner
# =====================================

def run_app(host="0.0.0.0", port=5001, debug=False):
    """Run the Flask app with alarm scheduler."""
    start_alarm_scheduler()
    app.run(host=host, port=port, debug=debug, threaded=True)

# Start alarm scheduler when app is imported
start_alarm_scheduler()

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
