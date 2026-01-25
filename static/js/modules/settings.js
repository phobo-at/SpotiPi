// /static/js/modules/settings.js
import { DOM } from './state.js';
import { updateStatus, updateSleepTimer, updateAlarmStatus } from './ui.js';
import { t } from './translation.js';
import { fetchAPI } from './api.js';

/**
 * Smoothly hide an element with animation
 */
function smoothHide(element) {
  if (!element || element.classList.contains('hidden')) return;
  element.classList.add('hidden');
}

/**
 * Smoothly show an element with animation
 */
function smoothShow(element) {
  if (!element || !element.classList.contains('hidden')) return;
  element.classList.remove('hidden');
}

/**
 * Saves alarm settings automatically when changes are made
 */
export function saveAlarmSettings() {
  const statusElement = updateStatus('alarm-timer', t('saving_settings') || 'Saving settings...');
  if (!statusElement) return;
  
  const originalStatus = statusElement.innerHTML;
  const form = document.getElementById('alarm-form');
  if (!form) return;
  
  // Create FormData from form
  const formData = new FormData(form);
  
  // Add current alarm volume value from the dedicated slider
  const alarmVolumeSlider = DOM.getElement('alarm_volume_slider');
  const alarmVolume = alarmVolumeSlider && alarmVolumeSlider.value ? alarmVolumeSlider.value : 50;
  formData.set('alarm_volume', alarmVolume);
  
  // Playlist URI from hidden field
  const playlistUri = DOM.getElement('playlist_uri')?.value || '';
  formData.set('playlist_uri', playlistUri);
  
  // Debug output
  console.log('💾 Saving alarm settings:', {
    enabled: formData.get('enabled'),
    time: formData.get('time'),
    device_name: formData.get('device_name'),
    playlist_uri: formData.get('playlist_uri'),
    fade_in: formData.get('fade_in'),
    shuffle: formData.get('shuffle'),
    alarm_volume: formData.get('alarm_volume')
  });
  
  // Use fetchAPI instead of direct fetch for proper rate limiting
  fetchAPI('/save_alarm', {
    method: 'POST',
    body: formData
  })
  .then(async response => {
    console.log('DEBUG: Received response:', response);
    
    // fetchAPI returns Response object for POST requests, need to parse JSON
    if (!response.ok) {
      throw new Error(t('save_failed') || 'Save failed');
    }
    
    const data = await response.json();
    console.log('DEBUG: Parsed data:', data);
    
    if (data && data.success) {
      const payload = data.data || {};
      const alarmData = payload.alarm || payload;

      const timeValue = alarmData.time || formData.get('time') || t('unknown') || 'unknown';
      const volumeValue = typeof alarmData.alarm_volume === 'number'
        ? alarmData.alarm_volume
        : (alarmVolume || '50');

      const devicePrefix = t('alarm_device_label') || 'Device:';
      const deviceValue = String(formData.get('device_name') || '').trim() || t('alarm_device_unknown') || 'Unknown device';

      const enabledFlag = typeof alarmData.enabled === 'boolean'
        ? alarmData.enabled
        : (formData.get('enabled') === 'on');

      // Escape HTML to prevent XSS and template literal issues
      const escapeHtml = (str) => String(str).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[char]);

      const statusMessage = enabledFlag
        ? `${escapeHtml(t('alarm_set_for') || 'Alarm set for')} ${escapeHtml(timeValue)}<br><span class="volume-info">${escapeHtml(t('volume') || 'Volume')}: ${escapeHtml(volumeValue)}%</span><br><span class="device-info">${escapeHtml(devicePrefix)} ${escapeHtml(deviceValue)}</span>`
        : escapeHtml(t('no_alarm_active') || 'No alarm active');
        
      updateStatus('alarm-timer', statusMessage, true);
      console.log('✅ Alarm settings saved successfully');
      await updateAlarmStatus();
    } else {
      console.error('Error saving settings:', data ? data.message : 'No data received');
      statusElement.innerHTML = originalStatus;
      const errorMessage = String((data && data.message) || t('unknown_error') || 'Unknown error');
      const saveErrorMsg = String(t('save_error') || 'Save error');
      alert(`${saveErrorMsg}: ${errorMessage}`);
    }
  })
  .catch(error => {
    console.error('Error saving settings:', error);
    statusElement.innerHTML = originalStatus;
    const saveErrorMsg = String(t('save_error') || 'Error saving settings');
    alert(saveErrorMsg);
  });
}


