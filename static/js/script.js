// =============================
// 🌐 Constants & Configuration
// =============================

const CONFIG = {
  SYNC_COOLDOWN: 2000,          // 2 seconds cooldown after user interaction
  UPDATE_INTERVALS: {
    SLEEP_TIMER: 1000,          // Update sleep timer (1 second)
    PLAYBACK: 5000,             // Update play/pause (5 seconds) - weniger aggressiv
    VOLUME: 10000               // Sync volume (10 seconds)
  }
};

// State variables
let userIsDragging = false;
let lastUserInteraction = 0;

// Central DOM element cache for frequently used elements
const DOM = {
  getElement(id) {
    if (!this._cache) this._cache = {};
    if (!this._cache[id]) this._cache[id] = document.getElementById(id);
    return this._cache[id];
  },
  
  getElements(selectors) {
    const elements = {};
    for (const key in selectors) {
      if (selectors[key].startsWith('#')) {
        // ID-Selector
        elements[key] = this.getElement(selectors[key].substring(1));
      } else {
        // General CSS selector
        elements[key] = document.querySelector(selectors[key]);
      }
    }
    return elements;
  },
  
  clearCache() {
    this._cache = {};
  }
};

// =================
// 🔄 API-Functions
// =================

/**
 * General function for API calls
 * @param {string} url - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} - API response as JSON
 */
async function fetchAPI(url, options = {}) {
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
      return await response.json();
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

/**
 * Gets the current playback status
 * @returns {Promise<Object} Playback status
 */
async function getPlaybackStatus() {
  return await fetchAPI("/playback_status");
}

/**
 * Gets the current sleep status
 * @returns {Promise<Object>} Sleep status
 */
async function getSleepStatus() {
  return await fetchAPI("/sleep_status");
}

/**
 * Sets the volume and saves it
 * @param {number} value - Volume value (0-100)
 */
async function setVolumeAndSave(value) {
  lastUserInteraction = Date.now();
  updateLocalVolumeDisplay(value);
  
  try {
    await Promise.all([
      fetchAPI("/volume", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `volume=${value}`
      }),
      fetchAPI("/save_volume", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `volume=${value}`
      })
    ]);
  } catch (error) {
    console.error('Failed to set and save volume:', error);
  }
}

// =======================
// 🔊 Volume Control
// =======================

/**
 * Updates the global volume slider and hidden input fields
 * @param {number} percent - Volume value (0-100)
 */
function updateVolumeSlider(percent) {
  // No updates during user interaction or cooldown
  if (userIsDragging || (Date.now() - lastUserInteraction < CONFIG.SYNC_COOLDOWN)) {
    return;
  }
  
  const elements = DOM.getElements({
    globalSlider: '#global-volume',
    globalLabel: '#volume-display',
    alarmVolume: '#volume',
    sleepVolume: '#sleep-volume'
  });

  // Update global slider and label
  if (elements.globalSlider && elements.globalLabel) {
    elements.globalSlider.value = percent;
    elements.globalLabel.innerText = percent;
  }

  // Update hidden input fields
  if (elements.alarmVolume) elements.alarmVolume.value = percent;
  if (elements.sleepVolume) elements.sleepVolume.value = percent;
}

/**
 * Updates the display only, without syncing with Spotify
 * @param {number} value - Volume value (0-100)
 */
function updateLocalVolumeDisplay(value) {
  const elements = DOM.getElements({
    globalSlider: '#global-volume',
    globalLabel: '#volume-display',
    alarmVolume: '#volume',
    sleepVolume: '#sleep-volume'
  });

  // Update global label and slider
  if (elements.globalLabel) elements.globalLabel.innerText = value;
  if (elements.globalSlider) elements.globalSlider.value = value;

  // Update hidden input fields
  if (elements.alarmVolume) elements.alarmVolume.value = value;
  if (elements.sleepVolume) elements.sleepVolume.value = value;
}

// Event handler for slider
function handleSliderStart() {
  userIsDragging = true;
}

function handleSliderEnd(value) {
  userIsDragging = false;
  lastUserInteraction = Date.now();
  setVolumeAndSave(value);
}

function handleSliderChange(value) {
  updateLocalVolumeDisplay(value);
}

/**
 * Synchronizes the volume slider with the actual Spotify volume
 */
async function syncVolumeFromSpotify() {
  if (document.visibilityState !== 'visible') return;
  if (userIsDragging || (Date.now() - lastUserInteraction < CONFIG.SYNC_COOLDOWN)) {
    return;
  }
  
  try {
    const data = await getPlaybackStatus();
    if (data?.device?.volume_percent !== undefined) {
      updateVolumeSlider(data.device.volume_percent);
    }
  } catch {
    // Errors already logged in fetchAPI
  }
}

// =======================
// ⏸️ Play/Pause Control
// =======================

/**
 * Translation function for JavaScript
 * @param {string} key - The key of the string to be translated
 * @param {Object} params - Parameters for replacing placeholders in the translation
 * @returns {string} - The translated string or the key itself if no translation was found
 */
function t(key, params = {}) {
  if (!window.TRANSLATIONS || !window.TRANSLATIONS[key]) {
    console.warn(`Translation missing for key: ${key}`);
    return key; // Fallback
  }
  
  let translation = window.TRANSLATIONS[key];
  
  // Replace placeholders - robust implementation
  try {
    Object.keys(params).forEach(param => {
      const regex = new RegExp(`\\{${param}\\}`, 'g');
      translation = translation.replace(regex, params[param]);
    });
  } catch (error) {
    console.error(`Error in translation for key ${key}:`, error);
    return key;
  }
  
  return translation;
}

/**
 * Updates the play/pause icon
 * @param {boolean} isPlaying - Whether playback is active
 */
function updatePlayPauseButtonText(isPlaying) {
  const playPauseBtn = DOM.getElement('playPauseBtn');
  if (playPauseBtn) {
    playPauseBtn.innerHTML = isPlaying ? '<i class="fas fa-pause"></i>' : '<i class="fas fa-play"></i>';
    playPauseBtn.setAttribute('aria-label', isPlaying ? t('play_pause') : t('play_pause'));
    if (isPlaying) {
      playPauseBtn.classList.add("playing");
    } else {
      playPauseBtn.classList.remove("playing");
    }
  }
}

/**
 * Toggles playback state (Play <-> Pause)
 */
async function togglePlayPause() {
  try {
    await fetchAPI("/toggle_play_pause", { method: "POST" });
    // Optimistically update the UI, then fetch the true state
    setTimeout(() => updatePlaybackInfo(false), 150);
  } catch (error) {
    console.error('Failed to toggle play/pause:', error);
  }
}

