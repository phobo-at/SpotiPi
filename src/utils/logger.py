#!/usr/bin/env python3
"""
🔍 Centralized Logging System for SpotiPi
Logs all activities to structured files with rotation
Automatically adapts to Raspberry Pi for SD-card protection
"""

import logging
import logging.handlers
import os
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

# Environment detection
IS_RASPBERRY_PI = (
    (platform.machine().startswith('arm') and platform.system() == 'Linux') or
    'raspberrypi' in platform.node().lower() or
    os.path.exists('/sys/firmware/devicetree/base/model') or  # Pi-specific file
    os.getenv('SPOTIPI_RASPBERRY_PI') == '1'
)
IS_DEV_MODE = '--dev' in sys.argv or os.getenv('SPOTIPI_DEV') == '1'

# SD-Card friendly settings for Raspberry Pi
if IS_RASPBERRY_PI and not IS_DEV_MODE:
    # Minimal logging for production on Raspberry Pi
    LOG_LEVEL = logging.WARNING
    ENABLE_FILE_LOGGING = False
    ENABLE_DAILY_LOGS = False
    ENABLE_ERROR_LOGS = True  # Only critical errors
    MAX_LOG_SIZE = 1 * 1024 * 1024  # 1MB max
    BACKUP_COUNT = 1  # Only 1 backup file
    ENABLE_SYSTEM_INFO = False
    LOG_DIR = Path("/tmp/spotipi_logs")  # Use RAM disk for minimal logging
else:
    # Full logging for development or non-Pi systems
    LOG_LEVEL = logging.INFO
    ENABLE_FILE_LOGGING = True
    ENABLE_DAILY_LOGS = True
    ENABLE_ERROR_LOGS = True
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB max
    BACKUP_COUNT = 5
    ENABLE_SYSTEM_INFO = True
    LOG_DIR = Path.home() / ".spotify_wakeup" / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

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
    
    if IS_RASPBERRY_PI and not IS_DEV_MODE:
        # Simple formatter for Raspberry Pi
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
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(LOG_LEVEL)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Error-only log file (minimal even on Raspberry Pi)
    if ENABLE_ERROR_LOGS:
        error_log_file = LOG_DIR / "spotipi_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s'
        )
        error_handler.setFormatter(error_formatter)
        logger.addHandler(error_handler)
    
    # Daily log files (disabled on Raspberry Pi)
    if ENABLE_DAILY_LOGS:
        daily_log_file = LOG_DIR / f"spotipi_{datetime.now().strftime('%Y-%m-%d')}.log"
        daily_handler = logging.handlers.TimedRotatingFileHandler(
            daily_log_file,
            when='midnight',
            interval=1,
            backupCount=7,  # Keep 7 days
            encoding='utf-8'
        )
        daily_handler.setLevel(LOG_LEVEL)
        daily_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s'
        )
        daily_handler.setFormatter(daily_formatter)
        logger.addHandler(daily_handler)
    
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
    print(f"\n📂 Logs written to: {LOG_DIR}")
