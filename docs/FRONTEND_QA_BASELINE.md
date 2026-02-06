# Frontend QA Baseline

This checklist defines the baseline for validating frontend changes before and after each UX/A11y/refactor step.

## Scope

- UI shell and navigation tabs (Alarm, Sleep, Library, Settings)
- Playback controls and current track card
- Alarm and sleep forms
- Playlist selector modal and item selection
- Settings panel and feature flag toggles

## Devices and Breakpoints

Test each flow on these viewport widths:

- 320px (small mobile)
- 375px (iPhone baseline)
- 768px (tablet)
- 992px (desktop)
- 1200px (large desktop)
- 1400px (wide desktop)

Test browsers:

- Safari (iOS/macOS)
- Chrome (Android/Desktop)
- Firefox (Desktop)

## Functional Flows

### 1) Alarm

- Open Alarm tab and verify it is visible by default.
- Set time, device, playlist, volume and save.
- Enable/disable alarm from config mode.
- Enable/disable alarm from active mode.
- Verify timer/status updates after save and after refresh.

### 2) Sleep

- Open Sleep tab.
- Select playlist, device, duration (preset and custom).
- Activate timer from config mode.
- Deactivate timer from active mode.
- Verify countdown updates and state survives refresh.

### 3) Library

- Open Library tab.
- Open playlist modal, switch tabs (playlists/albums/tracks/artists).
- Search/filter items.
- Select an item and trigger playback on selected speaker.

### 4) Settings

- Open Settings tab and load account info.
- Toggle feature flags (sleep/library) and verify tab visibility updates.
- Change language and verify reload behavior.
- Change default volume and verify value persistence.
- Trigger clear cache button and verify feedback.

### 5) Playback Controls

- Previous / Play-Pause / Next work and reflect state.
- Disabled states are correct when no active playback exists.
- Current track card updates title/artist/cover and status.

## Accessibility Baseline

- Keyboard-only navigation works across all interactive elements.
- Toggle switches are focusable and operable via keyboard.
- Visible focus ring exists on buttons, inputs, selects, tabs.
- Tablist semantics are valid (`tab`, `tabpanel`, `aria-selected`, `aria-controls`).
- No duplicate `id` attributes in rendered DOM.
- Live regions do not spam and remain understandable.

## Responsiveness Baseline

- No horizontal overflow on app shell or modal.
- Touch targets remain usable on mobile (>= 44x44 where relevant).
- Sidebar/main split remains readable at desktop widths.
- Playlist modal remains scrollable and usable on iOS Safari.

## Release Gate

A change is acceptable when:

- No critical regressions in any functional flow above.
- No P0/P1 A11y or security issues introduced.
- Baseline checks pass on at least one mobile and two desktop browsers.
