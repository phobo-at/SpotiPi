#!/usr/bin/env python3
"""
⚡ Streaming Music Library API
============================

Provides instant-loading music library through progressive data streaming.
Sends priority data (playlists) first, then additional sections progressively.

Key Benefits:
- UI becomes usable immediately (100-200ms instead of 1000-2000ms)
- Progressive enhancement instead of blocking loading
- Better perceived performance through priority-based data delivery
"""

import json
import time
import logging
from typing import Dict, List, Any, Generator, Optional
from flask import Response
from concurrent.futures import ThreadPoolExecutor, as_completed

def create_streaming_music_library_response(token: str, sections: List[str] = None) -> Response:
    """Create a streaming JSON response for music library data.
    
    Args:
        token: Spotify access token
        sections: List of sections to include (default: all)
        
    Returns:
        Streaming Flask Response with progressive JSON data
    """
    if not sections:
        sections = ['playlists', 'albums', 'tracks', 'artists']
    
    def generate_streaming_json() -> Generator[str, None, None]:
        """Generate streaming JSON data with priority-based ordering."""
        logger = logging.getLogger('streaming_api')
        start_time = time.time()
        
        # Start JSON structure
        yield '{"status":"streaming","timestamp":' + str(int(time.time())) + ',"data":{'
        
        # Import section loaders
        from ..api.spotify import get_playlists, get_saved_albums, get_user_saved_tracks, get_followed_artists
        
        section_loaders = {
            'playlists': get_playlists,
            'albums': get_saved_albums, 
            'tracks': get_user_saved_tracks,
            'artists': get_followed_artists
        }
        
        # Priority order: playlists first (most commonly used), then others
        priority_order = ['playlists', 'albums', 'tracks', 'artists']
        ordered_sections = [s for s in priority_order if s in sections]
        
        # Add any remaining sections not in priority list
        for section in sections:
            if section not in ordered_sections:
                ordered_sections.append(section)
        
        # Stream each section progressively
        sections_completed = 0
        total_sections = len(ordered_sections)
        
        for i, section in enumerate(ordered_sections):
            section_start = time.time()
            
            try:
                loader = section_loaders.get(section)
                if not loader:
                    logger.warning(f"⚠️ No loader for section {section}")
                    continue
                
                # Load section data
                section_data = loader(token)
                section_duration = time.time() - section_start
                
                # Stream this section
                is_last = (i == total_sections - 1)
                comma = ',' if not is_last else ''
                
                section_json = json.dumps(section_data, separators=(',', ':'))
                yield f'"{section}":{section_json}{comma}'
                
                sections_completed += 1
                logger.info(f"✅ Streamed {section}: {len(section_data)} items in {section_duration:.2f}s")
                
                # Add progress metadata after each section (except last)
                if not is_last:
                    progress = (sections_completed / total_sections) * 100
                    yield f'"_progress":{{"completed":{sections_completed},"total":{total_sections},"percentage":{progress:.1f}}},'
                
            except Exception as e:
                logger.error(f"❌ Error streaming section {section}: {e}")
                # Stream empty section on error
                is_last = (i == total_sections - 1)
                comma = ',' if not is_last else ''
                yield f'"{section}":[]{comma}'
        
        # Close JSON structure with final metadata
        total_duration = time.time() - start_time
        yield f'}},"completed_at":{int(time.time())},"duration_seconds":{total_duration:.2f},"sections_count":{sections_completed}}}'
        
        logger.info(f"🎉 Streaming completed in {total_duration:.2f}s - {sections_completed}/{total_sections} sections")
    
    return Response(
        generate_streaming_json(),
        mimetype='application/json',
        headers={
            'Cache-Control': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
            'X-Music-Library-Streaming': 'true'
        }
    )

