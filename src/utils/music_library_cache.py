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
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
from enum import Enum

from .simple_cache import write_json_cache, read_json_cache

LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')


def _get_worker_limit() -> int:
    override = os.getenv('SPOTIPI_LIBRARY_WORKERS')
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            logging.getLogger('music_cache').warning(
                "Invalid SPOTIPI_LIBRARY_WORKERS=%s; using default",
                override
            )
    return 2 if LOW_POWER_MODE else 4


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
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'total_requests': 0,
            'last_cleanup': time.time()
        }

        try:
            self._max_entries = max(16, int(os.getenv('SPOTIPI_CACHE_MAX_ENTRIES', '64')))
        except ValueError:
            self._max_entries = 64
        
        # Paths for persistent cache
        if project_root:
            self.cache_dir = project_root / "cache"
        else:
            self.cache_dir = Path(__file__).parent.parent.parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # TTL configuration (seconds)
        def _parse_int(env_name: str, default: int) -> int:
            value = os.getenv(env_name)
            if value is None:
                return default
            try:
                return int(value)
            except ValueError:
                logging.getLogger('music_cache').warning(
                    "Invalid %s=%s; using %s",
                    env_name,
                    value,
                    default
                )
                return default

        library_minutes = _parse_int('SPOTIPI_LIBRARY_TTL_MINUTES', 60)
        library_minutes = min(120, max(30, library_minutes))
        legacy_library_seconds = os.getenv('SPOTIPI_MUSIC_CACHE_TTL')
        if legacy_library_seconds and not os.getenv('SPOTIPI_LIBRARY_TTL_MINUTES'):
            try:
                library_minutes = max(30, min(120, int(int(legacy_library_seconds) / 60)))
            except ValueError:
                pass
        library_ttl_seconds = library_minutes * 60

        device_ttl = _parse_int('SPOTIPI_DEVICE_TTL', 10)
        if 'SPOTIPI_DEVICE_TTL' not in os.environ and 'SPOTIPI_DEVICE_CACHE_TTL' in os.environ:
            device_ttl = _parse_int('SPOTIPI_DEVICE_CACHE_TTL', device_ttl)
        device_ttl = min(15, max(5, device_ttl))

        section_minutes = _parse_int('SPOTIPI_SECTION_TTL_MINUTES', library_minutes)
        section_minutes = min(120, max(30, section_minutes))
        section_ttl_seconds = section_minutes * 60

        self._ttl_config = {
            CacheType.FULL_LIBRARY: library_ttl_seconds,
            CacheType.PLAYLISTS: section_ttl_seconds,
            CacheType.ALBUMS: section_ttl_seconds,
            CacheType.TRACKS: section_ttl_seconds,
            CacheType.ARTISTS: section_ttl_seconds,
            CacheType.DEVICES: device_ttl,
        }
        
        # Auto-cleanup interval
        self._cleanup_interval = 300  # 5 minutes
        
        self.logger.info("🎵 Unified Music Library Cache initialized")

    def _scoped_cache_key(self, namespace: str, token: Optional[str]) -> str:
        """Build a stable cache key scoped to the current access token."""
        token_value = token or ""
        digest = hashlib.sha256(token_value.encode("utf-8")).hexdigest()[:16]
        return f"{namespace}_{digest}"

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
                self._metadata.pop(cache_key, None)
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_access = now
            self._stats['hits'] += 1
            
            self.logger.debug(f"✅ Cache hit for {cache_key} ({cache_type.value})")
            return entry.data

    def set(self, cache_key: str, data: Any, cache_type: CacheType,
            hash_value: Optional[str] = None, source: str = 'memory') -> None:
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
            self._metadata[cache_key] = {
                'timestamp': now,
                'ttl': ttl,
                'cache_type': cache_type.value,
                'hash': hash_value,
                'source': source,
            }
            self.logger.debug(f"💾 Cached {cache_key} ({cache_type.value}) TTL={ttl}s")
            
            if cache_type == CacheType.DEVICES:
                self._persist_device_cache(cache_key, data)

            self._evict_if_needed()
            # Trigger cleanup if needed
            self._maybe_cleanup()

    def _device_cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def _persist_device_cache(self, cache_key: str, data: Any) -> None:
        try:
            write_json_cache(str(self._device_cache_path(cache_key)), data)
            self.logger.debug("💾 Persisted devices to disk cache")
        except Exception as exc:
            self.logger.debug(f"⚠️ Could not persist device cache: {exc}")

    def _delete_device_cache_file(self, cache_key: str) -> None:
        path = self._device_cache_path(cache_key)
        try:
            if path.exists():
                path.unlink()
                self.logger.debug("🗑️ Removed device cache file")
        except Exception as exc:
            self.logger.debug(f"⚠️ Could not delete device cache file: {exc}")

    def _load_device_cache(self, cache_key: str) -> Optional[CacheEntry]:
        path = self._device_cache_path(cache_key)
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                payload = json.load(fp)
            cached_at = float(payload.get('_cached_at', 0))
            data = payload.get('data', [])
            if not cached_at:
                return None
            entry = CacheEntry(
                data=data,
                timestamp=cached_at,
                ttl=self._ttl_config[CacheType.DEVICES],
                cache_type=CacheType.DEVICES,
                hash_value=None,
                access_count=0,
                last_access=time.time()
            )
            self._cache[cache_key] = entry
            self._metadata[cache_key] = {
                'timestamp': cached_at,
                'ttl': entry.ttl,
                'cache_type': CacheType.DEVICES.value,
                'hash': None,
                'source': 'disk'
            }
            self.logger.debug("📀 Loaded devices from disk cache")
            return entry
        except Exception as exc:
            self.logger.debug(f"⚠️ Could not read device cache: {exc}")
            return None

    def _evict_if_needed(self) -> None:
        if len(self._cache) <= self._max_entries:
            return
        surplus = len(self._cache) - self._max_entries
        victims = sorted(
            self._cache.items(),
            key=lambda item: item[1].last_access or item[1].timestamp
        )
        for idx in range(surplus):
            key, entry = victims[idx]
            self.logger.debug(f"🧹 Evicting {key} ({entry.cache_type.value}) from cache")
            self._cache.pop(key, None)
            self._metadata.pop(key, None)

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
        cache_key = self._scoped_cache_key("full_library", token)
        
        if not force_refresh:
            cached_data = self.get(cache_key, CacheType.FULL_LIBRARY)
            if cached_data:
                result = self._add_cache_metadata(cached_data, cached=True)
                meta = self.get_metadata(cache_key)
                if meta:
                    result['cache'] = meta
                    result['lastUpdated'] = meta['timestamp']
                    if 'hash' not in result and meta.get('hash'):
                        result['hash'] = meta['hash']
                return result
        
        # Load fresh data
        self.logger.info("🔄 Loading fresh complete music library...")
        fresh_data = loader_func(token)
        
        # Cache the fresh data
        from ..utils.library_utils import compute_library_hash
        hash_value = fresh_data.get("hash") if isinstance(fresh_data, dict) else None
        if not hash_value:
            hash_value = compute_library_hash(fresh_data)
            if isinstance(fresh_data, dict):
                fresh_data["hash"] = hash_value
        self.set(cache_key, fresh_data, CacheType.FULL_LIBRARY, hash_value, source='network')
        
        # Also persist to disk for offline fallback
        try:
            cache_file = self.cache_dir / "music_library_cache.json"
            write_json_cache(str(cache_file), fresh_data)
            self.logger.debug("💾 Persisted library cache to disk")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not persist cache to disk: {e}")
        
        result = self._add_cache_metadata(fresh_data, cached=False)
        meta = self.get_metadata(cache_key)
        if meta:
            result['cache'] = meta
            result['lastUpdated'] = meta['timestamp']
            if meta.get('hash'):
                result['hash'] = meta['hash']
        elif isinstance(fresh_data, dict) and fresh_data.get("hash"):
            result['hash'] = fresh_data["hash"]
        return result

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
            cache_key = self._scoped_cache_key(section_name, token)
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
                self.set(cache_key, fresh_data, cache_type, source='network')
                section_cache_status[section_name] = False
                return fresh_data
            except Exception as e:
                self.logger.error(f"❌ Failed loading section {section_name}: {e}")
                return []
        
        # Load sections; skip thread overhead when only one section or worker limit is 1
        worker_limit = _get_worker_limit()
        max_workers = max(1, min(len(wanted), worker_limit))

        if max_workers == 1 or len(wanted) == 1:
            for sec in wanted:
                results[sec] = load_section(sec)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {sec: executor.submit(load_section, sec) for sec in wanted}
                for sec, future in future_map.items():
                    results[sec] = future.result()
        
        # Fill in empty sections
        for section in valid_sections:
            if section not in results:
                results[section] = []
        
        total_items = sum(len(results[s]) for s in wanted)
        section_meta: Dict[str, Dict[str, Any]] = {}
        for sec in wanted:
            meta = self.get_metadata(self._scoped_cache_key(sec, token))
            if meta:
                section_meta[sec] = meta
        
        return {
            **results,
            "total": total_items,
            "partial": True,
            "sections": wanted,
            "cached": section_cache_status,
            "cache": section_meta
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
        cache_key = self._scoped_cache_key("spotify_devices", token)

        disk_entry: Optional[CacheEntry] = None

        if not force_refresh:
            cached_devices = self.get(cache_key, CacheType.DEVICES)
            if cached_devices:
                return cached_devices
            disk_entry = self._load_device_cache(cache_key)
            if disk_entry:
                return disk_entry.data

        try:
            fresh_devices = loader_func(token)
            self.set(cache_key, fresh_devices, CacheType.DEVICES, source='network')
            return fresh_devices
        except Exception as e:
            self.logger.error(f"❌ Failed loading devices: {e}")
            if cache_key in self._cache:
                return self._cache[cache_key].data
            if not disk_entry:
                disk_entry = self._load_device_cache(cache_key)
            return disk_entry.data if disk_entry else []

    def get_metadata(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a cached entry including freshness info."""
        with self._lock:
            entry = self._cache.get(cache_key)
            meta = self._metadata.get(cache_key)
            if not entry and not meta:
                return None

            if meta:
                info = dict(meta)
            else:
                info = {
                    'timestamp': entry.timestamp if entry else 0,
                    'ttl': entry.ttl if entry else 0,
                    'cache_type': entry.cache_type.value if entry else None,
                    'hash': entry.hash_value if entry else None,
                    'source': 'memory' if entry else 'unknown'
                }

            timestamp = float(info.get('timestamp') or (entry.timestamp if entry else 0))
            ttl = int(info.get('ttl') or (entry.ttl if entry else 0))
            now = time.time()
            info['timestamp'] = timestamp
            info['ttl'] = ttl
            info['age'] = max(0.0, now - timestamp) if timestamp else 0.0
            info['expires_in'] = (timestamp + ttl) - now if ttl else 0.0
            info['stale'] = info['expires_in'] <= 0 if ttl else False
            return info

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
                entry = self._cache.pop(key, None)
                self._metadata.pop(key, None)
                if entry and entry.cache_type == CacheType.DEVICES:
                    self._delete_device_cache_file(key)
            
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
            self._metadata.pop(key, None)
        
        self._stats['last_cleanup'] = now
        
        if expired_keys:
            self.logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")

    def clear(self) -> None:
        """Clear all cache data."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._metadata.clear()
            self._stats = {
                'hits': 0,
                'misses': 0,
                'total_requests': 0,
                'last_cleanup': time.time()
            }
            try:
                for file in self.cache_dir.glob("spotify_devices_*.json"):
                    file.unlink()
            except Exception as exc:
                self.logger.debug(f"⚠️ Could not purge device cache files: {exc}")
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
