from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor

from src.utils.thread_safety import ThreadSafeConfigManager


class _InMemoryConfigManager:
    def __init__(self, initial):
        self._config = copy.deepcopy(initial)

    def load_config(self):
        return copy.deepcopy(self._config)

    def save_config(self, config):
        self._config = copy.deepcopy(config)
        return True


def test_config_transaction_rolls_back_nested_mutations():
    manager = ThreadSafeConfigManager(
        _InMemoryConfigManager(
            {"last_known_devices": {"device": {"id": 1}}, "foo": "bar"}
        )
    )

    try:
        with manager.config_transaction() as txn:
            config = txn.load()
            config["last_known_devices"]["device"]["id"] = 99
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    current = manager.load_config()
    assert current["last_known_devices"]["device"]["id"] == 1


def test_load_config_returns_isolated_nested_copy():
    manager = ThreadSafeConfigManager(
        _InMemoryConfigManager(
            {"last_known_devices": {"device": {"id": 1}}, "foo": "bar"}
        )
    )

    loaded = manager.load_config()
    loaded["last_known_devices"]["device"]["id"] = 99

    current = manager.load_config()
    assert current["last_known_devices"]["device"]["id"] == 1


def test_change_listener_receives_isolated_copy():
    manager = ThreadSafeConfigManager(
        _InMemoryConfigManager(
            {"last_known_devices": {"device": {"id": 1}}, "foo": "bar"}
        )
    )

    def _listener(config):
        config["last_known_devices"]["device"]["id"] = 77

    manager.add_change_listener(_listener)
    manager.save_config({"last_known_devices": {"device": {"id": 2}}, "foo": "baz"})

    current = manager.load_config()
    assert current["last_known_devices"]["device"]["id"] == 2


def test_update_config_atomic_prevents_lost_updates():
    manager = ThreadSafeConfigManager(_InMemoryConfigManager({"counter": 0}))

    def increment_many() -> None:
        for _ in range(50):
            assert manager.update_config_atomic(
                lambda config: {**config, "counter": int(config.get("counter", 0)) + 1}
            )

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(increment_many) for _ in range(8)]
        for future in futures:
            future.result()

    current = manager.load_config()
    assert current["counter"] == 400
