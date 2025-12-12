"""
🗑️ Cache Management Routes Blueprint
Handles cache status, invalidation, and management endpoints.
"""

import datetime
import logging

from flask import Blueprint

from ..utils.cache_migration import get_cache_migration_layer
from ..utils.rate_limiting import rate_limit
from .helpers import api_response

cache_bp = Blueprint("cache", __name__)
logger = logging.getLogger(__name__)


@cache_bp.route("/api/cache/status")
@rate_limit("status_check")
def get_cache_status():
    """📊 Get unified cache performance and statistics."""
    try:
        cache_migration = get_cache_migration_layer()
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


@cache_bp.route("/api/cache/invalidate", methods=["POST"])
@rate_limit("config_changes")
def invalidate_cache():
    """🗑️ Invalidate all cache data."""
    try:
        cache_migration = get_cache_migration_layer()
        count = cache_migration.invalidate_all_cache()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "invalidated_entries": count
        }, message=f"Successfully invalidated {count} cache entries")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return api_response(False, message=str(e), status=500, error_code="cache_invalidate_error")


@cache_bp.route("/api/cache/invalidate/music-library", methods=["POST"])
@rate_limit("config_changes") 
def invalidate_music_library_cache():
    """🎵 Invalidate only music library cache data."""
    try:
        cache_migration = get_cache_migration_layer()
        count = cache_migration.invalidate_music_library()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "invalidated_entries": count
        }, message=f"Successfully invalidated {count} music library cache entries")
    except Exception as e:
        logger.error(f"Error invalidating music library cache: {e}")
        return api_response(False, message=str(e), status=500, error_code="music_cache_invalidate_error")


@cache_bp.route("/api/cache/invalidate/devices", methods=["POST"])
@rate_limit("config_changes")
def invalidate_device_cache():
    """📱 Invalidate only device cache data."""
    try:
        cache_migration = get_cache_migration_layer()
        count = cache_migration.invalidate_devices()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "invalidated_entries": count
        }, message=f"Successfully invalidated {count} device cache entries")
    except Exception as e:
        logger.error(f"Error invalidating device cache: {e}")
        return api_response(False, message=str(e), status=500, error_code="device_cache_invalidate_error")