def create_core_music_library_response(token: str, sections: List[str] = None) -> Dict[str, Any]:
    """Create ultra-fast core music library response with minimal data.
    
    Only includes essential fields (name, uri) for immediate UI rendering.
    Heavy metadata can be loaded separately on-demand.
    
    Args:
        token: Spotify access token
        sections: List of sections to include
        
    Returns:
        Lightweight library data for instant UI rendering
    """
    if not sections:
        sections = ['playlists']  # Default to most important
    
    logger = logging.getLogger('core_api')
    start_time = time.time()
    
    # Import section loaders
    from ..api.spotify import get_playlists, get_saved_albums, get_user_saved_tracks, get_followed_artists
    
    section_loaders = {
        'playlists': get_playlists,
        'albums': get_saved_albums,
        'tracks': get_user_saved_tracks, 
        'artists': get_followed_artists
    }
    
    def extract_core_fields(items: List[Dict[str, Any]], item_type: str) -> List[Dict[str, str]]:
        """Extract only core fields for instant rendering."""
        core_items = []
        for item in items:
            if item_type == 'playlists':
                # Playlists are already processed by get_playlists()
                core_items.append({
                    'name': item.get('name', ''),
                    'uri': item.get('uri', ''),
                    'type': 'playlist',
                    'track_count': item.get('track_count', 0),
                    'image_url': item.get('image_url', '')
                })
            elif item_type == 'albums':
                # Albums are already processed by get_saved_albums()
                core_items.append({
                    'name': item.get('name', ''),
                    'uri': item.get('uri', ''),
                    'type': 'album',
                    'artist': item.get('artist', 'Unknown Artist'),
                    'track_count': item.get('track_count', 0),
                    'image_url': item.get('image_url', '')
                })
            elif item_type == 'tracks':
                # Tracks are already processed by get_user_saved_tracks()
                core_items.append({
                    'name': item.get('name', ''),
                    'uri': item.get('uri', ''),
                    'type': 'track',
                    'artist': item.get('artist', 'Unknown Artist'),
                    'album': item.get('album', ''),
                    'duration_ms': item.get('duration_ms', 0)
                })
            elif item_type == 'artists':
                # Artists are already processed by get_followed_artists()
                core_items.append({
                    'name': item.get('name', ''),
                    'uri': item.get('uri', ''),
                    'type': 'artist',
                    'artist': item.get('artist', ''),  # Follower count
                    'image_url': item.get('image_url', ''),
                    'artist_id': item.get('artist_id', '')
                })
        return core_items
    
    # Load sections in parallel for maximum speed
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(sections), 4)) as executor:
        future_to_section = {
            executor.submit(section_loaders[section], token): section 
            for section in sections if section in section_loaders
        }
        
        for future in as_completed(future_to_section):
            section = future_to_section[future]
            try:
                raw_data = future.result(timeout=5)  # Fast timeout for core data
                core_data = extract_core_fields(raw_data, section)
                results[section] = core_data
                logger.info(f"⚡ Core {section}: {len(core_data)} items")
            except Exception as e:
                logger.error(f"❌ Error loading core {section}: {e}")
                results[section] = []
    
    duration = time.time() - start_time
    logger.info(f"⚡ Core library loaded in {duration:.3f}s")
    
    return {
        **results,
        'core_mode': True,
        'duration_seconds': duration,
        'timestamp': int(time.time())
    }

def handle_network_error(error: Exception) -> Dict[str, Any]:
    """Handle network errors with user-friendly messages.
    
    Args:
        error: The network error that occurred
        
    Returns:
        Error response with appropriate message
    """
    logger = logging.getLogger('network_handler')
    
    # Analyze error type for user-friendly messaging
    error_msg = str(error).lower()
    
    if 'timeout' in error_msg or 'connection' in error_msg:
        return {
            'error': True,
            'error_code': 'NO_INTERNET',
            'message': 'Keine Internetverbindung',
            'message_en': 'No internet connection',
            'retry_suggested': True,
            'timestamp': int(time.time())
        }
    elif 'unauthorized' in error_msg or '401' in error_msg:
        return {
            'error': True,
            'error_code': 'SPOTIFY_AUTH_FAILED',
            'message': 'Spotify-Authentifizierung fehlgeschlagen',
            'message_en': 'Spotify authentication failed',
            'retry_suggested': False,
            'timestamp': int(time.time())
        }
    else:
        logger.error(f"Unexpected network error: {error}")
        return {
            'error': True,
            'error_code': 'SPOTIFY_API_ERROR',
            'message': 'Spotify-Service nicht verfügbar',
            'message_en': 'Spotify service unavailable', 
            'retry_suggested': True,
            'timestamp': int(time.time())
        }