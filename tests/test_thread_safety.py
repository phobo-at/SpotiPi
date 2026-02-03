from __future__ import annotations

import copy

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
