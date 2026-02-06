// /static/js/modules/eventListeners.js
// Centralizes all event listeners
import { DOM, setLastUserInteraction, setUserIsDragging, CONFIG } from './state.js';
import { updateLocalVolumeDisplay, handleDurationChange, showInterface, updateTime, updatePlaybackInfo, updateVolumeSlider } from './ui.js';
import { setVolumeImmediateThrottled, flushVolumeThrottle, togglePlayPause, fetchAPI, getPlaybackStatus, skipToNext, skipToPrevious } from './api.js';
import { saveAlarmSettings } from './settings.js';

console.log("eventListeners.js loaded");

// -----------------------------------------------
// 📳 Haptic Feedback System
// -----------------------------------------------

/**
 * Haptic feedback patterns (duration in ms)
 */
const HAPTIC = {
  TAP: 10,           // Light tap for navigation
  SUCCESS: [10, 50, 10], // Double pulse for success
  ERROR: [50, 30, 50],   // Stronger pattern for errors
  TOGGLE: 15         // Slightly longer for toggles
};

/**
 * Triggers haptic feedback on supported devices
 * @param {number|number[]} pattern - Vibration pattern in ms
 */
function triggerHaptic(pattern = HAPTIC.TAP) {
  if ('vibrate' in navigator) {
    try {
      navigator.vibrate(pattern);
    } catch {
      // Silently fail on unsupported devices
    }
  }
}

// Export for use in other modules
export { triggerHaptic, HAPTIC };

// Delayed volume sync timer
let volumeSyncTimer = null;

/**
 * Schedule a volume sync from Spotify after user interaction ends
 * This ensures the slider reflects the actual Spotify volume
 */
function scheduleVolumeSync() {
    if (volumeSyncTimer) {
        clearTimeout(volumeSyncTimer);
    }
    
    // Wait for cooldown + small buffer, then sync
    volumeSyncTimer = setTimeout(async () => {
        volumeSyncTimer = null;
        try {
            const data = await getPlaybackStatus();
            const payload = data?.playback || data;
            if (payload?.device?.volume_percent !== undefined) {
                updateVolumeSlider(payload.device.volume_percent);
            }
        } catch {
            // Errors already logged
        }
    }, CONFIG.SYNC_COOLDOWN + 500);
}

// Debouncing for alarm settings to prevent rapid-fire saves
let alarmSaveTimeout = null;
let lastAlarmSaveTime = 0;
const ALARM_SAVE_COOLDOWN = 2000; // 2 seconds between saves

function throttledSaveAlarmSettings(options = {}) {
    const immediate = Boolean(options.immediate);
    const now = Date.now();
    
    // Clear existing timeout
    if (alarmSaveTimeout) {
        clearTimeout(alarmSaveTimeout);
    }

    if (immediate) {
        lastAlarmSaveTime = now;
        console.log('🚨 Immediate alarm save (forced)');
        saveAlarmSettings();
        return;
    }
    
    // If enough time has passed since last save, save immediately
    if (now - lastAlarmSaveTime >= ALARM_SAVE_COOLDOWN) {
        lastAlarmSaveTime = now;
        console.log('🚨 Immediate alarm save (cooldown passed)');
        saveAlarmSettings();
    } else {
        // Otherwise, debounce the save
        alarmSaveTimeout = setTimeout(() => {
            lastAlarmSaveTime = Date.now();
            console.log('🚨 Debounced alarm save');
            saveAlarmSettings();
        }, 1000);
    }
}

