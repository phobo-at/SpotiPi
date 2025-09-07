#!/usr/bin/env python3
"""
🚦 Rate Limiting System for SpotiPi
Provides comprehensive rate limiting to protect against:
- API abuse and DoS attacks
- Spot        # Very strict for config changes
        self.add_rule(RateLimitRule(
            name="config_changes",
            requests_per_window=10,
            window_seconds=60,
            limit_type=RateLimitType.FIXED_WINDOW,
            block_duration_seconds=300  # 5 minutes block
        ))
        
        # Frequent status checks allowed
        self.add_rule(RateLimitRule(
            name="status_check",
            requests_per_window=200,
            window_seconds=60,
            limit_type=RateLimitType.SLIDING_WINDOW,
            block_duration_seconds=30
        ))
        
        # Spotify API calls - respect their limits
        self.add_rule(RateLimitRule(
            name="spotify_api",
            requests_per_window=50,
            window_seconds=60,
            limit_type=RateLimitType.SLIDING_WINDOW,
            block_duration_seconds=120
        ))rate limit violations
- Resource exhaustion from excessive requests
- Brute force attempts on sensitive endpoints
"""

import time
import threading
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from functools import wraps
import hashlib
import logging
from flask import request, jsonify, g
from enum import Enum

class RateLimitType(Enum):
    """Types of rate limits with different strategies."""
    FIXED_WINDOW = "fixed_window"      # Traditional rate limiting
    SLIDING_WINDOW = "sliding_window"  # More accurate, smoother
    TOKEN_BUCKET = "token_bucket"      # Burst tolerance
    ADAPTIVE = "adaptive"              # Dynamic based on load

@dataclass
class RateLimitRule:
    """Defines a rate limiting rule."""
    name: str
    requests_per_window: int
    window_seconds: int
    limit_type: RateLimitType = RateLimitType.SLIDING_WINDOW
    burst_allowance: int = 0           # Extra requests for token bucket
    block_duration_seconds: int = 60   # How long to block after limit exceeded
    exempt_ips: List[str] = field(default_factory=list)
    priority: int = 100                # Lower number = higher priority

@dataclass 
class RateLimitStatus:
    """Current status of rate limiting for a client."""
    requests_made: int
    requests_remaining: int
    window_reset_time: float
    is_blocked: bool
    block_expires_at: Optional[float] = None
    total_requests: int = 0
    first_request_time: float = 0

