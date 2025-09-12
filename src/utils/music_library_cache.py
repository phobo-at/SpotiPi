#!/usr/bin/env python3
"""
🎵 Unified Music Library Cache System
====================================

Ersetzt alle bisherigen Cache-Implementierungen:
- In-Memory Cache in app.py (api_music_library._cache)
- Section Cache in spotify.py (_LIB_SECTION_CACHE) 
- JSON File Cache (music_library_cache.json)
- Device Cache (_DEVICE_CACHE)

Bietet einheitliche Interfaces für:
- Vollständige Library (playlists, albums, tracks, artists)
- Partielle/Section-basierte Library-Abfragen
- Device-Caching
- Persistente Offline-Fallbacks
- Thread-sichere Operations
- Konfigurierbare TTL-Werte
- Cache-Statistiken und -Management
"""

import os
import time
import threading
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
from enum import Enum

from .simple_cache import write_json_cache, read_json_cache


class CacheType(Enum):
    """Types of cacheable music library data."""
    FULL_LIBRARY = "full_library"
    PLAYLISTS = "playlists"
    ALBUMS = "albums"
    TRACKS = "tracks"
    ARTISTS = "artists"
    DEVICES = "devices"


@dataclass
class CacheEntry:
    """Individual cache entry with metadata."""
    data: Any
    timestamp: float
    ttl: int
    cache_type: CacheType
    hash_value: Optional[str] = None
    access_count: int = 0
    last_access: float = 0


@dataclass 
class CacheStats:
    """Cache performance statistics."""
    total_entries: int
    hit_rate: float
    memory_usage_bytes: int
    oldest_entry: float
    most_accessed_type: str
    cache_efficiency: str


