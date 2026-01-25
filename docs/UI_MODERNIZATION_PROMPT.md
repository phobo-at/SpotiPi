# SpotiPi UI/UX Modernization — Agent Prompt

> **Zweck:** Strukturierter Prompt für KI-Agenten zur Implementierung von UI/UX-Verbesserungen
> **Erstellt:** Januar 2026
> **Version:** 1.0

---

## Projekt-Kontext

Du bist ein Senior Frontend-Entwickler. Implementiere die folgenden UI/UX-Verbesserungen für SpotiPi, eine Spotify Alarm Clock & Sleep Timer PWA.

### Stack & Architektur
- **Backend:** Flask (Python 3.9+)
- **Frontend:** Vanilla JS (ES6 Modules), CSS Custom Properties
- **CSS-Architektur:** Modulare Struktur in `static/css/`
  - `foundation/` — variables.css, base.css, utilities.css, accessibility.css
  - `components/` — buttons.css, forms.css, sliders.css, notifications.css, toggles.css, tabs.css
  - `features/` — alarm.css, sleep.css, music.css, playlists.css, devices.css
  - `layout/` — main-layout.css, desktop-layout.css, responsive.css, pwa.css
- **JS-Module:** `static/js/modules/`
  - ui.js, state.js, api.js, eventListeners.js, deviceManager.js, playlistSelector.js, translation.js