/**
 * Updates playback info and track display
 * @param {boolean} updateVolume - Whether to update the volume as well
 */
async function updatePlaybackInfo(updateVolume = true) {
  if (document.visibilityState !== 'visible') return;
  try {
    const data = await getPlaybackStatus();

    // Check if data contains an error field or no active playback
    if (data?.error) {
      if (window.location.href.includes('debug=true')) {
        console.log('No active playback or API error:', data.error);
      }
      handleNoActivePlayback();
      return;
    }
    
    if (data?.is_playing !== undefined) {
      updatePlayPauseButtonText(data.is_playing);
    }
    
    if (updateVolume && data?.device?.volume_percent !== undefined) {
      updateVolumeSlider(data.device.volume_percent);
    }
    
    if (data?.current_track) {
      updateCurrentTrack(data.current_track);
    } else {
      // No track info available
      hideCurrentTrack();
    }
  } catch {
    // Errors already handled in fetchAPI
    handleNoActivePlayback();
  }
}

/**
 * Handles the case where no active playback exists
 */
function handleNoActivePlayback() {
  // Set play/pause button to "Play"
  updatePlayPauseButtonText(false);

  // Hide current track
  hideCurrentTrack();
}

/**
 * Hides the current track display
 */
function hideCurrentTrack() {
  const trackContainer = document.querySelector('.current-track');
  if (trackContainer) {
    trackContainer.style.display = 'none';
  }
}

// ================
// 🎵 Track Display
// ================

/**
 * Updates the current track with album cover
 * @param {Object} trackData - Data of the current track
 */
function updateCurrentTrack(trackData) {
  const trackContainer = document.querySelector('.current-track');
  
  if (!trackContainer || !trackData) return;

  // Control container visibility
  if (!trackData.name) {
    trackContainer.style.display = 'none';
    return;
  }
  
  trackContainer.style.display = 'flex';

  // Remove placeholder styles
  trackContainer.querySelectorAll('.placeholder-glow').forEach(el => {
    el.classList.remove('placeholder-glow');
  });
  const titleEl = trackContainer.querySelector('.title');
  const artistEl = trackContainer.querySelector('.artist');
  if (titleEl) titleEl.classList.remove('placeholder-glow');
  if (artistEl) artistEl.classList.remove('placeholder-glow');

  // HTML structure
  let html = '';
  
  if (trackData.album_image) {
    html += `
      <div class="album-cover">
        <img src="${trackData.album_image}" alt="Album Cover" class="album-image">
      </div>
    `;
  } else {
    html += `
      <div class="album-cover">
      </div>
    `;
  }
  
  html += `
    <div class="track-info">
      <span class="title">${trackData.name}</span>
      <span class="artist">${trackData.artist}</span>
    </div>
  `;
  
  trackContainer.innerHTML = html;
}

// =======================
// 😴 Sleep Timer Handling
// =======================

/**
 * Updates the sleep timer display
 */
async function updateSleepTimer() {
  if (document.visibilityState !== 'visible') return;
  try {
    const data = await getSleepStatus();
    const elements = DOM.getElements({
      sleepTimer: '#sleep-timer',
      sleepBtn: '#sleep-toggle-btn',
      sleepEnabled: '#sleep_enabled',
      sleepEnabledActive: '#sleep_enabled_active',
      sleepForm: '#sleep-form',
      activeSleepMode: '#active-sleep-mode'
    });

    // Update timer display
    if (elements.sleepTimer) {
      if (!data.active || data.remaining_seconds <= 0) {
        elements.sleepTimer.innerText = t('no_sleep_timer');
      } else {
        const min = Math.floor(data.remaining_seconds / 60);
        const sec = data.remaining_seconds % 60;
        elements.sleepTimer.innerText = t('sleep_ends_in', {min: min, sec: sec});
      }
    }

    // Update button text
    if (elements.sleepBtn) {
      elements.sleepBtn.innerText = data.active ? t('sleep_stop') : t('sleep_start');
    }

    // Update toggle states for both forms
    if (elements.sleepEnabled) {
      elements.sleepEnabled.checked = data.active;
    }
    if (elements.sleepEnabledActive) {
      elements.sleepEnabledActive.checked = data.active;
    }

    // ✨ NEW: Switch between inactive and active UI modes
    if (elements.sleepForm && elements.activeSleepMode) {
      if (data.active && data.remaining_seconds > 0) {
        // Show active mode (hide form, show active mode)
        elements.sleepForm.style.display = 'none';
        elements.activeSleepMode.style.display = 'block';
      } else {
        // Show inactive mode (show form, hide active mode)
        elements.sleepForm.style.display = 'block';
        elements.activeSleepMode.style.display = 'none';
      }
    }
  } catch (error) {
    console.error("Failed to update sleep timer:", error);
  }
}

// =======================
// 😴 Sleep timer function
// =======================

/**
 * Shows or hides the custom duration field
 * @param {string} value - Selected value
 */
function handleDurationChange(value) {
  try {
    const customField = DOM.getElement("custom-duration-container");
    if (customField) {
      customField.style.display = value === "custom" ? "block" : "none";
      customField.classList.toggle("active", value === "custom");

      // Set focus on the input field when "custom"
      if (value === "custom") {
        setTimeout(() => {
          const customInput = DOM.getElement("custom_duration");
          if (customInput) customInput.focus();
        }, 50);
      }
    } else if (window.location.href.includes('debug=true')) {
      console.warn("Element 'custom-duration-container' not found");
    }
  } catch (err) {
    console.error("Error updating duration display:", err);
  }
}

// ===============================================
// 🕒 Uhrzeit-Aktualisierung
// ===============================================

function updateTime() {
  const now = new Date();
  const timeElem = DOM.getElement('current-time');
  if (timeElem) {
    const locale = window.LANGUAGE === 'de' ? 'de-DE' : 'en-US';
    timeElem.textContent = now.toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit'
    });
  }
}

// Initiale Aktualisierung
updateTime();

// Aktualisiere die Zeit jede Sekunde, aber nur wenn die Seite sichtbar ist
setInterval(() => {
  if (document.visibilityState === 'visible') {
    updateTime();
  }
}, 1000);

// Event-Listener für Sichtbarkeitsänderungen
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    updateTime(); // Aktualisiert sofort beim Zurückkehren zur Seite
    updatePlaybackInfo(); // Aktualisiert Wiedergabeinformationen beim Zurückkehren
  }
});

