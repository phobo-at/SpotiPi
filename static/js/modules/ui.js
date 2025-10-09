// /static/js/modules/ui.js
// Manages all DOM manipulations and UI updates
import { DOM, CONFIG, userIsDragging, lastUserInteraction, setActiveDevice } from './state.js';
import { t } from './translation.js';
import { getPlaybackStatus, getSleepStatus, fetchAPI, unwrapResponse } from './api.js';
import { setUserIsDragging } from './state.js';

let cachedSleepStatus = null;
let cachedSleepTimestamp = 0;

/**
 * Updates playback info and track display
 * @param {boolean} updateVolume - Whether to update the volume as well
 */
export function applyPlaybackStatus(data, { updateVolume = true } = {}) {
    if (!data || typeof data !== 'object') return;

    if (document.visibilityState !== 'visible') {
      // Still update internal device cache for later use
      if (data?.device) {
        setActiveDevice(data.device);
      }
      return;
    }

    const playbackData = data;

    if (playbackData?.error) {
      if (window.location.href.includes('debug=true')) {
        console.log('No active playback or API error:', playbackData.error);
      }
      handleNoActivePlayback();
      return;
    }

    if (playbackData?.is_playing !== undefined) {
      updatePlayPauseButtonText(playbackData.is_playing);
    }

    if (playbackData?.device) {
      setActiveDevice(playbackData.device);
    } else {
      setActiveDevice(null);
    }

    if (updateVolume && playbackData?.device?.volume_percent !== undefined) {
      updateVolumeSlider(playbackData.device.volume_percent);
    }

    if (playbackData?.current_track) {
      updateCurrentTrack(playbackData.current_track);
    } else {
      hideCurrentTrack();
    }
}

export async function updatePlaybackInfo(updateVolume = true) {
    if (document.visibilityState !== 'visible') return;
    try {
      const raw = await getPlaybackStatus();
      const data = unwrapResponse(raw);

      applyPlaybackStatus(data, { updateVolume });
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
    globalLabel: '#volume-display'
  });

  // Update global slider and label only
  if (elements.globalSlider && elements.globalLabel) {
    elements.globalSlider.value = percent;
    elements.globalLabel.innerText = percent;
  }

  // Note: Alarm volume (#alarm_volume_slider) and sleep volume are independent
  // and should not be updated by global volume changes
}

/**
 * Updates the display only, without syncing with Spotify
 * @param {number} value - Volume value (0-100)
 */
