// /static/js/modules/api.js
// Handles all communication with the backend API
import { t } from './translation.js';

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
    // Attach If-None-Match header when we have a stored hash for music library endpoints
    const headers = new Headers(options.headers || {});
    if (url.startsWith('/api/music-library') && !headers.has('If-None-Match')) {
      const cachedMeta = JSON.parse(localStorage.getItem('musicLibraryMeta') || 'null');
      if (cachedMeta?.hash) {
        headers.set('If-None-Match', cachedMeta.hash);
      }
    }
    const response = await fetch(url, { ...options, headers });

    // If it's a POST request, return the response directly
    if (options.method === 'POST') {
      return response;
    }

    // Special handling: 304 Not Modified for music library endpoints should reuse cached data
    if (response.status === 304 && url.startsWith('/api/music-library')) {
      try {
        const cachedFullRaw = localStorage.getItem('musicLibraryFull');
        if (cachedFullRaw) {
          const parsedFull = JSON.parse(cachedFullRaw);
          console.log('♻️ Using cached FULL music library (304 Not Modified)');
          return parsedFull; // envelope or data object as stored
        }
      } catch (e) { /* swallow */ }
      try {
        const cachedPartialRaw = localStorage.getItem('musicLibraryPartial');
        if (cachedPartialRaw) {
          const parsedPartial = JSON.parse(cachedPartialRaw);
          console.log('♻️ Using cached PARTIAL music library (304 Not Modified)');
          return parsedPartial; // plain data object
        }
      } catch (e) { /* swallow */ }
      // No cached data available; treat as soft success with empty payload
      return { success: true, data: {}, notModified: true };
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
 * Toggles playback state (Play <-> Pause)
 */
export async function togglePlayPause() {
    try {
      await fetchAPI("/toggle_play_pause", { method: "POST" });
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