export function initializeEventListeners() {
    console.log("Event Listeners Initializing...");

    const elements = DOM.getElements({
        alarmTab: '#alarm-tab',
        sleepTab: '#sleep-tab',
        libraryTab: '#library-tab',
        settingsTab: '#settings-tab',
        playPauseBtn: '#playPauseBtn',
        globalVolume: '#global-volume',
        globalVolumeDesktop: '#global-volume-desktop',
        durationSelect: '#duration',
        // Alarm form elements
        alarmEnabled: '#enabled',
        alarmEnabledActive: '#enabled_active',
        alarmTime: '#time',
        alarmVolumeSlider: '#alarm_volume_slider',
        deviceSelect: '#alarm-device-name',
        fadeInSelect: '#fade_in',
        shuffleCheckbox: '#shuffle'
    });

    // Tab switching with haptic feedback
    if (elements.alarmTab) elements.alarmTab.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); showInterface('alarm'); });
    if (elements.sleepTab) elements.sleepTab.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); showInterface('sleep'); });
    if (elements.libraryTab) elements.libraryTab.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); showInterface('library'); });
    if (elements.settingsTab) elements.settingsTab.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); showInterface('settings'); });

    const tabButtons = [
      elements.alarmTab,
      elements.sleepTab,
      elements.libraryTab,
      elements.settingsTab
    ].filter(Boolean);

    const getVisibleTabs = () => tabButtons.filter(tab => {
      if (!tab) return false;
      if (tab.hidden) return false;
      if (tab.style.display === 'none') return false;
      return true;
    });

    const activateTabByElement = (tab) => {
      if (!tab || !tab.id.endsWith('-tab')) return;
      const mode = tab.id.replace('-tab', '');
      showInterface(mode);
    };

    tabButtons.forEach(tab => {
      tab.addEventListener('keydown', (event) => {
        const visibleTabs = getVisibleTabs();
        if (!visibleTabs.length) return;

        const currentIndex = visibleTabs.indexOf(tab);
        if (currentIndex < 0) return;

        let nextIndex = null;
        switch (event.key) {
          case 'ArrowRight':
          case 'ArrowDown':
            nextIndex = (currentIndex + 1) % visibleTabs.length;
            break;
          case 'ArrowLeft':
          case 'ArrowUp':
            nextIndex = (currentIndex - 1 + visibleTabs.length) % visibleTabs.length;
            break;
          case 'Home':
            nextIndex = 0;
            break;
          case 'End':
            nextIndex = visibleTabs.length - 1;
            break;
          case 'Enter':
          case ' ':
            event.preventDefault();
            triggerHaptic(HAPTIC.TAP);
            activateTabByElement(tab);
            return;
          default:
            return;
        }

        event.preventDefault();
        const nextTab = visibleTabs[nextIndex];
        if (!nextTab) return;
        nextTab.focus();
        triggerHaptic(HAPTIC.TAP);
        activateTabByElement(nextTab);
      });
    });
    
    // Playback controls with haptic feedback
    const btnPlayPause = document.getElementById('btn-play-pause');
    const btnPrevious = document.getElementById('btn-previous');
    const btnNext = document.getElementById('btn-next');
    
    if (btnPlayPause) btnPlayPause.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); togglePlayPause(); });
    if (btnPrevious) btnPrevious.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); skipToPrevious(); });
    if (btnNext) btnNext.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); skipToNext(); });
    
    // Legacy play/pause button (if exists)
    if (elements.playPauseBtn) elements.playPauseBtn.addEventListener('click', () => { triggerHaptic(HAPTIC.TAP); togglePlayPause(); });

    // Helper function to sync both volume sliders
    function syncVolumeSliders(value, sourceId) {
        const mobileSlider = document.getElementById('global-volume');
        const desktopSlider = document.getElementById('global-volume-desktop');
        const mobileDisplay = document.getElementById('volume-display');
        const desktopDisplay = document.getElementById('volume-display-desktop');
        
        // Update both sliders (except the source) with ARIA attributes
        if (mobileSlider && mobileSlider.id !== sourceId) {
            mobileSlider.value = value;
            mobileSlider.setAttribute('aria-valuenow', value);
            mobileSlider.setAttribute('aria-valuetext', `${value}%`);
        }
        if (desktopSlider && desktopSlider.id !== sourceId) {
            desktopSlider.value = value;
            desktopSlider.setAttribute('aria-valuenow', value);
            desktopSlider.setAttribute('aria-valuetext', `${value}%`);
        }
        
        // Update the source slider's ARIA attributes too
        const sourceSlider = document.getElementById(sourceId);
        if (sourceSlider) {
            sourceSlider.setAttribute('aria-valuenow', value);
            sourceSlider.setAttribute('aria-valuetext', `${value}%`);
        }
        
        // Update both displays
        if (mobileDisplay) mobileDisplay.textContent = value + '%';
        if (desktopDisplay) desktopDisplay.textContent = value + '%';
    }

    // Volume slider event handler factory
    function setupVolumeSlider(slider) {
        if (!slider) return;
        
        // Track the last known value for touchend (which doesn't have target.value reliably)
        let lastSliderValue = slider.value;
        
        slider.addEventListener('input', (e) => {
            lastSliderValue = e.target.value;
            syncVolumeSliders(e.target.value, e.target.id);
            setLastUserInteraction(Date.now());
            setVolumeImmediateThrottled(e.target.value);
        });
        
        slider.addEventListener('mousedown', () => {
            setUserIsDragging(true);
            setLastUserInteraction(Date.now());
        });
        slider.addEventListener('touchstart', () => {
            setUserIsDragging(true);
            setLastUserInteraction(Date.now());
        }, { passive: true });
        
        slider.addEventListener('mouseup', (e) => {
            setUserIsDragging(false);
            setLastUserInteraction(Date.now());
            flushVolumeThrottle(e.target.value);
            scheduleVolumeSync(); // Sync with Spotify after cooldown
        });
        slider.addEventListener('touchend', () => {
            setUserIsDragging(false);
            setLastUserInteraction(Date.now());
            // Use tracked value since touchend event may not have reliable target.value
            flushVolumeThrottle(lastSliderValue);
            scheduleVolumeSync(); // Sync with Spotify after cooldown
        }, { passive: true });
        
        // Handle cases where user releases mouse outside the slider
        slider.addEventListener('mouseleave', (e) => {
            if (e.buttons === 0 && slider.matches(':active') === false) {
                // Mouse left while not pressing - might have released outside
                setUserIsDragging(false);
            }
        });
    }

    // Setup both volume sliders
    setupVolumeSlider(elements.globalVolume);
    setupVolumeSlider(elements.globalVolumeDesktop);

    if (elements.durationSelect) {
        elements.durationSelect.addEventListener('change', (e) => handleDurationChange(e.target.value));
    }

    // Update time immediately and then every second
    updateTime();
    setInterval(updateTime, 1000);

    // Update playback info immediately
    updatePlaybackInfo();

    // Alarm form event handlers with intelligent throttling
    if (elements.alarmEnabled) {
        elements.alarmEnabled.addEventListener('change', function() {
            console.log('🚨 Alarm enabled changed:', this.checked);
            triggerHaptic(HAPTIC.TOGGLE);
            throttledSaveAlarmSettings({ immediate: true });
        });
    }
    if (elements.alarmEnabledActive) {
        elements.alarmEnabledActive.addEventListener('change', function() {
            console.log('🚨 Alarm active toggle changed:', this.checked);
            triggerHaptic(HAPTIC.TOGGLE);
            const configToggle = DOM.getElement('enabled');
            if (configToggle) {
                configToggle.checked = this.checked;
            }
            throttledSaveAlarmSettings({ immediate: true });
        });
    }

    if (elements.alarmTime) {
        elements.alarmTime.addEventListener('change', function() {
            console.log('🚨 Alarm time changed:', this.value);
            throttledSaveAlarmSettings();
        });
    }

    if (elements.alarmVolumeSlider) {
        elements.alarmVolumeSlider.addEventListener('input', function() {
            // Always update display immediately
            const display = document.getElementById('alarm-volume-display');
            if (display) {
                display.textContent = this.value + '%';
            }
            
            console.log('🚨 Alarm volume changed:', this.value);
            throttledSaveAlarmSettings();
        });
    }

    if (elements.deviceSelect) {
        elements.deviceSelect.addEventListener('change', function() {
            console.log('🚨 Device changed:', this.value);
            throttledSaveAlarmSettings();
        });
    }

    if (elements.fadeInSelect) {
        elements.fadeInSelect.addEventListener('change', function() {
            console.log('🚨 Fade in changed:', this.value);
            throttledSaveAlarmSettings();
        });
    }

    if (elements.shuffleCheckbox) {
        elements.shuffleCheckbox.addEventListener('change', function() {
            console.log('🚨 Shuffle changed:', this.checked);
            throttledSaveAlarmSettings();
        });
    }

    // Initialize pull-to-refresh gesture
    initPullToRefresh();

    console.log("Event Listeners Initialized");
}

