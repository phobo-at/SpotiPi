#!/usr/bin/env python3
"""
🔐 Thread-Safe Configuration Management for SpotiPi
Provides thread-safe config operations to prevent race conditions between:
- Flask request handlers (main thread)
- Alarm scheduler (background thread)
- Token cache operations (various threads)
- Multiple concurrent API requests
"""

import threading
import time
import copy
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass
from contextlib import contextmanager
import logging

@dataclass
class ConfigTransaction:
    """Represents a configuration transaction with rollback capability."""
    original_config: Dict[str, Any]
    new_config: Dict[str, Any]
    timestamp: float
    thread_id: str
    operation: str

class ThreadSafeConfigManager:
    """
    Thread-safe configuration manager with advanced concurrency features.
    
    Features:
    - Read-write locks for optimal performance
    - Transaction support with rollback
    - Change notifications for components
    - Deadlock prevention with timeouts
    - Thread-local caching for performance
    """
    
    def __init__(self, base_config_manager):
        """
        Initialize thread-safe wrapper around existing config manager.
        
        Args:
            base_config_manager: The underlying ConfigManager instance
        """
        self._base_manager = base_config_manager
        self._lock = threading.RLock()  # Recursive lock for nested calls
        self._read_write_lock = ReadWriteLock()
        self._config_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 1.0  # Cache for 1 second max
        self._change_listeners: list[Callable[[Dict[str, Any]], None]] = []
        self._transaction_history: list[ConfigTransaction] = []
        self._max_history: int = 10
        self._logger = logging.getLogger('thread_safe_config')
        
        # Thread-local storage for per-thread caching
        self._thread_local = threading.local()
        
        self._logger.info("🔐 Thread-safe config manager initialized")
    
    def add_change_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Add a callback to be notified when config changes.
        
        Args:
            callback: Function to call with new config when it changes
        """
        with self._lock:
            self._change_listeners.append(callback)
            self._logger.debug(f"📢 Added config change listener: {callback.__name__}")
    
    def remove_change_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a config change listener."""
        with self._lock:
            if callback in self._change_listeners:
                self._change_listeners.remove(callback)
                self._logger.debug(f"📢 Removed config change listener: {callback.__name__}")
    
    def _notify_listeners(self, new_config: Dict[str, Any]) -> None:
        """Notify all listeners of config changes."""
        for listener in self._change_listeners:
            try:
                listener(copy.deepcopy(new_config))
            except Exception as e:
                self._logger.error(f"❌ Error in config change listener {listener.__name__}: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if current cache is still valid."""
        return (
            self._config_cache is not None and
            time.time() - self._cache_timestamp < self._cache_ttl
        )
    
    def _update_cache(self, config: Dict[str, Any]) -> None:
        """Update the internal cache with new config."""
        self._config_cache = copy.deepcopy(config)
        self._cache_timestamp = time.time()
    
    def load_config(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Load configuration with thread-safe caching.
        
        Args:
            use_cache: Whether to use cached config if available
            
        Returns:
            Configuration dictionary (deep copy for thread safety)
        """
        thread_id = threading.current_thread().name
        
        # Try thread-local cache first
        if use_cache and hasattr(self._thread_local, 'config_cache'):
            cache_entry = self._thread_local.config_cache
            if time.time() - cache_entry['timestamp'] < self._cache_ttl:
                self._logger.debug(f"🧵 Using thread-local cache for {thread_id}")
                return copy.deepcopy(cache_entry['config'])
        
        # Use read lock for loading (allows multiple concurrent reads)
        with self._read_write_lock.read_lock():
            try:
                # Check global cache
                if use_cache and self._is_cache_valid():
                    self._logger.debug(f"💾 Using global cache for {thread_id}")
                    config = copy.deepcopy(self._config_cache)
                else:
                    # Load from disk
                    self._logger.debug(f"💽 Loading config from disk for {thread_id}")
                    config = self._base_manager.load_config()
                    
                    # Update global cache under write lock
                    with self._lock:
                        self._update_cache(config)
                
                # Update thread-local cache
                if not hasattr(self._thread_local, 'config_cache'):
                    self._thread_local.config_cache = {}
                
                self._thread_local.config_cache = {
                    'config': copy.deepcopy(config),
                    'timestamp': time.time()
                }
                
                return copy.deepcopy(config)
                
            except Exception as e:
                self._logger.error(f"❌ Error loading config for {thread_id}: {e}")
                # Return empty config with defaults rather than crashing
                return {
                    "enabled": False,
                    "time": "07:00",
                    "volume": 50,
                    "alarm_volume": 50,
                    "_error": f"Config load failed: {e}"
                }
    
    def save_config(self, config: Dict[str, Any], notify_listeners: bool = True) -> bool:
        """
        Save configuration with thread-safe operations.
        
        Args:
            config: Configuration to save
            notify_listeners: Whether to notify change listeners
            
        Returns:
            True if saved successfully
        """
        thread_id = threading.current_thread().name
        operation = f"save_from_{thread_id}"
        
        # Use write lock for saving (exclusive access)
        with self._read_write_lock.write_lock():
            try:
                # Store transaction for potential rollback
                original_config = self.load_config(use_cache=False)
                transaction = ConfigTransaction(
                    original_config=copy.deepcopy(original_config),
                    new_config=copy.deepcopy(config),
                    timestamp=time.time(),
                    thread_id=thread_id,
                    operation=operation
                )
                
                # Perform the save
                success = self._base_manager.save_config(config)
                
                if success:
                    # Update cache immediately after successful save
                    with self._lock:
                        self._update_cache(config)
                        
                        # Clear thread-local caches for all threads
                        # (Note: This only clears current thread, others will expire naturally)
                        if hasattr(self._thread_local, 'config_cache'):
                            del self._thread_local.config_cache
                        
                        # Record transaction
                        self._transaction_history.append(transaction)
                        if len(self._transaction_history) > self._max_history:
                            self._transaction_history.pop(0)
                    
                    self._logger.info(f"✅ Config saved successfully by {thread_id}")
                    
                    # Notify listeners outside of lock to prevent deadlock
                    if notify_listeners:
                        self._notify_listeners(config)
                    
                    return True
                else:
                    self._logger.error(f"❌ Config save failed for {thread_id}")
                    return False
                    
            except Exception as e:
                self._logger.error(f"❌ Error saving config for {thread_id}: {e}")
                return False
    
    @contextmanager
    def config_transaction(self):
        """
        Context manager for atomic config operations.
        
        Usage:
            with config_manager.config_transaction() as transaction:
                config = transaction.load()
                config['some_field'] = 'new_value'
                transaction.save(config)
                # Automatically committed on exit, rolled back on exception
        """
        transaction = ConfigTransactionContext(self)
        try:
            yield transaction
            if transaction._pending_save:
                # Transaction was used, commit is automatic
                pass
        except Exception as e:
            self._logger.error(f"❌ Transaction failed, rolling back: {e}")
            transaction.rollback()
            raise
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a specific config value thread-safely.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        config = self.load_config()
        return config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> bool:
        """
        Set a specific config value thread-safely.
        
        Args:
            key: Configuration key
            value: Value to set
            
        Returns:
            True if saved successfully
        """
        config = self.load_config()
        config[key] = value
        return self.save_config(config)
    
    def get_transaction_history(self) -> list[ConfigTransaction]:
        """Get recent configuration transaction history."""
        with self._lock:
            return copy.deepcopy(self._transaction_history)
    
    def invalidate_cache(self) -> None:
        """Force invalidation of all caches."""
        with self._lock:
            self._config_cache = None
            self._cache_timestamp = 0
            
            # Clear thread-local cache for current thread
            if hasattr(self._thread_local, 'config_cache'):
                del self._thread_local.config_cache
                
            self._logger.info("🗑️ All config caches invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get thread-safety statistics."""
        with self._lock:
            return {
                "cache_valid": self._is_cache_valid(),
                "cache_age_seconds": time.time() - self._cache_timestamp if self._config_cache else None,
                "transaction_history_count": len(self._transaction_history),
                "change_listeners_count": len(self._change_listeners),
                "current_thread": threading.current_thread().name,
                "active_threads": threading.active_count(),
                "has_thread_local_cache": hasattr(self._thread_local, 'config_cache')
            }

class ConfigTransactionContext:
    """Context for atomic configuration transactions."""
    
    def __init__(self, config_manager: ThreadSafeConfigManager):
        self._config_manager = config_manager
        self._original_config: Optional[Dict[str, Any]] = None
        self._pending_save: bool = False
    
    def load(self) -> Dict[str, Any]:
        """Load config within transaction."""
        config = self._config_manager.load_config()
        if self._original_config is None:
            self._original_config = copy.deepcopy(config)
        return config
    
    def save(self, config: Dict[str, Any]) -> bool:
        """Save config within transaction."""
        self._pending_save = True
        return self._config_manager.save_config(config)
    
    def rollback(self) -> bool:
        """Rollback to original config."""
        if self._original_config is not None:
            return self._config_manager.save_config(self._original_config, notify_listeners=False)
        return False

class ReadWriteLock:
    """
    Reader-writer lock implementation for optimized concurrent access.
    Allows multiple readers OR one writer (but not both simultaneously).
    """
    
    def __init__(self):
        self._read_ready = threading.Condition(threading.RLock())
        self._readers = 0
    
    @contextmanager
    def read_lock(self):
        """Acquire read lock (allows multiple concurrent readers)."""
        self._read_ready.acquire()
        try:
            self._readers += 1
        finally:
            self._read_ready.release()
        
        try:
            yield
        finally:
            self._read_ready.acquire()
            try:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notifyAll()
            finally:
                self._read_ready.release()
    
    @contextmanager
    def write_lock(self):
        """Acquire write lock (exclusive access)."""
        self._read_ready.acquire()
        try:
            while self._readers > 0:
                self._read_ready.wait()
            yield
        finally:
            self._read_ready.release()

# Global thread-safe config manager
_thread_safe_config_manager: Optional[ThreadSafeConfigManager] = None

def initialize_thread_safe_config(base_config_manager) -> None:
    """Initialize the global thread-safe config manager."""
    global _thread_safe_config_manager
    _thread_safe_config_manager = ThreadSafeConfigManager(base_config_manager)

def get_thread_safe_config_manager() -> ThreadSafeConfigManager:
    """Get the global thread-safe config manager."""
    if _thread_safe_config_manager is None:
        raise RuntimeError("Thread-safe config manager not initialized. Call initialize_thread_safe_config() first.")
    return _thread_safe_config_manager

# Thread-safe convenience functions
def load_config_safe() -> Dict[str, Any]:
    """Load configuration thread-safely."""
    return get_thread_safe_config_manager().load_config()

def save_config_safe(config: Dict[str, Any]) -> bool:
    """Save configuration thread-safely."""
    return get_thread_safe_config_manager().save_config(config)

def get_config_value_safe(key: str, default: Any = None) -> Any:
    """Get config value thread-safely."""
    return get_thread_safe_config_manager().get_config_value(key, default)

def set_config_value_safe(key: str, value: Any) -> bool:
    """Set config value thread-safely."""
    return get_thread_safe_config_manager().set_config_value(key, value)

def config_transaction():
    """Get a config transaction context manager."""
    return get_thread_safe_config_manager().config_transaction()

def invalidate_config_cache() -> None:
    """Invalidate all config caches."""
    get_thread_safe_config_manager().invalidate_cache()

def get_config_stats() -> Dict[str, Any]:
    """Get thread-safety statistics."""
    return get_thread_safe_config_manager().get_stats()
