"""
🏗️ Services Routes Blueprint
Handles service layer health, performance, and diagnostics endpoints.
"""

import datetime
import logging

from flask import Blueprint

from ..services.service_manager import get_service_manager
from ..utils.perf_monitor import perf_monitor
from ..utils.rate_limiting import get_rate_limiter, rate_limit
from .helpers import api_response, _iso_timestamp_now

services_bp = Blueprint("services", __name__)
logger = logging.getLogger(__name__)


@services_bp.route("/api/services/health")
@rate_limit("status_check")
def api_services_health():
    """📊 Get health status of all services."""
    try:
        service_manager = get_service_manager()
        result = service_manager.health_check_all()
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "health": result.data})
        else:
            return api_response(False, message=result.message or "Health check failed", status=500, error_code=result.error_code or "services_health_error")
            
    except Exception as e:
        logger.error(f"Error in services health check: {e}")
        return api_response(False, message=str(e), status=500, error_code="services_health_exception")


@services_bp.route("/api/services/performance")
@rate_limit("status_check")
def api_services_performance():
    """📈 Get performance overview of all services."""
    try:
        service_manager = get_service_manager()
        result = service_manager.get_performance_overview()
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "performance": result.data})
        else:
            return api_response(False, message=result.message or "Performance check failed", status=500, error_code=result.error_code or "services_performance_error")
            
    except Exception as e:
        logger.error(f"Error getting performance overview: {e}")
        return api_response(False, message=str(e), status=500, error_code="services_performance_exception")


@services_bp.route("/api/services/diagnostics")
@rate_limit("status_check")
def api_services_diagnostics():
    """🔧 Run comprehensive system diagnostics."""
    try:
        service_manager = get_service_manager()
        result = service_manager.run_diagnostics()
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "diagnostics": result.data})
        else:
            return api_response(False, message=result.message or "Diagnostics failed", status=500, error_code=result.error_code or "services_diagnostics_error")
            
    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        return api_response(False, message=str(e), status=500, error_code="services_diagnostics_exception")


@services_bp.route("/api/perf/metrics")
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


@services_bp.route("/api/rate-limiting/status")
@rate_limit("status_check") 
def get_rate_limiting_status():
    """📊 Get rate limiting status and statistics."""
    try:
        rate_limiter = get_rate_limiter()
        stats = rate_limiter.get_stats()
        return api_response(True, data={
            "timestamp": datetime.datetime.now().isoformat(),
            "rate_limiting": stats
        })
    except Exception as e:
        logger.error(f"Error getting rate limiting status: {e}")
        return api_response(False, message=str(e), status=500, error_code="rate_limit_status_error")


@services_bp.route("/api/rate-limiting/reset", methods=["POST"])
@rate_limit("config_changes")
def reset_rate_limiting():
    """🔄 Reset rate limiting statistics and storage."""
    try:
        rate_limiter = get_rate_limiter()
        rate_limiter.reset()
        return api_response(True, data={"timestamp": datetime.datetime.now().isoformat()}, message="Rate limiting data reset successfully")
    except Exception as e:
        logger.error(f"Error resetting rate limiting: {e}")
        return api_response(False, message=str(e), status=500, error_code="rate_limit_reset_error")
