// /static/js/modules/api.js
// Handles all communication with the backend API
import { t } from './translation.js';
import { getActiveDevice } from './state.js';

console.log("api.js loaded");

/**
 * Shows a toast notification
 * @param {string} message 
 */
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => {
        document.body.removeChild(toast);
      }, 300);
    }, 3000);
}

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
    // For network errors
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
    try {
      // Get current play/pause button to provide immediate feedback
      const playPauseBtn = document.getElementById('playPauseBtn');
      if (!playPauseBtn) {
        console.warn('Play/Pause button not found');
        return;
      }
      
      const wasPlaying = playPauseBtn.innerHTML?.includes('fa-pause');
      
      // Immediate UI feedback - toggle the button state
      if (wasPlaying) {
        playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
        playPauseBtn.setAttribute('aria-label', 'Play');
      } else {
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';  
        playPauseBtn.setAttribute('aria-label', 'Pause');
      }
      
      // Fire and forget API call - don't wait for response
      fetchAPI("/toggle_play_pause", { method: "POST" }).catch(error => {
        console.error('Failed to toggle play/pause:', error);
        
        // Revert UI change on error
        if (wasPlaying) {
          playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
          playPauseBtn.setAttribute('aria-label', 'Pause');
        } else {
          playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
          playPauseBtn.setAttribute('aria-label', 'Play');
        }
      });
      
    } catch (error) {
      console.error('Failed to toggle play/pause:', error);
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
        if (response?.success && response?.data?.devices) {
            console.log(`🔄 Fast device refresh: ${response.data.devices.length} devices loaded`);
            return response.data.devices;
        } else {
            console.warn('⚠️ Fast device refresh failed:', response?.error || response?.message);
            return [];
        }
    } catch (error) {
        console.error('❌ Error in fast device refresh:', error);
        return [];
    }
}

/**
 * Device refresh with change detection
 * @param {Array} currentDevices - Current device list for comparison
 * @returns {Promise<{devices: Array, hasChanges: boolean}>}
 */
export async function refreshDevicesWithChangeDetection(currentDevices = []) {
    try {
        const newDevices = await refreshDevicesFast();
        
        // Simple change detection: compare device count and device IDs
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
        
        return { devices: newDevices, hasChanges };
    } catch (error) {
        console.error('❌ Error in device change detection:', error);
        return { devices: currentDevices, hasChanges: false };
    }
}
