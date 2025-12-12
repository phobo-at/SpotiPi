"""
🎵 Music Library Routes Blueprint
Handles music library browsing and API endpoints.
"""

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, render_template, request

from ..api.spotify import (get_access_token, get_devices, get_followed_artists,
                           get_playlists, get_saved_albums,
                           get_user_saved_tracks, get_user_library)
from ..utils.cache_migration import get_cache_migration_layer
from ..utils.library_utils import compute_library_hash, prepare_library_payload
from ..utils.rate_limiting import rate_limit
from ..utils.translations import t_api
from .helpers import api_error_handler, api_response

music_bp = Blueprint("music", __name__)
logger = logging.getLogger(__name__)

# Section loaders mapping
_VALID_LIBRARY_SECTIONS = ("playlists", "albums", "tracks", "artists")
_SECTION_LOADERS = {
    "playlists": get_playlists,
    "albums": get_saved_albums,
    "tracks": get_user_saved_tracks,
    "artists": get_followed_artists,
}


def _parse_library_sections(
    raw: Optional[str],
    *,
    default: Optional[List[str]] = None,
    ensure_default_on_empty: bool = False
) -> List[str]:
    """Parse and validate comma separated sections parameter."""
    if raw is None:
        return list(default or [])
    items = [s.strip() for s in raw.split(",") if s.strip()]
    filtered = [s for s in items if s in _VALID_LIBRARY_SECTIONS]
    if not filtered and ensure_default_on_empty:
        return list(default or ["playlists"])
    return filtered


def _load_music_library_data(
    token: str,
    *,
    sections: List[str],
    force_refresh: bool
) -> Dict[str, Any]:
    """Load music library data (full or sections) via cache migration layer."""
    cache_migration = get_cache_migration_layer()
    if sections:
        return cache_migration.get_library_sections_cached(
            token=token,
            sections=sections,
            section_loaders=_SECTION_LOADERS,
            force_refresh=force_refresh,
        )
    return cache_migration.get_full_library_cached(
        token=token,
        loader_func=get_user_library,
        force_refresh=force_refresh,
    )


def _build_library_response(
    token: str,
    *,
    sections: List[str],
    force_refresh: bool,
    want_fields: Optional[str],
    if_modified: Optional[str],
    request_obj,
) -> Response:
    """Create a unified music library response with shared headers."""
    raw_library = _load_music_library_data(token, sections=sections, force_refresh=force_refresh)
    basic_view = want_fields == "basic"
    payload = prepare_library_payload(raw_library, basic=basic_view, sections=sections or None)
    hash_val = payload.get("hash") or compute_library_hash(payload)

    if if_modified and if_modified == hash_val:
        resp = Response(status=304)
        resp.headers["ETag"] = hash_val
        resp.headers["X-MusicLibrary-Hash"] = hash_val
        return resp

    is_offline = bool(payload.get("offline_mode"))
    cached_sections = payload.get("cached_sections") if sections else None
    cached_flag = payload.get("cached") if not sections else None

    cached_complete = False
    if sections:
        if isinstance(cached_sections, dict):
            cached_complete = all(cached_sections.get(sec, False) for sec in sections)
        else:
            cached_sections = {sec: False for sec in sections}
    else:
        cached_complete = bool(cached_flag)

    if is_offline:
        message = "ok (offline cache)"
    elif sections and not cached_complete:
        message = t_api("ok_partial", request_obj)
    elif cached_complete:
        message = "ok (cached)"
    else:
        message = "ok (fresh)"

    resp = api_response(True, data=payload, message=message)
    resp.headers["X-MusicLibrary-Hash"] = hash_val
    resp.headers["ETag"] = hash_val
    if basic_view:
        resp.headers["X-Data-Fields"] = "basic"
    return resp


@music_bp.route("/music_library")
@api_error_handler
@rate_limit("spotify_api")
def music_library():
    """Standalone music library browser."""
    token = get_access_token()
    devices = get_devices(token) if token else []
    
    return render_template('music_library.html', 
                         devices=devices,
                         has_token=bool(token))


@music_bp.route("/api/music-library")
@api_error_handler
@rate_limit("spotify_api")
def api_music_library():
    """API endpoint for music library data with unified caching."""
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')

    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    want_fields = request.args.get('fields')
    if_modified = request.headers.get('If-None-Match')
    raw_sections = request.args.get('sections')
    requested_sections = _parse_library_sections(raw_sections, ensure_default_on_empty=True)

    cache_migration = get_cache_migration_layer()
    
    try:
        return _build_library_response(
            token,
            sections=requested_sections,
            force_refresh=force_refresh,
            want_fields=want_fields,
            if_modified=if_modified,
            request_obj=request,
        )
    except Exception:
        logging.exception("Error loading music library")
        if not requested_sections:
            fallback_data = cache_migration.get_offline_fallback()
            if fallback_data:
                resp_data = prepare_library_payload(fallback_data, basic=False)
                hash_val = resp_data["hash"]
                resp = api_response(True, data=resp_data, message=t_api("served_offline_cache", request))
                resp.headers['X-MusicLibrary-Hash'] = hash_val
                resp.headers['ETag'] = hash_val
                return resp

        return api_response(False, message=t_api("spotify_unavailable", request), status=503, error_code="spotify_unavailable")


@music_bp.route("/api/music-library/sections")
@api_error_handler
@rate_limit("spotify_api")
def api_music_library_sections():
    """Load only requested music library sections with unified caching.

    Query params:
        sections: comma separated list (playlists,albums,tracks,artists)
        refresh: force bypass cache if '1' or 'true'
        fields: 'basic' for slimmed down response
    """
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")

    sections = _parse_library_sections(
        request.args.get('sections', 'playlists'),
        default=['playlists'],
        ensure_default_on_empty=True
    )
    force = request.args.get('refresh') in ('1', 'true', 'yes')
    want_fields = request.args.get('fields')
    if_modified = request.headers.get('If-None-Match')

    try:
        return _build_library_response(
            token,
            sections=sections,
            force_refresh=force,
            want_fields=want_fields,
            if_modified=if_modified,
            request_obj=request,
        )
    except Exception as e:
        logging.exception("Error loading partial music library")
        return api_response(False, message=str(e), status=500, error_code="music_library_partial_error")


@music_bp.route("/api/artist-top-tracks/<artist_id>")
@api_error_handler
@rate_limit("spotify_api")
def api_artist_top_tracks(artist_id):
    """API endpoint for artist top tracks."""
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    try:
        from ..api.spotify import get_artist_top_tracks
        tracks = get_artist_top_tracks(token, artist_id)
        
        return api_response(True, data={"artist_id": artist_id, "tracks": tracks, "total": len(tracks)})
        
    except Exception as e:
        logging.exception("Error loading artist top tracks")
        return api_response(False, message=f"Failed to load artist top tracks: {str(e)}", status=500, error_code="artist_tracks_failed")