// ===============================
// 🧩 Status-Update-Funktionen
// ===============================

/**
 * Allgemeine Funktion zum Aktualisieren eines Status-Elements mit visueller Rückmeldung
 * @param {string} elementId - ID des Status-Elements
 * @param {string} message - Die Nachricht, die angezeigt werden soll
 * @param {boolean} addAnimation - Ob eine Speichern-Animation hinzugefügt werden soll
 * @param {string} resetMessage - Optional: Nachricht, auf die nach der Animation zurückgesetzt wird
 */
function updateStatus(elementId, message, addAnimation = false, resetMessage = null) {
  const statusElement = DOM.getElement(elementId);
  if (!statusElement) return;
  
  statusElement.innerHTML = message;
  
  if (addAnimation) {
    statusElement.classList.add('saved');
    setTimeout(() => {
      statusElement.classList.remove('saved');
      
      if (resetMessage) {
        statusElement.innerHTML = resetMessage;
      }
    }, 1000);
  }
  
  return statusElement;
}

// ===============================
// 🧩 Wecker-Speicherfunktionen
// ===============================

/**
 * Speichert die Wecker-Einstellungen automatisch bei Änderungen
 * Diese Funktion sendet die Formular-Daten asynchron an den Server
 */
function saveAlarmSettings() {
  const statusElement = updateStatus('alarm-timer', t('saving_settings'));
  if (!statusElement) return;
  
  const originalStatus = statusElement.innerHTML;
  const form = document.getElementById('alarm-form');
  if (!form) return;
  
  const formData = new FormData(form);
  const currentVolume = DOM.getElement('global-volume')?.value || 50;
  formData.append('alarm_volume', currentVolume);
  
  fetch('/save_alarm', {
    method: 'POST',
    body: formData
  })
  .then(response => {
    if (!response.ok) throw new Error('Speichern fehlgeschlagen');
    return response.json();
  })
  .then(data => {
    if (data.success) {
      const statusMessage = formData.get('enabled') === 'on' 
        ? `${t('alarm_set', {time: formData.get('time')})}<br><span class="volume-info">${t('alarm_volume_info', {volume: currentVolume})}</span>`
        : t('no_alarm');
        
      updateStatus('alarm-timer', statusMessage, true);
    } else {
      console.error('Fehler beim Speichern:', data.message);
      statusElement.innerHTML = originalStatus;
      alert(`${t('error_saving')}: ${data.message}`);
    }
  })
  .catch(error => {
    console.error('Fehler beim Speichern:', error);
    statusElement.innerHTML = originalStatus;
    alert(t('error_saving'));
  });
}

// ===============================
// 🧩 Sleep-Speicherfunktionen
// ===============================

/**
 * Speichert und aktiviert/deaktiviert die Sleep-Timer-Einstellungen
 * @param {boolean} activateNow - Ob der Sleep-Timer sofort aktiviert/deaktiviert werden soll
 */
function saveSleepSettings(activateNow) {
  const statusElement = updateStatus('sleep-timer', '⏳ Einstellungen werden gespeichert...');
  if (!statusElement) return;
  
  const originalStatus = statusElement.innerHTML;
  const form = document.getElementById('sleep-form');
  
  // Falls wir den Sleep aktivieren/deaktivieren wollen
  if (activateNow === true) {
    // Sleep-Status von aktivem Sleep prüfen
    const sleepToggle = DOM.getElement('sleep_enabled');
    if (!sleepToggle) {
      statusElement.innerHTML = originalStatus;
      return; // Sicherheitsprüfung
    }
    
    const sleepStatus = sleepToggle.checked;
    
    if (sleepStatus) {
      // Timer aktivieren (nur wenn wir im Formular-Modus sind)
      if (form) {
        const formData = new FormData(form);
        
        // Convert FormData to URLSearchParams for proper Content-Type
        const urlParams = new URLSearchParams();
        for (const [key, value] of formData.entries()) {
          urlParams.append(key, value);
        }
        
        fetch('/sleep', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
          },
          body: urlParams
        })
        .then(response => {
          if (!response.ok) throw new Error('Aktivierung fehlgeschlagen');
          return response.json();
        })
        .then(data => {
          if (data.success) {
            window.location.reload(); // Neu laden, um aktiven Sleep anzuzeigen
          } else {
            alert(`Fehler beim Aktivieren: ${data.message}`);
            statusElement.innerHTML = originalStatus;
          }
        })
        .catch(error => {
          console.error('Fehler beim Aktivieren:', error);
          statusElement.innerHTML = originalStatus;
          alert('Fehler beim Aktivieren des Sleep-Timers');
        });
      }
    } else {
      // Timer deaktivieren
      fetch('/stop_sleep', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        }
      })
      .then(response => {
        if (!response.ok) throw new Error('Deaktivierung fehlgeschlagen');
        return response.json();
      })
      .then(() => {
        window.location.reload(); // Neu laden, um inaktiven Sleep anzuzeigen
      })
      .catch(error => {
        console.error('Fehler beim Deaktivieren:', error);
        statusElement.innerHTML = originalStatus;
        alert('Fehler beim Deaktivieren des Sleep-Timers');
      });
    }
    return;
  }
  
  // Hier beginnt die Implementierung für normales Speichern (nicht aktivieren/deaktivieren)
  if (form) {
    const formData = new FormData(form);
    
    fetch('/save_sleep_settings', {
      method: 'POST',
      body: formData
    })
    .then(response => {
      if (!response.ok) throw new Error('Speichern fehlgeschlagen');
      return response.json();
    })
    .then(data => {
      if (data.success) {
        // Anzeige mit Erfolgsbestätigung aktualisieren und nach 1s zurücksetzen
        // falls kein aktiver Sleep-Timer läuft
        updateStatus('sleep-timer', t('settings_saved') || '💾 Einstellungen gespeichert', true, 
          !data.active_sleep ? `<i class="fas fa-compact-disc"></i> ${t('no_sleep_timer') || 'Kein aktiver Sleep-Timer'}` : null);
      } else {
        // Fehler anzeigen
        console.error('Fehler beim Speichern:', data.message);
        statusElement.innerHTML = originalStatus;
        alert(`${t('error_saving') || 'Fehler beim Speichern'}: ${data.message}`);
      }
    })
    .catch(error => {
      console.error('Fehler beim Speichern:', error);
      statusElement.innerHTML = originalStatus;
      alert('Fehler beim Speichern der Sleep-Einstellungen');
    });
  } else {
    // Kein Formular gefunden
    statusElement.innerHTML = originalStatus;
  }
}

