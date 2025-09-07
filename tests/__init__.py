"""
SpotiPi Test Suite
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

__all__ = ['test_alarm', 'test_spotify_api', 'test_config', 'test_scheduler']
