// /static/js/modules/ui.js
// Manages all DOM manipulations and UI updates
import { DOM, CONFIG, userIsDragging, lastUserInteraction, setActiveDevice } from './state.js';
import { t } from './translation.js';
import { getPlaybackStatus, getSleepStatus, fetchAPI, unwrapResponse } from './api.js';
import { setUserIsDragging } from './state.js';
import { playIcon, pauseIcon } from './icons.js';

let cachedSleepStatus = null;
let cachedSleepTimestamp = 0;

/**
 * Creates a ripple effect on button click
 * Material Design-inspired touch feedback
 * @param {MouseEvent|TouchEvent} event
 */
export function createRipple(event) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  
  const button = event.currentTarget;
  if (!button) return;
  
  const rect = button.getBoundingClientRect();
  const ripple = document.createElement('span');
  
  const x = (event.clientX || event.touches?.[0]?.clientX) - rect.left;
  const y = (event.clientY || event.touches?.[0]?.clientY) - rect.top;
  const size = Math.max(rect.width, rect.height) * 2;
  
  ripple.className = 'ripple';
  ripple.style.cssText = `
    left: ${x - size / 2}px;
    top: ${y - size / 2}px;
    width: ${size}px;
    height: ${size}px;
  `;
  
  button.appendChild(ripple);
  ripple.addEventListener('animationend', () => ripple.remove());
}

/**
 * Initialize ripple effects on all interactive buttons
 */
export function initRippleEffects() {
  const selectors = [
    '.toggle-buttons button',
    '.control-btn',
    '.btn-primary',
    '.weekday-bubble'
  ];
  
  selectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(button => {
      // Avoid duplicate listeners
      if (!button.dataset.rippleInit) {
        button.addEventListener('click', createRipple);
        button.dataset.rippleInit = 'true';
      }
    });
  });
}

/**
 * Smoothly hide an element with animation
 * @param {HTMLElement} element - Element to hide
 */
function smoothHide(element) {
  if (!element || element.classList.contains('hidden')) return;
  
  // Add hidden class and let CSS transition handle the rest
  element.classList.add('hidden');
}

/**
 * Smoothly show an element with animation
 * @param {HTMLElement} element - Element to show
 */
function smoothShow(element) {
  if (!element || !element.classList.contains('hidden')) return;
  
  // Remove hidden class and let CSS transition handle the rest
  element.classList.remove('hidden');
}