// =======================================
// 📅 Weekday Selection Bubbles
// =======================================

/**
 * Initializes the weekday selection bubbles
 */
function initializeWeekdayBubbles() {
  const weekdayBubbles = document.querySelectorAll('.weekday-bubble');
  
  if (weekdayBubbles.length === 0) {
    console.log('ℹ️ Keine Wochentag-Bubbles gefunden - möglicherweise nicht auf Alarm-Seite');
    return;
  }
  
  console.log('📅 Initialisiere Wochentag-Bubbles...');
  
  // Click-Handler für alle Bubbles
  weekdayBubbles.forEach(bubble => {
    bubble.addEventListener('click', function() {
      toggleWeekday(this);
    });
  });
  
  // Lade gespeicherte Auswahl
  loadSavedWeekdays();
}

/**
 * Toggle-Funktion für einzelne Wochentage
 */
function toggleWeekday(bubble) {
  bubble.classList.toggle('active');
  
  // Visuelles Feedback
  bubble.style.transform = 'scale(0.9)';
  setTimeout(() => {
    bubble.style.transform = '';
  }, 100);
  
  // Speichere Auswahl
  saveWeekdaySelection();
  
  console.log(`📅 Wochentag ${bubble.getAttribute('data-day')} ${bubble.classList.contains('active') ? 'aktiviert' : 'deaktiviert'}`);
}

/**
 * Speichert die aktuelle Wochentag-Auswahl
 */
function saveWeekdaySelection() {
  const activeBubbles = document.querySelectorAll('.weekday-bubble.active');
  const selectedDays = Array.from(activeBubbles).map(bubble => bubble.getAttribute('data-day'));
  
  // Speichere in localStorage für persistente Auswahl
  localStorage.setItem('selectedWeekdays', JSON.stringify(selectedDays));
  
  // Update verstecktes Formular-Feld wenn vorhanden
  const weekdaysInput = document.querySelector('input[name="weekdays"]');
  if (weekdaysInput) {
    weekdaysInput.value = selectedDays.join(',');
  }
  
  console.log('💾 Wochentage gespeichert:', selectedDays);
}

/**
 * Lädt gespeicherte Wochentag-Auswahl
 */
function loadSavedWeekdays() {
  try {
    const saved = localStorage.getItem('selectedWeekdays');
    if (saved) {
      const selectedDays = JSON.parse(saved);
      
      selectedDays.forEach(day => {
        const bubble = document.querySelector(`.weekday-bubble[data-day="${day}"]`);
        if (bubble) {
          bubble.classList.add('active');
        }
      });
      
      console.log('📅 Wochentage geladen:', selectedDays);
    }
  } catch (error) {
    console.warn('⚠️ Fehler beim Laden der Wochentage:', error);
  }
}

// ===============================================
// 🚀 Asynchronous Data Loading
// ===============================================

/**
 * Loads all initial data needed for the UI asynchronously.
 */
async function loadInitialData() {
  console.log('🚀 Kicking off asynchronous data loading...');
  
  try {
    // Fetch data in parallel
    const [playback, devices] = await Promise.all([
      getPlaybackStatus(),
      fetchAPI('/api/spotify/devices')
    ]);

    // Check for errors in API responses
    if (devices?.error) {
      console.error('❌ Failed to load Spotify devices:', devices.error);
      updateDevices([]); // Update with empty list to show "No devices found"
    } else if (devices) {
      updateDevices(devices);
    }

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
  const selectors = document.querySelectorAll('select[name="device_name"]');
  if (!selectors.length) {
    console.warn('No device selectors found to update.');
    return;
  }

  selectors.forEach(selector => {
    const currentValue = selector.value;
    selector.innerHTML = ''; // Clear existing options

    if (!devices || devices.length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = t('no_devices_found') || 'Keine Geräte gefunden';
      selector.appendChild(option);
      return;
    }

    devices.forEach(device => {
      const option = document.createElement('option');
      option.value = device.name;
      option.textContent = `${device.name} (${device.type})`;
      if (device.is_active) {
        option.selected = true;
      }
      selector.appendChild(option);
    });

    // Restore previous selection if it still exists
    if (Array.from(selector.options).some(opt => opt.value === currentValue)) {
      selector.value = currentValue;
    }
  });
  console.log('✅ Device selectors updated.');
}


// ===============================
// 🧩 Initialisierung & Intervalle
// ===============================

function showInterface(mode) {
  const elements = DOM.getElements({
    alarmInterface: '#alarm-interface',
    sleepInterface: '#sleep-interface',
    libraryInterface: '#library-interface',
    alarmTab: '#alarm-tab',
    sleepTab: '#sleep-tab',
    libraryTab: '#library-tab'
  });
  
  elements.alarmInterface.style.display = (mode === 'alarm') ? 'block' : 'none';
  elements.sleepInterface.style.display = (mode === 'sleep') ? 'block' : 'none';
  elements.libraryInterface.style.display = (mode === 'library') ? 'block' : 'none';
  
  elements.alarmTab.setAttribute('aria-selected', String(mode === 'alarm'));
  elements.sleepTab.setAttribute('aria-selected', String(mode === 'sleep'));
  elements.libraryTab.setAttribute('aria-selected', String(mode === 'library'));
  
  localStorage.setItem("activeTab", mode);
  
  if (mode === 'alarm') {
    setTimeout(updateAlarmStatus, 100);
  }
  
  if (mode === 'library') {
    if (window.musicLibraryBrowser && !window.musicLibraryBrowser.isInitialized) {
      window.musicLibraryBrowser.initialize();
    }
  }
}

// Initialisierung nach DOM-Laden
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Initializing Spotipi application...');
  
  // DOM-Cache zurücksetzen beim Page-Load
  DOM.clearCache();
  
  // UI initialisieren
  const saved = localStorage.getItem("activeTab") || "alarm";
  showInterface(saved);
  
  // Load all dynamic data from Spotify
  loadInitialData();

  // Update static timers and UI elements
  updateSleepTimer();
  updateAlarmStatus();
  
  // Initialize playlist selectors
  console.log('🎵 Initializing playlist selectors...');
  
  // Initialize for alarm tab
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
        if (typeof saveAlarmSettings === 'function') {
          saveAlarmSettings();
        }
      }
    }
  });
  
  // Initialize for sleep tab
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
  
  // Store selectors globally for access from other functions
  window.playlistSelectors = {
    alarm: alarmPlaylistSelector,
    sleep: sleepPlaylistSelector
  };
  
  console.log('✅ Playlist selectors initialized');
  
  // Automatisches Speichern für Wecker-Einstellungen
  const alarmForm = document.getElementById('alarm-form');
  if (alarmForm) {
    const formElements = alarmForm.querySelectorAll('input, select');
    formElements.forEach(element => {
      if (element.id !== 'playlist_uri' && element.id !== 'sleep_playlist_uri') {
        element.addEventListener('change', saveAlarmSettings);
      }
    });
  }
  
  // Sleep-Toggle-Handler
  function handleSleepToggleChange(toggleElement) {
    const activeSleepMode = document.querySelector('#active-sleep-mode');
    if (activeSleepMode?.style.display !== 'none') {
      fetch('/stop_sleep', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        }
      })
      .then(response => {
        if (!response.ok) throw new Error('Deaktivierung fehlgeschlagen');
        return response.json();
      })
      .then(() => {
        updateSleepTimer();
      })
      .catch(error => {
        console.error('Fehler beim Deaktivieren:', error);
        alert('Fehler beim Deaktivieren des Sleep-Timers');
        toggleElement.checked = true;
      });
    } else {
      saveSleepSettings(true);
    }
  }

  // Register event listeners for both sleep toggles
  const sleepToggle = DOM.getElement('sleep_enabled');
  if (sleepToggle) {
    sleepToggle.addEventListener('change', function() {
      handleSleepToggleChange(this);
    });
  }

  const sleepToggleActive = DOM.getElement('sleep_enabled_active');
  if (sleepToggleActive) {
    sleepToggleActive.addEventListener('change', function() {
      handleSleepToggleChange(this);
    });
  }
  
  // Initialer Zustand des Custom-Feldes für Sleep-Timer
  const durationSelect = DOM.getElement("duration");
  if (durationSelect) {
    handleDurationChange(durationSelect.value);
    durationSelect.addEventListener("change", function() {
      handleDurationChange(this.value);
    });
  }

  // Wochentag-Bubbles Funktionalität initialisieren
  initializeWeekdayBubbles();
});

