// /static/js/modules/eventListeners.js
// Centralizes all event listeners
import { DOM, setLastUserInteraction, setUserIsDragging } from './state.js';
import { updateLocalVolumeDisplay, handleDurationChange, showInterface, updateTime, updatePlaybackInfo } from './ui.js';
import { setVolumeImmediateThrottled, flushVolumeThrottle, togglePlayPause, fetchAPI } from './api.js';
import { saveAlarmSettings } from './settings.js';

console.log("eventListeners.js loaded");

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
        playPauseBtn: '#playPauseBtn',
        globalVolume: '#global-volume',
        globalVolumeDesktop: '#global-volume-desktop',
        durationSelect: '#duration',
        // Alarm form elements
        alarmEnabled: '#enabled',
        alarmEnabledActive: '#enabled_active',
        alarmTime: '#time',
        alarmVolumeSlider: '#alarm_volume_slider',
        deviceSelect: '#device_name',
        fadeInSelect: '#fade_in',
        shuffleCheckbox: '#shuffle'
    });

    if (elements.alarmTab) elements.alarmTab.addEventListener('click', () => showInterface('alarm'));
    if (elements.sleepTab) elements.sleepTab.addEventListener('click', () => showInterface('sleep'));
    if (elements.libraryTab) elements.libraryTab.addEventListener('click', () => showInterface('library'));
    if (elements.playPauseBtn) elements.playPauseBtn.addEventListener('click', togglePlayPause);

    // Helper function to sync both volume sliders
    function syncVolumeSliders(value, sourceId) {
        const mobileSlider = document.getElementById('global-volume');
        const desktopSlider = document.getElementById('global-volume-desktop');
        const mobileDisplay = document.getElementById('volume-display');
        const desktopDisplay = document.getElementById('volume-display-desktop');
        
        // Update both sliders (except the source)
        if (mobileSlider && mobileSlider.id !== sourceId) {
            mobileSlider.value = value;
        }
        if (desktopSlider && desktopSlider.id !== sourceId) {
            desktopSlider.value = value;
        }
        
        // Update both displays
        if (mobileDisplay) mobileDisplay.textContent = value + '%';
        if (desktopDisplay) desktopDisplay.textContent = value + '%';
    }

    // Volume slider event handler factory
    function setupVolumeSlider(slider) {
        if (!slider) return;
        
        slider.addEventListener('input', (e) => {
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
        });
        
        slider.addEventListener('mouseup', (e) => {
            setUserIsDragging(false);
            setLastUserInteraction(Date.now());
            flushVolumeThrottle(e.target.value);
        });
        slider.addEventListener('touchend', (e) => {
            setUserIsDragging(false);
            setLastUserInteraction(Date.now());
            flushVolumeThrottle(e.target.value);
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
            throttledSaveAlarmSettings({ immediate: true });
        });
    }
    if (elements.alarmEnabledActive) {
        elements.alarmEnabledActive.addEventListener('change', function() {
            console.log('🚨 Alarm active toggle changed:', this.checked);
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

    console.log("Event Listeners Initialized");
}
