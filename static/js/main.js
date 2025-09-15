// Main entry point for the application
// Imports other modules and initializes the application logic

import { initializeEventListeners } from './modules/eventListeners.js';
import { initializeUI, updateSleepTimer, updateAlarmStatus, updatePlaybackInfo, updateVolumeSlider, hideCurrentTrack, updateCurrentTrack, updatePlayPauseButtonText, handleDurationChange } from './modules/ui.js';
import { DOM, CONFIG } from './modules/state.js';
import { getPlaybackStatus, fetchAPI, playMusic } from './modules/api.js';
import { PlaylistSelector } from './modules/playlistSelector.js';
import { saveAlarmSettings, activateSleepTimerDirect, deactivateSleepTimerDirect } from './modules/settings.js';
import { initializeWeekdayBubbles } from './modules/weekdays.js';
import { initializeDeviceManager } from './modules/deviceManager.js';
import { loadMusicLibraryProgressively } from './modules/streamingLoader.js';
import { t } from './modules/translation.js';

/**
 * Synchronizes the volume slider with the actual Spotify volume
 */
async function syncVolumeFromSpotify() {
    if (document.visibilityState !== 'visible') return;
    
    try {
      const data = await getPlaybackStatus();
      if (data?.device?.volume_percent !== undefined) {
        updateVolumeSlider(data.device.volume_percent);
      }
    } catch {
      // Errors already logged in fetchAPI
    }
}

/**
 * Loads all initial data needed for the UI asynchronously.
 */
async function loadInitialData() {
    console.log('🚀 Starting asynchronous data loading...');
    
    try {
      // Get initial playback status (devices are now handled by DeviceManager)
      const playback = await getPlaybackStatus();

      if (playback?.error) {
          console.warn('⚠️ Could not get playback status:', playback.error);
          handleNoActivePlayback(); // Set UI to default state
      } else if (playback) {
          if (playback.current_track) {
              updateCurrentTrack(playback.current_track);
          } else {
              hideCurrentTrack();
          }
  
          if (playback.is_playing !== undefined) {
              updatePlayPauseButtonText(playback.is_playing);
          }
  
          if (playback.device?.volume_percent !== undefined) {
              updateVolumeSlider(playback.device.volume_percent);
          }
      }
  
      // This function already exists and fetches the music library for the selectors
      loadPlaylistsForSelectors();
      
      console.log('✅ Initial data loading complete.');
    } catch (error) {
      console.error('❌ Failed during initial data load:', error);
      // Optionally, show an error message to the user
    }
}

// Function to load music library for selectors with progressive loading
async function loadPlaylistsForSelectors() {
    console.log('⚡ Loading music library with progressive streaming...');
    
    try {
        // Initialize streaming loader automatically (lazy initialization)
        
        // Collect all selectors for updating
        const selectors = {
            alarm: window.playlistSelectors?.alarm,
            sleep: window.playlistSelectors?.sleep, 
            library: window.playlistSelectors?.library
        };
        
        // Try fast LocalStorage hydration first (handled by streamingLoader)
        // await loadFromLocalStorageFirst(selectors);
        
        // Load progressively with streaming API
        await loadMusicLibraryProgressively(selectors, {
            onProgress: (progress) => {
                console.log(`⚡ Loading: ${progress.percentage.toFixed(1)}%`);
            },
            onComplete: () => {
                console.log('⚡ Progressive music library loading completed!');
                
                // Load previously selected playlists
                loadSelectedPlaylists();
            }
        });
        
    } catch (error) {
        console.error('❌ Progressive loading failed, trying fallback:', error);
        
        // Fallback to old loading method
        await loadPlaylistsFallback();
    }
}

/**
 * Fast LocalStorage hydration for instant UI
 */
async function loadFromLocalStorageFirst(selectors) {
    // LocalStorage hydration is now handled by streamingLoader directly
    console.log('💾 Cache hydration delegated to progressive loader');
}

