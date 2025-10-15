#!/usr/bin/env python3
"""
SpotiPi Runner - Starts the application with the new modular structure
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the configured app from src structure
from src.app import app, start_alarm_scheduler
from src.config import load_config
from src.utils.wsgi_logging import TidyRequestHandler
from src.utils.logger import setup_logger

try:
    from waitress import serve
except ImportError:  # pragma: no cover - waitress installed in deployment
    serve = None

if __name__ == "__main__":
    logger = setup_logger("runner")
    # Load configuration for port and debug settings
    config = load_config()
    
    # Determine port based on environment
    if config.get("environment") == "production":
        default_port = 5000  # Production port
    else:
        default_port = 5001  # Development port
    
    port = int(os.environ.get("PORT", default_port))
    debug_mode = config.get("debug", False)
    
    host = config.get("host", "0.0.0.0")

    print(f"🚀 Starting SpotiPi on {host}:{port} with new modular structure")
    print(f"🌍 Environment: {config.get('environment', 'unknown')}")
    print(f"🔧 Debug mode: {debug_mode}")
    
    # Ensure background scheduler is started for run.py based runs
    try:
        start_alarm_scheduler()
        logger.info("⏰ Alarm scheduler started (run.py)")
    except Exception as exc:
        logger.exception("Failed to start alarm scheduler via run.py", exc_info=exc)

    if debug_mode or serve is None:
        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            request_handler=TidyRequestHandler,
        )
    else:
        threads = int(os.environ.get("SPOTIPI_WAITRESS_THREADS", "4"))
        backlog = int(os.environ.get("SPOTIPI_WAITRESS_BACKLOG", "128"))
        print(f"🍽️ Using Waitress WSGI server (threads={threads}, backlog={backlog})")
        serve(
            app,
            host=host,
            port=port,
            threads=threads,
            backlog=backlog
        )
