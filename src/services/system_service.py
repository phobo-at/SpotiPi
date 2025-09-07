"""
🔧 System Service - Business Logic for System Management
=======================================================

Handles system-wide operations including health monitoring,
performance tracking, service coordination, and maintenance tasks.
"""

import os
import psutil
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta

from . import BaseService, ServiceResult
from .alarm_service import AlarmService
from .spotify_service import SpotifyService
from .sleep_service import SleepService
from ..utils.token_cache import get_token_cache_info
from ..utils.thread_safety import get_config_stats
from ..utils.rate_limiting import get_rate_limiter

class SystemService(BaseService):
    """Service for system-wide management and monitoring."""
    
    def __init__(self):
        super().__init__("system")
        self.alarm_service = AlarmService()
        self.spotify_service = SpotifyService()
        self.sleep_service = SleepService()
        self.start_time = datetime.now()
        
        # Initialize all services
        self._initialize_services()
    
    def _initialize_services(self) -> None:
        """Initialize all sub-services."""
        services = [
            self.alarm_service,
            self.spotify_service,
            self.sleep_service
        ]
        
        for service in services:
            result = service.initialize()
            if not result.success:
                self.logger.warning(f"Failed to initialize {service.name}: {result.message}")
    
    def get_system_health(self) -> ServiceResult:
        """Get comprehensive system health status."""
        try:
            # Collect health from all services
            service_health = {}
            overall_healthy = True
            
            services = {
                "alarm": self.alarm_service,
                "spotify": self.spotify_service,
                "sleep": self.sleep_service
            }
            
            for name, service in services.items():
                health = service.health_check()
                service_health[name] = health.data if health.success else {
                    "status": "error",
                    "error": health.message
                }
                
                if not health.success or service_health[name].get("status") != "healthy":
                    overall_healthy = False
            
            # System resources
            system_stats = self._get_system_resources()
            
            # Application metrics
            app_metrics = self._get_application_metrics()
            
            health_data = {
                "overall_status": "healthy" if overall_healthy else "degraded",
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "services": service_health,
                "system": system_stats,
                "application": app_metrics
            }
            
            return self._success_result(
                data=health_data,
                message="System health check completed"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_system_health")
    
    def _get_system_resources(self) -> Dict[str, Any]:
        """Get system resource usage."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Process info
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_percent": memory.percent
                },
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "process": {
                    "memory_mb": round(process_memory.rss / (1024**2), 1),
                    "memory_percent": process.memory_percent(),
                    "cpu_percent": process.cpu_percent(),
                    "threads": process.num_threads(),
                    "pid": process.pid
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting system resources: {e}")
            return {"error": "Unable to retrieve system resources"}
    
    def _get_application_metrics(self) -> Dict[str, Any]:
        """Get application-specific metrics."""
        try:
            metrics = {}
            
            # Token cache metrics
            try:
                cache_info = get_token_cache_info()
                metrics["token_cache"] = cache_info
            except Exception as e:
                metrics["token_cache"] = {"error": str(e)}
            
            # Thread safety metrics
            try:
                config_stats = get_config_stats()
                metrics["thread_safety"] = config_stats
            except Exception as e:
                metrics["thread_safety"] = {"error": str(e)}
            
            # Rate limiting metrics
            try:
                rate_limiter = get_rate_limiter()
                rate_stats = rate_limiter.get_statistics()
                metrics["rate_limiting"] = rate_stats
            except Exception as e:
                metrics["rate_limiting"] = {"error": str(e)}
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting application metrics: {e}")
            return {"error": "Unable to retrieve application metrics"}
    
    def get_performance_summary(self) -> ServiceResult:
        """Get performance summary across all components."""
        try:
            # Token cache performance
            cache_info = get_token_cache_info()
            cache_hit_rate = cache_info.get("cache_hit_rate", 0)
            
            # Rate limiting effectiveness
            rate_limiter = get_rate_limiter()
            rate_stats = rate_limiter.get_statistics()
            block_rate = rate_stats.get("block_rate_percent", 0)
            
            # Thread safety performance
            config_stats = get_config_stats()
            concurrent_success_rate = config_stats.get("success_rate", 0)
            
            # System resource efficiency
            system_stats = self._get_system_resources()
            memory_usage = system_stats.get("process", {}).get("memory_mb", 0)
            cpu_usage = system_stats.get("process", {}).get("cpu_percent", 0)
            
            performance_data = {
                "efficiency_scores": {
                    "token_cache_hit_rate": cache_hit_rate,
                    "thread_safety_success_rate": concurrent_success_rate,
                    "rate_limiting_block_rate": block_rate
                },
                "resource_usage": {
                    "memory_mb": memory_usage,
                    "cpu_percent": cpu_usage,
                    "efficiency_rating": self._calculate_efficiency_rating(memory_usage, cpu_usage)
                },
                "overall_performance": {
                    "score": self._calculate_performance_score(
                        cache_hit_rate, concurrent_success_rate, block_rate, memory_usage, cpu_usage
                    ),
                    "grade": self._get_performance_grade(cache_hit_rate, concurrent_success_rate)
                }
            }
            
            return self._success_result(
                data=performance_data,
                message="Performance summary generated successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_performance_summary")
    
    def _calculate_efficiency_rating(self, memory_mb: float, cpu_percent: float) -> str:
        """Calculate resource efficiency rating."""
        if memory_mb < 50 and cpu_percent < 5:
            return "excellent"
        elif memory_mb < 100 and cpu_percent < 10:
            return "good"
        elif memory_mb < 200 and cpu_percent < 20:
            return "fair"
        else:
            return "poor"
    
    def _calculate_performance_score(self, cache_hit_rate: float, thread_success_rate: float, 
                                   block_rate: float, memory_mb: float, cpu_percent: float) -> float:
        """Calculate overall performance score (0-100)."""
        # Cache performance (30% weight)
        cache_score = cache_hit_rate * 0.3
        
        # Thread safety (25% weight)
        thread_score = thread_success_rate * 0.25
        
        # Rate limiting effectiveness (20% weight) - lower block rate is better for normal operation
        rate_score = max(0, (100 - block_rate)) * 0.2
        
        # Resource efficiency (25% weight)
        memory_score = max(0, (200 - memory_mb) / 200 * 100) * 0.125  # Better when < 200MB
        cpu_score = max(0, (20 - cpu_percent) / 20 * 100) * 0.125     # Better when < 20%
        
        total_score = cache_score + thread_score + rate_score + memory_score + cpu_score
        return round(min(100, max(0, total_score)), 1)
    
    def _get_performance_grade(self, cache_hit_rate: float, thread_success_rate: float) -> str:
        """Get performance grade based on key metrics."""
        if cache_hit_rate >= 95 and thread_success_rate >= 98:
            return "A+"
        elif cache_hit_rate >= 90 and thread_success_rate >= 95:
            return "A"
        elif cache_hit_rate >= 85 and thread_success_rate >= 90:
            return "B+"
        elif cache_hit_rate >= 80 and thread_success_rate >= 85:
            return "B"
        elif cache_hit_rate >= 70 and thread_success_rate >= 80:
            return "C+"
        else:
            return "C"
    
    def run_system_diagnostics(self) -> ServiceResult:
        """Run comprehensive system diagnostics."""
        try:
            diagnostics = {
                "timestamp": datetime.now().isoformat(),
                "tests": []
            }
            
            # Test each service
            services = {
                "alarm": self.alarm_service,
                "spotify": self.spotify_service,
                "sleep": self.sleep_service
            }
            
            for name, service in services.items():
                start_time = time.time()
                health = service.health_check()
                duration = time.time() - start_time
                
                test_result = {
                    "service": name,
                    "status": "pass" if health.success else "fail",
                    "duration_ms": round(duration * 1000, 2),
                    "details": health.data if health.success else health.message
                }
                diagnostics["tests"].append(test_result)
            
            # System resource check
            start_time = time.time()
            system_stats = self._get_system_resources()
            duration = time.time() - start_time
            
            system_healthy = (
                system_stats.get("process", {}).get("memory_mb", 0) < 500 and
                system_stats.get("cpu", {}).get("usage_percent", 0) < 80
            )
            
            diagnostics["tests"].append({
                "service": "system_resources",
                "status": "pass" if system_healthy else "warn",
                "duration_ms": round(duration * 1000, 2),
                "details": system_stats
            })
            
            # Calculate overall result
            passed_tests = sum(1 for test in diagnostics["tests"] if test["status"] == "pass")
            total_tests = len(diagnostics["tests"])
            
            diagnostics["summary"] = {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": round((passed_tests / total_tests) * 100, 1),
                "overall_status": "healthy" if passed_tests == total_tests else "issues_detected"
            }
            
            return self._success_result(
                data=diagnostics,
                message=f"System diagnostics completed: {passed_tests}/{total_tests} tests passed"
            )
            
        except Exception as e:
            return self._handle_error(e, "run_system_diagnostics")
    
    def get_service_registry(self) -> ServiceResult:
        """Get registry of all available services and their status."""
        try:
            services = {
                "alarm": {
                    "name": "Alarm Service",
                    "description": "Manages alarm scheduling and execution",
                    "initialized": self.alarm_service.is_initialized(),
                    "endpoints": ["/alarm_status", "/save_alarm"],
                    "health": self.alarm_service.health_check().success
                },
                "spotify": {
                    "name": "Spotify Service", 
                    "description": "Handles Spotify integration and music control",
                    "initialized": self.spotify_service.is_initialized(),
                    "endpoints": ["/api/music-library", "/playback_status"],
                    "health": self.spotify_service.health_check().success
                },
                "sleep": {
                    "name": "Sleep Service",
                    "description": "Manages sleep timers and related functionality", 
                    "initialized": self.sleep_service.is_initialized(),
                    "endpoints": ["/sleep_status", "/sleep", "/stop_sleep"],
                    "health": self.sleep_service.health_check().success
                },
                "system": {
                    "name": "System Service",
                    "description": "Provides system monitoring and coordination",
                    "initialized": self.is_initialized(),
                    "endpoints": ["/api/system/health", "/api/system/diagnostics"],
                    "health": True
                }
            }
            
            return self._success_result(
                data=services,
                message=f"Service registry retrieved: {len(services)} services"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_service_registry")
    
    def health_check(self) -> ServiceResult:
        """Perform system service health check."""
        try:
            base_health = super().health_check()
            if not base_health.success:
                return base_health
            
            # Check all sub-services
            services_healthy = 0
            total_services = 3
            
            for service in [self.alarm_service, self.spotify_service, self.sleep_service]:
                if service.health_check().success:
                    services_healthy += 1
            
            health_data = {
                "service": "system",
                "status": "healthy" if services_healthy == total_services else "degraded",
                "services_healthy": services_healthy,
                "total_services": total_services,
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds()
            }
            
            return self._success_result(
                data=health_data,
                message="System service health check completed"
            )
            
        except Exception as e:
            return self._handle_error(e, "health_check")
