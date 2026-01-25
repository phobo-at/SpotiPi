"""
🎵 Spotify Service - Business Logic for Spotify Integration
==========================================================

Handles all Spotify-related business logic including authentication,
device management, playlist operations, and playback control.
"""

from datetime import datetime
from typing import Any, Mapping, Optional

from ..api.spotify import (get_access_token, get_combined_playback,
                           get_devices, get_playlists, get_user_library,
                           resume_playback, set_volume, start_playback,
                           stop_playback, toggle_playback,
                           toggle_playback_fast, skip_to_next, skip_to_previous)
from ..utils.token_cache import get_token_cache_info
from ..utils.validation import ValidationError, validate_volume_only
from . import BaseService, ServiceResult


class SpotifyService(BaseService):
    """Service for Spotify integration and music management."""
    
    def __init__(self):
        super().__init__("spotify")
        self._last_token_check = None
        self._token_valid = False
    
    def get_authentication_status(self) -> ServiceResult:
        """Check Spotify authentication status."""
        try:
            token = get_access_token()
            
            if token:
                self._token_valid = True
                self._last_token_check = datetime.now()
                
                # Get token cache information
                cache_info = get_token_cache_info()
                
                return self._success_result(
                    data={
                        "authenticated": True,
                        "token_available": True,
                        "token_cache": cache_info,
                        "last_check": self._last_token_check.isoformat()
                    },
                    message="Spotify authentication successful"
                )
            else:
                self._token_valid = False
                return self._error_result(
                    "Spotify authentication required. Please configure your credentials.",
                    error_code="AUTH_REQUIRED"
                )
                
        except Exception as e:
            self._token_valid = False
            return self._handle_error(e, "get_authentication_status")
    
    def get_available_devices(self) -> ServiceResult:
        """Get list of available Spotify devices."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result
            
            token = get_access_token()
            devices = get_devices(token)
            
            if devices is None:
                return self._error_result(
                    "Failed to retrieve devices from Spotify",
                    error_code="DEVICES_UNAVAILABLE"
                )
            
            # Enhance device information
            enhanced_devices = []
            for device in devices:
                enhanced_devices.append({
                    "id": device.get("id"),
                    "name": device.get("name"),
                    "type": device.get("type"),
                    "is_active": device.get("is_active", False),
                    "is_private_session": device.get("is_private_session", False),
                    "is_restricted": device.get("is_restricted", False),
                    "volume_percent": device.get("volume_percent", 0)
                })
            
            return self._success_result(
                data=enhanced_devices,
                message=f"Found {len(enhanced_devices)} Spotify devices"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_available_devices")
    
    def get_user_playlists(self) -> ServiceResult:
        """Get user's Spotify playlists."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result
            
            token = get_access_token()
            playlists = get_playlists(token)
            
            if playlists is None:
                return self._error_result(
                    "Failed to retrieve playlists from Spotify",
                    error_code="PLAYLISTS_UNAVAILABLE"
                )
            
            # Enhance playlist information
            enhanced_playlists = []
            for playlist in playlists:
                enhanced_playlists.append({
                    "uri": playlist.get("uri"),
                    "name": playlist.get("name"),
                    "track_count": playlist.get("track_count", 0),
                    "owner": playlist.get("artist"),
                    "image_url": playlist.get("image_url"),
                    "type": playlist.get("type", "playlist")
                })
            
            return self._success_result(
                data=enhanced_playlists,
                message=f"Found {len(enhanced_playlists)} playlists"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_user_playlists")
    
    def get_music_library(self) -> ServiceResult:
        """Get complete music library including playlists and saved music."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result
            
            token = get_access_token()
            
            # Get playlists and user library
            playlists = get_playlists(token)
            user_library = get_user_library(token)

            library_data = {
                "playlists": playlists or [],
                "saved_albums": user_library.get("albums", []) if user_library else [],
                "saved_tracks": user_library.get("tracks", []) if user_library else [],
                "saved_artists": user_library.get("artists", []) if user_library else [],
                "total_playlists": len(playlists) if playlists else 0,
                "total_saved_albums": len(user_library.get("albums", [])) if user_library else 0,
                "total_saved_tracks": len(user_library.get("tracks", [])) if user_library else 0,
                "total_saved_artists": len(user_library.get("artists", [])) if user_library else 0
            }
            
            return self._success_result(
                data=library_data,
                message="Music library retrieved successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_music_library")
    
    def get_playback_status(self) -> ServiceResult:
        """Get current playback status and track information."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result
            
            token = get_access_token()
            
            combined = get_combined_playback(token)
            if not combined:
                status_data = {
                    "is_playing": False,
                    "current_track": None,
                    "volume": 50,
                    "device": None,
                    "progress_ms": 0,
                    "shuffle_state": False,
                    "repeat_state": "off"
                }
            else:
                status_data = combined
            
            return self._success_result(
                data=status_data,
                message="Playback status retrieved successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_playback_status")
    
    def control_playback(self, action: str, **kwargs) -> ServiceResult:
        """Control Spotify playback (start, stop, resume, toggle)."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result
            
            token = get_access_token()
            
            if action == "start":
                device_id = kwargs.get("device_id")
                playlist_uri = kwargs.get("playlist_uri")
                
                if not device_id or not playlist_uri:
                    return self._error_result(
                        "Device ID and playlist URI required for starting playback",
                        error_code="MISSING_PARAMETERS"
                    )
                
                success = start_playback(token, device_id, playlist_uri)
                
            elif action == "stop":
                success = stop_playback(token)
                
            elif action == "resume":
                success = resume_playback(token)
                
            elif action == "toggle":
                success = toggle_playback(token)
                
            else:
                return self._error_result(
                    f"Unknown playback action: {action}",
                    error_code="INVALID_ACTION"
                )
            
            if success:
                return self._success_result(
                    message=f"Playback {action} executed successfully"
                )
            else:
                return self._error_result(
                    f"Failed to {action} playback",
                    error_code="PLAYBACK_FAILED"
                )
                
        except Exception as e:
            return self._handle_error(e, "control_playback")

    def toggle_playback_fast(self) -> ServiceResult:
        """Toggle playback state using the fast toggle endpoint."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result

            token = get_access_token()
            if not token:
                return self._error_result(
                    "Spotify authentication required. Please configure your credentials.",
                    error_code="auth_required"
                )

            result = toggle_playback_fast(token)
            if isinstance(result, dict):
                success = result.get("success", True)
                if success:
                    return self._success_result(
                        data=result,
                        message="Playback toggled successfully"
                    )
                return self._error_result(
                    result.get("error") or "Playback toggle failed",
                    error_code="playback_toggle_failed",
                    data=result
                )

            return self._success_result(
                data={"result": result},
                message="Playback toggled successfully"
            )
        except Exception as e:
            return self._handle_error(e, "toggle_playback_fast")

    def skip_to_next(self) -> ServiceResult:
        """Skip to next track."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result

            token = get_access_token()
            if not token:
                return self._error_result(
                    "Spotify authentication required.",
                    error_code="auth_required"
                )

            result = skip_to_next(token)
            if result.get("success"):
                return self._success_result(
                    data=result,
                    message="Skipped to next track"
                )
            
            error = result.get("error", "skip_failed")
            if error == "auth_required":
                return self._error_result("Authentication required", error_code="auth_required")
            if error == "no_active_device":
                return self._error_result("No active playback device", error_code="no_active_device")
            
            return self._error_result(f"Skip failed: {error}", error_code="skip_failed")
        except Exception as e:
            return self._handle_error(e, "skip_to_next")

    def skip_to_previous(self) -> ServiceResult:
        """Skip to previous track."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result

            token = get_access_token()
            if not token:
                return self._error_result(
                    "Spotify authentication required.",
                    error_code="auth_required"
                )

            result = skip_to_previous(token)
            if result.get("success"):
                return self._success_result(
                    data=result,
                    message="Skipped to previous track"
                )
            
            error = result.get("error", "skip_failed")
            if error == "auth_required":
                return self._error_result("Authentication required", error_code="auth_required")
            if error == "no_active_device":
                return self._error_result("No active playback device", error_code="no_active_device")
            
            return self._error_result(f"Skip failed: {error}", error_code="skip_failed")
        except Exception as e:
            return self._handle_error(e, "skip_to_previous")

    def set_playback_volume(self, volume: int, device_id: Optional[str] = None) -> ServiceResult:
        """Set Spotify playback volume."""
        try:
            if not (0 <= volume <= 100):
                return self._error_result(
                    "Volume must be between 0 and 100",
                    error_code="volume"
                )
            
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result
            
            token = get_access_token()
            success = set_volume(token, volume, device_id)
            
            if success:
                return self._success_result(
                    data={"volume": volume},
                    message=f"Volume set to {volume}%"
                )
            else:
                return self._error_result(
                    "Failed to set volume",
                    error_code="volume_set_failed"
                )
                
        except Exception as e:
            return self._handle_error(e, "set_playback_volume")

    def set_volume_from_form(self, form_data: Mapping[str, Any]) -> ServiceResult:
        """Validate and apply volume changes from form payloads."""
        try:
            volume = validate_volume_only(form_data)
        except ValidationError as exc:
            return self._error_result(
                f"Invalid {exc.field_name}: {exc.message}",
                error_code=exc.field_name
            )

        device_id = form_data.get("device_id") or None
        return self.set_playback_volume(volume, device_id)

    def start_playback_from_payload(self, payload: Mapping[str, Any], *, payload_type: str) -> ServiceResult:
        """Start playback based on JSON or form payloads."""
        try:
            auth_result = self.get_authentication_status()
            if not auth_result.success:
                return auth_result

            token = get_access_token()
            if not token:
                return self._error_result(
                    "Spotify authentication required. Please configure your credentials.",
                    error_code="auth_required"
                )

            if payload_type == "json":
                context_uri = payload.get("context_uri")
                device_id = payload.get("device_id")
                device_name = None
                if not context_uri:
                    return self._error_result(
                        "Missing context_uri",
                        error_code="missing_context_uri"
                    )
            else:
                context_uri = payload.get("uri")
                device_name = payload.get("device_name")
                device_id = None

                if not context_uri:
                    return self._error_result(
                        "Missing URI",
                        error_code="missing_uri"
                    )
                if not device_name:
                    return self._error_result(
                        "Missing device name",
                        error_code="missing_device"
                    )

            resolved_device_id = device_id
            if device_name and not resolved_device_id:
                devices = get_devices(token)
                if not devices:
                    return self._error_result(
                        "No devices available",
                        error_code="no_devices"
                    )

                target = next((d for d in devices if d.get("name") == device_name), None)
                if not target:
                    return self._error_result(
                        f"Device '{device_name}' not found",
                        error_code="device_not_found",
                        data={"device_name": device_name}
                    )
                resolved_device_id = target.get("id")

            success = start_playback(token, resolved_device_id, context_uri)
            if success:
                return self._success_result(
                    data={
                        "context_uri": context_uri,
                        "device_id": resolved_device_id,
                        "device_name": device_name
                    },
                    message="Playback started successfully"
                )
            return self._error_result(
                "Failed to start playback",
                error_code="playback_start_failed"
            )
        except Exception as e:
            return self._handle_error(e, "start_playback_from_payload")
    
    def validate_device_and_playlist(self, device_id: str, playlist_uri: str) -> ServiceResult:
        """Validate that device and playlist are accessible."""
        try:
            # Check devices
            devices_result = self.get_available_devices()
            if not devices_result.success:
                return devices_result
            
            device_found = any(d["id"] == device_id for d in devices_result.data)
            if not device_found:
                return self._error_result(
                    f"Device with ID {device_id} not found or not available",
                    error_code="DEVICE_NOT_FOUND"
                )
            
            # Check playlists
            playlists_result = self.get_user_playlists()
            if not playlists_result.success:
                return playlists_result
            
            playlist_found = any(p["uri"] == playlist_uri for p in playlists_result.data)
            if not playlist_found:
                return self._error_result(
                    f"Playlist with URI {playlist_uri} not found or not accessible",
                    error_code="PLAYLIST_NOT_FOUND"
                )
            
            return self._success_result(
                data={
                    "device_id": device_id,
                    "playlist_uri": playlist_uri,
                    "validated": True
                },
                message="Device and playlist validation successful"
            )
            
        except Exception as e:
            return self._handle_error(e, "validate_device_and_playlist")
    
    def health_check(self) -> ServiceResult:
        """Perform Spotify service health check."""
        try:
            base_health = super().health_check()
            if not base_health.success:
                return base_health
            
            # Check authentication
            auth_status = self.get_authentication_status()
            auth_ok = auth_status.success
            
            # Quick API test
            api_ok = False
            if auth_ok:
                devices_result = self.get_available_devices()
                api_ok = devices_result.success
            
            health_data = {
                "service": "spotify",
                "status": "healthy" if all([auth_ok, api_ok]) else "degraded",
                "components": {
                    "authentication": "ok" if auth_ok else "error",
                    "api_access": "ok" if api_ok else "error",
                    "token_cache": "ok" if self._token_valid else "unknown"
                },
                "last_token_check": self._last_token_check.isoformat() if self._last_token_check else None
            }
            
            return self._success_result(
                data=health_data,
                message="Spotify service health check completed"
            )
            
        except Exception as e:
            return self._handle_error(e, "health_check")
