"""
🏗️ Service Layer - Base Service Interface
==========================================

Defines the base interface and common functionality for all services.
Services contain business logic and coordinate between different modules.
"""

import logging
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ServiceResult:
    """Standardized result object for service operations."""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "success": self.success,
            "timestamp": self.timestamp.isoformat()
        }
        
        if self.data is not None:
            result["data"] = self.data
        if self.message:
            result["message"] = self.message
        if self.error_code:
            result["error_code"] = self.error_code
            
        return result

class BaseService(ABC):
    """Base class for all services with common functionality."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"service.{name}")
        self._initialized = False
        
    def initialize(self) -> ServiceResult:
        """Initialize the service. Override in subclasses."""
        try:
            self._initialized = True
            self.logger.info(f"🔧 {self.name} service initialized")
            return ServiceResult(
                success=True,
                message=f"{self.name} service initialized successfully"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.name} service: {e}")
            return ServiceResult(
                success=False,
                message=f"Failed to initialize {self.name} service",
                error_code="INIT_FAILED"
            )
    
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
    
    def health_check(self) -> ServiceResult:
        """Perform health check. Override in subclasses for specific checks."""
        if not self._initialized:
            return ServiceResult(
                success=False,
                message=f"{self.name} service not initialized",
                error_code="NOT_INITIALIZED"
            )
        
        return ServiceResult(
            success=True,
            data={"status": "healthy", "service": self.name}
        )
    
    def _handle_error(self, error: Exception, operation: str) -> ServiceResult:
        """Standard error handling for service operations."""
        error_msg = f"Error in {self.name}.{operation}: {str(error)}"
        self.logger.error(error_msg, exc_info=True)
        
        return ServiceResult(
            success=False,
            message=error_msg,
            error_code="OPERATION_FAILED"
        )
    
    def _success_result(self, data: Any = None, message: str = None) -> ServiceResult:
        """Helper to create success results."""
        return ServiceResult(
            success=True,
            data=data,
            message=message
        )
    
    def _error_result(self, message: str, error_code: str = "ERROR", data: Any = None) -> ServiceResult:
        """Helper to create error results."""
        return ServiceResult(
            success=False,
            data=data,
            message=message,
            error_code=error_code
        )
