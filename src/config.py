"""
Centralized configuration management for SpotiPi
Handles environment-specific configs and validation with thread safety

Since v1.3.8: Enhanced with Pydantic schema validation for type-safety
"""

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Pydantic schema validation (v1.3.8+)
try:
    from .config_schema import SpotiPiConfig, validate_config_dict, migrate_legacy_config
    SCHEMA_VALIDATION_AVAILABLE = True
except ImportError:
    SCHEMA_VALIDATION_AVAILABLE = False
    SpotiPiConfig = None  # type: ignore


class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent
        self.config_dir = self.base_path / "config"
        
        # Auto-detect environment based on platform
        self.environment = self._detect_environment()
        
    def _detect_environment(self) -> str:
        """Auto-detect environment based on platform and environment variables"""
        # Explicit environment variable takes precedence
        env_var = os.getenv("SPOTIPI_ENV")
        if env_var:
            return env_var
            
        # Auto-detect Raspberry Pi
        try:
            import platform
            is_raspberry_pi = (
                (platform.machine().startswith('arm') and platform.system() == 'Linux') or
                'raspberrypi' in platform.node().lower() or
                os.path.exists('/sys/firmware/devicetree/base/model') or
                os.getenv('SPOTIPI_RASPBERRY_PI') == '1'
            )
            
            return "production" if is_raspberry_pi else "development"
            
        except ImportError:
            # Fallback if platform module is not available
            return "development"
        
    def load_config(self, config_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration based on environment
        
        Args:
            config_name: Specific config file name (without .json)
                        If None, uses environment-based config
        
        Returns:
            Configuration dictionary
        """
        if config_name is None:
            config_name = self.environment
            
        config_file = self.config_dir / f"{config_name}.json"
        default_config_file = self.config_dir / "default_config.json"
        
        # Load default config first
        default_config = {}
        if default_config_file.exists():
            try:
                with open(default_config_file, 'r') as f:
                    default_config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load default config: {e}")
        
        # Load environment-specific config
        env_config = {}
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    env_config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {config_name} config: {e}")
        
        # Merge configs (environment overrides default)
        config = {**default_config, **env_config}
        
        # Add runtime environment info
        config["_runtime"] = {
            "environment": self.environment,
            "config_file": str(config_file),
            "base_path": str(self.base_path)
        }
        
        return self.validate_config(config)
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean configuration.
        
        Since v1.3.8: Uses Pydantic schema if available for strict validation.
        Falls back to legacy validation for backward compatibility.
        """
        logger = logging.getLogger(__name__)
        
        # Try Pydantic schema validation first (v1.3.8+)
        if SCHEMA_VALIDATION_AVAILABLE:
            try:
                # Migrate legacy formats if needed
                migrated_config = migrate_legacy_config(config)
                
                # Validate against schema
                validated_model, warnings = validate_config_dict(migrated_config)
                
                # Log any warnings
                for warning in warnings:
                    logger.warning(f"Config validation warning: {warning}")
                
                # Convert back to dict for runtime use
                validated_dict = validated_model.to_dict()
                
                # Preserve runtime metadata
                if "_runtime" in config:
                    validated_dict["_runtime"] = config["_runtime"]
                
                logger.debug("✅ Configuration validated against Pydantic schema")
                return validated_dict
                
            except ValueError as e:
                logger.error(f"❌ Configuration schema validation failed: {e}")
                logger.warning("Falling back to legacy validation (data may be incomplete)")
                # Fall through to legacy validation
            except Exception as e:
                logger.warning(f"Unexpected error in schema validation: {e}")
                # Fall through to legacy validation
        
        # Legacy validation (pre-v1.3.8 compatibility)
        return self._legacy_validate_config(config)
    
    def _legacy_validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy validation for backward compatibility."""
        # Ensure required fields have defaults
        defaults = {
            "time": "07:00",
            "enabled": False,
            "playlist_uri": "",
            "device_name": "",
            "alarm_volume": 50,
            "fade_in": False,
            "shuffle": False,
            "debug": False,
            "log_level": "INFO",
            "timezone": os.getenv("SPOTIPI_TIMEZONE", "Europe/Vienna"),
            "last_known_devices": {},
        }
        
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = copy.deepcopy(default_value)
        
        # Validate types and ranges
        try:
            config["alarm_volume"] = max(0, min(100, int(config.get("alarm_volume", 50))))
        except (ValueError, TypeError):
            config["alarm_volume"] = 50
        
        # Validate last known devices cache
        last_known_devices = config.get("last_known_devices", {})
        if not isinstance(last_known_devices, dict):
            last_known_devices = {}
        config["last_known_devices"] = last_known_devices
        
        # Validate time format
        try:
            from datetime import datetime
            datetime.strptime(config["time"], "%H:%M")
        except ValueError:
            config["time"] = "07:00"

        # Validate timezone
        tz_value = str(config.get("timezone") or "").strip()
        if not tz_value:
            tz_value = "Europe/Vienna"
        try:
            ZoneInfo(tz_value)
            config["timezone"] = tz_value
        except (ZoneInfoNotFoundError, ValueError):
            logging.getLogger(__name__).warning(
                "Invalid timezone '%s' in config – falling back to Europe/Vienna",
                tz_value,
            )
            config["timezone"] = "Europe/Vienna"

        return config
    
    def save_config(self, config: Dict[str, Any], config_name: Optional[str] = None) -> bool:
        """
        Save configuration to file
        
        Args:
            config: Configuration to save
            config_name: Config file name (without .json)
        
        Returns:
            True if saved successfully
        """
        if config_name is None:
            config_name = self.environment
            
        config_file = self.config_dir / f"{config_name}.json"
        
        try:
            # Use Pydantic serialization if available (v1.3.8+) for cleaner output
            if SCHEMA_VALIDATION_AVAILABLE:
                try:
                    validated_model, _ = validate_config_dict(config)
                    save_data = validated_model.to_json_safe()
                except Exception:
                    # Fallback to manual filtering
                    save_data = {k: v for k, v in config.items() if not k.startswith("_")}
            else:
                save_data = {k: v for k, v in config.items() if not k.startswith("_")}
            
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            return True
        except (IOError, json.JSONDecodeError):
            return False
    
    def get_environment(self) -> str:
        """Get current environment"""
        return self.environment
    
    def set_environment(self, environment: str) -> None:
        """Set environment for config loading"""
        self.environment = environment
    
    def list_available_configs(self) -> list[str]:
        """List all available configuration files"""
        if not self.config_dir.exists():
            return []
        
        configs = []
        for config_file in self.config_dir.glob("*.json"):
            configs.append(config_file.stem)
        
        return sorted(configs)

# Global config manager instance
config_manager = ConfigManager()

# Initialize thread-safe config system
from .utils.thread_safety import (initialize_thread_safe_config,  # noqa: E402
                                  load_config_safe, save_config_safe)

initialize_thread_safe_config(config_manager)

# Global constants for backward compatibility
CONFIG_FILE = str(config_manager.config_dir / f"{config_manager.environment}.json")

# Thread-safe convenience functions (replacing old unsafe ones)
def load_config() -> Dict[str, Any]:
    """Load current environment configuration (THREAD-SAFE)"""
    return load_config_safe()

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration (THREAD-SAFE)"""
    return save_config_safe(config)

def get_config_value(key: str, default: Any = None) -> Any:
    """Get specific configuration value (THREAD-SAFE)"""
    from .utils.thread_safety import get_config_value_safe
    return get_config_value_safe(key, default)

def set_config_value(key: str, value: Any) -> bool:
    """Set specific configuration value (THREAD-SAFE)"""
    from .utils.thread_safety import set_config_value_safe
    return set_config_value_safe(key, value)