// Regelmäßige Updates mit konfigurierbaren Intervallen
setInterval(updateSleepTimer, CONFIG.UPDATE_INTERVALS.SLEEP_TIMER);
setInterval(() => updatePlaybackInfo(false), CONFIG.UPDATE_INTERVALS.PLAYBACK);
setInterval(syncVolumeFromSpotify, CONFIG.UPDATE_INTERVALS.VOLUME);


// In script.js - neue Funktion hinzufügen:
/**
 * Aktualisiert den Wecker-Status live
 */
async function updateAlarmStatus() {
  try {
    const data = await fetchAPI("/alarm_status");
    
    if (data?.error) {
      console.warn('Could not get alarm status:', data.error);
      return;
    }
    
    if (data) {
      const elements = DOM.getElements({
        alarmTimer: '#alarm-timer',
        enabledToggle: '#enabled'
      });
      
      if (elements.enabledToggle && elements.enabledToggle.checked !== data.enabled) {
        elements.enabledToggle.checked = data.enabled;
      }
      
      if (elements.alarmTimer) {
        const statusMessage = data.enabled 
          ? `${t('alarm_set', {time: data.time})}<br><span class="volume-info">${t('alarm_volume_info', {volume: data.alarm_volume})}</span>`
          : t('no_alarm');
        elements.alarmTimer.innerHTML = statusMessage;
      }
    }
  } catch (error) {
    console.error('Failed to update alarm status:', error);
  }
}

// ===============================================
// 🎵 Playlist Auswahl Modal
// ===============================================