// -----------------------------------------------
// 📲 Pull-to-Refresh Gesture
// -----------------------------------------------

let pullStartY = 0;
let pullDistance = 0;
const PULL_THRESHOLD = 80;
let pullIndicator = null;

/**
 * Initialize pull-to-refresh gesture for mobile devices
 */
function initPullToRefresh() {
  const container = document.querySelector('.app-content');
  if (!container || !('ontouchstart' in window)) return;
  
  // Create pull indicator element
  pullIndicator = document.createElement('div');
  pullIndicator.className = 'pull-indicator';
  pullIndicator.innerHTML = `
    <svg class="pull-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
    </svg>
  `;
  pullIndicator.style.cssText = `
    position: fixed;
    top: 0;
    left: 50%;
    transform: translateX(-50%) translateY(-50px);
    z-index: 1000;
    opacity: 0;
    transition: opacity 0.2s, transform 0.2s;
    color: var(--color-primary);
    pointer-events: none;
  `;
  document.body.appendChild(pullIndicator);
  
  container.addEventListener('touchstart', (e) => {
    if (window.scrollY === 0) {
      pullStartY = e.touches[0].clientY;
    }
  }, { passive: true });
  
  container.addEventListener('touchmove', (e) => {
    if (pullStartY === 0) return;
    pullDistance = e.touches[0].clientY - pullStartY;
    
    if (pullDistance > 0 && pullDistance < PULL_THRESHOLD * 1.5) {
      updatePullIndicator(pullDistance / PULL_THRESHOLD);
    }
  }, { passive: true });
  
  container.addEventListener('touchend', () => {
    if (pullDistance >= PULL_THRESHOLD) {
      triggerPullRefresh();
    }
    resetPullState();
  });
}

