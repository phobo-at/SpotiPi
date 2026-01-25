// /static/js/modules/api.js
// Handles all communication with the backend API
import { t } from './translation.js';
import { getActiveDevice, setLastUserInteraction } from './state.js';
import { showToast, showErrorToast, showConnectionStatus } from './ui.js';
import { playIcon, pauseIcon } from './icons.js';

// Track connection state to avoid spam
let lastConnectionState = true;
let connectionToastShown = false;

/**
 * General function for API calls
 * @param {string} url - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} - API response as JSON
 */
export async function fetchAPI(url, options = {}) {
  try {
    // Backoff handling for polling endpoints
    if (typeof window.__API_BACKOFF_UNTIL === 'number' && Date.now() < window.__API_BACKOFF_UNTIL) {
      return { error: "Backoff", success: false, offline: true };
    }
    const response = await fetch(url, options);
    
    // Connection restored
    if (!lastConnectionState && !connectionToastShown) {
      showToast(t('connection_restored') || 'Verbindung wiederhergestellt', { type: 'success' });
      connectionToastShown = true;
      setTimeout(() => { connectionToastShown = false; }, 5000);
    }
    lastConnectionState = true;

    // If it's a POST request, return the response directly
    if (options.method === 'POST') {
      return response;
    }

    // For non-successful responses, return a structured error object instead of throwing an error
    if (!response.ok) {
      // Only log to console in debug mode
      if (window.location.href.includes('debug=true')) {
        console.warn(`API Status (${url}): ${response.status}`);
      }
      // Increase backoff on service unavailable
      if (response.status === 503) {
        window.__API_BACKOFF_MS = Math.min((window.__API_BACKOFF_MS || 2000) * 2, 30000);
        window.__API_BACKOFF_UNTIL = Date.now() + window.__API_BACKOFF_MS;
        // Show user feedback for service unavailable
        if (!options.silent) {
          showErrorToast(t('service_unavailable') || 'Dienst vorübergehend nicht verfügbar');
        }
      }
      // Return structured error response
      return { 
        error: `${response.status}`, 
        success: false 
      };
    }

    // Try to parse the response as JSON
    try {
      const json = await response.json();
      return json;
    } catch (parseError) {
      // If the response is not valid JSON
      if (window.location.href.includes('debug=true')) {
        console.warn(`Parse error (${url}):`, parseError);
      }
      return { 
        error: "Invalid response format", 
        success: false 
      };
    }
  } catch (networkError) {
    // For network errors - show user feedback
    if (lastConnectionState && !connectionToastShown) {
      showConnectionStatus(false);
      connectionToastShown = true;
      setTimeout(() => { connectionToastShown = false; }, 5000);
    }
    lastConnectionState = false;
    
    if (window.location.href.includes('debug=true')) {
      console.warn(`Network error (${url}):`, networkError);
    }
    // Exponential backoff on network errors
    window.__API_BACKOFF_MS = Math.min((window.__API_BACKOFF_MS || 2000) * 2, 30000);
    window.__API_BACKOFF_UNTIL = Date.now() + window.__API_BACKOFF_MS;
    return { 
      error: "Network error", 
      success: false,
      offline: true
    };
  }
}

// Unified API unwrap helper (tolerates legacy top-level fields)
export function unwrapResponse(obj) {
  if (!obj || typeof obj !== 'object') return obj;
  if ('success' in obj && obj.data && typeof obj.data === 'object') {
    // Merge data and keep meta under _meta
    return { ...obj.data, _meta: { success: obj.success, message: obj.message, error_code: obj.error_code } };
  }
  return obj; // legacy shape
}

/**
 * Gets the current playback status
 * @returns {Promise<Object>} Playback status
 */
export async function getPlaybackStatus() {
  const raw = await fetchAPI("/playback_status");
  return unwrapResponse(raw);
}

/**
 * Gets the current sleep status
 * @returns {Promise<Object>} Sleep status
 */
export async function getSleepStatus() {
  const raw = await fetchAPI("/sleep_status");
  return unwrapResponse(raw);
}

export async function getDashboardStatus() {
  const raw = await fetchAPI("/api/dashboard/status");
  return unwrapResponse(raw);
}

/**
 * Sets the volume and saves it
 * @param {number} value - Volume value (0-100)
 */
export async function setVolumeAndSave(value) {
  try {
    // Use unified volume endpoint with save_config=true
    await fetchAPI("/volume", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `volume=${value}&save_config=true`
    });
  } catch (error) {
    console.error('Failed to set and save volume:', error);
  }
}

/**
 * Sets the volume immediately (without saving to config)
 * @param {number} value - Volume value (0-100)
 */
export async function setVolumeImmediate(value) {
  try {
    // Use unified volume endpoint without save_config for immediate response
    const params = new URLSearchParams();
    params.set('volume', value);

    const activeDevice = getActiveDevice();
    if (activeDevice && activeDevice.id) {
      params.set('device_id', activeDevice.id);
    }

    await fetchAPI("/volume", {
      method: "POST", 
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString()
    });
  } catch (error) {
    console.error('Failed to set immediate volume:', error);
  }
}