class PlaylistSelector {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.warn(`⚠️ PlaylistSelector: Container '${containerId}' not found. Selector will be inactive.`);
      return;
    }
    this.options = {
      onSelect: options.onSelect || (() => {}),
      searchPlaceholder: options.searchPlaceholder || 'Playlist suchen...',
      noResultsText: options.noResultsText || t('no_music_found') || 'Keine Playlists gefunden',
      ...options
    };
    
    this.playlists = [];
    this.albums = [];
    this.tracks = [];
    this.artists = [];
    this.currentTab = 'playlists';
    this.selectedItem = null;
    this.isOpen = false;
    this.filteredItems = [];
    
    this.init();
  }
  
  init() {
    if (!this.container) {
      console.error('Playlist selector container not found');
      return;
    }

    // Verwende existierendes HTML aus Templates statt render()
    this.addModalToExistingHTML();
    this.attachEvents();
  }
  
  addModalToExistingHTML() {
    // Prüfe ob Modal bereits existiert
    if (this.container.querySelector('#playlist-modal')) {
      return;
    }
    
    // Füge Modal mit korrekter CSS-Struktur hinzu
    const modalHTML = `
      <div class="playlist-modal" id="playlist-modal">
        <div class="playlist-modal-header">
          <div class="playlist-tabs tab-container" id="playlist-tabs">
            <!-- Tabs werden dynamisch generiert -->
          </div>
          <div class="playlist-search">
            <input type="text" id="playlist-search" placeholder="${this.options.searchPlaceholder}" class="form-input">
            <button class="playlist-close-btn" id="playlist-close">✕</button>
          </div>
        </div>
        <div class="playlist-grid" id="playlist-grid">
          <div class="music-library-loader">
            <div class="music-library-spinner"></div>
            <div class="music-library-loader-text">Musik-Bibliothek wird geladen...</div>
          </div>
        </div>
      </div>
    `;
    
    this.container.insertAdjacentHTML('beforeend', modalHTML);
    console.log('✅ Modal added to container:', this.container.id);
  }
  
  setPlaylists(playlists) {
    this.playlists = playlists || [];
    this.updateCurrentTab();
  }
  
  setAlbums(albums) {
    this.albums = albums || [];
    this.updateCurrentTab();
  }
  
  setMusicLibrary(data) {
    if (!this.container) {
      console.warn('⚠️ PlaylistSelector: Cannot set music library, container not found');
      return;
    }
    if (data?.error) {
        this.playlists = [];
        this.albums = [];
        this.tracks = [];
        this.artists = [];
        this.createTabs(); // Will show nothing
        this.updateCurrentTab(); // Will show "no results"
        const grid = this.container.querySelector('#playlist-grid');
        if (grid) {
            grid.innerHTML = `<div class="playlist-no-results">${t('error_loading_music') || 'Fehler beim Laden der Musik'}</div>`;
        }
        return;
    }
    this.playlists = data.playlists || [];
    this.albums = data.albums || [];
    this.tracks = data.tracks || [];
    this.artists = data.artists || [];
    this.createTabs();
    this.updateCurrentTab();
  }
  
  createTabs() {
    if (!this.container) return;
    
    const tabsContainer = this.container.querySelector('#playlist-tabs');
    if (!tabsContainer) return;
    
    const tabs = [];
    
    // Nur Tabs mit Inhalten anzeigen
    if (this.playlists.length > 0) {
      tabs.push({
        id: 'playlists',
        icon: '',
        label: 'Playlists',
        count: this.playlists.length
      });
    }
    
    if (this.albums.length > 0) {
      tabs.push({
        id: 'albums', 
        icon: '',
        label: 'Alben',
        count: this.albums.length
      });
    }
    
    if (this.tracks.length > 0) {
      tabs.push({
        id: 'tracks',
        icon: '',
        label: 'Songs',
        count: this.tracks.length
      });
    }
    
    if (this.artists.length > 0) {
      tabs.push({
        id: 'artists',
        icon: '',
        label: 'Künstler',
        count: this.artists.length
      });
    }
    
    // Falls der aktuelle Tab nicht mehr verfügbar ist, wechsle zum ersten verfügbaren
    const availableTabIds = tabs.map(tab => tab.id);
    if (!availableTabIds.includes(this.currentTab) && availableTabIds.length > 0) {
      this.currentTab = availableTabIds[0];
    }
    
    // Tabs HTML generieren
    tabsContainer.innerHTML = tabs.map(tab => `
      <button class="playlist-tab tab-button ${this.currentTab === tab.id ? 'active' : ''}" data-tab="${tab.id}">
        ${tab.label}
      </button>
    `).join('');
  }
  
  setSelected(itemUri) {
    // Find in playlists, albums, tracks, and artists
    this.selectedItem = this.playlists.find(p => p.uri === itemUri) || 
                       this.albums.find(a => a.uri === itemUri) ||
                       this.tracks.find(t => t.uri === itemUri) ||
                       this.artists.find(ar => ar.uri === itemUri) || null;
    this.updatePreview();
    this.updateModal();
  }
  
  attachEvents() {
    const input = this.container.querySelector('.playlist-input');
    
    console.log('🔧 Attaching events for:', this.container.id);
    console.log('📋 Input found:', !!input);
    
    // Toggle Modal
    input?.addEventListener('click', (e) => {
      console.log('🎵 Playlist input clicked!');
      e.preventDefault();
      this.toggle();
    });
    
    // Tab switching
    this.container.addEventListener('click', (e) => {
      if (e.target.classList.contains('tab-button')) {
        const newTab = e.target.dataset.tab;
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        this.switchTab(newTab);
        return false;
      } else if (e.target.id === 'playlist-close' || e.target.classList.contains('playlist-close-btn')) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        this.close();
        return false;
      }
    });
    
    this.container.querySelector('#playlist-search')?.addEventListener('input', (e) => {
      this.filterItems(e.target.value);
    });
    
    // ESC key to close
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
  }
  
  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }
  
  open() {
    const input = this.container.querySelector('.playlist-input');
    const modal = this.container.querySelector('#playlist-modal');
    
    console.log('🎵 Opening modal...');
    console.log('📋 Input for toggle:', !!input);
    console.log('📋 Modal for toggle:', !!modal);
    
    input?.classList.add('active', 'modal-open');
    modal?.classList.add('show');
    this.isOpen = true;
    
    // iOS Safari scroll fix - multiple approaches
    setTimeout(() => {
      const container = this.container.querySelector('.form-group');
      if (container) {
        // Force layout recalculation
        container.offsetHeight;
        
        // Method 1: Try scrollIntoView with various options
        try {
          container.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start',
            inline: 'nearest'
          });
        } catch (e) {
          console.log('scrollIntoView failed:', e);
        }
        
        // Method 2: Direct element focus (iOS sometimes responds to this)
        setTimeout(() => {
          try {
            const rect = container.getBoundingClientRect();
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const elementTop = rect.top + scrollTop - 20;
            
            // Force scroll with multiple methods
            window.scrollTo({
              top: elementTop,
              behavior: 'smooth'
            });
            
            // Fallback for iOS
            document.documentElement.scrollTop = elementTop;
            document.body.scrollTop = elementTop;
            
          } catch (e) {
            console.log('Manual scroll failed:', e);
          }
        }, 100);
        
        // Method 3: iOS specific - focus an input to trigger scroll
        setTimeout(() => {
          const searchInput = this.container.querySelector('#playlist-search');
          if (searchInput) {
            searchInput.focus();
            searchInput.blur();
            searchInput.focus();
          }
        }, 200);
      }
    }, 200);
    
    // Focus search field after all scroll attempts
    setTimeout(() => {
      const search = this.container.querySelector('#playlist-search');
      if (search) {
        search.focus();
      }
    }, 500);
  }
  
  close() {
    const input = this.container.querySelector('.playlist-input');
    const modal = this.container.querySelector('#playlist-modal');
    const search = this.container.querySelector('#playlist-search');
    
    input?.classList.remove('active', 'modal-open');
    modal?.classList.remove('show');
    this.isOpen = false;
    
    // Clear search
    if (search) search.value = '';
    this.updateCurrentTab();
  }
  
  updatePreview() {
    const previewImage = this.container.querySelector('#preview-image');
    const previewName = this.container.querySelector('#preview-name');
    const previewMeta = this.container.querySelector('#preview-meta');
    
    if (this.selectedItem) {
      if (previewImage) {
        if (this.selectedItem.image_url) {
          previewImage.style.backgroundImage = `url(${this.selectedItem.image_url})`;
          previewImage.textContent = '';
        } else {
          previewImage.style.backgroundImage = '';
          previewImage.textContent = this.selectedItem.type === 'album' ? '💿' : '';
        }
      }
      
      if (previewName) {
        previewName.textContent = this.selectedItem.name;
      }
      
      if (previewMeta) {
        if (this.selectedItem.type === 'playlist') {
          const trackCount = this.selectedItem.track_count || 0;
          const creator = this.selectedItem.artist || 'Spotify';
          previewMeta.textContent = `${creator} · ${trackCount} Songs`;
        } else if (this.selectedItem.type === 'album') {
          const trackCount = this.selectedItem.track_count || 0;
          const artist = this.selectedItem.artist || 'Unknown Artist';
          previewMeta.textContent = `${artist} · ${trackCount} Tracks`;
        } else if (this.selectedItem.type === 'track' && this.selectedItem.artist) {
          previewMeta.textContent = this.selectedItem.artist;
        } else {
          const trackCount = this.selectedItem.track_count || 0;
          const trackText = this.selectedItem.type === 'album' ? 'Tracks' : 'Songs';
          previewMeta.textContent = `${trackCount} ${trackText}`;
        }
      }
    } else {
      if (previewImage) {
        previewImage.style.backgroundImage = '';
        previewImage.textContent = '';
      }
      if (previewName) previewName.textContent = t('playlist_select_text') || 'Musik auswählen';
      if (previewMeta) previewMeta.textContent = '';
    }
  }
  
  updateHiddenInput() {
    const hiddenInput = this.container.querySelector('#playlist_uri');
    if (hiddenInput) {
      hiddenInput.value = this.selectedItem ? this.selectedItem.uri : '';
    }
  }
  
  updateModal() {
    const grid = this.container.querySelector('#playlist-grid');
    if (!grid) return;
    
    // Zeige Loader wenn noch keine Daten geladen sind
    if (this.playlists.length === 0 && this.albums.length === 0 && this.tracks.length === 0 && this.artists.length === 0) {
      grid.innerHTML = `
        <div class="music-library-loader">
          <div class="music-library-spinner"></div>
          <div class="music-library-loader-text">Musik-Bibliothek wird geladen...</div>
        </div>
      `;
      return;
    }
    
    // Zeige "Keine Ergebnisse" wenn gefilterte Items leer sind
    if (this.filteredItems.length === 0) {
      const emptyText = this.currentTab === 'playlists' ? 
        (t('playlist_no_results') || 'Keine Playlists gefunden') : 
        this.currentTab === 'albums' ? (t('no_music_found') || 'Keine Alben gefunden') : 
        this.currentTab === 'artists' ? (t('no_music_found') || 'Keine Künstler gefunden') : (t('no_music_found') || 'Keine Songs gefunden');
      grid.innerHTML = `<div class="playlist-no-results">${emptyText}</div>`;
      return;
    }
    
    // Performance-Optimierung: Bei vielen Items (>100) asynchron rendern
    if (this.filteredItems.length > 100) {
      this.renderItemsAsync(grid);
      return;
    }
    
    // Standard-Rendering für kleinere Listen
    this.renderItemsSync(grid);
  }
  
  renderItemsSync(grid) {
    grid.innerHTML = this.filteredItems.map(item => {
      const isSelected = this.selectedItem && this.selectedItem.uri === item.uri;
      const imageStyle = item.image_url 
        ? `background-image: url(${item.image_url})` 
        : '';
      const trackCount = item.track_count || 0;
      const trackText = item.type === 'album' ? 'Tracks' : 'Songs';
      
      // Unterschiedliche Anzeige je nach Typ
      let metaText = '';
      if (item.type === 'playlist') {
        const creator = item.artist || 'Spotify';
        metaText = `${creator} · ${trackCount} Songs`;
      } else if (item.type === 'album') {
        const artist = item.artist || 'Unknown Artist';
        metaText = `${artist} · ${trackCount} Tracks`;
      } else if (item.type === 'artist') {
        metaText = item.artist || 'Künstler'; // Follower-Info aus dem artist Feld
      } else if (item.type === 'track' && item.artist) {
        metaText = item.artist; // Artist für einzelne Songs
      } else {
        metaText = `${trackCount} ${trackText}`;
      }
      
      return `
        <div class="playlist-item ${isSelected ? 'selected' : ''}" data-uri="${item.uri}">
          <div class="playlist-item-image" style="${imageStyle}">
            ${!item.image_url ? (item.type === 'album' ? '💿' : item.type === 'artist' ? '🎤' : '📋') : ''}
          </div>
          <div class="playlist-item-info">
            <div class="playlist-item-name">${item.name}</div>
            <div class="playlist-item-meta">${metaText}</div>
          </div>
        </div>
      `;
    }).join('');
    
    this.attachItemClickListeners(grid);
  }
  
  renderItemsAsync(grid) {
    // Zeige Loading während async render
    grid.innerHTML = `
      <div class="music-library-loader">
        <div class="music-library-spinner"></div>
        <div class="music-library-loader-text">Rendere ${this.filteredItems.length} ${this.currentTab === 'tracks' ? 'Songs' : 'Einträge'}...</div>
      </div>
    `;
    
    // Render in chunks um UI responsive zu halten
    setTimeout(() => {
      const chunkSize = 20;
      let html = '';
      
      for (let i = 0; i < this.filteredItems.length; i += chunkSize) {
        const chunk = this.filteredItems.slice(i, i + chunkSize);
        chunk.forEach(item => {
          const isSelected = this.selectedItem && this.selectedItem.uri === item.uri;
          const imageStyle = item.image_url 
            ? `background-image: url(${item.image_url})` 
            : '';
          const trackCount = item.track_count || 0;
          const trackText = item.type === 'album' ? 'Tracks' : 'Songs';
          
          // Unterschiedliche Anzeige je nach Typ
          let metaText = '';
          if (item.type === 'playlist') {
            const creator = item.artist || 'Spotify';
            metaText = `${creator} · ${trackCount} Songs`;
          } else if (item.type === 'album') {
            const artist = item.artist || 'Unknown Artist';
            metaText = `${artist} · ${trackCount} Tracks`;
          } else if (item.type === 'artist') {
            metaText = item.artist || 'Künstler'; // Follower-Info aus dem artist Feld
          } else if (item.type === 'track' && item.artist) {
            metaText = item.artist; // Artist für einzelne Songs
          } else {
            metaText = `${trackCount} ${trackText}`;
          }
          
          html += `
            <div class="playlist-item ${isSelected ? 'selected' : ''}" data-uri="${item.uri}">
              <div class="playlist-item-image" style="${imageStyle}">
                ${!item.image_url ? (item.type === 'album' ? '💿' : item.type === 'artist' ? '🎤' : '📋') : ''}
              </div>
              <div class="playlist-item-info">
                <div class="playlist-item-name">${item.name}</div>
                <div class="playlist-item-meta">${metaText}</div>
              </div>
            </div>
          `;
        });
        
        // Alle 100 Items UI update damit es responsive bleibt
        if (i > 0 && i % 100 === 0) {
          setTimeout(() => {}, 1); // Yield to browser
        }
      }
      
      grid.innerHTML = html;
      this.attachItemClickListeners(grid);
    }, 10);
  }
  
  attachItemClickListeners(grid) {
    grid.querySelectorAll('.playlist-item').forEach(item => {
      item.addEventListener('click', () => {
        const uri = item.dataset.uri;
        const selectedItem = this.filteredItems.find(p => p.uri === uri);
        this.selectItem(selectedItem);
      });
    });
  }
  
  switchTab(tabName) {
    this.currentTab = tabName;
    
    // Update tab buttons
    const tabs = this.container.querySelectorAll('.tab-button');
    tabs.forEach(tab => {
      tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    
    // Zeige sofort Loading für neue Tabs
    const grid = this.container.querySelector('#playlist-grid');
    if (grid) {
      grid.innerHTML = `
        <div class="music-library-loader">
          <div class="music-library-spinner"></div>
          <div class="music-library-loader-text">Lade ${tabName === 'playlists' ? 'Playlists' : tabName === 'albums' ? 'Alben' : tabName === 'artists' ? 'Künstler' : 'Songs'}...</div>
        </div>
      `;
    }
    
    // Kleine Verzögerung für UI-Update, dann Daten laden
    setTimeout(() => {
      this.updateCurrentTab();
    }, 50);
  }
  
  updateCurrentTab() {
    let items;
    switch (this.currentTab) {
      case 'playlists':
        items = this.playlists;
        break;
      case 'albums':
        items = this.albums;
        break;
      case 'tracks':
        items = this.tracks;
        break;
      case 'artists':
        items = this.artists;
        break;
      default:
        items = this.playlists;
    }
    this.filteredItems = [...items];
    this.updateModal();
  }
  
  filterItems(searchTerm) {
    let currentItems;
    switch (this.currentTab) {
      case 'playlists':
        currentItems = this.playlists;
        break;
      case 'albums':
        currentItems = this.albums;
        break;
      case 'tracks':
        currentItems = this.tracks;
        break;
      case 'artists':
        currentItems = this.artists;
        break;
      default:
        currentItems = this.playlists;
    }
    
    if (!searchTerm) {
      this.filteredItems = [...currentItems];
    } else {
      const term = searchTerm.toLowerCase();
      this.filteredItems = currentItems.filter(item =>
        item.name.toLowerCase().includes(term) ||
        (item.artist?.toLowerCase().includes(term))
      );
    }
    this.updateModal();
  }
  
  selectItem(item) {
    this.selectedItem = item;
    this.updatePreview();
    this.updateHiddenInput();
    this.close();
    
    // Trigger callback
    if (this.options.onSelect) {
      this.options.onSelect(item);
    }
    
    // Jetzt MANUELL speichern, da wir das automatische Change-Event deaktiviert haben
    if (typeof saveAlarmSettings === 'function') {
      saveAlarmSettings();
    }
  }
}

// Function to load music library for selectors
async function loadPlaylistsForSelectors() {
  console.log('📋 Loading music library from API...');
  
  try {
    const data = await fetchAPI('/api/music-library');

    if (data?.error) {
      console.error('❌ Failed to load music library:', data.error);
      // Update selectors to show an error state
      if (window.playlistSelectors?.alarm) {
        window.playlistSelectors.alarm.setMusicLibrary({ error: true });
      }
      if (window.playlistSelectors?.sleep) {
        window.playlistSelectors.sleep.setMusicLibrary({ error: true });
      }
      return; // Stop execution
    }

    console.log('📋 Music library loaded:', data?.total || 0, 'items');
    
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
      
      console.log('✅ Music library selectors updated successfully');
    } else {
      console.warn('⚠️ No music library data received');
    }
  } catch (error) {
    console.error('❌ Failed to load music library:', error);
  }
}

