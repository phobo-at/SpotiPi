// /static/js/modules/ui.js
// Manages all DOM manipulations and UI updates
import { DOM, CONFIG, userIsDragging, lastUserInteraction } from './state.js';
import { t } from './translation.js';
import { getPlaybackStatus, getSleepStatus, fetchAPI } from './api.js';
import { setUserIsDragging } from './state.js';

/**
 * Updates playback info and track display
 * @param {boolean} updateVolume - Whether to update the volume as well
 */
export async function updatePlaybackInfo(updateVolume = true) {
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
      // Set play/pause button to "Play" and hide current track
      updatePlayPauseButtonText(false);
      hideCurrentTrack();
    }
}

export function initializeUI() {
    // Initial UI setup can go here
    console.log("UI Initialized");
    const saved = localStorage.getItem("activeTab") || "alarm";
    showInterface(saved);
    updateTime();
}

/**
 * Updates the global volume slider and hidden input fields
 * @param {number} percent - Volume value (0-100)
 */
export function updateVolumeSlider(percent) {
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
export function updateLocalVolumeDisplay(value) {
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

/**
 * Updates the play/pause icon
 * @param {boolean} isPlaying - Whether playback is active
 */
export function updatePlayPauseButtonText(isPlaying) {
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
 * Hides the current track display
 */
export function hideCurrentTrack() {
    const trackContainer = document.querySelector('.current-track');
    if (trackContainer) {
      trackContainer.style.display = 'none';
    }
}

/**
 * Updates the current track with album cover
 * @param {Object} trackData - Data of the current track
 */
export function updateCurrentTrack(trackData) {
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

/**
 * Updates the sleep timer display
 */
export async function updateSleepTimer() {
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
          elements.sleepTimer.innerText = 'Kein Sleep-Timer';
        } else {
          const min = Math.floor(data.remaining_seconds / 60);
          const sec = data.remaining_seconds % 60;
          elements.sleepTimer.innerText = `Sleep endet in ${min}:${sec.toString().padStart(2, '0')}`;
        }
      }
  
      // Update button text
      if (elements.sleepBtn) {
        elements.sleepBtn.innerText = data.active ? 'Sleep stoppen' : 'Sleep starten';
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

/**
 * Shows or hides the custom duration field
 * @param {string} value - Selected value
 */
export function handleDurationChange(value) {
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

/**
 * Updates the time display
 */
export function updateTime() {
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

/**
 * Shows a toast notification
 * @param {string} message 
 */
export function showToast(message) {
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

export function showInterface(mode) {
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
}

/**
 * Allgemeine Funktion zum Aktualisieren eines Status-Elements mit visueller Rückmeldung
 * @param {string} elementId - ID des Status-Elements
 * @param {string} message - Die Nachricht, die angezeigt werden soll
 * @param {boolean} addAnimation - Ob eine Speichern-Animation hinzugefügt werden soll
 * @param {string} resetMessage - Optional: Nachricht, auf die nach der Animation zurückgesetzt wird
 */
export function updateStatus(elementId, message, addAnimation = false, resetMessage = null) {
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

/**
 * Aktualisiert den Wecker-Status live
 */
export async function updateAlarmStatus() {
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
            ? `${t('alarm_set_for') || 'Alarm set for'} ${data.time}<br><span class="volume-info">${t('volume') || 'Volume'}: ${data.alarm_volume}%</span>`
            : t('no_alarm_active') || 'No alarm active';
          elements.alarmTimer.innerHTML = statusMessage;
        }
      }
    } catch (error) {
      console.error('Failed to update alarm status:', error);
    }
}