- **Templates:** Jinja2 in `templates/` (index.html, alarm.html, sleep.html, music_library.html)
- **Design:** Dark Theme mit Spotify-Grün (#1db954), Mobile-First

---

## Aufgaben (nach Priorität)

### 🔴 Priorität HOCH

#### 1. Skeleton Shimmer Animation
**Datei:** `static/css/foundation/utilities.css`

**Anforderung:** Füge einen animierten Shimmer-Effekt zu den bestehenden Skeleton-Loadern hinzu.

```css
/* Gewünschter Effekt: Horizontaler Lichtstreifen der von links nach rechts wandert */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.placeholder-glow {
  background: linear-gradient(
    90deg,
    var(--color-surface) 25%,
    rgba(255, 255, 255, 0.08) 50%,
    var(--color-surface) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite ease-in-out;
}
```

**Ziel-Selektoren:** `.placeholder-glow`, `.skeleton-line`, `.skeleton-media`, `.skeleton-tile`

**Wichtig:** Respektiere `prefers-reduced-motion` in `accessibility.css`

---

#### 2. Empty States mit Illustrationen
**Dateien:** `templates/alarm.html`, `templates/sleep.html`, `static/css/features/alarm.css`, `static/css/features/sleep.css`

**Anforderung:** Visuelle Empty States wenn kein Alarm/Sleep Timer aktiv ist.

**HTML-Struktur:**
```html
<div class="empty-state" id="alarm-empty-state">
  <div class="empty-state-icon">
    <!-- Inline SVG: Wecker-Illustration, monochrom -->
  </div>
  <h3 class="empty-state-title">{{ t('empty_alarm_title') }}</h3>
  <p class="empty-state-description">{{ t('empty_alarm_description') }}</p>
</div>
```

**CSS:**
```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xxl);
  text-align: center;
  animation: fadeIn 0.5s ease-out;
}

.empty-state-icon {
  width: 120px;
  height: 120px;
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-muted);
  opacity: 0.6;
}

.empty-state-title {
  font-size: var(--font-xl);
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
}

.empty-state-description {
  color: var(--color-text-muted);
  max-width: 280px;
}
```

**Übersetzungen hinzufügen:** `src/translations/` (de.json, en.json)
- `empty_alarm_title`: "Noch kein Alarm" / "No alarm set"
- `empty_alarm_description`: "Starte deinen Tag mit deiner Lieblingsmusik!" / "Start your day with your favorite music!"
- `empty_sleep_title`: "Kein Sleep Timer" / "No sleep timer"
- `empty_sleep_description`: "Schlaf sanft ein mit entspannender Musik." / "Fall asleep gently with relaxing music."

---

#### 3. Button Ripple-Effekt
**Dateien:** `static/css/components/buttons.css`, `static/js/modules/ui.js`

**Anforderung:** Material Design Ripple-Effekt für alle interaktiven Buttons.

**CSS:**
```css
.ripple-container {
  position: relative;
  overflow: hidden;
}

.ripple {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  transform: scale(0);
  animation: ripple-animation 0.6s ease-out forwards;
  pointer-events: none;
}

@keyframes ripple-animation {
  to {
    transform: scale(4);
    opacity: 0;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .ripple {
    animation: none;
    display: none;
  }
}
```

**JavaScript (ui.js):**
```javascript
/**
 * Creates a ripple effect on button click
 * @param {MouseEvent|TouchEvent} event
 */
export function createRipple(event) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  
  const button = event.currentTarget;
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
```

**Ziel-Selektoren:** `.toggle-buttons button`, `.control-btn`, `.btn-primary`, `.weekday-bubble`

---

### 🟡 Priorität MITTEL

#### 4. View Transitions für Tab-Wechsel
**Dateien:** `static/js/modules/ui.js`, `static/css/foundation/utilities.css`

**Anforderung:** Smooth Crossfade zwischen Alarm/Sleep/Library Tabs.

**CSS:**
```css
/* Modern browsers with View Transitions API */
@view-transition {
  navigation: auto;
}

[role="tabpanel"] {
  view-transition-name: tab-content;
}

/* Fallback transition */
.tab-content > div {
  opacity: 1;
  transform: translateX(0);
  transition: opacity 0.25s ease-out, transform 0.25s ease-out;
}

.tab-content > div.tab-exit {
  opacity: 0;
  transform: translateX(-10px);
  position: absolute;
}

.tab-content > div.tab-enter {
  opacity: 0;
  transform: translateX(10px);
}
```

**JavaScript — showInterface() anpassen:**
```javascript
export function showInterface(interfaceId) {
  const panels = document.querySelectorAll('[role="tabpanel"]');
  const targetPanel = document.getElementById(`${interfaceId}-interface`);
  
  // Use View Transitions API if available
  if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.startViewTransition(() => {
      panels.forEach(p => p.style.display = 'none');
      if (targetPanel) targetPanel.style.display = 'block';
    });
  } else {
    // Fallback
    panels.forEach(p => p.style.display = 'none');
    if (targetPanel) targetPanel.style.display = 'block';
  }
  
  localStorage.setItem('activeTab', interfaceId);
}
```

---

#### 5. Haptic Feedback für Touch
**Datei:** `static/js/modules/eventListeners.js`

**Anforderung:** Kurze Vibration bei Button-Interaktionen auf Mobile.

```javascript
/**
 * Triggers haptic feedback on supported devices
 * @param {number|number[]} pattern - Vibration pattern in ms
 */
function triggerHaptic(pattern = 10) {
  if ('vibrate' in navigator) {
    try {
      navigator.vibrate(pattern);
    } catch {
      // Silently fail on unsupported devices
    }
  }
}

// Patterns
const HAPTIC = {
  TAP: 10,
  SUCCESS: [10, 50, 10],
  ERROR: [50, 30, 50],
  TOGGLE: 15
};
```

**Auslösen bei:**
- Tab-Wechsel: `HAPTIC.TAP`
- Alarm speichern: `HAPTIC.SUCCESS`
- Play/Pause: `HAPTIC.TAP`
- Weekday-Bubble Toggle: `HAPTIC.TOGGLE`
- Fehler: `HAPTIC.ERROR`

---

#### 6. Glasmorphism für Now Playing Card
**Datei:** `static/css/features/music.css`, `static/css/layout/desktop-layout.css`

**Anforderung:** Moderner Glasmorphism-Effekt für die "Now Playing" Sidebar (nur Desktop).

```css
@media (min-width: 992px) {
  .now-playing-sidebar .current-track {
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    background: rgba(36, 36, 36, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 
      0 8px 32px rgba(0, 0, 0, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  
  /* Fallback for browsers without backdrop-filter */
  @supports not (backdrop-filter: blur(20px)) {
    .now-playing-sidebar .current-track {
      background: var(--color-surface);
    }
  }
}
```

---

### 🟢 Priorität NIEDRIG

#### 7. OLED Black Mode
**Datei:** `static/css/foundation/variables.css`

**Anforderung:** Zusätzliches Theme für AMOLED-Displays.

```css
/* OLED Black Mode */
:root[data-theme="oled"] {
  --color-bg: #000000;
  --color-bg-elevated: #0a0a0a;
  --color-bg-highlight: #1a1a1a;
  --color-surface: #0f0f0f;
  --color-surface-hover: #1a1a1a;
  --color-border: #222222;
  --color-border-subtle: #1a1a1a;
}

/* Smooth theme transition */
:root {
  transition: background-color 0.3s ease, color 0.3s ease;
}
```

**JavaScript — Theme Toggle:**
```javascript
function toggleOLEDMode() {
  const isOLED = document.documentElement.dataset.theme === 'oled';
  document.documentElement.dataset.theme = isOLED ? '' : 'oled';
  localStorage.setItem('theme', isOLED ? 'default' : 'oled');
}

// On page load
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'oled') {
  document.documentElement.dataset.theme = 'oled';
}
```

---

#### 8. Verbesserter Time Input
**Datei:** `static/css/features/alarm.css`

**Anforderung:** Größerer, prominenterer Zeitanzeige-Stil.

```css
.alarm-time-input {
  font-size: var(--font-4xl);
  font-weight: 700;
  padding: var(--spacing-xl) var(--spacing-lg);
  text-align: center;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.05em;
  max-width: 280px;
  margin: 0 auto;
}

.alarm-time-input:focus {
  box-shadow: 
    0 0 0 3px var(--color-primary-soft),
    0 0 40px rgba(29, 185, 84, 0.2);
}

@media (min-width: 768px) {
  .alarm-time-input {
    font-size: var(--font-5xl);
    max-width: 320px;
  }
}

@media (min-width: 992px) {
  .alarm-time-input {
    font-size: var(--font-hero);
    max-width: 400px;
  }
}
```

---

#### 9. Progressive Disclosure für Optionen
**Dateien:** `templates/alarm.html`, `templates/sleep.html`

**Anforderung:** "Erweiterte Optionen" Fieldset standardmäßig einklappen.

**HTML:**
```html
<details class="options-accordion" id="alarm-options">
  <summary class="options-accordion-header">
    <span>{{ t('further_options') }}</span>
    <svg class="accordion-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M7 10l5 5 5-5z"/>
    </svg>
  </summary>
  <div class="options-accordion-content">
    <!-- Existing options content -->
  </div>
</details>
```

**CSS:**
```css
.options-accordion {
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--border-radius-md);
  margin-top: var(--spacing-lg);
}

.options-accordion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  cursor: pointer;
  font-weight: 600;
  color: var(--color-text-muted);
  transition: color var(--transition-fast);
}

.options-accordion-header:hover {
  color: var(--color-text);
}

.accordion-icon {
  width: 24px;
  height: 24px;
  transition: transform var(--transition-normal);
}

.options-accordion[open] .accordion-icon {
  transform: rotate(180deg);
}

.options-accordion-content {
  padding: var(--spacing-md);
  padding-top: 0;
}
```

---

#### 10. Pull-to-Refresh Geste
**Datei:** `static/js/modules/eventListeners.js`

**Anforderung:** Native Pull-to-Refresh Geste für Device-Reload.

```javascript
let pullStartY = 0;
let pullDistance = 0;
const PULL_THRESHOLD = 80;

function initPullToRefresh() {
  const container = document.querySelector('.app-content');
  if (!container || !('ontouchstart' in window)) return;
  
  container.addEventListener('touchstart', (e) => {
    if (window.scrollY === 0) {
      pullStartY = e.touches[0].clientY;
    }
  }, { passive: true });
  
  container.addEventListener('touchmove', (e) => {
    if (pullStartY === 0) return;
    pullDistance = e.touches[0].clientY - pullStartY;
    
    if (pullDistance > 0 && pullDistance < PULL_THRESHOLD * 1.5) {
      // Show pull indicator
      updatePullIndicator(pullDistance / PULL_THRESHOLD);
    }
  }, { passive: true });
  
  container.addEventListener('touchend', () => {
    if (pullDistance >= PULL_THRESHOLD) {
      triggerRefresh();
    }
    resetPullState();
  });
}

async function triggerRefresh() {
  triggerHaptic(HAPTIC.SUCCESS);
  await deviceManager.refreshDevices();
  showToast(t('devices_refreshed'), 'success');
}
```

---

## Code-Stil Richtlinien

### CSS
- ✅ CSS Custom Properties für alle Farben/Spacing nutzen
- ✅ Mobile-First Media Queries (`min-width`)
- ✅ BEM-ähnliche Naming Convention (kebab-case)
- ✅ `prefers-reduced-motion` immer respektieren
- ❌ Keine `!important` außer bei Utility-Override

### JavaScript
- ✅ ES6 Module Syntax (`import`/`export`)
- ✅ JSDoc Kommentare für öffentliche Funktionen
- ✅ Defensive Checks (`element?.method()`)
- ✅ Event Delegation wo möglich
- ❌ Keine externen Dependencies

### HTML/Jinja2
- ✅ Semantisches HTML5 (`<nav>`, `<main>`, `<aside>`)
- ✅ ARIA-Attribute für Accessibility
- ✅ Übersetzungen via `{{ t('key') }}`
- ❌ Keine Inline-Styles

---

## Nicht ändern

- Backend API Endpoints (`src/api/`, `src/routes/`)
- Core State Management (`static/js/modules/state.js`)
- PWA Manifest Struktur (`static/manifest.json`)
- Bestehende Übersetzungslogik (`static/js/modules/translation.js`)
- Service Worker (falls vorhanden)

---

## Testing Checkliste

- [ ] Chrome Desktop (latest)
- [ ] Safari iOS 15+ (iPhone & iPad)
- [ ] Firefox Desktop (latest)
- [ ] Chrome Android
- [ ] Lighthouse Accessibility Score ≥ 90
- [ ] Keine Console Errors/Warnings
- [ ] `prefers-reduced-motion` getestet
- [ ] Touch-Gesten auf echtem Device getestet

---

## Commit Convention

```
feat(ui): add skeleton shimmer animation
feat(ui): add empty states with illustrations
feat(ui): add button ripple effect
feat(ui): add view transitions for tabs
feat(ui): add haptic feedback for touch
style(ui): add glasmorphism to now-playing card
feat(ui): add OLED black mode toggle
style(ui): enhance time input styling
feat(ui): add progressive disclosure for options
feat(ui): add pull-to-refresh gesture
```
