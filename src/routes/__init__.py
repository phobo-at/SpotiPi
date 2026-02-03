"""
SpotiPi Route Blueprints
Modular Flask blueprints for better code organization.
"""

from .alarm import alarm_bp
from .cache import cache_bp
from .devices import devices_bp
from .health import health_bp
from .music import music_bp
from .playback import playback_bp
from .services import services_bp
from .sleep import sleep_bp
from .main import main_bp

__all__ = [
    "alarm_bp",
    "cache_bp",
    "devices_bp",
    "health_bp",
    "music_bp",
    "playback_bp",
    "services_bp",
    "sleep_bp",
    "main_bp",
]
