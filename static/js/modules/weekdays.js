// /static/js/modules/weekdays.js
import { saveAlarmSettings } from './settings.js';

/**
 * Initializes the weekday selection bubbles
 */
export function initializeWeekdayBubbles() {
  const weekdayBubbles = document.querySelectorAll('.weekday-bubble');
  
  if (weekdayBubbles.length === 0) {
    console.log('ℹ️ No weekday bubbles found - possibly not on alarm page');
    return;
  }
  
  console.log('📅 Initializing weekday bubbles...');
  
  // Click handlers for all bubbles
  weekdayBubbles.forEach(bubble => {
    bubble.addEventListener('click', function() {
      toggleWeekday(this);
    });
  });
  
  // Load saved selection
  loadSavedWeekdays();
}

/**
 * Toggle function for individual weekdays
 */
function toggleWeekday(bubble) {
  bubble.classList.toggle('active');
  
  // Visual feedback
  bubble.style.transform = 'scale(0.9)';
  setTimeout(() => {
    bubble.style.transform = '';
  }, 100);
  
  // Save selection
  saveWeekdaySelection();
  
  // Auto-save after weekday change
  saveAlarmSettings();
  
  console.log(`📅 Weekday ${bubble.getAttribute('data-day')} ${bubble.classList.contains('active') ? 'activated' : 'deactivated'}`);
}

/**
 * Saves the current weekday selection
 */
function saveWeekdaySelection() {
  const activeBubbles = document.querySelectorAll('.weekday-bubble.active');
  const selectedDays = Array.from(activeBubbles).map(bubble => bubble.getAttribute('data-day'));
  
  // Save to localStorage for persistent selection
  localStorage.setItem('selectedWeekdays', JSON.stringify(selectedDays));
  
  // Update hidden form field if available
  const weekdaysInput = document.querySelector('input[name="weekdays"]');
  if (weekdaysInput) {
    weekdaysInput.value = selectedDays.join(',');
  }
  
  console.log('💾 Weekdays saved:', selectedDays);
}

/**
 * Loads saved weekday selection
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
