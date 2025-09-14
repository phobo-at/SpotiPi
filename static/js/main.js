// Main entry point for the application
// Imports other modules and initializes the application logic

import { initializeEventListeners } from './modules/eventListeners.js';
import { initializeUI, updateSleepTimer, updateAlarmStatus, updatePlaybackInfo, updateVolumeSlider, hideCurrentTrack, updateCurrentTrack, updatePlayPauseButtonText, handleDurationChange } from './modules/ui.js';
import { DOM, CONFIG } from './modules/state.js';
import { getPlaybackStatus, fetchAPI, playMusic } from './modules/api.js';
import { PlaylistSelector } from './modules/playlistSelector.js';
import { saveAlarmSettings, activateSleepTimerDirect, deactivateSleepTimerDirect } from './modules/settings.js';
import { initializeWeekdayBubbles } from './modules/weekdays.js';
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
      // Fetch data in parallel (devices now returned via unified API envelope)
      const [playback, devicesResp] = await Promise.all([
        getPlaybackStatus(),
        fetchAPI('/api/spotify/devices')
      ]);
  
      // Unwrap devices response (supports both legacy array and new envelope)
      let deviceList = [];
      if (devicesResp) {
        if (Array.isArray(devicesResp)) {
          deviceList = devicesResp;
        } else if (devicesResp.data && Array.isArray(devicesResp.data.devices)) {
          deviceList = devicesResp.data.devices;
        } else if (Array.isArray(devicesResp.devices)) { // defensive fallback
          deviceList = devicesResp.devices;
        } else if (devicesResp.error || devicesResp.success === false) {
          console.warn('⚠️ Devices response indicates failure:', devicesResp.error || devicesResp.error_code);
        }
      }
  
      updateDevices(deviceList);
  
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

/**
 * Populates the device selectors with a list of devices.
 * @param {Array} devices - Array of device objects from the Spotify API.
 */
function updateDevices(devices) {
    // Allow passing API envelope directly
    if (!Array.isArray(devices) && devices && Array.isArray(devices.devices)) {
      devices = devices.devices;
    }
    if (!Array.isArray(devices)) {
      devices = [];
    }
  
    const selectors = document.querySelectorAll('select[name="device_name"]');
    if (!selectors.length) {
      // Silently ignore if not on a page with device selectors
      return;
    }
  
    selectors.forEach(selector => {
      const currentValue = selector.value;
      selector.innerHTML = '';
  
      if (devices.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = t('no_devices_found') || 'No devices found';
        selector.appendChild(option);
        return;
      }
  
      devices.forEach(device => {
        if (!device || !device.name) return;
        const option = document.createElement('option');
        option.value = device.name;
        option.textContent = `${device.name} (${device.type || '?'})`;
        if (device.is_active) option.selected = true;
        selector.appendChild(option);
      });
  
      // Restore previous selection if still present
      if (currentValue && Array.from(selector.options).some(o => o.value === currentValue)) {
        selector.value = currentValue;
      }
    });
    if (devices.length > 0) {
      console.log(`✅ Device selectors updated (${devices.length} devices).`);
    } else {
      console.log('⚠️ No devices available to populate.');
    }
}

