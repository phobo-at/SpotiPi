"""
SpotiPi - Smart Alarm Clock & Sleep Timer with Spotify Integration
Main package initialization
"""

from .version import VERSION, get_app_info, get_version

__version__ = VERSION
__all__ = ['VERSION', 'get_version', 'get_app_info']
