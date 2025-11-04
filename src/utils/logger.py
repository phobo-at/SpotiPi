#!/usr/bin/env python3
"""
🔍 Centralized Logging System for SpotiPi
Logs all activities to structured files with rotation
Automatically adapts to Raspberry Pi for SD-card protection
Supports structured JSON logging for production observability
"""

import json
import logging
import logging.handlers
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Environment detection
IS_RASPBERRY_PI = (
    (platform.machine().startswith('arm') and platform.system() == 'Linux') or
    'raspberrypi' in platform.node().lower() or
    os.path.exists('/sys/firmware/devicetree/base/model') or  # Pi-specific file
    os.getenv('SPOTIPI_RASPBERRY_PI') == '1'
)
IS_DEV_MODE = '--dev' in sys.argv or os.getenv('SPOTIPI_DEV') == '1'

# JSON logging for production observability (since v1.3.8)
ENABLE_JSON_LOGS = os.getenv('SPOTIPI_JSON_LOGS', '0') == '1'

# Base defaults depending on environment (before overrides)
if IS_RASPBERRY_PI and not IS_DEV_MODE:
    LOG_LEVEL = logging.WARNING
    ENABLE_FILE_LOGGING = False
    ENABLE_DAILY_LOGS = False
    ENABLE_ERROR_LOGS = True
    MAX_LOG_SIZE = 1 * 1024 * 1024
    BACKUP_COUNT = 1
    ENABLE_SYSTEM_INFO = False
    LOG_DIR = Path("/tmp/spotipi_logs")
    # Enable JSON logs by default in production for observability
    if not ENABLE_JSON_LOGS and os.getenv('SPOTIPI_JSON_LOGS') is None:
        ENABLE_JSON_LOGS = True
else:
    LOG_LEVEL = logging.INFO
    ENABLE_FILE_LOGGING = True
    ENABLE_DAILY_LOGS = True
    ENABLE_ERROR_LOGS = True
    MAX_LOG_SIZE = 10 * 1024 * 1024
    BACKUP_COUNT = 5
    ENABLE_SYSTEM_INFO = True
    
    # Path-agnostic log directory detection
    def _get_app_log_dir():
        """Get application log directory path-agnostically"""
        _env_log_dir = os.getenv('SPOTIPI_LOG_DIR')
        if _env_log_dir:
            return Path(_env_log_dir)
        
        app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
        return Path.home() / f".{app_name}" / "logs"
    
    LOG_DIR = _get_app_log_dir()

# ---- Environment overrides (systemd friendly) ----
_env_level = os.getenv('SPOTIPI_LOG_LEVEL')
if _env_level:
    try:
        LOG_LEVEL = getattr(logging, _env_level.upper())
    except AttributeError:
        pass  # Ignore invalid level

if os.getenv('SPOTIPI_FORCE_FILE_LOG') == '1':
    ENABLE_FILE_LOGGING = True
    # Keep directory writable
    if 'LOG_DIR' not in globals():
        # Path-agnostic fallback
        app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi") 
        LOG_DIR = Path.home() / f".{app_name}" / "logs"

if os.getenv('SPOTIPI_DISABLE_DAILY_LOGS') == '1':
    ENABLE_DAILY_LOGS = False

if os.getenv('SPOTIPI_SYSTEM_INFO') == '0':
    ENABLE_SYSTEM_INFO = False

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # Fallback to console-only logging if directory is not writable
    ENABLE_FILE_LOGGING = False
    ENABLE_DAILY_LOGS = False
    ENABLE_ERROR_LOGS = False

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for console output.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log message with colors
        """
        if hasattr(record, 'no_color') and record.no_color:
            return super().format(record)
            
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Add color to levelname
        record.levelname = f"{color}{record.levelname}{reset}"
        
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for production observability.
    
    Outputs logs in JSON format with structured fields for easy parsing
    and correlation in log aggregation systems (journalctl, Loki, etc.).
    
    Example output:
        {"timestamp": "2025-11-04T10:30:00.123Z", "level": "ERROR", 
         "logger": "alarm_scheduler", "message": "Failed to trigger alarm",
         "alarm_id": "20251104T063000Z", "error": "Device not found"}
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            str: JSON-formatted log message
        """
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add source location for errors and warnings
        if record.levelno >= logging.WARNING:
            log_data['source'] = f"{record.filename}:{record.lineno}"
            log_data['function'] = record.funcName
        
        # Include exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add any extra fields passed via logger.info("msg", extra={...})
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in (
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'message', 'pathname', 'process', 'processName', 'relativeCreated',
                    'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                    'getMessage', 'no_color'
                ):
                    # Only include serializable values
                    try:
                        json.dumps(value)
                        log_data[key] = value
                    except (TypeError, ValueError):
                        log_data[key] = str(value)
        
        try:
            return json.dumps(log_data, ensure_ascii=True, sort_keys=True)
        except (TypeError, ValueError) as e:
            # Fallback: convert all values to strings
            safe_data = {k: str(v) for k, v in log_data.items()}
            safe_data['_json_error'] = str(e)
            return json.dumps(safe_data, ensure_ascii=True, sort_keys=True)

