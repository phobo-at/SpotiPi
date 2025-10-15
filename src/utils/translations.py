"""
SpotiPi Translation System
Automatic language detection: German for de-*, all others = English
"""

from typing import Dict, Any, Optional

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    'de': {
        # Header & Navigation
        'app_title': '<i class="fab fa-spotify"></i> SpotiPi - Wecker & Sleep-Timer',
        'alarm_tab': '<i class="fas fa-alarm-clock"></i><span>Wecker</span>',
        'sleep_tab': '<i class="fas fa-moon"></i><span>Sleep</span>',
        'library_tab': '<i class="fas fa-music"></i><span>Bibliothek</span>',
        'library_play_help': 'Musik direkt abspielen',
        'volume_label': '<i class="fas fa-volume-high"></i> Lautstärke',
        
        # Alarm Interface
        'alarm_configure': 'Wecker konfigurieren',
        'alarm_time_label': '<i class="fas fa-clock"></i> Weckzeit',
        'alarm_time_help': 'Uhrzeit, zu der der Wecker klingeln soll',
        'single_alarm_mode_label': 'Einmaliger Alarm',
        'playlist_label': '<i class="fas fa-list-music"></i> Playlist',
        'playlist_help': 'Musik, die beim Wecken abgespielt wird',
        'device_label': '<i class="fa-brands fa-spotify"></i> Lautsprecher',
        'device_help': 'Gerät, auf dem die Musik abgespielt wird',
        'further_options': 'Weitere Optionen',
        'fade_in': 'Fade-In',
        'shuffle': 'Shuffle',
        'enable_alarm': 'Wecker aktivieren',
        'alarm_active_title': 'Wecker aktiv',
        'alarm_active_info': 'Wecker geplant für {time} Uhr. Du kannst ihn unten deaktivieren.',
        'alarm_next_label': 'Nächster Alarm:',
        'alarm_next_unknown': 'Noch nicht berechnet',
        'alarm_device_label': 'Gerät:',
        'alarm_device_unknown': 'Unbekanntes Gerät',
        'alarm_set': 'Wecker gestellt für {time} Uhr',
        'alarm_volume_info': 'Lautstärke: {volume}%',
        'no_alarm': 'Kein Wecker gestellt',
        
        # Playlist Selector
        'playlist_search_placeholder': 'Musik suchen...',
        'playlist_no_results': 'Keine Musik gefunden',
        'playlist_select_text': 'Musik auswählen',
        
        # Sleep Interface
        'sleep_configure': 'Sleep-Timer konfigurieren',
        'sleep_playlist_help': 'Musik, die während des Einschlafens gespielt wird',
        'duration_label': '<i class="fas fa-clock"></i> Dauer',
        'duration_help': 'Zeitdauer bis zum automatischen Stoppen der Musik',
        'duration_15min': '15 Minuten',
        'duration_30min': '30 Minuten',
        'duration_45min': '45 Minuten',
        'duration_1h': '1 Stunde',
        'duration_15h': '1.5 Stunden',
        'duration_2h': '2 Stunden',
        'duration_custom': 'Benutzerdefiniert',
        'custom_duration_label': 'Benutzerdefinierte Dauer (Minuten)',
        'stop_if_playing': 'Nur laufende Musik stoppen',
        'enable_sleep': 'Sleep-Timer aktivieren',
        'sleep_active_title': 'Sleep-Timer aktiv',
        'sleep_active_info': 'Die Musik wird automatisch gestoppt, wenn die eingestellte Zeit abgelaufen ist.',
        'no_sleep_timer': 'Kein aktiver Sleep-Timer',
        'sleep_timer_label': 'Sleep-Timer endet in',
        'sleep_ends_in': 'Sleep endet in {min}m {sec}s',
        
        # Music Library
        'library_title': 'Musik-Bibliothek',
        'search_music': 'Musik suchen...',
        'loading_music': 'Musik wird geladen...',
        'loading': 'Lade',
        'rendering': 'Rendere',
        'entries': 'Einträge',
        'playlists_tab': '<i class="fas fa-list"></i> Playlists',
        'playlists': 'Playlists',
        'albums_tab': '<i class="fas fa-compact-disc"></i> Alben',
        'albums': 'Alben',
        'songs_tab': '<i class="fas fa-music"></i> Songs',
        'songs': 'Songs',
        'artists_tab': '<i class="fas fa-microphone"></i> Künstler',
        'artists': 'Künstler',
        'artist': 'Künstler',
        'play_music': 'Abspielen',
        'no_music_found': 'Keine Musik gefunden',
        'playlist_select_text': 'Musik auswählen',
        'select_speaker': 'Lautsprecher wählen',
        'select_speaker_message': 'Bitte wähle einen Lautsprecher zum Abspielen der Musik aus.',
        'speaker_required': 'Lautsprecher erforderlich',
        'loading_devices': 'Lautsprecher werden geladen...',
        'no_devices_found': 'Keine Lautsprecher gefunden',
        'speaker_error': 'Fehler beim Laden der Lautsprecher',
        
        # Volume Controls
        'alarm_volume': '<i class="fas fa-volume-high"></i> Wecker-Lautstärke',
        'alarm_volume_help': 'Lautstärke nur für den Wecker (hat keine Auswirkung auf die aktuelle Wiedergabe)',
        
        # Status Messages
        'settings_saved': 'Einstellungen gespeichert!',
        'error_saving': 'Fehler beim Speichern der Einstellungen',
        'saving_settings': 'Einstellungen werden gespeichert...',
        'save_failed': 'Speichern fehlgeschlagen',
        'save_error': 'Speicherfehler',
        'unknown': 'unbekannt',
        'unknown_error': 'Unbekannter Fehler',
        'alarm_set_for': 'Wecker gestellt für',
        'volume': 'Lautstärke',
        'no_alarm_active': 'Kein Wecker aktiv',
        'activation_failed': 'Aktivierung fehlgeschlagen',
        'activation_error': 'Aktivierungsfehler',
        'deactivation_failed': 'Deaktivierung fehlgeschlagen',
        'deactivation_error': 'Deaktivierungsfehler',
        'sleep_timer_activation_error': 'Fehler beim Aktivieren des Sleep-Timers',
        'sleep_timer_deactivation_error': 'Fehler beim Deaktivieren des Sleep-Timers',
        'select_speaker_first': 'Bitte wähle zuerst einen Lautsprecher aus',
        'no_active_playback': 'Keine aktive Wiedergabe',
        'spotify_error': 'Spotify-Fehler',
        'network_error': 'Netzwerkfehler',
        'spotify_token_error': 'Fehler beim Abrufen des Spotify-Tokens.',
        
        # Actions
        'play_pause': 'Wiedergabe starten oder pausieren',
        'sleep_start': 'Sleep starten',
        'sleep_stop': 'Sleep stoppen',
        'currently_playing': 'Aktuell läuft',
        'cancel': 'Abbrechen',
        
        # API Messages
        'internal_server_error': 'Interner Server-Fehler',
        'no_valid_token': 'Kein gültiger Token',
        'invalid_volume': 'Ungültige Lautstärke',
        'volume_must_be_between': 'Lautstärke muss zwischen 0 und 100 liegen',
        'spotify_api_error': 'Spotify-API-Fehler',
        'data_updated': 'Daten aktualisiert',
        'error_updating_data': 'Fehler beim Aktualisieren der Daten',
        'sleep_mode_stopped': 'Sleep-Modus gestoppt',
        'could_not_stop_sleep': 'Sleep-Modus konnte nicht gestoppt werden',
        'test_error': 'Test-Fehler',
        'alarm_tested_for': 'Wecker wird {seconds} Sekunden getestet',
        'auth_required': 'Authentifizierung erforderlich',
        'invalid_time_format': 'Ungültiges Zeitformat. Verwenden Sie HH:MM.',
        'failed_save_config': 'Konfiguration konnte nicht gespeichert werden',
        'alarm_settings_saved': 'Wecker-Einstellungen gespeichert',
        'internal_error_saving': 'Interner Fehler beim Speichern des Weckers',
        'spotify_unavailable': 'Spotify nicht verfügbar: Musik-Bibliothek konnte nicht geladen werden',
        'served_offline_cache': 'Offline-Cache bereitgestellt (Spotify-Problem)',
        'ok_partial': 'OK (teilweise)',
        'ok': 'OK',
        'degraded': 'Beeinträchtigt',
        'no_active_playback': 'Keine aktive Wiedergabe',
        'failed_start_playback': 'Wiedergabe konnte nicht gestartet werden',
        'playback_started': 'Wiedergabe gestartet',
        'missing_context_uri': 'Fehlende context_uri',
        'missing_uri': 'Fehlende URI',
        'missing_device': 'Fehlendes Gerät',
        'no_devices': 'Keine Geräte verfügbar',
        'device_not_found': 'Gerät \'{name}\' nicht gefunden',
        'volume_set_failed': 'Lautstärke konnte nicht gesetzt werden',
        'volume_operation_failed': 'Lautstärke-Operation fehlgeschlagen',
        'volume_saved': 'Lautstärke gespeichert',
        'failed_save_volume': 'Lautstärke konnte nicht gespeichert werden',
        'failed_start_sleep': 'Sleep-Timer konnte nicht gestartet werden',
        'sleep_stopped': 'Sleep-Timer gestoppt',
        'failed_stop_sleep': 'Sleep-Timer konnte nicht gestoppt werden',
        'an_internal_error_occurred': 'Ein interner Fehler ist aufgetreten',
        'volume_set_saved': 'Lautstärke auf {volume} gesetzt und in der Konfiguration gespeichert',
        'page_not_found': 'Seite nicht gefunden',
        'internal_server_error_page': 'Interner Server-Fehler',
        
        # Time & Date
        'and': 'und',
        'hour': 'Stunde',
        'hours': 'Stunden', 
        'minute': 'Minute',
        'minutes': 'Minuten',
        'sleep_timer_preview': 'Dein Sleep-Timer würde {duration} laufen und um {time} Uhr enden.',
        
        # Weekdays
        'monday': 'Montag',
        'tuesday': 'Dienstag', 
        'wednesday': 'Mittwoch',
        'thursday': 'Donnerstag',
        'friday': 'Freitag',
        'saturday': 'Samstag',
        'sunday': 'Sonntag',
        'mon': 'Mo',
        'tue': 'Di',
        'wed': 'Mi',
        'thu': 'Do',
        'fri': 'Fr',
        'sat': 'Sa',
        'sun': 'So',
    },
    
    'en': {
        # Header & Navigation
        'app_title': '<i class="fab fa-spotify"></i> SpotiPi - Alarm Clock & Sleep Timer',
        'alarm_tab': '<i class="fas fa-alarm-clock"></i><span>Alarm</span>',
        'sleep_tab': '<i class="fas fa-moon"></i><span>Sleep</span>',
        'library_tab': '<i class="fas fa-music"></i><span>Library</span>',
        'library_play_help': 'Play music directly',
        'volume_label': '<i class="fas fa-volume-high"></i> Volume',
        
        # Alarm Interface
        'alarm_configure': 'Configure Alarm',
        'alarm_time_label': '<i class="fas fa-clock"></i> Wake-up Time',
        'alarm_time_help': 'Time when the alarm should ring',
        'single_alarm_mode_label': 'One-time alarm',
        'playlist_label': '<i class="fas fa-list-music"></i> Playlist',
        'playlist_help': 'Music to play when waking up',
        'device_label': '<i class="fa-brands fa-spotify"></i> Speaker',
        'device_help': 'Device to play music on',
        'further_options': 'Additional Options',
        'fade_in': 'Fade-In',
        'shuffle': 'Shuffle',
        'enable_alarm': 'Enable Alarm',
        'alarm_active_title': 'Alarm active',
        'alarm_active_info': 'Alarm scheduled for {time}. Use the switch below to disable it.',
        'alarm_next_label': 'Next alarm:',
        'alarm_next_unknown': 'Calculating...',
        'alarm_device_label': 'Speaker:',
        'alarm_device_unknown': 'Unknown device',
        'alarm_set': 'Alarm set for {time}',
        'alarm_volume_info': 'Volume: {volume}%',
        'no_alarm': 'No alarm set',
        
        # Playlist Selector
        'playlist_search_placeholder': 'Search music...',
        'playlist_no_results': 'No music found',
        'playlist_select_text': 'Select music',
        
        # Sleep Interface
        'sleep_configure': 'Configure Sleep Timer',
        'sleep_playlist_help': 'Music to play while falling asleep',
        'duration_label': '<i class="fas fa-clock"></i> Duration',
        'duration_help': 'Time until music stops automatically',
        'duration_15min': '15 minutes',
        'duration_30min': '30 minutes',
        'duration_45min': '45 minutes',
        'duration_1h': '1 hour',
        'duration_15h': '1.5 hours',
        'duration_2h': '2 hours',
        'duration_custom': 'Custom',
        'custom_duration_label': 'Custom Duration (minutes)',
        'stop_if_playing': 'Only stop running music',
        'enable_sleep': 'Enable Sleep Timer',
        'sleep_active_title': 'Sleep Timer Active',
        'sleep_active_info': 'Music will automatically stop when the set time expires.',
        'no_sleep_timer': 'No active sleep timer',
        'sleep_timer_label': 'Sleep timer ends in',
        'sleep_ends_in': 'Sleep ends in {min}m {sec}s',
        
        # Music Library
        'library_title': 'Music Library',
        'search_music': 'Search music...',
        'loading_music': 'Loading music...',
        'loading': 'Loading',
        'rendering': 'Rendering',
        'entries': 'entries',
        'playlists_tab': '<i class="fas fa-list"></i> Playlists',
        'playlists': 'playlists',
        'albums_tab': '<i class="fas fa-compact-disc"></i> Albums',
        'albums': 'albums',
        'songs_tab': '<i class="fas fa-music"></i> Songs',
        'songs': 'songs',
        'artists_tab': '<i class="fas fa-microphone"></i> Artists',
        'artists': 'artists',
        'artist': 'Artist',
        'play_music': 'Play',
        'no_music_found': 'No music found',
        'playlist_select_text': 'Select music',
        'select_speaker': 'Select speaker',
        'select_speaker_message': 'Please select a speaker to play the music.',
        'speaker_required': 'Speaker required',
        'loading_devices': 'Loading speakers...',
        'no_devices_found': 'No speakers found',
        'speaker_error': 'Error loading speakers',
        
        # Volume Controls
        'alarm_volume': '<i class="fas fa-volume-high"></i> Alarm Volume',
        'alarm_volume_help': 'Volume for alarm only (does not affect current playback)',
        
        # Status Messages
        'settings_saved': 'Settings saved!',
        'error_saving': 'Error saving settings',
        'saving_settings': 'Saving settings...',
        'save_failed': 'Save failed',
        'save_error': 'Save error',
        'unknown': 'unknown',
        'unknown_error': 'Unknown error',
        'alarm_set_for': 'Alarm set for',
        'volume': 'Volume',
        'no_alarm_active': 'No alarm active',
        'activation_failed': 'Activation failed',
        'activation_error': 'Activation error',
        'deactivation_failed': 'Deactivation failed',
        'deactivation_error': 'Deactivation error',
        'sleep_timer_activation_error': 'Error activating sleep timer',
        'sleep_timer_deactivation_error': 'Error deactivating sleep timer',
        'select_speaker_first': 'Please select a speaker first',
        'no_active_playback': 'No active playback',
        'spotify_error': 'Spotify error',
        'network_error': 'Network error',
        'spotify_token_error': 'Error retrieving Spotify token.',
        
        # Actions
        'play_pause': 'Start or pause playback',
        'sleep_start': 'Start sleep',
        'sleep_stop': 'Stop sleep',
        'currently_playing': 'Currently playing',
        'cancel': 'Cancel',
        
        # API Messages
        'internal_server_error': 'Internal server error',
        'no_valid_token': 'No valid token',
        'invalid_volume': 'Invalid volume',
        'volume_must_be_between': 'Volume must be between 0 and 100',
        'spotify_api_error': 'Spotify API error',
        'data_updated': 'Data updated',
        'error_updating_data': 'Error updating data',
        'sleep_mode_stopped': 'Sleep mode stopped',
        'could_not_stop_sleep': 'Could not stop sleep mode',
        'test_error': 'Test error',
        'alarm_tested_for': 'Alarm will be tested for {seconds} seconds',
        'auth_required': 'Authentication required',
        'invalid_time_format': 'Invalid time format. Use HH:MM.',
        'failed_save_config': 'Failed to save configuration',
        'alarm_settings_saved': 'Alarm settings saved',
        'internal_error_saving': 'Internal error saving alarm',
        'spotify_unavailable': 'Spotify unavailable: failed to load music library',
        'served_offline_cache': 'served offline cache (spotify issue)',
        'ok_partial': 'ok (partial)',
        'ok': 'ok',
        'degraded': 'degraded',
        'no_active_playback': 'No active playback',
        'failed_start_playback': 'Failed to start playback',
        'playback_started': 'Playback started',
        'missing_context_uri': 'Missing context_uri',
        'missing_uri': 'Missing URI',
        'missing_device': 'Missing device name',
        'no_devices': 'No devices available',
        'device_not_found': 'Device \'{name}\' not found',
        'volume_set_failed': 'Failed to set volume',
        'volume_operation_failed': 'Volume operation failed',
        'volume_saved': 'Volume saved',
        'failed_save_volume': 'Failed to save volume',
        'failed_start_sleep': 'Failed to start sleep timer',
        'sleep_stopped': 'Sleep timer stopped',
        'failed_stop_sleep': 'Failed to stop sleep timer',
        'an_internal_error_occurred': 'An internal error occurred',
        'volume_set_saved': 'Volume set to {volume} and saved to configuration',
        'page_not_found': 'Page not found',
        'internal_server_error_page': 'Internal server error',
        
        # Time & Date
        'and': 'and',
        'hour': 'hour',
        'hours': 'hours',
        'minute': 'minute', 
        'minutes': 'minutes',
        'sleep_timer_preview': 'Your sleep timer would run for {duration} and end at {time}.',
        
        # Weekdays
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday', 
        'thursday': 'Thursday',
        'friday': 'Friday',
        'saturday': 'Saturday',
        'sunday': 'Sunday',
        'mon': 'Mon',
        'tue': 'Tue',
        'wed': 'Wed',
        'thu': 'Thu',
        'fri': 'Fri',
        'sat': 'Sat',
        'sun': 'Sun',
    }
}

