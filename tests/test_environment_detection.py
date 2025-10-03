import platform

from src.config import ConfigManager


def _create_manager(monkeypatch, *, machine, system, node, env=None):
    """Helper to instantiate ConfigManager with controlled platform/env."""
    # Ensure baseline variables are cleared before applying overrides
    for var in ("SPOTIPI_ENV", "SPOTIPI_RASPBERRY_PI"):
        monkeypatch.delenv(var, raising=False)

    if env:
        for key, value in env.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    monkeypatch.setattr(platform, "machine", lambda: machine)
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "node", lambda: node)

    return ConfigManager()


def test_auto_detects_development_on_desktop(monkeypatch):
    manager = _create_manager(
        monkeypatch,
        machine="x86_64",
        system="Darwin",
        node="mac-mini",
    )

    config = manager.load_config()

    assert manager.get_environment() == "development"
    assert config["_runtime"]["environment"] == "development"
    assert config["port"] == 5001
    assert config["debug"] is True
    assert config["log_level"].upper() == "INFO"


def test_auto_detects_production_on_raspberry_pi(monkeypatch):
    manager = _create_manager(
        monkeypatch,
        machine="armv7l",
        system="Linux",
        node="raspberrypi",
        env={"SPOTIPI_RASPBERRY_PI": "1"},
    )

    config = manager.load_config()

    assert manager.get_environment() == "production"
    assert config["_runtime"]["environment"] == "production"
    assert config["port"] == 5000
    assert config["debug"] is False
    assert config["log_level"].upper() == "WARNING"


def test_environment_override_via_variable(monkeypatch):
    manager = _create_manager(
        monkeypatch,
        machine="x86_64",
        system="Darwin",
        node="mac-mini",
        env={"SPOTIPI_ENV": "production"},
    )

    config = manager.load_config()

    assert manager.get_environment() == "production"
    assert config["_runtime"]["environment"] == "production"
    assert config["port"] == 5000
    assert config["debug"] is False

    # Override should trump Raspberry Pi auto-detection
    manager_override = _create_manager(
        monkeypatch,
        machine="armv7l",
        system="Linux",
        node="raspberrypi",
        env={"SPOTIPI_ENV": "development", "SPOTIPI_RASPBERRY_PI": "1"},
    )

    config_override = manager_override.load_config()

    assert manager_override.get_environment() == "development"
    assert config_override["_runtime"]["environment"] == "development"
    assert config_override["port"] == 5001
    assert config_override["debug"] is True
