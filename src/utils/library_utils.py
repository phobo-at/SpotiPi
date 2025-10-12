"""Utilities for music library hashing and slimming.

Consolidates duplicated inline logic from endpoints in app.py.
"""
from __future__ import annotations
import datetime
from typing import Dict, List, Any, Iterable
import hashlib
from . import logger as _noop  # ensure package import side-effects if any
from ..constants import MUSIC_LIBRARY_BASIC_FIELDS

__all__ = [
    "compute_library_hash",
    "slim_collection",
    "prepare_library_payload"
]

def compute_library_hash(data: Dict[str, Any]) -> str:
    """Compute a stable hash for the music library selections.

    We use only URIs to keep the hash small and stable.
    Falls back to 32 zeros on error or empty content.
    """
    try:
        parts: List[str] = []
        for coll in ("playlists", "albums", "tracks", "artists"):
            for item in data.get(coll, []) or []:
                uri = item.get("uri")
                if uri:
                    parts.append(uri)
        if not parts:
            return "0" * 32
        raw = "|".join(sorted(parts))
        return hashlib.md5(raw.encode("utf-8")).hexdigest()  # noqa: S324 (non-crypto ok)
    except Exception:
        return "0" * 32

def slim_collection(items: Iterable[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    """Return a slimmed list of dicts restricted to whitelisted fields."""
    if not items:
        return []
    out: List[Dict[str, Any]] = []
    for it in items:
        out.append({k: it.get(k) for k in MUSIC_LIBRARY_BASIC_FIELDS if k in it})
    return out

def prepare_library_payload(raw: Dict[str, Any], *, basic: bool) -> Dict[str, Any]:
    """Create a response payload (optionally slim).

    Args:
        raw: full raw library dict
        basic: whether to slim lists
    """
    if not isinstance(raw, dict):  # defensive
        raw = {}
    payload = {
        "total": raw.get("total", 0),
    }
    for coll in ("playlists", "albums", "tracks", "artists"):
        col_items = raw.get(coll, []) or []
        payload[coll] = slim_collection(col_items) if basic else col_items
    existing_hash = raw.get("hash") if isinstance(raw, dict) else None
    payload["hash"] = existing_hash or compute_library_hash(raw)
    if "cached" in raw:
        payload["cached"] = bool(raw.get("cached"))
    if "offline_mode" in raw:
        payload["offline_mode"] = bool(raw.get("offline_mode"))
    cache_meta = raw.get("cache")
    if isinstance(cache_meta, dict):
        payload["cache"] = cache_meta
    last_updated = raw.get("lastUpdated")
    if last_updated:
        payload["lastUpdated"] = last_updated
        try:
            payload["lastUpdatedIso"] = datetime.datetime.fromtimestamp(last_updated).isoformat()
        except (TypeError, ValueError, OSError):
            pass
    return payload