/**
 * Internal function to activate sleep timer
 */
function activateSleepTimer(formData) {
  // Immediate UI switch with smooth animation
  const configSection = document.querySelector('#sleep-form');
  const activeSection = document.querySelector('#active-sleep-mode');
  
  if (configSection && activeSection) {
    smoothHide(configSection);
    smoothShow(activeSection);
    
    // Update the active checkbox to checked
    const activeCheckbox = DOM.getElement('sleep_enabled_active');
    if (activeCheckbox) {
      activeCheckbox.checked = true;
    }
  }

  // Then API call
  const urlParams = new URLSearchParams();
  for (const [key, value] of formData.entries()) {
    urlParams.append(key, value);
  }
  
  fetchAPI('/sleep', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json'
    },
    body: urlParams
  })
  .then(async response => {
    if (!response.ok) {
      throw new Error(t('activation_failed') || 'Activation failed');
    }
    
    const data = await response.json();
    if (data && data.success) {
      console.log('✅ Sleep timer activated successfully');
      // UI already switched, now just update timer display
      updateSleepTimer();
    } else {
      console.error('Error activating sleep timer:', data ? data.message : 'No data received');
      // Reset UI on error with animation
      if (configSection && activeSection) {
        smoothHide(activeSection);
        smoothShow(configSection);
        const configCheckbox = DOM.getElement('sleep_enabled');
        if (configCheckbox) configCheckbox.checked = false;
      }
      alert(`${t('activation_error') || 'Activation error'}: ${(data && data.message) || t('unknown_error') || 'Unknown error'}`);
    }
  })
  .catch(error => {
    console.error('Error activating sleep timer:', error);
    // Reset UI on error with animation
    if (configSection && activeSection) {
      smoothHide(activeSection);
      smoothShow(configSection);
      const configCheckbox = DOM.getElement('sleep_enabled');
      if (configCheckbox) configCheckbox.checked = false;
    }
    alert(t('sleep_timer_activation_error') || 'Error activating sleep timer');
  });
}

/**
 * Internal function to deactivate sleep timer
 */
function deactivateSleepTimer() {
  // Immediate UI switch with smooth animation
  const configSection = document.querySelector('#sleep-form');
  const activeSection = document.querySelector('#active-sleep-mode');
  
  if (configSection && activeSection) {
    smoothHide(activeSection);
    smoothShow(configSection);
    
    // Update the config checkbox to unchecked
    const configCheckbox = DOM.getElement('sleep_enabled');
    if (configCheckbox) {
      configCheckbox.checked = false;
    }
  }

  // Then API call
  fetchAPI('/stop_sleep', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json'
    }
  })
  .then(async response => {
    if (!response.ok) {
      throw new Error(t('deactivation_failed') || 'Deactivation failed');
    }
    
    const data = await response.json();
    if (data && data.success) {
      console.log('✅ Sleep timer deactivated successfully');
      // UI already switched, now just update timer display
      updateSleepTimer();
    } else {
      console.error('Error deactivating sleep timer:', data ? data.message : 'No data received');
      // Reset UI on error with animation
      if (configSection && activeSection) {
        smoothHide(configSection);
        smoothShow(activeSection);
        const activeCheckbox = DOM.getElement('sleep_enabled_active');
        if (activeCheckbox) activeCheckbox.checked = true;
      }
      alert(`${t('deactivation_error') || 'Deactivation error'}: ${(data && data.message) || t('unknown_error') || 'Unknown error'}`);
    }
  })
  .catch(error => {
    console.error('Error deactivating sleep timer:', error);
    // Reset UI on error with animation
    if (configSection && activeSection) {
      smoothHide(configSection);
      smoothShow(activeSection);
      const activeCheckbox = DOM.getElement('sleep_enabled_active');
      if (activeCheckbox) activeCheckbox.checked = true;
    }
    alert(t('sleep_timer_deactivation_error') || 'Error deactivating sleep timer');
  });
}