// Throttling for immediate volume changes
let volumeThrottleTimer = null;
let lastVolumeValue = null;

function dispatchImmediateVolume(value) {
  if (value === null || value === undefined) {
    return;
  }

  try {
    const promise = setVolumeImmediate(value);
    if (promise && typeof promise.catch === 'function') {
      promise.catch(error => {
        console.error('Failed to set immediate volume:', error);
      });
    }
  } catch (error) {
    console.error('Failed to dispatch immediate volume:', error);
  }
}

/**
 * Throttled version of setVolumeImmediate - prevents API spam during slider dragging
 * @param {number} value - Volume value (0-100)
 * @param {number} delay - Throttle delay in ms (default: 200ms)
 */
export function setVolumeImmediateThrottled(value, delay = 120) {
  lastVolumeValue = value;

  if (volumeThrottleTimer) {
    clearTimeout(volumeThrottleTimer);
  }

  volumeThrottleTimer = setTimeout(() => {
    const valueToSend = lastVolumeValue;
    lastVolumeValue = null;
    volumeThrottleTimer = null;
    dispatchImmediateVolume(valueToSend);
  }, Math.max(0, delay));
}

/**
 * Flush any pending throttled volume update immediately.
 * @param {number|null} valueOverride - Optional value to send right away
 */
export function flushVolumeThrottle(valueOverride = null) {
  if (volumeThrottleTimer) {
    clearTimeout(volumeThrottleTimer);
    volumeThrottleTimer = null;
  }

  if (valueOverride !== null) {
    lastVolumeValue = valueOverride;
  }

  if (lastVolumeValue !== null) {
    const valueToSend = lastVolumeValue;
    lastVolumeValue = null;
    dispatchImmediateVolume(valueToSend);
  }
}

/**
 * Toggles playback state (Play <-> Pause) with immediate UI feedback
 */
export async function togglePlayPause() {
    // Set cooldown to prevent polling from overwriting optimistic UI update
    setLastUserInteraction(Date.now());
    
    try {
      // Get current play/pause button - check new controls first, then legacy
      const playPauseBtn = document.getElementById('btn-play-pause') || document.getElementById('playPauseBtn');
      if (!playPauseBtn) {
        console.warn('Play/Pause button not found');
        // Still try to toggle playback even without button
        await fetchAPI("/toggle_play_pause", { method: "POST" });
        return;
      }
      
      // For new control buttons, check icon visibility
      const playIcon = playPauseBtn.querySelector('.icon-play');
      const pauseIcon = playPauseBtn.querySelector('.icon-pause');
      
      // Detect state - new controls use hidden class, legacy uses playing class
      const wasPlaying = pauseIcon && !pauseIcon.classList.contains('hidden') ||
                         playPauseBtn.classList.contains('playing') || 
                         playPauseBtn.innerHTML?.includes('pause');
      
      // Immediate UI feedback
      if (playIcon && pauseIcon) {
        // New playback controls with separate icons
        if (wasPlaying) {
          playIcon.classList.remove('hidden');
          pauseIcon.classList.add('hidden');
          playPauseBtn.setAttribute('aria-label', t('play') || 'Play');
        } else {
          playIcon.classList.add('hidden');
          pauseIcon.classList.remove('hidden');
          playPauseBtn.setAttribute('aria-label', t('pause') || 'Pause');
        }
      } else {
        // Legacy button with innerHTML swap
        if (wasPlaying) {
          playPauseBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
          playPauseBtn.setAttribute('aria-label', t('play') || 'Play');
          playPauseBtn.classList.remove('playing');
        } else {
          playPauseBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
          playPauseBtn.setAttribute('aria-label', t('pause') || 'Pause');
          playPauseBtn.classList.add('playing');
        }
      }
      
      // Fire and forget API call - don't wait for response
      fetchAPI("/toggle_play_pause", { method: "POST" }).catch(error => {
        console.error('Failed to toggle play/pause:', error);
        showErrorToast(t('playback_error') || 'Wiedergabe-Fehler');
        
        // Revert UI change on error
        const playIconEl = playPauseBtn.querySelector('.icon-play');
        const pauseIconEl = playPauseBtn.querySelector('.icon-pause');
        
        if (playIconEl && pauseIconEl) {
          // New controls - revert icon visibility
          if (wasPlaying) {
            playIconEl.classList.add('hidden');
            pauseIconEl.classList.remove('hidden');
            playPauseBtn.setAttribute('aria-label', t('pause') || 'Pause');
          } else {
            playIconEl.classList.remove('hidden');
            pauseIconEl.classList.add('hidden');
            playPauseBtn.setAttribute('aria-label', t('play') || 'Play');
          }
        } else {
          // Legacy button
          if (wasPlaying) {
            playPauseBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
            playPauseBtn.setAttribute('aria-label', t('pause') || 'Pause');
            playPauseBtn.classList.add('playing');
          } else {
            playPauseBtn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
            playPauseBtn.setAttribute('aria-label', t('play') || 'Play');
            playPauseBtn.classList.remove('playing');
          }
        }
      });
      
    } catch (error) {
      console.error('Failed to toggle play/pause:', error);
    }
}

