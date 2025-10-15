from __future__ import annotations

import pytest

from src.utils.translations import TRANSLATIONS, get_user_language, t_api


class MockRequest:
    """Lightweight stand-in for Flask's request object."""

    def __init__(self, accept_language: str | None = None):
        self.headers = {}
        if accept_language:
            self.headers["Accept-Language"] = accept_language


@pytest.fixture
def request_de() -> MockRequest:
    return MockRequest("de-DE,de;q=0.9")


@pytest.fixture
def request_en() -> MockRequest:
    return MockRequest("en-US,en;q=0.9")


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("de-DE,de;q=0.9", "de"),
        ("en-US,en;q=0.9", "en"),
        ("fr-FR,fr;q=0.8", "en"),  # fallback to English
        ("", "en"),
        (None, "en"),
    ],
)
def test_get_user_language_detection(header: str | None, expected: str) -> None:
    request = MockRequest(header)
    assert get_user_language(request) == expected


SAMPLE_KEYS = [
    "auth_required",
    "invalid_time_format",
    "alarm_settings_saved",
    "volume_saved",
    "playback_started",
    "page_not_found",
]


@pytest.mark.parametrize("key", SAMPLE_KEYS)
def test_translations_return_strings(key: str, request_de: MockRequest, request_en: MockRequest) -> None:
    de_text = t_api(key, request_de)
    en_text = t_api(key, request_en)
    assert isinstance(de_text, str) and de_text, "German translation should be non-empty"
    assert isinstance(en_text, str) and en_text, "English translation should be non-empty"


def test_parameterised_translation(request_de: MockRequest) -> None:
    translated = t_api("volume_set_saved", request_de, volume=75)
    assert "75" in translated


def test_translation_key_sets_are_in_sync() -> None:
    de_keys = set(TRANSLATIONS["de"].keys())
    en_keys = set(TRANSLATIONS["en"].keys())
    assert de_keys == en_keys, f"Mismatched translation keys: DE-only={de_keys - en_keys}, EN-only={en_keys - de_keys}"