class MusicLibraryCache:
    """Thread-safe unified cache for all music library data."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.logger = logging.getLogger("music_cache")
        self._lock = threading.RLock()
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'total_requests': 0,
            'last_cleanup': time.time()
        }
        
        # Paths for persistent cache
        if project_root:
            self.cache_dir = project_root / "logs"
        else:
            self.cache_dir = Path(__file__).parent.parent.parent / "logs"
        self.cache_dir.mkdir(exist_ok=True)
        
        # TTL configuration (seconds)
        self._ttl_config = {
            CacheType.FULL_LIBRARY: int(os.getenv('SPOTIPI_MUSIC_CACHE_TTL', '600')),  # 10 min
            CacheType.PLAYLISTS: int(os.getenv('SPOTIPI_LIBRARY_SECTION_TTL', '600')),  # 10 min
            CacheType.ALBUMS: int(os.getenv('SPOTIPI_LIBRARY_SECTION_TTL', '600')),    # 10 min
            CacheType.TRACKS: int(os.getenv('SPOTIPI_LIBRARY_SECTION_TTL', '600')),    # 10 min
            CacheType.ARTISTS: int(os.getenv('SPOTIPI_LIBRARY_SECTION_TTL', '600')),   # 10 min
            CacheType.DEVICES: int(os.getenv('SPOTIPI_DEVICE_CACHE_TTL', '15')),       # 15 sec
        }
        
        # Auto-cleanup interval
        self._cleanup_interval = 300  # 5 minutes
        
        self.logger.info("🎵 Unified Music Library Cache initialized")

    def get(self, cache_key: str, cache_type: CacheType) -> Optional[Any]:
        """Get data from cache if fresh.
        
        Args:
            cache_key: Unique cache identifier
            cache_type: Type of cached data
            
        Returns:
            Cached data if available and fresh, None otherwise
        """
        with self._lock:
            self._stats['total_requests'] += 1
            
            if cache_key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[cache_key]
            now = time.time()
            
            # Check if expired
            if (now - entry.timestamp) > entry.ttl:
                self._stats['misses'] += 1
                del self._cache[cache_key]
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_access = now
            self._stats['hits'] += 1
            
            self.logger.debug(f"✅ Cache hit for {cache_key} ({cache_type.value})")
            return entry.data

    def set(self, cache_key: str, data: Any, cache_type: CacheType, 
            hash_value: Optional[str] = None) -> None:
        """Store data in cache.
        
        Args:
            cache_key: Unique cache identifier
            data: Data to cache
            cache_type: Type of cached data
            hash_value: Optional hash for cache validation
        """
        with self._lock:
            now = time.time()
            ttl = self._ttl_config.get(cache_type, 600)
            
            entry = CacheEntry(
                data=data,
                timestamp=now,
                ttl=ttl,
                cache_type=cache_type,
                hash_value=hash_value,
                access_count=0,
                last_access=now
            )
            
            self._cache[cache_key] = entry
            self.logger.debug(f"💾 Cached {cache_key} ({cache_type.value}) TTL={ttl}s")
            
            # Trigger cleanup if needed
            self._maybe_cleanup()

    def get_full_library(self, token: str, loader_func: callable, 
                        force_refresh: bool = False) -> Dict[str, Any]:
        """Get complete music library with caching.
        
        Args:
            token: Spotify access token
            loader_func: Function to load fresh data (load_music_library_parallel)
            force_refresh: Bypass cache if True
            
        Returns:
            Complete music library data
        """
        cache_key = f"full_library_{hash(token) % 10000}"  # Token-specific cache
        
        if not force_refresh:
            cached_data = self.get(cache_key, CacheType.FULL_LIBRARY)
            if cached_data:
                return self._add_cache_metadata(cached_data, cached=True)
        
        # Load fresh data
        self.logger.info("🔄 Loading fresh complete music library...")
        fresh_data = loader_func(token)
        
        # Cache the fresh data
        from ..utils.library_utils import compute_library_hash
        hash_value = compute_library_hash(fresh_data)
        self.set(cache_key, fresh_data, CacheType.FULL_LIBRARY, hash_value)
        
        # Also persist to disk for offline fallback
        try:
            cache_file = self.cache_dir / "music_library_cache.json"
            write_json_cache(str(cache_file), fresh_data)
            self.logger.debug("💾 Persisted library cache to disk")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not persist cache to disk: {e}")
        
        return self._add_cache_metadata(fresh_data, cached=False)

    def get_library_sections(self, token: str, sections: List[str], 
                           section_loaders: Dict[str, callable], 
                           force_refresh: bool = False) -> Dict[str, Any]:
        """Get specific library sections with individual caching.
        
        Args:
            token: Spotify access token
            sections: List of section names to load
            section_loaders: Mapping of section names to loader functions
            force_refresh: Bypass cache if True
            
        Returns:
            Partial library with requested sections
        """
        valid_sections = {"playlists", "albums", "tracks", "artists"}
        wanted = [s for s in sections if s in valid_sections]
        if not wanted:
            wanted = ["playlists"]
        
        results = {}
        section_cache_status = {}
        
        def load_section(section_name: str) -> List[Dict[str, Any]]:
            cache_key = f"{section_name}_{hash(token) % 10000}"
            cache_type = getattr(CacheType, section_name.upper())
            
            # Try cache first
            if not force_refresh:
                cached = self.get(cache_key, cache_type)
                if cached:
                    section_cache_status[section_name] = True
                    return cached
            
            # Load fresh data
            loader = section_loaders.get(section_name)
            if not loader:
                self.logger.warning(f"⚠️ No loader for section {section_name}")
                return []
            
            try:
                fresh_data = loader(token)
                self.set(cache_key, fresh_data, cache_type)
                section_cache_status[section_name] = False
                return fresh_data
            except Exception as e:
                self.logger.error(f"❌ Failed loading section {section_name}: {e}")
                return []
        
        # Load sections in parallel
        with ThreadPoolExecutor(max_workers=min(len(wanted), 4)) as executor:
            future_map = {sec: executor.submit(load_section, sec) for sec in wanted}
            for sec, future in future_map.items():
                results[sec] = future.result()
        
        # Fill in empty sections
        for section in valid_sections:
            if section not in results:
                results[section] = []
        
        total_items = sum(len(results[s]) for s in wanted)
        
        return {
            **results,
            "total": total_items,
            "partial": True,
            "sections": wanted,
            "cached": section_cache_status
        }

    def get_devices(self, token: str, loader_func: callable, 
                   force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get Spotify devices with short-term caching.
        
        Args:
            token: Spotify access token
            loader_func: Function to load devices from Spotify API
            force_refresh: Bypass cache if True
            
        Returns:
            List of available devices
        """
        cache_key = "spotify_devices"
        
        if not force_refresh:
            cached_devices = self.get(cache_key, CacheType.DEVICES)
            if cached_devices:
                return cached_devices
        
        try:
            fresh_devices = loader_func(token)
            self.set(cache_key, fresh_devices, CacheType.DEVICES)
            return fresh_devices
        except Exception as e:
            self.logger.error(f"❌ Failed loading devices: {e}")
            # Try to return stale cache as fallback
            return self._cache.get(cache_key, CacheEntry([], 0, 0, CacheType.DEVICES)).data

    def get_offline_fallback(self) -> Optional[Dict[str, Any]]:
        """Get offline fallback data from persistent cache.
        
        Returns:
            Cached library data or None if unavailable
        """
        try:
            cache_file = self.cache_dir / "music_library_cache.json"
            # Allow older cache for offline use (7 days max)
            fallback_data = read_json_cache(str(cache_file), max_age_seconds=7*24*3600)
            if fallback_data:
                self.logger.info("📱 Using offline fallback cache")
                return self._add_cache_metadata(fallback_data, cached=True, offline=True)
        except Exception as e:
            self.logger.debug(f"No offline fallback available: {e}")
        return None

    def invalidate(self, cache_type: Optional[CacheType] = None, 
                  pattern: Optional[str] = None) -> int:
        """Invalidate cache entries.
        
        Args:
            cache_type: Specific type to invalidate, or None for all
            pattern: Key pattern to match, or None for all
            
        Returns:
            Number of invalidated entries
        """
        with self._lock:
            keys_to_remove = []
            
            for key, entry in self._cache.items():
                should_remove = True
                
                if cache_type and entry.cache_type != cache_type:
                    should_remove = False
                if pattern and pattern not in key:
                    should_remove = False
                    
                if should_remove:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
            
            count = len(keys_to_remove)
            self.logger.info(f"🗑️ Invalidated {count} cache entries")
            return count

    def get_statistics(self) -> CacheStats:
        """Get comprehensive cache statistics.
        
        Returns:
            Cache performance and usage statistics
        """
        with self._lock:
            if self._stats['total_requests'] == 0:
                hit_rate = 0.0
            else:
                hit_rate = (self._stats['hits'] / self._stats['total_requests']) * 100
            
            # Analyze cache entries
            if not self._cache:
                return CacheStats(
                    total_entries=0,
                    hit_rate=hit_rate,
                    memory_usage_bytes=0,
                    oldest_entry=0,
                    most_accessed_type="none",
                    cache_efficiency="empty"
                )
            
            # Calculate memory usage (rough estimate)
            memory_usage = sum(len(str(entry.data)) for entry in self._cache.values())
            
            # Find oldest entry
            oldest = min(entry.timestamp for entry in self._cache.values())
            
            # Find most accessed type
            type_counts = {}
            for entry in self._cache.values():
                type_name = entry.cache_type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + entry.access_count
            
            most_accessed = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else "none"
            
            # Calculate efficiency rating
            if hit_rate >= 80:
                efficiency = "excellent"
            elif hit_rate >= 60:
                efficiency = "good"
            elif hit_rate >= 40:
                efficiency = "fair"
            else:
                efficiency = "poor"
            
            return CacheStats(
                total_entries=len(self._cache),
                hit_rate=hit_rate,
                memory_usage_bytes=memory_usage,
                oldest_entry=oldest,
                most_accessed_type=most_accessed,
                cache_efficiency=efficiency
            )

    def _add_cache_metadata(self, data: Dict[str, Any], cached: bool = False, 
                          offline: bool = False) -> Dict[str, Any]:
        """Add cache-related metadata to response data."""
        data = data.copy()  # Don't modify original
        data["cached"] = cached
        if offline:
            data["offline_mode"] = True
        return data

    def _maybe_cleanup(self) -> None:
        """Clean up expired entries if needed."""
        now = time.time()
        if (now - self._stats['last_cleanup']) < self._cleanup_interval:
            return
        
        expired_keys = []
        for key, entry in self._cache.items():
            if (now - entry.timestamp) > entry.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        self._stats['last_cleanup'] = now
        
        if expired_keys:
            self.logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")

    def clear(self) -> None:
        """Clear all cache data."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats = {
                'hits': 0,
                'misses': 0,
                'total_requests': 0,
                'last_cleanup': time.time()
            }
            self.logger.info(f"🗑️ Cleared all cache data ({count} entries)")


# Global cache instance
_global_cache: Optional[MusicLibraryCache] = None


def get_music_library_cache(project_root: Optional[Path] = None) -> MusicLibraryCache:
    """Get the global music library cache instance.
    
    Args:
        project_root: Optional project root path for cache files
        
    Returns:
        Global cache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = MusicLibraryCache(project_root)
    return _global_cache


def clear_music_library_cache() -> None:
    """Clear all cached music library data."""
    global _global_cache
    if _global_cache:
        _global_cache.clear()