export function updateLocalVolumeDisplay(value) {
  const elements = DOM.getElements({
    globalSlider: '#global-volume',
    globalLabel: '#volume-display'
  });

  // Update global label and slider only
  if (elements.globalLabel) elements.globalLabel.innerText = value;
  if (elements.globalSlider) elements.globalSlider.value = value;

  // Note: Alarm and sleep volume controls are independent of global volume
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
export function applySleepStatus(data, { cache = true } = {}) {
    if (!data || typeof data !== 'object') return;

    if (cache) {
      cachedSleepStatus = data;
      cachedSleepTimestamp = Date.now();
    }

    const elements = DOM.getElements({
      sleepTimer: '#sleep-timer',
      sleepBtn: '#sleep-toggle-btn',
      sleepEnabled: '#sleep_enabled',
      sleepEnabledActive: '#sleep_enabled_active',
      sleepForm: '#sleep-form',
      activeSleepMode: '#active-sleep-mode'
    });

    const remainingSeconds = Math.max(0, Math.floor(data.remaining_seconds ?? data.remaining_time ?? 0));

    if (elements.sleepTimer) {
      if (!data.active || remainingSeconds <= 0) {
        elements.sleepTimer.innerText = t('no_sleep_timer') || 'No sleep timer';
      } else {
        const min = Math.floor(remainingSeconds / 60);
        const sec = remainingSeconds % 60;
        const label = t('sleep_timer_label') || 'Sleep ends in';
        elements.sleepTimer.innerText = `${label} ${min}:${sec.toString().padStart(2, '0')}`;
      }
    }

    if (elements.sleepBtn) {
      elements.sleepBtn.innerText = data.active
        ? (t('stop_sleep') || 'Stop sleep')
        : (t('start_sleep') || 'Start sleep');
    }

    if (elements.sleepEnabled) {
      elements.sleepEnabled.checked = !!data.active;
    }
    if (elements.sleepEnabledActive) {
      elements.sleepEnabledActive.checked = !!data.active;
    }

    if (elements.sleepForm && elements.activeSleepMode) {
      if (data.active && remainingSeconds > 0) {
        elements.sleepForm.style.display = 'none';
        elements.activeSleepMode.style.display = 'block';
      } else {
        elements.sleepForm.style.display = 'block';
        elements.activeSleepMode.style.display = 'none';
      }
    }
}

export function tickSleepCountdown() {
    if (!cachedSleepStatus || !cachedSleepStatus.active) {
      return;
    }

    const elapsed = Math.floor((Date.now() - cachedSleepTimestamp) / 1000);
    const baseRemaining = Math.floor(cachedSleepStatus.remaining_seconds ?? cachedSleepStatus.remaining_time ?? 0);
    const remaining = Math.max(0, baseRemaining - elapsed);

    applySleepStatus({
      ...cachedSleepStatus,
      remaining_seconds: remaining,
      remaining_time: remaining
    }, { cache: false });

    if (remaining <= 0) {
      cachedSleepStatus = { ...cachedSleepStatus, active: false, remaining_seconds: 0, remaining_time: 0 };
    }
}

export async function updateSleepTimer(providedData = null) {
    if (document.visibilityState !== 'visible' && !providedData) return;

    try {
      const data = providedData
        ? providedData
        : unwrapResponse(await getSleepStatus());

      if (data?.error) {
        return;
      }

      applySleepStatus(data);
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
export function applyAlarmStatus(data) {
    if (!data || typeof data !== 'object') return;

    const elements = DOM.getElements({
      alarmTimer: '#alarm-timer',
      enabledToggle: '#enabled',
      enabledToggleActive: '#enabled_active',
      alarmForm: '#alarm-form',
      activeAlarmMode: '#active-alarm-mode',
      nextAlarmSummary: '#next-alarm-summary',
      alarmActiveInfo: '#alarm-active-info-text',
      alarmDeviceName: '#alarm-device-name'
    });

    if (elements.enabledToggle && typeof data.enabled === 'boolean') {
      elements.enabledToggle.checked = data.enabled;
    }
    if (elements.enabledToggleActive && typeof data.enabled === 'boolean') {
      elements.enabledToggleActive.checked = data.enabled;
    }

    if (elements.alarmForm && elements.activeAlarmMode) {
      if (data.enabled) {
        elements.alarmForm.classList.add('hidden');
        elements.activeAlarmMode.classList.remove('hidden');
      } else {
        elements.alarmForm.classList.remove('hidden');
        elements.activeAlarmMode.classList.add('hidden');
      }
    }

    if (elements.alarmTimer) {
      const baseLabel = t('alarm_set_for') || 'Alarm set for';
      const noAlarmLabel = t('no_alarm_active') || 'No alarm active';
      const volumeLabel = t('volume') || 'Volume';

      const statusMessage = data.enabled
        ? `${baseLabel} ${data.time}<br><span class="volume-info">${volumeLabel}: ${data.alarm_volume}%</span>`
        : noAlarmLabel;
      elements.alarmTimer.innerHTML = statusMessage;
    }

    if (elements.nextAlarmSummary) {
      const nextInfo = data.next_alarm && typeof data.next_alarm === 'string' && data.next_alarm.trim()
        ? data.next_alarm
        : (t('alarm_next_unknown') || 'Pending');
      elements.nextAlarmSummary.textContent = nextInfo;
    }

    if (elements.alarmActiveInfo && data.time) {
      elements.alarmActiveInfo.textContent = t('alarm_active_info', { time: data.time }) || `Alarm scheduled for ${data.time}`;
    }

    if (elements.alarmDeviceName) {
      const deviceLabel = data.device_name && data.device_name.trim()
        ? data.device_name
        : (t('alarm_device_unknown') || 'Unknown device');
      elements.alarmDeviceName.textContent = deviceLabel;
    }
}

export async function updateAlarmStatus(providedData = null) {
    try {
      const data = providedData
        ? providedData
        : unwrapResponse(await fetchAPI("/alarm_status"));

      if (data?.error) {
        console.warn('Could not get alarm status:', data.error);
        return;
      }

      applyAlarmStatus(data);
    } catch (error) {
      console.error('Failed to update alarm status:', error);
    }
}
