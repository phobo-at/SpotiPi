#!/usr/bin/env python3
"""
🎟️ Spotify Token Cache Manager for SpotiPi
Provides intelligent token caching with automatic refresh to minimize API calls.
Reduces Spotify API requests from ~50+ per minute to ~1 per hour.
"""

import time
import threading
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CachedToken:
    """Represents a cached Spotify access token with metadata."""
    access_token: str
    expires_at: float  # Unix timestamp
    refresh_token: str
    created_at: float  # Unix timestamp
    refresh_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 5-minute buffer)."""
        buffer_seconds = 5 * 60  # 5 minutes buffer
        return time.time() >= (self.expires_at - buffer_seconds)
    
    @property
    def is_nearly_expired(self) -> bool:
        """Check if token expires within 10 minutes."""
        buffer_seconds = 10 * 60  # 10 minutes buffer
        return time.time() >= (self.expires_at - buffer_seconds)
    
    @property
    def time_until_expiry(self) -> int:
        """Get seconds until token expires."""
        return max(0, int(self.expires_at - time.time()))
    
    @property
    def age_seconds(self) -> int:
        """Get token age in seconds."""
        return int(time.time() - self.created_at)

class SpotifyTokenCache:
    """
    Intelligent Spotify token cache with automatic refresh.
    
    Features:
    - Automatic token refresh before expiration
    - Thread-safe operations
    - Performance metrics
    - Error resilience with fallback
    """
    
    def __init__(self, refresh_function: Callable[[], Optional[str]]):
        """
        Initialize token cache.
        
        Args:
            refresh_function: Function that returns a new access token
        """
        self._refresh_function = refresh_function
        self._cached_token: Optional[CachedToken] = None
        self._lock = threading.RLock()
        self._logger = logging.getLogger('app')
        
        # Performance metrics
        self._metrics = {
            'cache_hits': 0,
            'cache_misses': 0,
            'refresh_attempts': 0,
            'refresh_successes': 0,
            'refresh_failures': 0,
            'total_requests': 0
        }
        
        self._logger.info("🎟️ Spotify Token Cache initialized")
    
    def get_valid_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Optional[str]: Valid access token or None if refresh fails
        """
        with self._lock:
            self._metrics['total_requests'] += 1
            
            # Check if we have a valid cached token
            if self._cached_token and not self._cached_token.is_expired:
                self._metrics['cache_hits'] += 1
                
                # Log near-expiry warning
                if self._cached_token.is_nearly_expired:
                    minutes_left = self._cached_token.time_until_expiry // 60
                    self._logger.debug(f"⚠️ Token expires in {minutes_left} minutes - will refresh soon")
                
                return self._cached_token.access_token
            
            # Token is expired or doesn't exist - refresh it
            self._metrics['cache_misses'] += 1
            return self._refresh_and_cache_token()
    
    def _refresh_and_cache_token(self) -> Optional[str]:
        """
        Refresh token and cache it.
        
        Returns:
            Optional[str]: New access token or None if refresh fails
        """
        self._metrics['refresh_attempts'] += 1
        old_token_info = ""
        
        if self._cached_token:
            age_minutes = self._cached_token.age_seconds // 60
            old_token_info = f" (replacing {age_minutes}min old token)"
        
        self._logger.info(f"🔄 Refreshing Spotify access token{old_token_info}")
        
        try:
            # Call the provided refresh function
            new_access_token = self._refresh_function()
            
            if new_access_token:
                # Cache the new token (Spotify tokens typically expire in 1 hour)
                expires_in_seconds = 3600  # 1 hour
                current_time = time.time()
                
                self._cached_token = CachedToken(
                    access_token=new_access_token,
                    expires_at=current_time + expires_in_seconds,
                    refresh_token="",  # We don't need to store refresh token here
                    created_at=current_time,
                    refresh_count=self._cached_token.refresh_count + 1 if self._cached_token else 1
                )
                
                self._metrics['refresh_successes'] += 1
                
                expires_at_str = datetime.fromtimestamp(self._cached_token.expires_at).strftime("%H:%M:%S")
                self._logger.info(f"✅ Token refreshed successfully (expires at {expires_at_str})")
                
                return new_access_token
            else:
                self._metrics['refresh_failures'] += 1
                self._logger.error("❌ Token refresh failed - no token returned")
                return None
                
        except Exception as e:
            self._metrics['refresh_failures'] += 1
            self._logger.error(f"❌ Token refresh failed with exception: {e}")
            return None
    
    def force_refresh(self) -> Optional[str]:
        """
        Force a token refresh regardless of current token status.
        
        Returns:
            Optional[str]: New access token or None if refresh fails
        """
        with self._lock:
            self._logger.info("🔄 Force refreshing token")
            return self._refresh_and_cache_token()
    
    def invalidate_cache(self) -> None:
        """Invalidate the current cached token."""
        with self._lock:
            if self._cached_token:
                self._logger.info("🗑️ Invalidating cached token")
                self._cached_token = None
            else:
                self._logger.debug("🗑️ No cached token to invalidate")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get detailed cache information and performance metrics.
        
        Returns:
            Dict[str, Any]: Cache status and metrics
        """
        with self._lock:
            info = {
                'cache_metrics': self._metrics.copy(),
                'has_cached_token': self._cached_token is not None,
                'performance': {}
            }
            
            # Calculate cache hit rate
            total_token_requests = self._metrics['cache_hits'] + self._metrics['cache_misses']
            if total_token_requests > 0:
                hit_rate = (self._metrics['cache_hits'] / total_token_requests) * 100
                info['performance']['cache_hit_rate_percent'] = round(hit_rate, 1)
            
            # Calculate refresh success rate
            if self._metrics['refresh_attempts'] > 0:
                success_rate = (self._metrics['refresh_successes'] / self._metrics['refresh_attempts']) * 100
                info['performance']['refresh_success_rate_percent'] = round(success_rate, 1)
            
            # Add token-specific info if available
            if self._cached_token:
                info['token_info'] = {
                    'age_seconds': self._cached_token.age_seconds,
                    'age_minutes': self._cached_token.age_seconds // 60,
                    'time_until_expiry_seconds': self._cached_token.time_until_expiry,
                    'time_until_expiry_minutes': self._cached_token.time_until_expiry // 60,
                    'is_expired': self._cached_token.is_expired,
                    'is_nearly_expired': self._cached_token.is_nearly_expired,
                    'refresh_count': self._cached_token.refresh_count,
                    'expires_at': datetime.fromtimestamp(self._cached_token.expires_at).strftime("%Y-%m-%d %H:%M:%S")
                }
            
            return info
    
    def log_performance_summary(self) -> None:
        """Log a performance summary of the token cache."""
        info = self.get_cache_info()
        metrics = info['cache_metrics']
        performance = info['performance']
        
        self._logger.info("📊 Token Cache Performance Summary:")
        self._logger.info(f"   Total requests: {metrics['total_requests']}")
        self._logger.info(f"   Cache hits: {metrics['cache_hits']}")
        self._logger.info(f"   Cache misses: {metrics['cache_misses']}")
        self._logger.info(f"   Token refreshes: {metrics['refresh_successes']}/{metrics['refresh_attempts']}")
        
        if 'cache_hit_rate_percent' in performance:
            self._logger.info(f"   Cache hit rate: {performance['cache_hit_rate_percent']}%")
        
        if 'refresh_success_rate_percent' in performance:
            self._logger.info(f"   Refresh success rate: {performance['refresh_success_rate_percent']}%")
        
        if info['has_cached_token']:
            token_info = info['token_info']
            self._logger.info(f"   Current token: {token_info['age_minutes']}min old, expires in {token_info['time_until_expiry_minutes']}min")

# Global token cache instance (will be initialized in spotify.py)
_token_cache: Optional[SpotifyTokenCache] = None

def initialize_token_cache(refresh_function: Callable[[], Optional[str]]) -> None:
    """
    Initialize the global token cache.
    
    Args:
        refresh_function: Function to call for token refresh
    """
    global _token_cache
    _token_cache = SpotifyTokenCache(refresh_function)

def get_cached_token() -> Optional[str]:
    """
    Get a valid cached token.
    
    Returns:
        Optional[str]: Valid access token or None
    """
    if _token_cache is None:
        logging.getLogger('app').error("❌ Token cache not initialized!")
        return None
    
    return _token_cache.get_valid_token()

def force_token_refresh() -> Optional[str]:
    """
    Force refresh the cached token.
    
    Returns:
        Optional[str]: New access token or None
    """
    if _token_cache is None:
        logging.getLogger('app').error("❌ Token cache not initialized!")
        return None
    
    return _token_cache.force_refresh()

def invalidate_token_cache() -> None:
    """Invalidate the current token cache."""
    if _token_cache is not None:
        _token_cache.invalidate_cache()

def get_token_cache_info() -> Dict[str, Any]:
    """
    Get token cache information.
    
    Returns:
        Dict[str, Any]: Cache information or empty dict if not initialized
    """
    if _token_cache is None:
        return {'error': 'Token cache not initialized'}
    
    return _token_cache.get_cache_info()

def log_token_cache_performance() -> None:
    """Log token cache performance summary."""
    if _token_cache is not None:
        _token_cache.log_performance_summary()