function isSafeMediaUrl(candidate) {
  if (typeof candidate !== 'string' || !candidate.trim()) {
    return false;
  }

  try {
    const parsed = new URL(candidate, window.location.origin);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
}

function renderAlbumFallback(albumCover) {
  if (!albumCover) return;
  albumCover.replaceChildren();

  const fallback = document.createElement('div');
  fallback.className = 'album-fallback';

  const svgNs = 'http://www.w3.org/2000/svg';
  const iconEl = document.createElementNS(svgNs, 'svg');
  iconEl.setAttribute('class', 'icon icon-2x');
  iconEl.setAttribute('viewBox', '0 0 24 24');
  iconEl.setAttribute('fill', 'currentColor');
  iconEl.setAttribute('aria-hidden', 'true');

  const path = document.createElementNS(svgNs, 'path');
  path.setAttribute('d', 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z');
  iconEl.appendChild(path);
  fallback.appendChild(iconEl);
  albumCover.appendChild(fallback);
}

function renderAlarmTimerDetails(target, data) {
  if (!target) return;

  const baseLabel = t('alarm_set_for') || 'Alarm set for';
  const noAlarmLabel = t('no_alarm_active') || 'No alarm active';
  const volumeLabel = t('volume') || 'Volume';
  const devicePrefix = t('alarm_device_label') || 'Device:';
  const timeLabel = String(data?.time || '--:--');
  const resolvedVolume = typeof data?.alarm_volume === 'number'
    ? data.alarm_volume
    : (typeof data?.volume === 'number' ? data.volume : 50);
  const deviceLabel = data?.device_name && String(data.device_name).trim()
    ? String(data.device_name)
    : (t('alarm_device_unknown') || 'Unknown device');

  if (!data?.enabled) {
    target.textContent = noAlarmLabel;
    return;
  }

  const volumeInfo = document.createElement('span');
  volumeInfo.className = 'volume-info';
  volumeInfo.textContent = `${volumeLabel}: ${resolvedVolume}%`;

  const deviceInfo = document.createElement('span');
  deviceInfo.className = 'device-info';
  deviceInfo.textContent = `${devicePrefix} ${deviceLabel}`;

  target.replaceChildren(
    document.createTextNode(`${baseLabel} ${timeLabel}`),
    document.createElement('br'),
    volumeInfo,
    document.createElement('br'),
    deviceInfo
  );
}

function setStatusContent(target, content, { allowHtml = false } = {}) {
  if (!target) return;

  if (allowHtml) {
    target.innerHTML = String(content ?? '');
  } else {
    target.textContent = String(content ?? '');
  }
}

function renderTrackSkeleton(statusKey = 'status_pending') {
  const trackContainer = document.querySelector('.current-track');
  if (!trackContainer) return;

  trackContainer.classList.add('is-loading');
  trackContainer.style.display = 'flex';

  const albumCover = trackContainer.querySelector('.album-cover');
  if (albumCover) {
    albumCover.classList.add('skeleton-tile');
    albumCover.innerHTML = '<div class="placeholder-glow skeleton-media"></div>';
  }

  const titleEl = trackContainer.querySelector('.track-info .title');
  if (titleEl) {
    titleEl.classList.add('placeholder-glow', 'skeleton-line');
    titleEl.textContent = '';
  }

  const artistEl = trackContainer.querySelector('.track-info .artist');
  if (artistEl) {
    artistEl.classList.add('placeholder-glow', 'skeleton-line');
    artistEl.textContent = '';
  }

  const statusEl = trackContainer.querySelector('.playback-status');
  if (statusEl) {
    statusEl.textContent = t(statusKey) || t('status_pending') || '';
  }
}

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
      // Set button to inactive when there's an error
      updatePlayPauseButtonText(false, false);
      hideCurrentTrack('spotify_error');
      return;
    }

    if (playbackData?.is_playing !== undefined) {
      // We have playback data, so enable the button
      updatePlayPauseButtonText(playbackData.is_playing, true);
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
      // No current track = set button to inactive
      updatePlayPauseButtonText(false, false);
      hideCurrentTrack('no_active_playback');
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
      // Set play/pause button to inactive and hide current track
      updatePlayPauseButtonText(false, false);
      hideCurrentTrack('network_error');
    }
}

export function initializeUI() {
    // Initial UI setup can go here
    console.log("UI Initialized");
    const saved = localStorage.getItem("activeTab") || "alarm";
    renderTrackSkeleton();
    showInterface(saved);
    updateTime();
    
    // Initialize ripple effects on interactive buttons
    initRippleEffects();
}

/**
 * Updates the global volume slider and display from Spotify
 * Handles both mobile and desktop volume controls
 * @param {number} percent - Volume value (0-100)
 */
export function updateVolumeSlider(percent) {
  // No updates during user interaction or cooldown
  if (userIsDragging || (Date.now() - lastUserInteraction < CONFIG.SYNC_COOLDOWN)) {
    return;
  }
  
  const elements = DOM.getElements({
    globalSlider: '#global-volume',
    globalSliderDesktop: '#global-volume-desktop',
    globalLabel: '#volume-display',
    globalLabelDesktop: '#volume-display-desktop'
  });

  // Update both sliders (mobile + desktop)
  if (elements.globalSlider) {
    elements.globalSlider.value = percent;
    elements.globalSlider.setAttribute('aria-valuenow', percent);
    elements.globalSlider.setAttribute('aria-valuetext', `${percent}%`);
  }
  if (elements.globalSliderDesktop) {
    elements.globalSliderDesktop.value = percent;
    elements.globalSliderDesktop.setAttribute('aria-valuenow', percent);
    elements.globalSliderDesktop.setAttribute('aria-valuetext', `${percent}%`);
  }
  
  // Update both labels (mobile + desktop) with % suffix
  if (elements.globalLabel) elements.globalLabel.textContent = `${percent}%`;
  if (elements.globalLabelDesktop) elements.globalLabelDesktop.textContent = `${percent}%`;

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
    globalSliderDesktop: '#global-volume-desktop',
    globalLabel: '#volume-display',
    globalLabelDesktop: '#volume-display-desktop'
  });

  // Update global labels (mobile + desktop)
  if (elements.globalLabel) elements.globalLabel.innerText = value + '%';
  if (elements.globalLabelDesktop) elements.globalLabelDesktop.innerText = value + '%';
  
  // Update sliders (mobile + desktop)
  if (elements.globalSlider) elements.globalSlider.value = value;
  if (elements.globalSliderDesktop) elements.globalSliderDesktop.value = value;

  // Note: Alarm and sleep volume controls are independent of global volume
}