/**
 * Update the pull indicator visual state
 * @param {number} progress - Progress from 0 to 1+
 */
function updatePullIndicator(progress) {
  if (!pullIndicator) return;
  
  const clampedProgress = Math.min(progress, 1.2);
  pullIndicator.style.opacity = Math.min(clampedProgress, 1);
  pullIndicator.style.transform = `translateX(-50%) translateY(${clampedProgress * 50 - 50}px) rotate(${clampedProgress * 360}deg)`;
}

/**
 * Reset pull state
 */
function resetPullState() {
  pullStartY = 0;
  pullDistance = 0;
  if (pullIndicator) {
    pullIndicator.style.opacity = '0';
    pullIndicator.style.transform = 'translateX(-50%) translateY(-50px)';
  }
}

/**
 * Trigger refresh action
 */
async function triggerPullRefresh() {
  triggerHaptic(HAPTIC.SUCCESS);
  
  // Dynamically import deviceManager and refresh devices
  try {
    const { deviceManager } = await import('./deviceManager.js');
    if (deviceManager?.refreshDevices) {
      await deviceManager.refreshDevices();
    }
    
    // Also refresh playback status
    const { updatePlaybackInfo } = await import('./ui.js');
    await updatePlaybackInfo();
    
    // Show success feedback via toast if available
    const { t } = await import('./translation.js');
    const message = t('devices_refreshed') || 'Devices refreshed';
    console.log(`✅ ${message}`);
  } catch (error) {
    console.error('Pull refresh failed:', error);
    triggerHaptic(HAPTIC.ERROR);
  }
}