/**
 * Direct sleep timer functions - no complex logic needed!
 * Called directly by corresponding event handlers
 */
export function activateSleepTimerDirect(formData) {
  console.log('👉 Direct activation of sleep timer');
  activateSleepTimer(formData);
}

export function deactivateSleepTimerDirect() {
  console.log('👉 Direct deactivation of sleep timer');
  deactivateSleepTimer();
}

// =====================================
// ⚙️ Settings Panel Functions
// =====================================

let settingsPanelInitialized = false;

/**
 * Load current settings from API and update Settings panel UI
 */
export async function loadSettingsPanel() {
  try {
    const response = await fetch('/api/settings');
    const result = await response.json();
    
    if (result.success && result.data) {
      const settings = result.data;
      
      // Feature flags
      const sleepToggle = document.getElementById('feature-sleep');
      const libraryToggle = document.getElementById('feature-library');
      
      if (sleepToggle) sleepToggle.checked = settings.feature_flags?.sleep_timer ?? false;
      if (libraryToggle) libraryToggle.checked = settings.feature_flags?.music_library ?? true;
      
      // App settings
      const langSelect = document.getElementById('setting-language');
      if (langSelect) langSelect.value = settings.app?.language || 'de';
      
      const volSlider = document.getElementById('setting-default-volume');
      const volDisplay = document.getElementById('setting-default-volume-display');
      if (volSlider && volDisplay) {
        volSlider.value = settings.app?.default_volume || 50;
        volDisplay.textContent = `${volSlider.value}%`;
      }
    }
  } catch (error) {
    console.error('Failed to load settings:', error);
  }
}

/**
 * Load Spotify profile and display in Settings panel
 */
export async function loadSpotifyProfile() {
  const container = document.getElementById('spotify-account-info');
  if (!container) return;
  
  try {
    const response = await fetch('/api/spotify/profile');
    const result = await response.json();
    
    if (result.success && result.data) {
      const profile = result.data;
      const isPremium = profile.product === 'premium';
      const connectedText = t('connected_account') || 'Connected';
      
      container.innerHTML = `
        <div class="account-avatar">
          ${profile.avatar_url 
            ? `<img src="${escapeHtml(profile.avatar_url)}" alt="${escapeHtml(profile.display_name)}">`
            : `<svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>`
          }
        </div>
        <div class="account-info">
          <div class="account-name">
            ${escapeHtml(profile.display_name)}
            ${isPremium ? '<span class="badge">Premium</span>' : ''}
          </div>
          ${profile.email ? `<div class="account-email">${escapeHtml(profile.email)}</div>` : ''}
          <div class="account-status">${connectedText}</div>
        </div>
      `;
    } else {
      showAccountError(container);
    }
  } catch (error) {
    console.error('Failed to load Spotify profile:', error);
    showAccountError(container);
  }
}

/**
 * Show error state in account container
 */
function showAccountError(container) {
  const errorText = t('account_error') || 'Error loading account';
  container.innerHTML = `
    <div class="account-error account-status">
      <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
      <span>${errorText}</span>
    </div>
  `;
}

/**
 * Save a single setting to the API
 */