/**
 * Updates the play/pause button state
 * @param {boolean} isPlaying - Whether playback is active
 * @param {boolean} hasPlayback - Whether there is any playback available (false = inactive state)
 */
export function updatePlayPauseButtonText(isPlaying, hasPlayback = true) {
  // Skip updates during user interaction cooldown (prevents overwriting optimistic updates)
  if (Date.now() - lastUserInteraction < CONFIG.SYNC_COOLDOWN) {
    return;
  }
  
  // Update new playback controls button
  const btnPlayPause = document.getElementById('btn-play-pause');
  if (btnPlayPause) {
    const playIconEl = btnPlayPause.querySelector('.icon-play');
    const pauseIconEl = btnPlayPause.querySelector('.icon-pause');
    
    if (playIconEl && pauseIconEl) {
      if (isPlaying) {
        playIconEl.classList.add('hidden');
        pauseIconEl.classList.remove('hidden');
      } else {
        playIconEl.classList.remove('hidden');
        pauseIconEl.classList.add('hidden');
      }
    }
    
    btnPlayPause.setAttribute('aria-label', isPlaying ? t('pause') || 'Pause' : t('play') || 'Play');
    btnPlayPause.disabled = !hasPlayback;
  }
  
  // Also update prev/next buttons enabled state
  const btnPrevious = document.getElementById('btn-previous');
  const btnNext = document.getElementById('btn-next');
  if (btnPrevious) btnPrevious.disabled = !hasPlayback;
  if (btnNext) btnNext.disabled = !hasPlayback;
  
  // Legacy button support
  const playPauseBtn = DOM.getElement('playPauseBtn');
  if (playPauseBtn) {
    // Update icon using SVG
    playPauseBtn.innerHTML = isPlaying ? pauseIcon() : playIcon();
    playPauseBtn.setAttribute('aria-label', isPlaying ? t('pause') || 'Pause' : t('play') || 'Play');
    
    // Update playing state
    if (isPlaying) {
      playPauseBtn.classList.add("playing");
    } else {
      playPauseBtn.classList.remove("playing");
    }
    
    // Update disabled/inactive state
    if (hasPlayback) {
      playPauseBtn.disabled = false;
      playPauseBtn.classList.remove("is-inactive");
    } else {
      playPauseBtn.disabled = true;
      playPauseBtn.classList.add("is-inactive");
    }
  }
}

/**
 * Hides the current track display
 */
export function hideCurrentTrack(statusKey = 'status_pending') {
  renderTrackSkeleton(statusKey);
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
    hideCurrentTrack('no_active_playback');
    return;
  }
  
  trackContainer.style.display = 'flex';
  trackContainer.classList.remove('is-loading');

  // Remove placeholder styles
  trackContainer.querySelectorAll('.placeholder-glow').forEach(el => {
    el.classList.remove('placeholder-glow');
  });
  
  // Update album cover
  const albumCover = trackContainer.querySelector('.album-cover');
  if (albumCover) {
    albumCover.replaceChildren();
    if (isSafeMediaUrl(trackData.album_image)) {
      const img = document.createElement('img');
      img.className = 'album-image';
      img.alt = 'Album Cover';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.src = trackData.album_image;
      albumCover.appendChild(img);
    } else {
      renderAlbumFallback(albumCover);
    }
    albumCover.classList.remove('skeleton-tile');
  }
  
  // Update track info
  const titleEl = trackContainer.querySelector('.title');
  const artistEl = trackContainer.querySelector('.artist');
  if (titleEl) {
    titleEl.textContent = trackData.name;
    titleEl.classList.remove('placeholder-glow', 'skeleton-line');
  }
  if (artistEl) {
    artistEl.textContent = trackData.artist;
    artistEl.classList.remove('placeholder-glow', 'skeleton-line');
  }
  
  // Update playback status
  const statusEl = trackContainer.querySelector('.playback-status');
  if (statusEl) {
    statusEl.textContent = trackData.is_playing ? (t('currently_playing') || 'Currently playing') : (t('paused') || 'Paused');
  }
  
  // Update playing state class
  if (trackData.is_playing) {
    trackContainer.classList.add('is-playing');
  } else {
    trackContainer.classList.remove('is-playing');
  }
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
 * Shows a toast notification with optional type
 * @param {string} message - The message to display
 * @param {Object} options - Toast options
 * @param {string} options.type - Toast type: 'success' | 'error' | 'warning' | 'info'
 * @param {number} options.duration - Duration in ms (default: 3000)
 */
