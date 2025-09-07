#!/usr/bin/env python3
"""
🗃️ Simple JSON cache helpers
Minimal helpers to persist and retrieve small JSON payloads (e.g., music library cache)
without adding external dependencies.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def write_json_cache(path: str, data: Dict[str, Any]) -> None:
    """Write JSON cache to disk with metadata."""
    _ensure_dir(path)
    payload = {
        "_cached_at": int(time.time()),
        "data": data or {}
    }
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp_path, path)


def read_json_cache(path: str, max_age_seconds: int = 7 * 24 * 3600) -> Optional[Dict[str, Any]]:
    """Read JSON cache from disk if not older than max_age_seconds.

    Returns the stored "data" dictionary, or None if unavailable/expired.
    """
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cached_at = int(payload.get("_cached_at", 0))
        if cached_at and (time.time() - cached_at) > max_age_seconds:
            return None
        return payload.get("data")
    except Exception:
        return None