def setup_logging() -> logging.Logger:
    """Initialize logging system for the application.
    
    Returns:
        logging.Logger: The main logger instance
    """
    return setup_logger("spotipi")

def setup_logger(name: str) -> logging.Logger:
    """
    Sets up a logger with appropriate handlers based on environment
    
    Args:
        name: Logger name (usually module name)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    logger.setLevel(LOG_LEVEL)
    
    # Console handler (always enabled, but respects log level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    
    # Choose formatter based on environment and JSON flag
    if ENABLE_JSON_LOGS:
        # JSON formatter for production observability
        console_formatter = JSONFormatter()
    elif IS_RASPBERRY_PI and not IS_DEV_MODE:
        # Simple formatter for Raspberry Pi (non-JSON)
        console_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    else:
        # Colored formatter for development
        console_formatter = ColoredFormatter()
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File logging (disabled on Raspberry Pi in production)
    if ENABLE_FILE_LOGGING:
        # Main rotating log file
        main_log_file = LOG_DIR / "spotipi.log"
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                main_log_file,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(LOG_LEVEL)
            
            # Use JSON formatter for file logs if enabled
            if ENABLE_JSON_LOGS:
                file_formatter = JSONFormatter()
            else:
                file_formatter = logging.Formatter(
                    '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s'
                )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass
    
    # Error-only log file (minimal even on Raspberry Pi)
    if ENABLE_ERROR_LOGS:
        error_log_file = LOG_DIR / "spotipi_errors.log"
        try:
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            
            # Always use JSON for error logs in production for better debugging
            if ENABLE_JSON_LOGS:
                error_formatter = JSONFormatter()
            else:
                error_formatter = logging.Formatter(
                    '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s'
                )
            error_handler.setFormatter(error_formatter)
            logger.addHandler(error_handler)
        except Exception:
            pass
    
    # Daily log files (disabled on Raspberry Pi)
    if ENABLE_DAILY_LOGS:
        daily_log_file = LOG_DIR / f"spotipi_{datetime.now().strftime('%Y-%m-%d')}.log"
        try:
            daily_handler = logging.handlers.TimedRotatingFileHandler(
                daily_log_file,
                when='midnight',
                interval=1,
                backupCount=7,  # Keep 7 days
                encoding='utf-8'
            )
            daily_handler.setLevel(LOG_LEVEL)
            
            # Use JSON formatter for daily logs if enabled
            if ENABLE_JSON_LOGS:
                daily_formatter = JSONFormatter()
            else:
                daily_formatter = logging.Formatter(
                    '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s'
                )
            daily_handler.setFormatter(daily_formatter)
            logger.addHandler(daily_handler)
        except Exception:
            pass
    
    return logger

def log_system_info(logger: logging.Logger) -> None:
    """Log system information for debugging.
    
    Args:
        logger: Logger instance to use for output
    """
    try:
        import psutil
    except ImportError:
        logger.warning("psutil not available - skipping system info")
        return
    
    try:
        logger.info("=" * 50)
        logger.info("🚀 SpotiPi System Information")
        logger.info("=" * 50)
        logger.info(f"🖥️  Platform: {platform.platform()}")
        logger.info(f"🐍 Python: {platform.python_version()}")
        logger.info(f"💾 Memory: {psutil.virtual_memory().available / (1024**3):.1f}GB available")
        logger.info(f"💽 Disk: {psutil.disk_usage('/').free / (1024**3):.1f}GB free")
        logger.info(f"📂 Log Directory: {LOG_DIR}")
        logger.info("=" * 50)
    except Exception as e:
        logger.warning(f"Could not gather system info: {e}")

def log_startup(module_name: str) -> None:
    """Log startup information for a module.
    
    Args:
        module_name: Name of the module being started
        
    Note:
        Only shows detailed system info in development mode
    """
    logger = logging.getLogger(module_name)
    logger.info(f"🎵 Starting {module_name}")
    
    # Only show detailed system info in development mode
    if ENABLE_SYSTEM_INFO:
        try:
            import psutil

            # System information
            logger.info("=" * 50)
            logger.info("🚀 SpotiPi System Information")
            logger.info("=" * 50)
            logger.info(f"🖥️  Platform: {platform.platform()}")
            logger.info(f"🐍 Python: {platform.python_version()}")
            
            # Memory info (rounded to GB)
            memory = psutil.virtual_memory()
            memory_gb = memory.available / (1024**3)
            logger.info(f"💾 Memory: {memory_gb:.1f}GB available")
            
            # Disk info (rounded to GB)
            disk = psutil.disk_usage('/')
            disk_gb = disk.free / (1024**3)
            logger.info(f"💽 Disk: {disk_gb:.1f}GB free")
            
            logger.info(f"📂 Log Directory: {LOG_DIR}")
            logger.info("=" * 50)
            
        except ImportError:
            logger.warning("psutil not available - skipping system info")
        except Exception as e:
            logger.warning(f"Could not gather system info: {e}")
    else:
        logger.info(f"🚀 Running on {'Raspberry Pi' if IS_RASPBERRY_PI else 'development system'}")
        logger.info(f"📂 Logs: {LOG_DIR}")

def log_shutdown(logger: logging.Logger, component_name: str) -> None:
    """Log component shutdown.
    
    Args:
        logger: Logger instance to use
        component_name: Name of the component being shut down
    """
    logger.info(f"🛑 Shutting down {component_name}")
    
    # Flush all handlers
    for handler in logger.handlers:
        handler.flush()

def log_exception(logger: logging.Logger, exc_info: bool = True) -> None:
    """Log an exception with full traceback.
    
    Args:
        logger: Logger instance to use
        exc_info: Whether to include exception info in the log
    """
    logger.exception("❌ Unhandled exception occurred:", exc_info=exc_info)

def cleanup_old_logs() -> None:
    """Clean up log files older than specified days.
    
    Note:
        More aggressive cleanup on Raspberry Pi to protect SD card
    """
    try:
        logger = setup_logger("cleanup")
        
        # On Raspberry Pi, be more aggressive with cleanup
        if IS_RASPBERRY_PI and not IS_DEV_MODE:
            days_to_keep = 2  # Keep only 2 days on Pi
        else:
            days_to_keep = 7  # Keep 7 days on development systems
        
        import time
        current_time = time.time()
        cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
        
        cleaned = 0
        for log_file in LOG_DIR.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned += 1
            except (OSError, ValueError):
                continue
        
        if cleaned > 0:
            logger.info(f"🧹 Cleaned up {cleaned} old log files (keeping {days_to_keep} days)")
            
    except Exception:
        # Don't let log cleanup break the application
        pass


def log_structured(logger: logging.Logger, level: int, message: str, **context: Any) -> None:
    """Log a message with structured context fields.
    
    This is a convenience wrapper that works with both JSON and traditional formatters.
    In JSON mode, context fields appear as separate JSON keys. In traditional mode,
    they're appended to the message.
    
    Args:
        logger: Logger instance to use
        level: Log level (e.g., logging.INFO)
        message: Human-readable log message
        **context: Additional structured fields (e.g., user_id="123", duration_ms=45.2)
    
    Example:
        >>> log_structured(logger, logging.INFO, "Alarm triggered",
        ...                alarm_id="20251104T063000Z", device="Living Room",
        ...                spotify_track_uri="spotify:track:abc123")
        
        JSON output:
        {"timestamp": "2025-11-04T06:30:00.123Z", "level": "INFO",
         "message": "Alarm triggered", "alarm_id": "20251104T063000Z",
         "device": "Living Room", "spotify_track_uri": "spotify:track:abc123"}
    """
    if ENABLE_JSON_LOGS:
        # JSON formatter will pick up extra fields automatically
        logger.log(level, message, extra=context)
    else:
        # Traditional formatter: append context as key=value pairs
        if context:
            context_str = " ".join(f"{k}={v}" for k, v in context.items())
            logger.log(level, f"{message} | {context_str}")
        else:
            logger.log(level, message)


# Global logger for quick access
main_logger = setup_logger("spotipi")

if __name__ == "__main__":
    # Test the logging system
    test_logger = setup_logger("test")
    log_startup("test")
    test_logger.debug("Debug message")
    test_logger.info("Info message")
    test_logger.warning("Warning message")
    test_logger.error("Error message")
    
    try:
        raise ValueError("Test exception")
    except Exception:
        log_exception(test_logger)
    
    log_shutdown(test_logger, "test")
    test_logger.info(f"Logs written to: {LOG_DIR}")
