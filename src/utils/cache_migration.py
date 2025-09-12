#!/usr/bin/env python3
"""
🔄 Music Library Cache Migration Layer
======================================

Migriert schrittweise von den aktuellen Cache-Implementierungen 
zum neuen einheitlichen System:

PHASE 1: Wrapper für bestehende Funktionen (Kompatibilität erhalten)
PHASE 2: Direkte Integration in app.py und spotify.py  
PHASE 3: Entfernung alter Cache-Code

Bietet:
- Drop-in Replacements für bestehende Cache-Funktionen
- Graduelle Migration ohne Breaking Changes
- Performance-Verbesserungen durch einheitliches System
- Rückwärtskompatibilität für bestehende APIs
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

from .music_library_cache import get_music_library_cache, CacheType


class CacheMigrationLayer:
    """Migration wrapper für bestehende Cache-Operationen."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.logger = logging.getLogger("cache_migration")
        self.unified_cache = get_music_library_cache(project_root)
        
        # Track migration status
        self._migration_stats = {
            'legacy_calls': 0,
            'unified_calls': 0,
            'migration_start': time.time()
        }
        
        self.logger.info("🔄 Cache migration layer initialized")

    # =====================================
    # 1. App.py Cache Migration (api_music_library._cache)
    # =====================================
    
    def get_legacy_app_cache(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Ersetzt api_music_library._cache Logic in app.py.
        
        Args:
            force_refresh: Bypass cache if True
            
        Returns:
            Cached music library data or None
        """
        self._migration_stats['legacy_calls'] += 1
        
        # Simulate legacy cache key behavior
        cache_key = "app_music_library"
        
        if not force_refresh:
            cached_data = self.unified_cache.get(cache_key, CacheType.FULL_LIBRARY)
            if cached_data:
                self.logger.debug("✅ Legacy app cache hit -> unified cache")
                return cached_data
        
        return None
    
    def set_legacy_app_cache(self, data: Dict[str, Any]) -> None:
        """Ersetzt api_music_library._cache Speicherung.
        
        Args:
            data: Music library data to cache
        """
        cache_key = "app_music_library"
        
        # Store in unified cache with legacy-compatible TTL
        self.unified_cache.set(cache_key, data, CacheType.FULL_LIBRARY)
        self.logger.debug("💾 Legacy app cache -> unified cache")

    # =====================================
    # 2. Spotify.py Section Cache Migration (_LIB_SECTION_CACHE)
    # =====================================
    
    def get_legacy_section_cache(self, section_name: str) -> Dict[str, Any]:
        """Ersetzt _get_section_cache() in spotify.py.
        
        Args:
            section_name: Name of library section (playlists, albums, etc.)
            
        Returns:
            Legacy-format cache dict {"ts": float, "data": list}
        """
        self._migration_stats['legacy_calls'] += 1
        
        # Map section name to cache type
        type_mapping = {
            'playlists': CacheType.PLAYLISTS,
            'albums': CacheType.ALBUMS,
            'tracks': CacheType.TRACKS,
            'artists': CacheType.ARTISTS
        }
        
        cache_type = type_mapping.get(section_name, CacheType.PLAYLISTS)
        cache_key = f"legacy_section_{section_name}"
        
        cached_data = self.unified_cache.get(cache_key, cache_type)
        
        # Return legacy format for compatibility
        if cached_data:
            return {"ts": time.time(), "data": cached_data}
        else:
            return {"ts": 0.0, "data": []}
    
    def set_legacy_section_cache(self, section_name: str, data: List[Dict[str, Any]]) -> None:
        """Ersetzt section cache update in spotify.py.
        
        Args:
            section_name: Name of library section
            data: Section data to cache
        """
        type_mapping = {
            'playlists': CacheType.PLAYLISTS,
            'albums': CacheType.ALBUMS,
            'tracks': CacheType.TRACKS,
            'artists': CacheType.ARTISTS
        }
        
        cache_type = type_mapping.get(section_name, CacheType.PLAYLISTS)
        cache_key = f"legacy_section_{section_name}"
        
        self.unified_cache.set(cache_key, data, cache_type)
        self.logger.debug(f"💾 Legacy section cache {section_name} -> unified cache")

    # =====================================
    # 3. Device Cache Migration (_DEVICE_CACHE)
    # =====================================
    
    def get_legacy_device_cache(self) -> Dict[str, Any]:
        """Ersetzt _DEVICE_CACHE in spotify.py.
        
        Returns:
            Legacy-format device cache {"ts": float, "data": list}
        """
        self._migration_stats['legacy_calls'] += 1
        
        cached_devices = self.unified_cache.get("spotify_devices", CacheType.DEVICES)
        
        # Return legacy format for compatibility
        if cached_devices:
            return {"ts": time.time(), "data": cached_devices}
        else:
            return {"ts": 0.0, "data": []}
    
    def set_legacy_device_cache(self, devices: List[Dict[str, Any]]) -> None:
        """Ersetzt device cache update in spotify.py.
        
        Args:
            devices: Device list to cache
        """
        self.unified_cache.set("spotify_devices", devices, CacheType.DEVICES)
        self.logger.debug("💾 Legacy device cache -> unified cache")

    # =====================================
    # 4. Modern API für neue Implementierungen
    # =====================================
    
    def get_full_library_cached(self, token: str, loader_func: Callable, 
                               force_refresh: bool = False) -> Dict[str, Any]:
        """Moderne API für vollständige Library mit Caching.
        
        Args:
            token: Spotify access token
            loader_func: Function to load fresh library data
            force_refresh: Bypass cache if True
            
        Returns:
            Complete music library with cache metadata
        """
        self._migration_stats['unified_calls'] += 1
        return self.unified_cache.get_full_library(token, loader_func, force_refresh)
    
    def get_library_sections_cached(self, token: str, sections: List[str], 
                                   section_loaders: Dict[str, Callable], 
                                   force_refresh: bool = False) -> Dict[str, Any]:
        """Moderne API für section-basierte Library-Abfragen.
        
        Args:
            token: Spotify access token
            sections: List of section names to load
            section_loaders: Mapping of section names to loader functions
            force_refresh: Bypass cache if True
            
        Returns:
            Partial library with requested sections
        """
        self._migration_stats['unified_calls'] += 1
        return self.unified_cache.get_library_sections(token, sections, section_loaders, force_refresh)
    
    def get_devices_cached(self, token: str, loader_func: Callable, 
                          force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Moderne API für Device-Caching.
        
        Args:
            token: Spotify access token
            loader_func: Function to load devices from API
            force_refresh: Bypass cache if True
            
        Returns:
            List of Spotify devices
        """
        self._migration_stats['unified_calls'] += 1
        return self.unified_cache.get_devices(token, loader_func, force_refresh)

    # =====================================
    # 5. Cache Management
    # =====================================
    
    def invalidate_all_cache(self) -> int:
        """Invalidiert alle Cache-Daten.
        
        Returns:
            Number of invalidated entries
        """
        return self.unified_cache.invalidate()
    
    def invalidate_music_library(self) -> int:
        """Invalidiert nur Music Library Cache.
        
        Returns:
            Number of invalidated entries
        """
        count = 0
        count += self.unified_cache.invalidate(CacheType.FULL_LIBRARY)
        count += self.unified_cache.invalidate(CacheType.PLAYLISTS)
        count += self.unified_cache.invalidate(CacheType.ALBUMS)
        count += self.unified_cache.invalidate(CacheType.TRACKS)
        count += self.unified_cache.invalidate(CacheType.ARTISTS)
        return count
    
    def invalidate_devices(self) -> int:
        """Invalidiert nur Device Cache.
        
        Returns:
            Number of invalidated entries
        """
        return self.unified_cache.invalidate(CacheType.DEVICES)
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Liefert umfassende Cache-Statistiken.
        
        Returns:
            Cache performance statistics including migration info
        """
        unified_stats = self.unified_cache.get_statistics()
        
        # Add migration-specific stats
        total_calls = self._migration_stats['legacy_calls'] + self._migration_stats['unified_calls']
        if total_calls > 0:
            migration_progress = (self._migration_stats['unified_calls'] / total_calls) * 100
        else:
            migration_progress = 0
        
        return {
            "cache_performance": {
                "total_entries": unified_stats.total_entries,
                "hit_rate": unified_stats.hit_rate,
                "memory_usage_mb": unified_stats.memory_usage_bytes / (1024 * 1024),
                "efficiency": unified_stats.cache_efficiency,
                "most_used_type": unified_stats.most_accessed_type
            },
            "migration_status": {
                "legacy_calls": self._migration_stats['legacy_calls'],
                "unified_calls": self._migration_stats['unified_calls'],
                "migration_progress": f"{migration_progress:.1f}%",
                "days_since_start": (time.time() - self._migration_stats['migration_start']) / 86400
            }
        }
    
    def get_offline_fallback(self) -> Optional[Dict[str, Any]]:
        """Liefert Offline-Fallback Daten.
        
        Returns:
            Offline cache data or None
        """
        return self.unified_cache.get_offline_fallback()


# Global migration layer instance
_migration_layer: Optional[CacheMigrationLayer] = None


def get_cache_migration_layer(project_root: Optional[Path] = None) -> CacheMigrationLayer:
    """Get the global cache migration layer instance.
    
    Args:
        project_root: Optional project root path
        
    Returns:
        Global migration layer instance
    """
    global _migration_layer
    if _migration_layer is None:
        _migration_layer = CacheMigrationLayer(project_root)
    return _migration_layer


# =====================================
# Convenience functions für direkte Integration
# =====================================

def migrate_app_music_library_cache(project_root: Path):
    """Drop-in replacement für app.py music library caching.
    
    Usage in app.py:
    # Ersetzt: if not hasattr(api_music_library, '_cache'):
    # Ersetzt:     api_music_library._cache = { 'data': None, 'ts': 0 }
    
    # Ersetzt: cache_ttl = int(os.getenv('SPOTIPI_MUSIC_CACHE_TTL', '600'))
    # Ersetzt: if api_music_library._cache['data'] and (now - api_music_library._cache['ts'] < cache_ttl):
    # Mit:     cached = get_migrated_app_cache(force_refresh)
    """
    return get_cache_migration_layer(project_root)


def migrate_spotify_section_cache():
    """Drop-in replacement für spotify.py section caching.
    
    Usage in spotify.py:
    # Ersetzt: def _get_section_cache(name: str) -> Dict[str, Any]:
    # Mit:     migration_layer.get_legacy_section_cache(name)
    """
    return get_cache_migration_layer()


def migrate_device_cache():
    """Drop-in replacement für spotify.py device caching.
    
    Usage in spotify.py:
    # Ersetzt: globals()['_DEVICE_CACHE'] = {'ts': 0, 'data': []}
    # Mit:     migration_layer.get_legacy_device_cache()
    """
    return get_cache_migration_layer()