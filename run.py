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

if __name__ == "__main__":
    # Load configuration for port and debug settings
    config = load_config()
    
    # Determine port based on environment
    if config.get("environment") == "production":
        default_port = 5000  # Production port
    else:
        default_port = 5001  # Development port
    
    port = int(os.environ.get("PORT", default_port))
    debug_mode = config.get("debug", False)
    
    print(f"🚀 Starting SpotiPi on port {port} with new modular structure")
    print(f"🌍 Environment: {config.get('environment', 'unknown')}")
    print(f"🔧 Debug mode: {debug_mode}")
    
    # Ensure background scheduler is started for run.py based runs
    try:
        start_alarm_scheduler()
    except Exception:
        pass

    app.run(
        host="0.0.0.0", 
        port=port, 
        debug=debug_mode
    )