/**
 * Load previously selected playlists
 */
function loadSelectedPlaylists() {
    // Load alarm playlist selection
    const alarmContainer = document.getElementById('alarm-playlist-selector');
    const currentAlarmUri = alarmContainer?.dataset?.currentPlaylistUri;
    if (currentAlarmUri && window.playlistSelectors?.alarm) {
        console.log('🔄 Restoring alarm playlist selection:', currentAlarmUri);
        window.playlistSelectors.alarm.setSelected(currentAlarmUri);
    }
    
    // Load sleep playlist selection  
    const sleepContainer = document.getElementById('sleep-playlist-selector');
    const currentSleepUri = sleepContainer?.dataset?.currentSleepPlaylistUri;
    if (currentSleepUri && window.playlistSelectors?.sleep) {
        console.log('🔄 Restoring sleep playlist selection:', currentSleepUri);
        window.playlistSelectors.sleep.setSelected(currentSleepUri);
    }
}

/**
 * Fallback to traditional loading if progressive fails
 */
async function loadPlaylistsFallback() {
    console.log('🔄 Using fallback loading method...');
    
    try {
        // Use the traditional API endpoints
        const resp = await fetchAPI('/api/music-library/sections?sections=playlists&fields=basic');
        
        let data = resp;
        if (resp?.data && (resp.data.playlists || resp.data.albums)) {
            data = resp.data;
        }

        if (resp?.success === false && !data.playlists && !data.albums) {
            console.error('❌ Failed to load music library:', resp.error || resp.message || resp.error_code);
            if (window.playlistSelectors?.alarm) window.playlistSelectors.alarm.setMusicLibrary({ error: true });
            if (window.playlistSelectors?.sleep) window.playlistSelectors.sleep.setMusicLibrary({ error: true });
            if (window.playlistSelectors?.library) window.playlistSelectors.library.setMusicLibrary({ error: true });
            return;
        }

        console.log('📋 Fallback music library loaded:', (data?.playlists?.length || 0), 'playlists');
        
        if (data && (data.playlists || data.albums)) {
            if (window.playlistSelectors?.alarm) {
                window.playlistSelectors.alarm.setMusicLibrary(data);
            }
            if (window.playlistSelectors?.sleep) {
                window.playlistSelectors.sleep.setMusicLibrary(data);
            }
            if (window.playlistSelectors?.library) {
                window.playlistSelectors.library.setMusicLibrary(data);
            }
            
            // Load selected playlists
            loadSelectedPlaylists();
        }
        
    } catch (error) {
        console.error('❌ Fallback loading also failed:', error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("SpotiPi Main Initializing...");
    DOM.clearCache();
    initializeUI();
    initializeEventListeners();
    loadInitialData();

    // Initialize playlist selectors
    const alarmPlaylistSelector = new PlaylistSelector('alarm-playlist-selector', {
        searchPlaceholder: t('playlist_search_placeholder') || 'Playlist suchen...',
        noResultsText: t('playlist_no_results') || 'Keine Playlists gefunden',
        onSelect: (playlist) => {
          console.log('🎵 Alarm playlist selected:', playlist.name);
          // Update hidden field for form submission
          const alarmForm = document.querySelector('#alarm-form');
          if (alarmForm) {
            const hiddenInput = alarmForm.querySelector('input[name="playlist_uri"]');
            if (hiddenInput) {
              hiddenInput.value = playlist.uri;
              console.log('🔄 Updated alarm playlist URI:', playlist.uri);
            }
            // Trigger auto-save for alarm settings
            saveAlarmSettings();
          }
        }
    });
    
    const sleepPlaylistSelector = new PlaylistSelector('sleep-playlist-selector', {
        searchPlaceholder: t('playlist_search_placeholder') || 'Playlist suchen...',
        noResultsText: t('playlist_no_results') || 'Keine Playlists gefunden',
        onSelect: (playlist) => {
            console.log('🎵 Sleep playlist selected:', playlist.name);
            // Update hidden field for form submission
            const sleepForm = document.querySelector('#sleep-form');
            if (sleepForm) {
            const hiddenInput = sleepForm.querySelector('input[name="playlist_uri"]');
            if (hiddenInput) {
                hiddenInput.value = playlist.uri;
                console.log('🔄 Updated sleep playlist URI:', playlist.uri);
            }
            }
        }
    });

    const libraryPlaylistSelector = new PlaylistSelector('library-playlist-selector', {
        searchPlaceholder: t('playlist_search_placeholder') || 'Playlist suchen...',
        noResultsText: t('playlist_no_results') || 'Keine Playlists gefunden',
        onSelect: (item) => {
          console.log('🎵 Library item selected:', item.name);
          const deviceSelector = DOM.getElement('library-speaker-selector');
          if (deviceSelector?.value) {
            playMusic(item.uri, deviceSelector.value);
          } else {
            // Fallback to the first available device if none is selected
            const firstDevice = document.querySelector('#library-speaker-selector option[value]');
            if (firstDevice?.value) {
              playMusic(item.uri, firstDevice.value);
            } else {
              alert(t('select_speaker_first') || 'Please select a speaker first.');
            }
          }
        }
    });

    window.playlistSelectors = {
        alarm: alarmPlaylistSelector,
        sleep: sleepPlaylistSelector,
        library: libraryPlaylistSelector
    };

    // Auto-save for alarm settings
    const alarmForm = document.getElementById('alarm-form');
    if (alarmForm) {
        const formElements = alarmForm.querySelectorAll('input:not([type="checkbox"]), select');
        formElements.forEach(element => {
            if (element.id !== 'playlist_uri' && element.id !== 'weekdays') {
                element.addEventListener('change', saveAlarmSettings);
            }
        });
    }

    // Auto-save for sleep settings 
    // Sleep settings are only saved when timer is activated
    // Duration and other settings are transferred together with the timer
    // This is more logical: settings become relevant only when timer is activated

    // Get sleep checkbox elements
    const sleepEnabled = DOM.getElement('sleep_enabled');
    const sleepEnabledActive = DOM.getElement('sleep_enabled_active');

    // Separate event handlers for each sleep checkbox - much cleaner!
    if (sleepEnabled) {
        sleepEnabled.addEventListener('change', function() {
            console.log('🔧 sleep_enabled changed:', this.checked);
            if (this.checked) {
                // Config checkbox was activated -> activate timer
                const form = document.getElementById('sleep-form');
                if (form) {
                    const formData = new FormData(form);
                    activateSleepTimerDirect(formData);
                }
            }
            // If unchecked, do nothing (timer is already inactive)
        });
    }
    
    if (sleepEnabledActive) {
        sleepEnabledActive.addEventListener('change', function() {
            console.log('🔧 sleep_enabled_active changed:', this.checked);
            if (!this.checked) {
                // Active checkbox was deactivated -> deactivate timer
                deactivateSleepTimerDirect();
            }
            // If checked, do nothing (timer is already running)
        });
    }
    
    initializeWeekdayBubbles();

    // Initialize automatic device management
    initializeDeviceManager();

    updateSleepTimer();
    updateAlarmStatus();
    updatePlaybackInfo();

    // Regular updates
    setInterval(updateSleepTimer, CONFIG.UPDATE_INTERVALS.SLEEP_TIMER);
    setInterval(() => updatePlaybackInfo(false), CONFIG.UPDATE_INTERVALS.PLAYBACK);
    setInterval(syncVolumeFromSpotify, CONFIG.UPDATE_INTERVALS.VOLUME);

    console.log("SpotiPi Main Initialized successfully.");
});

// Make functions globally available for inline HTML event handlers
window.handleDurationChange = handleDurationChange;