async function saveSettingValue(path, value) {
  const [category, key] = path.split('.');
  const payload = { [category]: { [key]: value } };
  
  try {
    const response = await fetch('/api/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const result = await response.json();
    
    if (result.success) {
      updateStatus('settings-status', t('settings_saved') || 'Settings saved');
      
      // If we changed feature flags, update tab visibility
      if (category === 'feature_flags') {
        updateTabVisibility(key, value);
      }
    } else {
      updateStatus('settings-status', result.message || t('settings_save_error') || 'Save failed');
    }
  } catch (error) {
    console.error('Failed to save setting:', error);
    updateStatus('settings-status', t('settings_save_error') || 'Save failed');
  }
}

/**
 * Update tab visibility based on feature flag change
 */
function updateTabVisibility(feature, enabled) {
  const tabMap = {
    'sleep_timer': 'sleep-tab',
    'music_library': 'library-tab'
  };
  
  const tabId = tabMap[feature];
  if (tabId) {
    const tab = document.getElementById(tabId);
    if (tab) {
      tab.style.display = enabled ? '' : 'none';
    }
  }
}

/**
 * Clear all application caches
 */
async function clearAppCache() {
  const btn = document.getElementById('clear-cache-btn');
  if (!btn) return;
  
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/settings/cache/clear', { method: 'POST' });
    const result = await response.json();
    
    if (result.success) {
      updateStatus('settings-status', t('cache_cleared') || 'Cache cleared');
    } else {
      updateStatus('settings-status', result.message || 'Error clearing cache');
    }
  } catch (error) {
    console.error('Failed to clear cache:', error);
    updateStatus('settings-status', 'Error clearing cache');
  } finally {
    btn.disabled = false;
  }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Initialize settings panel event listeners
 */
export function initSettingsPanel() {
  if (settingsPanelInitialized) return;
  settingsPanelInitialized = true;
  
  // Feature flag toggles
  const sleepToggle = document.getElementById('feature-sleep');
  if (sleepToggle) {
    sleepToggle.addEventListener('change', (e) => {
      saveSettingValue('feature_flags.sleep_timer', e.target.checked);
    });
  }
  
  const libraryToggle = document.getElementById('feature-library');
  if (libraryToggle) {
    libraryToggle.addEventListener('change', (e) => {
      saveSettingValue('feature_flags.music_library', e.target.checked);
    });
  }
  
  // Language select
  const langSelect = document.getElementById('setting-language');
  if (langSelect) {
    langSelect.addEventListener('change', (e) => {
      saveSettingValue('app.language', e.target.value);
      // Reload page to apply language change
      setTimeout(() => location.reload(), 500);
    });
  }
  
  // Volume slider
  const volSlider = document.getElementById('setting-default-volume');
  const volDisplay = document.getElementById('setting-default-volume-display');
  
  if (volSlider && volDisplay) {
    volSlider.addEventListener('input', (e) => {
      volDisplay.textContent = `${e.target.value}%`;
    });
    
    volSlider.addEventListener('change', (e) => {
      saveSettingValue('app.default_volume', parseInt(e.target.value, 10));
    });
  }
  
  // Clear cache button
  const clearCacheBtn = document.getElementById('clear-cache-btn');
  if (clearCacheBtn) {
    clearCacheBtn.addEventListener('click', clearAppCache);
  }
  
  // Disconnect Spotify button
  const disconnectBtn = document.getElementById('disconnect-spotify-btn');
  if (disconnectBtn) {
    disconnectBtn.addEventListener('click', () => {
      const confirmText = t('disconnect_spotify_desc') || 'Disconnect from Spotify?';
      if (confirm(confirmText)) {
        updateStatus('settings-status', 'Spotify disconnection not implemented yet');
      }
    });
  }
  
  console.log('⚙️ Settings panel initialized');
}

/**
 * Called when settings tab is activated
 */
export function onSettingsTabActivated() {
  loadSettingsPanel();
  loadSpotifyProfile();
  initSettingsPanel();
}

