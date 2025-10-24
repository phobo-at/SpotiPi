#!/usr/bin/env python3
"""
🎟️ Spotify Token Cache Manager for SpotiPi
Provides intelligent token caching with automatic refresh to minimize API calls.
Reduces Spotify API requests from ~50+ per minute to ~1 per hour.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional


@dataclass
class TokenResponse:
    """Normalized token refresh response from Spotify."""
    access_token: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    token_type: Optional[str] = None
    received_at: float = field(default_factory=time.time)

    @property
    def expires_at(self) -> float:
        return self.received_at + max(0, int(self.expires_in))


@dataclass
class CachedToken:
    """Represents a cached Spotify access token with metadata."""
    access_token: str
    expires_at: float  # Unix timestamp
    refresh_token: str
    created_at: float  # Unix timestamp
    refresh_count: int = 0
    scope: Optional[str] = None
    token_type: Optional[str] = None
    
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
    
    def __init__(self, refresh_function: Callable[[], Optional[TokenResponse]]):
        """
        Initialize token cache.
        
        Args:
            refresh_function: Function that returns a new access token
        """
        self._refresh_function = refresh_function
        self._cached_token: Optional[CachedToken] = None
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
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
        
        self._logger.debug("🎟️ Spotify Token Cache initialized")
    
    def get_valid_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Optional[str]: Valid access token or None if refresh fails
        """
        warn_minutes_left: Optional[int] = None
        token_value: Optional[str] = None

        with self._lock:
            self._metrics['total_requests'] += 1

            if self._cached_token and not self._cached_token.is_expired:
                self._metrics['cache_hits'] += 1
                token_value = self._cached_token.access_token
                if self._cached_token.is_nearly_expired:
                    warn_minutes_left = self._cached_token.time_until_expiry // 60
            else:
                self._metrics['cache_misses'] += 1

        if token_value:
            if warn_minutes_left is not None:
                self._logger.debug(
                    "⚠️ Token expires in %s minutes - will refresh soon",
                    warn_minutes_left,
                )
            return token_value

        return self._refresh_and_cache_token()

    def needs_refresh(self, window_seconds: int) -> bool:
        """Check whether the cached token will expire within the given window."""
        with self._lock:
            if self._cached_token is None:
                return True
            return self._cached_token.time_until_expiry <= window_seconds

    def ensure_fresh(self, window_seconds: int) -> Optional[str]:
        """
        Ensure a token is valid for at least the given number of seconds.

        Args:
            window_seconds: Minimum required validity period in seconds

        Returns:
            Optional[str]: Valid access token or None if refresh fails
        """
        with self._lock:
            self._metrics['total_requests'] += 1
            if self._cached_token and self._cached_token.time_until_expiry > window_seconds:
                self._metrics['cache_hits'] += 1
                return self._cached_token.access_token
            self._metrics['cache_misses'] += 1

        return self._refresh_and_cache_token()

    def seed(self, token_response: TokenResponse) -> None:
        """
        Seed the cache from a persisted token response.

        Args:
            token_response: Previously saved token response data
        """
        with self._lock:
            received_at = token_response.received_at or time.time()
            expires_in_seconds = max(60, int(token_response.expires_in))
            self._cached_token = CachedToken(
                access_token=token_response.access_token,
                expires_at=received_at + expires_in_seconds,
                refresh_token=token_response.refresh_token or "",
                created_at=received_at,
                refresh_count=0,
                scope=token_response.scope,
                token_type=token_response.token_type
            )
    
    def _refresh_and_cache_token(self) -> Optional[str]:
        """
        Refresh token and cache it.
        
        Returns:
            Optional[str]: New access token or None if refresh fails
        """
        with self._refresh_lock:
            with self._lock:
                if self._cached_token and not self._cached_token.is_expired:
                    return self._cached_token.access_token

            with self._lock:
                self._metrics['refresh_attempts'] += 1
                if self._cached_token:
                    age_minutes = self._cached_token.age_seconds // 60
                    old_token_info = f" (replacing {age_minutes}min old token)"
                else:
                    old_token_info = ""

            self._logger.debug("🔄 Refreshing Spotify access token%s", old_token_info)

            try:
                token_response = self._refresh_function()
            except Exception as exc:
                with self._lock:
                    self._metrics['refresh_failures'] += 1
                self._logger.error("❌ Token refresh failed with exception: %s", exc)
                return None

            if not token_response:
                with self._lock:
                    self._metrics['refresh_failures'] += 1
                self._logger.error("❌ Token refresh failed - no token returned")
                return None

            expires_in_seconds = max(60, int(token_response.expires_in))
            received_at = token_response.received_at or time.time()

            with self._lock:
                previous_refresh_count = self._cached_token.refresh_count if self._cached_token else 0
                refresh_token = token_response.refresh_token or (self._cached_token.refresh_token if self._cached_token else "")
                self._cached_token = CachedToken(
                    access_token=token_response.access_token,
                    expires_at=received_at + expires_in_seconds,
                    refresh_token=refresh_token,
                    created_at=received_at,
                    refresh_count=previous_refresh_count + 1,
                    scope=token_response.scope,
                    token_type=token_response.token_type
                )
                self._metrics['refresh_successes'] += 1
                expires_at_str = datetime.fromtimestamp(self._cached_token.expires_at).strftime("%H:%M:%S")
                token_value = self._cached_token.access_token

            self._logger.debug("✅ Token refreshed successfully (expires at %s)", expires_at_str)
            return token_value
    
    def force_refresh(self) -> Optional[str]:
        """
        Force a token refresh regardless of current token status.
        
        Returns:
            Optional[str]: New access token or None if refresh fails
        """
        self._logger.debug("🔄 Force refreshing token")
        return self._refresh_and_cache_token()
    
    def invalidate_cache(self) -> None:
        """Invalidate the current cached token."""
        with self._lock:
            if self._cached_token:
                self._logger.debug("🗑️ Invalidating cached token")
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

def initialize_token_cache(refresh_function: Callable[[], Optional[TokenResponse]]) -> None:
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
        Optional[str]: New access token or None if refresh fails
    """
    if _token_cache is None:
        logging.getLogger('app').error("❌ Token cache not initialized!")
        return None
    
    return _token_cache.force_refresh()

def ensure_token_valid(window_seconds: int) -> Optional[str]:
    """
    Ensure the cached token remains valid for the given window.

    Args:
        window_seconds: Minimum required validity window in seconds

    Returns:
        Optional[str]: Access token or None if refresh fails
    """
    if _token_cache is None:
        logging.getLogger('app').error("❌ Token cache not initialized!")
        return None

    return _token_cache.ensure_fresh(window_seconds)

def token_needs_refresh(window_seconds: int) -> bool:
    """
    Check whether the token will expire within the given window.

    Args:
        window_seconds: Time window in seconds

    Returns:
        bool: True if a refresh is required
    """
    if _token_cache is None:
        return True
    return _token_cache.needs_refresh(window_seconds)

def seed_token_cache(token_response: TokenResponse) -> None:
    """
    Seed the cache with a persisted token response.

    Args:
        token_response: Token response data
    """
    if _token_cache is not None:
        _token_cache.seed(token_response)

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