class RateLimitStorage:
    """Thread-safe storage for rate limit data."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._client_data: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._cleanup_interval = 300  # Clean up every 5 minutes
        self._last_cleanup = time.time()
    
    def get_client_data(self, client_id: str, rule_name: str) -> Dict[str, Any]:
        """Get rate limit data for a client and rule."""
        with self._lock:
            return self._client_data[client_id].get(rule_name, {
                'requests': deque(),
                'tokens': 0,
                'last_refill': time.time(),
                'blocked_until': 0,
                'total_requests': 0,
                'first_request': time.time()
            })
    
    def set_client_data(self, client_id: str, rule_name: str, data: Dict[str, Any]) -> None:
        """Set rate limit data for a client and rule."""
        with self._lock:
            self._client_data[client_id][rule_name] = data
            self._maybe_cleanup()
    
    def _maybe_cleanup(self) -> None:
        """Clean up old rate limit data."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        # Remove data older than 1 hour
        cutoff = now - 3600
        
        clients_to_remove = []
        for client_id, rules_data in self._client_data.items():
            rules_to_remove = []
            for rule_name, data in rules_data.items():
                if data.get('first_request', now) < cutoff:
                    rules_to_remove.append(rule_name)
            
            for rule_name in rules_to_remove:
                del rules_data[rule_name]
            
            if not rules_data:
                clients_to_remove.append(client_id)
        
        for client_id in clients_to_remove:
            del self._client_data[client_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._lock:
            return {
                'total_clients': len(self._client_data),
                'total_rules_tracked': sum(len(rules) for rules in self._client_data.values()),
                'last_cleanup': self._last_cleanup,
                'memory_usage_estimate': len(str(self._client_data))
            }
    
    def clear(self) -> None:
        """Clear all rate limiting data."""
        with self._lock:
            self._client_data.clear()
            self._last_cleanup = time.time()

class RateLimiter:
    """Advanced rate limiting engine with multiple strategies."""
    
    def __init__(self):
        self._rules: Dict[str, RateLimitRule] = {}
        self._storage = RateLimitStorage()
        self._logger = logging.getLogger('rate_limiter')
        self._enabled = True
        self._global_stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'start_time': time.time()
        }
        
        # Default rules
        self._register_default_rules()
        
        self._logger.info("🚦 Rate limiter initialized")
    
    def _register_default_rules(self) -> None:
        """Register default rate limiting rules."""
        
        # General API protection
        self.add_rule(RateLimitRule(
            name="api_general",
            requests_per_window=100,
            window_seconds=60,
            limit_type=RateLimitType.SLIDING_WINDOW,
            block_duration_seconds=60
        ))
        
        # Strict limit for sensitive endpoints
        self.add_rule(RateLimitRule(
            name="api_strict",
            requests_per_window=20,
            window_seconds=60,
            limit_type=RateLimitType.SLIDING_WINDOW,
            block_duration_seconds=300  # 5 minutes block
        ))
        
        # Very strict for config changes
        self.add_rule(RateLimitRule(
            name="config_changes",
            requests_per_window=10,
            window_seconds=60,
            limit_type=RateLimitType.FIXED_WINDOW,
            block_duration_seconds=600  # 10 minutes block
        ))
        
        # Burst-tolerant for music library
        self.add_rule(RateLimitRule(
            name="music_library", 
            requests_per_window=30,
            window_seconds=60,
            limit_type=RateLimitType.TOKEN_BUCKET,
            burst_allowance=10,  # Allow 10 extra requests in burst
            block_duration_seconds=120
        ))
        
        # Spotify API protection (very conservative)
        self.add_rule(RateLimitRule(
            name="spotify_api",
            requests_per_window=50,  # Spotify allows ~100/minute
            window_seconds=60,
            limit_type=RateLimitType.SLIDING_WINDOW,
            block_duration_seconds=300
        ))
        
        # Frequent status checks allowed
        self.add_rule(RateLimitRule(
            name="status_check",
            requests_per_window=200,
            window_seconds=60,
            limit_type=RateLimitType.SLIDING_WINDOW,
            block_duration_seconds=30
        ))
    
    def add_rule(self, rule: RateLimitRule) -> None:
        """Add a rate limiting rule."""
        self._rules[rule.name] = rule
        self._logger.info(f"📋 Added rate limit rule: {rule.name} ({rule.requests_per_window}/{rule.window_seconds}s)")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rate limiting rule."""
        if rule_name in self._rules:
            del self._rules[rule_name]
            self._logger.info(f"🗑️ Removed rate limit rule: {rule_name}")
            return True
        return False
    
    def _get_client_id(self, request_obj=None) -> str:
        """Generate client identifier for rate limiting."""
        if request_obj is None:
            request_obj = request
        
        # Use IP address + User-Agent hash for identification
        ip = request_obj.environ.get('HTTP_X_FORWARDED_FOR', request_obj.remote_addr)
        user_agent = request_obj.headers.get('User-Agent', '')
        
        # Create stable client ID
        client_data = f"{ip}:{hashlib.md5(user_agent.encode()).hexdigest()[:8]}"
        return client_data
    
    def _check_sliding_window(self, client_id: str, rule: RateLimitRule) -> RateLimitStatus:
        """Check rate limit using sliding window algorithm."""
        now = time.time()
        data = self._storage.get_client_data(client_id, rule.name)
        
        requests = data['requests']
        window_start = now - rule.window_seconds
        
        # Remove old requests outside the window
        while requests and requests[0] <= window_start:
            requests.popleft()
        
        # Check if blocked
        if data['blocked_until'] > now:
            return RateLimitStatus(
                requests_made=len(requests),
                requests_remaining=0,
                window_reset_time=data['blocked_until'],
                is_blocked=True,
                block_expires_at=data['blocked_until'],
                total_requests=data['total_requests']
            )
        
        # Check if limit exceeded
        if len(requests) >= rule.requests_per_window:
            # Block the client
            data['blocked_until'] = now + rule.block_duration_seconds
            self._storage.set_client_data(client_id, rule.name, data)
            
            return RateLimitStatus(
                requests_made=len(requests),
                requests_remaining=0,
                window_reset_time=data['blocked_until'],
                is_blocked=True,
                block_expires_at=data['blocked_until'],
                total_requests=data['total_requests']
            )
        
        # Allow request
        requests.append(now)
        data['total_requests'] += 1
        if data['total_requests'] == 1:
            data['first_request'] = now
        
        self._storage.set_client_data(client_id, rule.name, data)
        
        return RateLimitStatus(
            requests_made=len(requests),
            requests_remaining=rule.requests_per_window - len(requests),
            window_reset_time=now + rule.window_seconds,
            is_blocked=False,
            total_requests=data['total_requests'],
            first_request_time=data['first_request']
        )
    
    def _check_token_bucket(self, client_id: str, rule: RateLimitRule) -> RateLimitStatus:
        """Check rate limit using token bucket algorithm."""
        now = time.time()
        data = self._storage.get_client_data(client_id, rule.name)
        
        # Check if blocked
        if data['blocked_until'] > now:
            return RateLimitStatus(
                requests_made=0,
                requests_remaining=0,
                window_reset_time=data['blocked_until'],
                is_blocked=True,
                block_expires_at=data['blocked_until'],
                total_requests=data['total_requests']
            )
        
        # Refill tokens
        time_passed = now - data['last_refill']
        max_tokens = rule.requests_per_window + rule.burst_allowance
        refill_rate = rule.requests_per_window / rule.window_seconds
        tokens_to_add = time_passed * refill_rate
        
        data['tokens'] = min(max_tokens, data['tokens'] + tokens_to_add)
        data['last_refill'] = now
        
        # Check if tokens available
        if data['tokens'] < 1:
            # Block if no tokens and this would exceed normal rate
            requests = data.get('requests', deque())
            window_start = now - rule.window_seconds
            
            # Clean old requests
            while requests and requests[0] <= window_start:
                requests.popleft()
            
            if len(requests) >= rule.requests_per_window:
                data['blocked_until'] = now + rule.block_duration_seconds
                self._storage.set_client_data(client_id, rule.name, data)
                
                return RateLimitStatus(
                    requests_made=len(requests),
                    requests_remaining=0,
                    window_reset_time=data['blocked_until'],
                    is_blocked=True,
                    block_expires_at=data['blocked_until'],
                    total_requests=data['total_requests']
                )
        
        # Consume token
        if data['tokens'] >= 1:
            data['tokens'] -= 1
            data['total_requests'] += 1
            
            # Track requests for window calculation
            if 'requests' not in data:
                data['requests'] = deque()
            data['requests'].append(now)
            
            if data['total_requests'] == 1:
                data['first_request'] = now
            
            self._storage.set_client_data(client_id, rule.name, data)
            
            return RateLimitStatus(
                requests_made=rule.requests_per_window - int(data['tokens']),
                requests_remaining=int(data['tokens']),
                window_reset_time=now + (max_tokens - data['tokens']) / refill_rate,
                is_blocked=False,
                total_requests=data['total_requests'],
                first_request_time=data.get('first_request', now)
            )
        
        # No tokens available
        return RateLimitStatus(
            requests_made=rule.requests_per_window,
            requests_remaining=0,
            window_reset_time=now + (1 / refill_rate),
            is_blocked=True,
            total_requests=data['total_requests']
        )
    
    def check_rate_limit(self, rule_name: str, client_id: Optional[str] = None) -> RateLimitStatus:
        """Check if request is allowed under rate limit."""
        if not self._enabled:
            return RateLimitStatus(
                requests_made=0,
                requests_remaining=999999,
                window_reset_time=time.time() + 3600,
                is_blocked=False
            )
        
        self._global_stats['total_requests'] += 1
        
        if client_id is None:
            client_id = self._get_client_id()
        
        rule = self._rules.get(rule_name)
        if not rule:
            self._logger.warning(f"⚠️ Unknown rate limit rule: {rule_name}")
            return RateLimitStatus(
                requests_made=0,
                requests_remaining=999999,
                window_reset_time=time.time() + 3600,
                is_blocked=False
            )
        
        # Check if client is exempt
        client_ip = client_id.split(':')[0]
        if client_ip in rule.exempt_ips:
            return RateLimitStatus(
                requests_made=0,
                requests_remaining=999999,
                window_reset_time=time.time() + 3600,
                is_blocked=False
            )
        
        # Apply rate limiting based on type
        if rule.limit_type == RateLimitType.TOKEN_BUCKET:
            status = self._check_token_bucket(client_id, rule)
        else:  # SLIDING_WINDOW or FIXED_WINDOW
            status = self._check_sliding_window(client_id, rule)
        
        if status.is_blocked:
            self._global_stats['blocked_requests'] += 1
            self._logger.warning(f"🚫 Rate limit exceeded for {client_id} on rule {rule_name}")
        
        return status
    
    def is_request_allowed(self, rule_name: str, client_id: Optional[str] = None) -> bool:
        """Simple boolean check if request is allowed."""
        status = self.check_rate_limit(rule_name, client_id)
        return not status.is_blocked
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive rate limiter statistics."""
        uptime = time.time() - self._global_stats['start_time']
        storage_stats = self._storage.get_stats()
        
        return {
            'enabled': self._enabled,
            'uptime_seconds': uptime,
            'global_stats': self._global_stats.copy(),
            'storage_stats': storage_stats,
            'rules': {
                name: {
                    'requests_per_window': rule.requests_per_window,
                    'window_seconds': rule.window_seconds,
                    'limit_type': rule.limit_type.value,
                    'block_duration': rule.block_duration_seconds
                }
                for name, rule in self._rules.items()
            },
            'requests_per_second': self._global_stats['total_requests'] / max(uptime, 1),
            'block_rate_percent': (
                self._global_stats['blocked_requests'] / max(self._global_stats['total_requests'], 1)
            ) * 100
        }
    
    def enable(self) -> None:
        """Enable rate limiting."""
        self._enabled = True
        self._logger.info("🟢 Rate limiting enabled")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Alias for get_stats() for API compatibility."""
        return self.get_stats()
    
    def disable(self) -> None:
        """Disable rate limiting (for debugging)."""
        self._enabled = False
        self._logger.warning("🔴 Rate limiting disabled")

# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

def rate_limit(rule_name: str, error_response: Optional[Dict[str, Any]] = None):
    """
    Decorator for rate limiting Flask endpoints.
    
    Args:
        rule_name: Name of the rate limiting rule to apply
        error_response: Custom error response (optional)
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            status = limiter.check_rate_limit(rule_name)
            
            if status.is_blocked:
                response = error_response or {
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {int(status.window_reset_time - time.time())} seconds.",
                    "rate_limit": {
                        "requests_made": status.requests_made,
                        "requests_remaining": status.requests_remaining,
                        "reset_time": status.window_reset_time,
                        "block_expires_at": status.block_expires_at
                    }
                }
                
                # Add rate limit headers
                resp = jsonify(response)
                resp.status_code = 429  # Too Many Requests
                resp.headers['X-RateLimit-Limit'] = str(limiter._rules[rule_name].requests_per_window)
                resp.headers['X-RateLimit-Remaining'] = str(status.requests_remaining)
                resp.headers['X-RateLimit-Reset'] = str(int(status.window_reset_time))
                resp.headers['Retry-After'] = str(int(status.window_reset_time - time.time()))
                
                return resp
            
            # Add rate limit info to Flask global context
            g.rate_limit_status = status
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def add_rate_limit_headers(response):
    """Add rate limit headers to response."""
    if hasattr(g, 'rate_limit_status'):
        status = g.rate_limit_status
        response.headers['X-RateLimit-Remaining'] = str(status.requests_remaining)
        response.headers['X-RateLimit-Reset'] = str(int(status.window_reset_time))
    return response