// ===============================================
// 🎵 Music Library Browser (Standalone)
// ===============================================

class MusicLibraryBrowser {
  constructor() {
    this.currentTab = 'playlists';
    this.devices = [];
    this.selectedDevice = null;
  }

  async initialize() {
    if (this.isInitialized) return;
    
    try {
      console.log('🎵 Initializing Music Library Browser...');
      await this.loadDevices();
      await this.loadMusicData();
      this.setupEventListeners();
      this.isInitialized = true;
      console.log('✅ Music Library Browser initialized');
    } catch (error) {
      console.error('❌ Failed to initialize Music Library Browser:', error);
      this.showError('Fehler beim Laden der Musik-Bibliothek');
    }
  }

  async loadDevices() {
    try {
      const devices = await fetchAPI('/api/spotify/devices');
      if (devices && !devices.error) {
        this.devices = devices;
      } else {
        this.devices = [];
      }
      this.populateDeviceSelector();
    } catch (error) {
      console.error('Error loading devices:', error);
      this.showDeviceError();
    }
  }

  populateDeviceSelector() {
    const selector = document.getElementById('speaker-selector');
    if (!selector) return;
    
    // Clear existing options
    selector.innerHTML = '';
    
    if (!this.devices || this.devices.length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = t('no_devices_found') || 'Keine Geräte gefunden';
      selector.appendChild(option);
      return;
    }

    this.devices.forEach(device => {
      const option = document.createElement('option');
      option.value = device.name;
      option.textContent = `${device.name} (${device.type})`;
      if (device.is_active) {
        option.selected = true;
        this.selectedDevice = device.name; // Set default selected device
      }
      selector.appendChild(option);
    });
  }