export function showToast(message, options = {}) {
    const { type = 'success', duration = 3000 } = options;
    
    // Remove any existing toasts
    const existingToasts = document.querySelectorAll('.toast-notification');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.appendChild(toast);
    
    // Trigger reflow for animation
    void toast.offsetWidth;
    
    setTimeout(() => {
      toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, duration);
}

/**
 * Shows an error toast with appropriate styling
 * @param {string} message - Error message
 */
export function showErrorToast(message) {
    showToast(message, { type: 'error', duration: 4000 });
}

/**
 * Shows a connection status indicator
 * @param {boolean} isOnline - Whether the connection is online
 */
export function showConnectionStatus(isOnline) {
    if (!isOnline) {
        showToast(t('connection_lost') || 'Verbindung verloren', { type: 'warning', duration: 5000 });
    }
}

export function showInterface(mode) {
    const elements = DOM.getElements({
      alarmInterface: '#alarm-interface',
      sleepInterface: '#sleep-interface',
      libraryInterface: '#library-interface',
      settingsInterface: '#settings-interface',
      alarmTab: '#alarm-tab',
      sleepTab: '#sleep-tab',
      libraryTab: '#library-tab',
      settingsTab: '#settings-tab'
    });
    
    const panels = [
      elements.alarmInterface,
      elements.sleepInterface,
      elements.libraryInterface,
      elements.settingsInterface
    ].filter(Boolean);
    
    const targetPanel = {
      'alarm': elements.alarmInterface,
      'sleep': elements.sleepInterface,
      'library': elements.libraryInterface,
      'settings': elements.settingsInterface
    }[mode];
    
    // Use View Transitions API if available and motion is allowed
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    
    if (document.startViewTransition && !prefersReducedMotion) {
      document.startViewTransition(() => {
        panels.forEach(p => { if (p) p.style.display = 'none'; });
        if (targetPanel) targetPanel.style.display = 'block';
      });
    } else {
      // Fallback for browsers without View Transitions API
      panels.forEach(p => { if (p) p.style.display = 'none'; });
      if (targetPanel) targetPanel.style.display = 'block';
    }
    
    elements.alarmTab.setAttribute('aria-selected', String(mode === 'alarm'));
    elements.sleepTab.setAttribute('aria-selected', String(mode === 'sleep'));
    elements.libraryTab.setAttribute('aria-selected', String(mode === 'library'));
    if (elements.settingsTab) {
      elements.settingsTab.setAttribute('aria-selected', String(mode === 'settings'));
    }
    
    localStorage.setItem("activeTab", mode);
    
    if (mode === 'alarm') {
      setTimeout(updateAlarmStatus, 100);
    }
    
    // Load settings panel data when switching to settings tab
    if (mode === 'settings') {
      import('./settings.js').then(module => {
        module.onSettingsTabActivated();
      });
    }
}

/**
 * Allgemeine Funktion zum Aktualisieren eines Status-Elements mit visueller Rückmeldung
 * @param {string} elementId - ID des Status-Elements
 * @param {string} message - Die Nachricht, die angezeigt werden soll
 * @param {boolean} addAnimation - Ob eine Speichern-Animation hinzugefügt werden soll
 * @param {string} resetMessage - Optional: Nachricht, auf die nach der Animation zurückgesetzt wird
 */
export function updateStatus(elementId, message, addAnimation = false, resetMessage = null, options = {}) {
    const statusElement = DOM.getElement(elementId);
    if (!statusElement) return;
    
    setStatusContent(statusElement, message, options);
    
    if (addAnimation) {
      statusElement.classList.add('saved');
      setTimeout(() => {
        statusElement.classList.remove('saved');
        
        if (resetMessage) {
          setStatusContent(statusElement, resetMessage, options);
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
      activeAlarmMode: '#active-alarm-mode'
    });

    if (elements.enabledToggle && typeof data.enabled === 'boolean') {
      elements.enabledToggle.checked = data.enabled;
    }
    if (elements.enabledToggleActive && typeof data.enabled === 'boolean') {
      elements.enabledToggleActive.checked = data.enabled;
    }

    if (elements.alarmForm && elements.activeAlarmMode) {
      if (data.enabled) {
        smoothHide(elements.alarmForm);
        smoothShow(elements.activeAlarmMode);
      } else {
        smoothShow(elements.alarmForm);
        smoothHide(elements.activeAlarmMode);
      }
    }

    renderAlarmTimerDetails(elements.alarmTimer, data);
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
