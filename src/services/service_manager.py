"""
🔧 Service Manager - Central Service Coordination
===============================================

Manages all services and provides a unified interface for the Flask application.
"""

import logging
from typing import Dict, Any, Optional

from .system_service import SystemService
from .alarm_service import AlarmService  
from .spotify_service import SpotifyService
from .sleep_service import SleepService
from . import ServiceResult

class ServiceManager:
    """Central manager for all application services."""
    
    def __init__(self):
        self.logger = logging.getLogger("service_manager")
        
        # Initialize services
        self.system = SystemService()
        self.alarm = AlarmService()
        self.spotify = SpotifyService()
        self.sleep = SleepService()
        
        # Service registry
        self.services = {
            "system": self.system,
            "alarm": self.alarm,
            "spotify": self.spotify,
            "sleep": self.sleep
        }
        
        self._initialize_all()
    
    def _initialize_all(self) -> None:
        """Initialize all services."""
        self.logger.info("🚀 Initializing service manager...")
        
        for name, service in self.services.items():
            try:
                result = service.initialize()
                if result.success:
                    self.logger.info(f"✅ {name} service initialized")
                else:
                    self.logger.error(f"❌ {name} service initialization failed: {result.message}")
            except Exception as e:
                self.logger.error(f"💥 {name} service crashed during initialization: {e}")
        
        self.logger.info("🎯 Service manager initialization completed")
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get a specific service by name."""
        return self.services.get(name)
    
    def health_check_all(self) -> ServiceResult:
        """Perform health check on all services."""
        try:
            results = {}
            overall_healthy = True
            
            for name, service in self.services.items():
                health = service.health_check()
                results[name] = {
                    "healthy": health.success,
                    "status": health.data if health.success else {"error": health.message}
                }
                
                if not health.success:
                    overall_healthy = False
            
            return ServiceResult(
                success=True,
                data={
                    "overall_healthy": overall_healthy,
                    "services": results,
                    "total_services": len(self.services),
                    "healthy_services": sum(1 for r in results.values() if r["healthy"])
                },
                message="Health check completed for all services"
            )
            
        except Exception as e:
            self.logger.error(f"Error during health check: {e}")
            return ServiceResult(
                success=False,
                message=f"Health check failed: {str(e)}",
                error_code="HEALTH_CHECK_FAILED"
            )
    
    def get_performance_overview(self) -> ServiceResult:
        """Get performance overview across all services."""
        try:
            return self.system.get_performance_summary()
        except Exception as e:
            self.logger.error(f"Error getting performance overview: {e}")
            return ServiceResult(
                success=False,
                message=f"Performance overview failed: {str(e)}",
                error_code="PERFORMANCE_ERROR"
            )
    
    def run_diagnostics(self) -> ServiceResult:
        """Run comprehensive diagnostics across all services."""
        try:
            return self.system.run_system_diagnostics()
        except Exception as e:
            self.logger.error(f"Error running diagnostics: {e}")
            return ServiceResult(
                success=False,
                message=f"Diagnostics failed: {str(e)}",
                error_code="DIAGNOSTICS_FAILED"
            )

# Global service manager instance
_service_manager = None

def get_service_manager() -> ServiceManager:
    """Get the global service manager instance."""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager

def get_service(name: str) -> Optional[Any]:
    """Get a specific service by name."""
    return get_service_manager().get_service(name)
