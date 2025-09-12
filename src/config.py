"""
Centralized configuration management for SpotiPi
Handles environment-specific configs and validation with thread safety
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

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
        """Validate and clean configuration"""
        # Ensure required fields have defaults
        defaults = {
            "time": "07:00",
            "enabled": False,
            "playlist_uri": "",
            "device_name": "",
            "volume": 50,
            "alarm_volume": 50,
            "fade_in": False,
            "shuffle": False,
            "weekdays": [],
            "debug": False,
            "log_level": "INFO"
        }
        
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value
        
        # Validate types and ranges
        try:
            config["volume"] = max(0, min(100, int(config.get("volume", 50))))
            config["alarm_volume"] = max(0, min(100, int(config.get("alarm_volume", 50))))
        except (ValueError, TypeError):
            config["volume"] = 50
            config["alarm_volume"] = 50
        
        # Validate weekdays
        weekdays = config.get("weekdays", [])
        if isinstance(weekdays, list):
            # Remove duplicates and filter valid weekdays (0-6)
            valid_weekdays = list(set([day for day in weekdays if isinstance(day, int) and 0 <= day <= 6]))
            config["weekdays"] = sorted(valid_weekdays)
        else:
            config["weekdays"] = []
        
        # Validate time format
        try:
            from datetime import datetime
            datetime.strptime(config["time"], "%H:%M")
        except ValueError:
            config["time"] = "07:00"
        
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
            # Remove runtime info before saving
            save_config = {k: v for k, v in config.items() if not k.startswith("_")}

            # Ensure directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)

            # Pre-flight permission diagnostics
            if not os.access(config_file.parent, os.W_OK):
                logging.error(f"Config directory not writable: {config_file.parent}")
            else:
                logging.debug(f"Config directory writable: {config_file.parent}")

            temp_path = config_file.parent / (config_file.name + ".tmp")
            try:
                with open(temp_path, 'w') as tf:
                    json.dump({"_write_test": True}, tf)
                os.remove(temp_path)
            except Exception as te:
                logging.error(f"Temp write test failed in config dir {config_file.parent}: {te}")

            with open(config_file, 'w') as f:
                json.dump(save_config, f, indent=2)

            logging.info(f"Configuration saved to {config_file}")
            return True

        except (IOError, json.JSONDecodeError) as e:
            logging.exception(f"Error saving config file {config_file}: {e}")
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
from .utils.thread_safety import initialize_thread_safe_config, load_config_safe, save_config_safe
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
