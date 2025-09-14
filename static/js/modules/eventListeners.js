// /static/js/modules/eventListeners.js
// Centralizes all event listeners
import { DOM, setLastUserInteraction, setUserIsDragging } from './state.js';
import { updateLocalVolumeDisplay, handleDurationChange, showInterface, updateTime, updatePlaybackInfo } from './ui.js';
import { setVolumeAndSave, togglePlayPause, fetchAPI } from './api.js';
import { saveAlarmSettings } from './settings.js';

console.log("eventListeners.js loaded");

export function initializeEventListeners() {
    console.log("Event Listeners Initializing...");

    const elements = DOM.getElements({
        alarmTab: '#alarm-tab',
        sleepTab: '#sleep-tab',
        libraryTab: '#library-tab',
        playPauseBtn: '#playPauseBtn',
        globalVolume: '#global-volume',
        durationSelect: '#duration',
        // Alarm form elements
        alarmEnabled: '#enabled',
        alarmTime: '#time',
        alarmVolumeSlider: '#volume-slider',
        deviceSelect: '#device_name',
        fadeInSelect: '#fade_in',
        shuffleCheckbox: '#shuffle'
    });

    if (elements.alarmTab) elements.alarmTab.addEventListener('click', () => showInterface('alarm'));
    if (elements.sleepTab) elements.sleepTab.addEventListener('click', () => showInterface('sleep'));
    if (elements.libraryTab) elements.libraryTab.addEventListener('click', () => showInterface('library'));
    if (elements.playPauseBtn) elements.playPauseBtn.addEventListener('click', togglePlayPause);

    if (elements.globalVolume) {
        elements.globalVolume.addEventListener('input', (e) => updateLocalVolumeDisplay(e.target.value));
        elements.globalVolume.addEventListener('mousedown', () => setUserIsDragging(true));
        elements.globalVolume.addEventListener('touchstart', () => setUserIsDragging(true));
        elements.globalVolume.addEventListener('mouseup', (e) => {
            setUserIsDragging(false);
            setVolumeAndSave(e.target.value);
        });
        elements.globalVolume.addEventListener('touchend', (e) => {
            setUserIsDragging(false);
            setVolumeAndSave(e.target.value);
        });
    }

    if (elements.durationSelect) {
        elements.durationSelect.addEventListener('change', (e) => handleDurationChange(e.target.value));
    }

    // Update time immediately and then every second
    updateTime();
    setInterval(updateTime, 1000);

    // Update playback info immediately
    updatePlaybackInfo();

    // Alarm form event handlers - rely on backend rate limiting
    if (elements.alarmEnabled) {
        elements.alarmEnabled.addEventListener('change', function() {
            console.log('🚨 Alarm enabled changed:', this.checked);
            saveAlarmSettings();
        });
    }

    if (elements.alarmTime) {
        elements.alarmTime.addEventListener('change', function() {
            console.log('🚨 Alarm time changed:', this.value);
            saveAlarmSettings();
        });
    }

    if (elements.alarmVolumeSlider) {
        elements.alarmVolumeSlider.addEventListener('input', function() {
            console.log('🚨 Alarm volume changed:', this.value);
            saveAlarmSettings();
        });
    }

    if (elements.deviceSelect) {
        elements.deviceSelect.addEventListener('change', function() {
            console.log('🚨 Device changed:', this.value);
            saveAlarmSettings();
        });
    }

    if (elements.fadeInSelect) {
        elements.fadeInSelect.addEventListener('change', function() {
            console.log('🚨 Fade in changed:', this.value);
            saveAlarmSettings();
        });
    }

    if (elements.shuffleCheckbox) {
        elements.shuffleCheckbox.addEventListener('change', function() {
            console.log('🚨 Shuffle changed:', this.checked);
            saveAlarmSettings();
        });
    }

    console.log("Event Listeners Initialized");
}
