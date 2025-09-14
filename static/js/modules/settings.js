// /static/js/modules/settings.js
import { DOM } from './state.js';
import { updateStatus, updateSleepTimer } from './ui.js';
import { t } from './translation.js';
import { fetchAPI } from './api.js';

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
  
  // Weekdays from hidden field
  const weekdaysValue = DOM.getElement('weekdays')?.value || '';
  formData.set('weekdays', weekdaysValue);
  
  // Debug output
  console.log('💾 Saving alarm settings:', {
    enabled: formData.get('enabled'),
    time: formData.get('time'),
    device_name: formData.get('device_name'),
    playlist_uri: formData.get('playlist_uri'),
    weekdays: formData.get('weekdays'),
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
      const timeValue = formData.get('time') || t('unknown') || 'unknown';
      const volumeValue = alarmVolume || '50';
      const statusMessage = formData.get('enabled') === 'on' 
        ? `${t('alarm_set_for') || 'Alarm set for'} ${timeValue}<br><span class="volume-info">${t('volume') || 'Volume'}: ${volumeValue}%</span>`
        : t('no_alarm_active') || 'No alarm active';
        
      updateStatus('alarm-timer', statusMessage, true);
      console.log('✅ Alarm settings saved successfully');
    } else {
      console.error('Error saving settings:', data ? data.message : 'No data received');
      statusElement.innerHTML = originalStatus;
      const errorMessage = (data && data.message) || t('unknown_error') || 'Unknown error';
      alert(`${t('save_error') || 'Save error'}: ${errorMessage}`);
    }
  })
  .catch(error => {
    console.error('Error saving settings:', error);
    statusElement.innerHTML = originalStatus;
    alert(t('save_error') || 'Error saving settings');
  });
}


/**
 * Internal function to activate sleep timer
 */
function activateSleepTimer(formData) {
  // Immediate UI switch like alarm system
  const configSection = document.querySelector('#sleep-form').closest('div');
  const activeSection = document.querySelector('#active-sleep-mode');
  
  if (configSection && activeSection) {
    configSection.classList.add('hidden');
    activeSection.classList.remove('hidden');
    
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
      // Reset UI on error
      if (configSection && activeSection) {
        activeSection.classList.add('hidden');
        configSection.classList.remove('hidden');
        const configCheckbox = DOM.getElement('sleep_enabled');
        if (configCheckbox) configCheckbox.checked = false;
      }
      alert(`${t('activation_error') || 'Activation error'}: ${(data && data.message) || t('unknown_error') || 'Unknown error'}`);
    }
  })
  .catch(error => {
    console.error('Error activating sleep timer:', error);
    // Reset UI on error
    if (configSection && activeSection) {
      activeSection.classList.add('hidden');
      configSection.classList.remove('hidden');
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
  // Immediate UI switch like alarm system
  const configSection = document.querySelector('#sleep-form').closest('div');
  const activeSection = document.querySelector('#active-sleep-mode');
  
  if (configSection && activeSection) {
    activeSection.classList.add('hidden');
    configSection.classList.remove('hidden');
    
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
      // Reset UI on error
      if (configSection && activeSection) {
        configSection.classList.add('hidden');
        activeSection.classList.remove('hidden');
        const activeCheckbox = DOM.getElement('sleep_enabled_active');
        if (activeCheckbox) activeCheckbox.checked = true;
      }
      alert(`${t('deactivation_error') || 'Deactivation error'}: ${(data && data.message) || t('unknown_error') || 'Unknown error'}`);
    }
  })
  .catch(error => {
    console.error('Error deactivating sleep timer:', error);
    // Reset UI on error
    if (configSection && activeSection) {
      configSection.classList.add('hidden');
      activeSection.classList.remove('hidden');
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