def get_language(request: Optional[Any] = None) -> str:
    """Determines language based on Accept-Language header.
    
    Args:
        request: Flask request object with headers
        
    Returns:
        str: Language code ('de' or 'en')
    """
    if not request or not hasattr(request, 'headers'):
        return 'en'
    
    try:
        accept_language = request.headers.get('Accept-Language', '').lower()
        
        # German if explicitly requesting German
        if 'de' in accept_language:
            return 'de'
        
        # All other languages = English
        return 'en'
    except (AttributeError, TypeError):
        # Fallback for malformed requests
        return 'en'

def get_user_language(request: Optional[Any] = None) -> str:
    """Alias for get_language for backward compatibility.
    
    Args:
        request: Flask request object with headers
        
    Returns:
        str: Language code ('de' or 'en')
    """
    return get_language(request)

def t(key: str, lang: str = 'en', **kwargs: Any) -> str:
    """Translation function with placeholder support.
    
    Args:
        key: Translation key to lookup
        lang: Language code ('de' or 'en')
        **kwargs: Placeholder values for string formatting
        
    Returns:
        str: Translated and formatted string
    """
    # Get translation with fallback chain: lang -> en -> key
    translation = TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS['en'].get(key, key))
    
    # Replace placeholders safely
    if kwargs:
        try:
            return translation.format(**kwargs)
        except (KeyError, ValueError, TypeError):
            # Return unformatted translation if formatting fails
            return translation
    
    return translation

def get_translations(lang: str = 'en') -> Dict[str, str]:
    """Returns all translations for a language.
    
    Args:
        lang: Language code ('de' or 'en')
        
    Returns:
        dict: All translations for the specified language
    """
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])

def t_api(key: str, request=None, **kwargs) -> str:
    """Translation function for API responses with automatic language detection.
    
    Args:
        key: Translation key to lookup
        request: Flask request object for language detection
        **kwargs: Placeholder values for string formatting
        
    Returns:
        str: Translated and formatted string
    """
    lang = get_user_language(request)
    return t(key, lang, **kwargs)