  async loadMusicData() {
    try {
      const data = await fetchAPI('/api/music-library');
      if (data && !data.error) {
        this.musicData = data;
        this.updateMusicDisplay();
      } else {
        console.error('Invalid music data received:', data);
      }
    } catch (error) {
      console.error('Error loading music data:', error);
    }
  }

  updateMusicDisplay() {
    // Implement display logic for music data
  }

  setupEventListeners() {
    const selector = document.getElementById('speaker-selector');
    if (selector) {
      selector.addEventListener('change', (e) => {
        this.selectedDevice = e.target.value;
        console.log('Selected device:', this.selectedDevice);
      });
    }
  }

  async playMusic(uri) {
    if (!this.selectedDevice) {
      alert(t('select_speaker_first') || 'Bitte wähle zuerst einen Lautsprecher aus.');
      return;
    }
    
    try {
      await fetchAPI('/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `device_name=${encodeURIComponent(this.selectedDevice)}&uri=${encodeURIComponent(uri)}`
      });
      // Optional: show feedback
      showToast(t('playback_started') || 'Wiedergabe gestartet!');
    } catch (error) {
      console.error('Failed to start playback:', error);
      alert(t('playback_failed') || 'Wiedergabe fehlgeschlagen.');
    }
  }
}

// Initialize the browser instance
window.musicLibraryBrowser = new MusicLibraryBrowser();

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