/**
 * Skip to next track
 */
export async function skipToNext() {
    // Set cooldown to prevent polling from overwriting optimistic UI update
    setLastUserInteraction(Date.now());
    
    try {
      const response = await fetchAPI("/api/playback/next", { method: "POST" });
      if (!response.ok) {
        console.error('Failed to skip to next track');
        showErrorToast(t('skip_error') || 'Konnte nicht zum nächsten Track springen');
      }
    } catch (error) {
      console.error('Failed to skip to next:', error);
      showErrorToast(t('skip_error') || 'Konnte nicht zum nächsten Track springen');
    }
}

/**
 * Skip to previous track
 */
export async function skipToPrevious() {
    // Set cooldown to prevent polling from overwriting optimistic UI update
    setLastUserInteraction(Date.now());
    
    try {
      const response = await fetchAPI("/api/playback/previous", { method: "POST" });
      if (!response.ok) {
        console.error('Failed to skip to previous track');
        showErrorToast(t('skip_error') || 'Konnte nicht zum vorherigen Track springen');
      }
    } catch (error) {
      console.error('Failed to skip to previous:', error);
      showErrorToast(t('skip_error') || 'Konnte nicht zum vorherigen Track springen');
    }
}

/**
 * Global playMusic function for playlist selectors
 * @param {string} uri 
 * @param {string} deviceName 
 */
export async function playMusic(uri, deviceName) {
    if (!deviceName) {
      alert(t('select_speaker_first') || 'Please select a speaker first.');
      return;
    }
    
    try {
      const response = await fetchAPI('/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `device_name=${encodeURIComponent(deviceName)}&uri=${encodeURIComponent(uri)}`
      });
      
      // fetchAPI returns raw response for POST requests, need to parse JSON
      if (response.ok) {
        const data = await response.json();
        if (data?.success) {
          showToast(t('playback_started') || 'Wiedergabe gestartet!');
        } else {
          console.error('Playback failed:', data);
          alert(t('playback_failed') || 'Wiedergabe fehlgeschlagen.');
        }
      } else {
        const errorData = await response.json();
        console.error('Playback failed:', errorData);
        alert(t('playback_failed') || 'Wiedergabe fehlgeschlagen.');
      }
    } catch (error) {
      console.error('Failed to start playback:', error);
      alert(t('playback_failed') || 'Wiedergabe fehlgeschlagen.');
    }
}

/**
 * Fast device refresh - bypasses cache for immediate updates
 * @returns {Promise<Array>} - Array of devices or empty array on error
 */
export async function refreshDevicesFast() {
    try {
        const response = await fetchAPI('/api/devices/refresh');
        if (response?.success && response?.data) {
            const payload = response.data;
            console.log(`🔄 Fast device refresh: ${payload.devices?.length || 0} devices loaded`);
            return {
                devices: payload.devices || [],
                status: payload.stale ? 'stale' : 'ok',
                cache: payload.cache || {},
                hydration: payload.hydration || {},
                lastUpdated: payload.lastUpdated,
                lastUpdatedIso: payload.lastUpdatedIso
            };
        }
        console.warn('⚠️ Fast device refresh failed:', response?.error || response?.message);
        return { devices: [], status: 'error', cache: {}, hydration: {} };
    } catch (error) {
        console.error('❌ Error in fast device refresh:', error);
        return { devices: [], status: 'error', cache: {}, hydration: {} };
    }
}

export async function getDevicesSnapshot({ forceRefresh = false } = {}) {
    const url = forceRefresh ? '/api/devices?refresh=1' : '/api/devices';
    const raw = await fetchAPI(url);
    return unwrapResponse(raw);
}

/**
 * Device refresh with change detection
 * @param {Array} currentDevices - Current device list for comparison
 * @returns {Promise<{devices: Array, hasChanges: boolean}>}
 */
export async function refreshDevicesWithChangeDetection(currentDevices = [], options = {}) {
    try {
        const force = options.force === true;
        const snapshot = await getDevicesSnapshot({ forceRefresh: force });
        const newDevices = snapshot?.devices || [];

        const hasChanges = (
            newDevices.length !== currentDevices.length ||
            !newDevices.every(newDevice => 
                currentDevices.some(currentDevice => 
                    currentDevice.id === newDevice.id && 
                    currentDevice.is_active === newDevice.is_active
                )
            )
        );
        
        if (hasChanges) {
            console.log('🔄 Device changes detected:', {
                old: currentDevices.length,
                new: newDevices.length,
                devices: newDevices.map(d => `${d.name} (${d.is_active ? 'active' : 'inactive'})`)
            });
        }
        
        return { 
            devices: newDevices, 
            hasChanges,
            status: snapshot?.status || 'pending',
            hydration: snapshot?.hydration || {},
            cache: snapshot?.cache || {},
            raw: snapshot
        };
    } catch (error) {
        console.error('❌ Error in device change detection:', error);
        return { devices: currentDevices, hasChanges: false, status: 'error', hydration: {}, cache: {} };
    }
}