// Function to load music library for selectors
async function loadPlaylistsForSelectors() {
    console.log('📋 Loading music library from API...');
    
    try {
      // Attempt to hydrate from LocalStorage first (fast path)
      const meta = JSON.parse(localStorage.getItem('musicLibraryMeta') || 'null');
      const cachedPartial = JSON.parse(localStorage.getItem('musicLibraryPartial') || 'null');
      if (cachedPartial && meta?.hash) {
        console.log('⚡ Using cached partial music library from LocalStorage');
        if (window.playlistSelectors?.alarm) window.playlistSelectors.alarm.setMusicLibrary(cachedPartial);
        if (window.playlistSelectors?.sleep) window.playlistSelectors.sleep.setMusicLibrary(cachedPartial);
        if (window.playlistSelectors?.library) window.playlistSelectors.library.setMusicLibrary(cachedPartial);
      }
  
      // Phase 1: fast partial load (playlists only) for quicker UI readiness, use basic field slimming
    const resp = await fetchAPI('/api/music-library/sections?sections=playlists&fields=basic');
      // Unwrap unified envelope
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
  
      console.log('📋 Partial music library loaded (phase 1):', (data?.playlists?.length || 0), 'playlists');
      
      if (data && (data.playlists || data.albums)) {
        // Update both selectors
        if (window.playlistSelectors?.alarm) {
          console.log('🔧 Setting music library for alarm selector...');
          window.playlistSelectors.alarm.setMusicLibrary(data);
          
          // Load currently selected playlist from data attribute
          const alarmContainer = document.getElementById('alarm-playlist-selector');
          const currentUri = alarmContainer?.dataset?.currentPlaylistUri;
          if (currentUri) {
            console.log('🔄 Loading previously selected alarm playlist:', currentUri);
            window.playlistSelectors.alarm.setSelected(currentUri);
          }
        }
        
        if (window.playlistSelectors?.sleep) {
          console.log('🔧 Setting music library for sleep selector...');
          window.playlistSelectors.sleep.setMusicLibrary(data);
          
          // Load currently selected playlist from data attribute
          const sleepContainer = document.getElementById('sleep-playlist-selector');
          const currentUri = sleepContainer?.dataset?.currentSleepPlaylistUri;
          if (currentUri) {
            console.log('🔄 Loading previously selected sleep playlist:', currentUri);
            window.playlistSelectors.sleep.setSelected(currentUri);
          }
        }
  
        if (window.playlistSelectors?.library) {
          console.log('🔧 Setting music library for library selector...');
          window.playlistSelectors.library.setMusicLibrary(data);
        }
        
        console.log('✅ Music library selectors updated (phase 1)');
        // Persist partial (playlists only) for reuse
        try {
          localStorage.setItem('musicLibraryPartial', JSON.stringify(data));
          localStorage.setItem('musicLibraryMeta', JSON.stringify({ hash: data.hash, ts: Date.now(), fields: 'basic', phase: 1 }));
        } catch (e) { console.debug('LocalStorage write failed (partial):', e); }
      } else {
        console.warn('⚠️ No music library data received');
      }
  
      // Phase 2: load remaining sections in background (albums, tracks, artists) lazily; we'll only prefetch hash now
      setTimeout(async () => {
        try {
          const fullResp = await fetchAPI('/api/music-library?fields=basic');
          let fullData = fullResp;
    if (fullResp?.data && (fullResp.data.albums || fullResp.data.tracks || fullResp.data.artists)) {
            fullData = fullResp.data;
          }
          if (fullData?.albums || fullData?.tracks || fullData?.artists) {
            // Merge by simply re-setting full library; selectors should re-render if open
              if (window.playlistSelectors?.alarm) window.playlistSelectors.alarm.setMusicLibrary(fullData);
              if (window.playlistSelectors?.sleep) window.playlistSelectors.sleep.setMusicLibrary(fullData);
              if (window.playlistSelectors?.library) window.playlistSelectors.library.setMusicLibrary(fullData);
              console.log('✅ Full music library loaded (phase 2)');
              try {
                localStorage.setItem('musicLibraryFull', JSON.stringify(fullResp)); // store with envelope for reuse
                localStorage.setItem('musicLibraryMeta', JSON.stringify({ hash: fullData.hash, ts: Date.now(), fields: 'basic', phase: 2 }));
              } catch (e) { console.debug('LocalStorage write failed (full):', e); }
          }
        } catch (e) {
          console.warn('⚠️ Failed background full library load:', e);
        }
      }, 250); // slight delay to let UI settle
    } catch (error) {
      console.error('❌ Failed to load music library:', error);
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
    }    initializeWeekdayBubbles();

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
