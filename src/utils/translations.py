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
        'volume_label': '<i class="fas fa-volume-high"></i> Lautstärke',
        
        # Alarm Interface
        'alarm_configure': 'Wecker konfigurieren',
        'alarm_time_label': '<i class="fas fa-clock"></i> Weckzeit',
        'alarm_time_help': 'Uhrzeit, zu der der Wecker klingeln soll',
        'playlist_label': '<i class="fas fa-list-music"></i> Playlist',
        'playlist_help': 'Musik, die beim Wecken abgespielt wird',
        'device_label': '<i class="fas fa-volume-high"></i> Lautsprecher',
        'device_help': 'Gerät, auf dem die Musik abgespielt wird',
        'further_options': 'Weitere Optionen',
        'fade_in': 'Fade-In',
        'shuffle': 'Shuffle',
        'enable_alarm': 'Wecker aktivieren',
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
        'sleep_ends_in': 'Sleep endet in {min}m {sec}s',
        
        # Music Library
        'library_title': 'Musik-Bibliothek',
        'search_music': 'Musik suchen...',
        'loading_music': 'Musik wird geladen...',
        'playlists_tab': '<i class="fas fa-list"></i> Playlists',
        'albums_tab': '<i class="fas fa-compact-disc"></i> Alben',
        'songs_tab': '<i class="fas fa-music"></i> Songs',
        'artists_tab': '<i class="fas fa-microphone"></i> Künstler',
        'play_music': 'Abspielen',
        'no_music_found': 'Keine Musik gefunden',
        'select_speaker': 'Lautsprecher wählen',
        'select_speaker_message': 'Bitte wähle einen Lautsprecher zum Abspielen der Musik aus.',
        'speaker_required': 'Lautsprecher erforderlich',
        'loading_devices': 'Lautsprecher werden geladen...',
        'no_devices_found': 'Keine Lautsprecher gefunden',
        'speaker_error': 'Fehler beim Laden der Lautsprecher',
        
        # Status Messages
        'settings_saved': 'Einstellungen gespeichert!',
        'error_saving': 'Fehler beim Speichern der Einstellungen',
        'saving_settings': 'Einstellungen werden gespeichert...',
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
        'volume_label': '<i class="fas fa-volume-high"></i> Volume',
        
        # Alarm Interface
        'alarm_configure': 'Configure Alarm',
        'alarm_time_label': '<i class="fas fa-clock"></i> Wake-up Time',
        'alarm_time_help': 'Time when the alarm should ring',
        'playlist_label': '<i class="fas fa-list-music"></i> Playlist',
        'playlist_help': 'Music to play when waking up',
        'device_label': '<i class="fas fa-volume-high"></i> Speaker',
        'device_help': 'Device to play music on',
        'further_options': 'Additional Options',
        'fade_in': 'Fade-In',
        'shuffle': 'Shuffle',
        'enable_alarm': 'Enable Alarm',
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
        'sleep_ends_in': 'Sleep ends in {min}m {sec}s',
        
        # Music Library
        'library_title': 'Music Library',
        'search_music': 'Search music...',
        'loading_music': 'Loading music...',
        'playlists_tab': '<i class="fas fa-list"></i> Playlists',
        'albums_tab': '<i class="fas fa-compact-disc"></i> Albums',
        'songs_tab': '<i class="fas fa-music"></i> Songs',
        'artists_tab': '<i class="fas fa-microphone"></i> Artists',
        'play_music': 'Play',
        'no_music_found': 'No music found',
        'select_speaker': 'Select speaker',
        'select_speaker_message': 'Please select a speaker to play the music.',
        'speaker_required': 'Speaker required',
        'loading_devices': 'Loading speakers...',
        'no_devices_found': 'No speakers found',
        'speaker_error': 'Error loading speakers',
        
        # Status Messages
        'settings_saved': 'Settings saved!',
        'error_saving': 'Error saving settings',
        'saving_settings': 'Saving settings...',
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