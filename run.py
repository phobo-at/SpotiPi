#!/usr/bin/env python3
"""
SpotiPi Runner - Starts the application with the new modular structure
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the configured app from src structure
from src.app import create_app, start_alarm_scheduler  # noqa: E402
from src.config import load_config  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402
from src.utils.wsgi_logging import TidyRequestHandler  # noqa: E402

try:
    from waitress import serve
except ImportError:  # pragma: no cover - waitress installed in deployment
    serve = None


def _env_bool(name: str, default: bool | None = None) -> bool | None:
    """Parse boolean environment variables.

    Accepted truthy values: 1, true, yes, on
    Accepted falsy values: 0, false, no, off
    """
    raw = os.environ.get(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default

if __name__ == "__main__":
    logger = setup_logger("runner")
    app = create_app()
    # Load configuration for port and debug settings
    config = load_config()
    
    # Determine port based on environment
    if config.get("environment") == "production":
        default_port = 5000  # Production port
    else:
        default_port = 5001  # Development port
    
    port = int(os.environ.get("PORT", default_port))

    # Security: never derive Flask/Werkzeug debug from the writable runtime config.
    # A LAN client can flip config["debug"] via POST /api/settings; if that reached
    # app.run(debug=True) on the next service restart it would expose the Werkzeug
    # interactive debugger and full tracebacks on 0.0.0.0. Debug is opt-in via the
    # SPOTIPI_DEBUG environment variable only.
    debug_mode = _env_bool("SPOTIPI_DEBUG", False) is True

    # When the dev server is enabled, default to loopback so the interactive
    # debugger is never exposed to the network unless HOST is set explicitly.
    default_host = "127.0.0.1" if debug_mode else config.get("host", "0.0.0.0")
    host = os.environ.get("HOST", default_host)
    disable_reloader = _env_bool("SPOTIPI_DISABLE_RELOADER", False) is True
    force_waitress = _env_bool("SPOTIPI_FORCE_WAITRESS", False) is True

    print(f"🚀 Starting SpotiPi on {host}:{port} with new modular structure")
    print(f"🌍 Environment: {config.get('environment', 'unknown')}")
    print(f"🔧 Debug mode: {debug_mode}")
    
    # Ensure background scheduler is started for run.py based runs
    try:
        start_alarm_scheduler()
        logger.info("⏰ Alarm scheduler started (run.py)")
    except Exception as exc:
        logger.exception("Failed to start alarm scheduler via run.py", exc_info=exc)

    if (debug_mode and not force_waitress) or serve is None:
        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            use_reloader=debug_mode and not disable_reloader,
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
