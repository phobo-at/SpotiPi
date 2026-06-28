# SpotiPi — UX- & Frontend-Review (v1.12.5)

> **Scope:** Usability- und Frontend-Bewertung aus Sicht UX-Expert:in + Frontend-Developer.
> **Auftrag:** Ergebnisdokumentation + Umsetzungsvorschlag. **Keine Code-Änderungen.**
> **Datum:** 2026-06-27 · **Basis:** `frontend/src/` (app.tsx, styles.css, hooks, lib), `templates/index.html`, `static/manifest.json`, E2E-Specs, Live-Screenshot.
> **Methodik:** 8 spezialisierte Review-Linsen, jeder Befund anschließend adversarial gegen den echten Code geprüft (file:line). 65 Befunde erhoben, **2 als Fehlinterpretation verworfen**, **63 verifiziert**. Schweregrade unten sind die *nach* Verifikation korrigierten.

---

## 1. Gesamturteil — 7/10

SpotiPi ist **keine Anfänger-UI**. Es ist eine sorgfältig handgebaute Preact-Appliance, die auf jeder Achse über dem Hobby-Niveau liegt: korrektes optimistisches Play/Pause mit Revert, vollständige Loading/Empty/Error/Auth/Pending-State-Machine, fokus-getrappte Sheets mit vollständigem Listbox-Keyboard-Contract, sichtbarkeits- und Pi-bewusstes Polling, korrekte Toast-ARIA-Rollen, 44/48px-Touch-Targets, `prefers-reduced-motion` und `env(safe-area-inset)`-Handling. Das Bundle bleibt klar unter Budget (JS 25,8/45 KiB gz).

Was es **vom State-of-the-art trennt, sind nicht verstreute Defekte, sondern ein paar systematische Ursachen.** Das Designsystem ist halb gebaut (Farbe/Radius/Schatten tokenisiert, Typo + Spacing freihändig), Feedback ist inkonsistent und für Screenreader teils stumm, und ausgerechnet der **Dauer-Anzeige-Zustand am Wandgerät** (die Kern-Nutzung) ist gleichzeitig der am häufigsten gezeigte *und* der teuerste Screen. Die gute Nachricht: Die meisten der wirkungsvollsten Fixes sind **S-Effort-CSS oder Wenige-Zeilen-Änderungen**, die die Constraints (Preact-only, kein Pi-Rebuild, Bundle-Budget) respektieren.

### Bewertung je Dimension

| Dimension | Score | Kurzurteil |
|---|---|---|
| Interaktion & Feedback | **7** | Optimistisches Play/Pause vorbildlich; Lücken konzentriert in wenigen High-Traffic-Momenten (stummes Alarm-Save, idler Play-Button als No-op). |
| Information-Architektur & Flows | **7** | Flaches Dashboard-Modell ist richtig für 4 Tasks; Schwächen sind Priorisierung *innerhalb* der Sheets, nicht das Navigations-Skelett. |
| Accessibility (WCAG 2.2 AA) | **7** | Statik (Landmarks, Fokus-Trap, Kontrast, Targets) stark; Lücke ist die **dynamische Schicht** — Polling-Statuswechsel werden AT nicht angesagt. |
| Frontend-Architektur & Perf (Pi Zero W) | **7** | Echte Pi-Instinkte verbaut; gebremst durch den 3.365-Zeilen-App-Monolith und unkonditionierten Re-Render pro Poll. |
| Visual Design & Ästhetik | **6** | Liebevoll, kohärent, mit echten Delight-Momenten — aber halb-systematisiert und noch nicht *distinctive* (eigene Markenidentität fehlt). |
| Responsive, Mobile & PWA | **6** | Als responsive Web-App gut; das „installierbare, offline-fähige PWA"-Versprechen ist **nicht eingelöst** (kein Service Worker, HTTP-only). |
| Microcopy, Content & i18n | **6** | Vollständig zweisprachig & freundlich — aber i18n ist *bilingual-by-hardcoding*; zwei driftende Übersetzungssysteme erzeugen sichtbare Bugs. |
| Motion & Micro-Interactions | **5** | Fundament stark (Reduced-Motion, Transition-Token), aber **jeder Signatur-Moment ist unanimiert** (Sheet teleportiert, Toast poppt, Artwork hard-cut). |

---

## 2. Was bereits stark ist (nicht anfassen)

Damit die Review ehrlich bleibt — das hier ist überdurchschnittlich gelöst und sollte als Referenz für den Rest dienen:

- **Optimistisches Play/Pause** mit Reconcile/Revert (`usePlaybackActions.ts:100-140`) — Lehrbuch.
- **State-Machine-Abdeckung**: Library/Devices/Queue/Account unterscheiden offline/loading/pending/auth_required/error/empty/ready — kaum „blank screens".
- **Modal-Mechanik**: Fokus-Trap + Escape + Opener-Restore + Scroll-Lock mit Scrollbar-Kompensation (`app.tsx:384-487, 1555-1577`), E2E-getestet.
- **Listbox-Keyboard-Contract** für die Custom-Dropdowns (`useListboxDropdown`, `app.tsx:650-739`).
- **Toast-A11y**: jeder Toast eigene atomare Live-Region, Errors `role=alert/assertive`, Info/Success `role=status/polite` (`app.tsx:343-371`).
- **Pi-bewusstes Polling**: Intervall nach `visibilityState` (4s/6s sichtbar, 30s/45s verborgen), Fast-Retry nur bei `pending`, Re-Arm nur auf settled (`useDashboardPolling.ts:101-176`).
- **Minuten-genauer Clock-Tick** statt Sekunden-Re-Render (`app.tsx:1532-1546`) — spart ~59 Reconciliations/Min.
- **Reduced-Motion-Killswitch** global (`styles.css:1829-1838`), `env(safe-area-inset)` an 6 Stellen real genutzt, Pinch-Zoom *nicht* deaktiviert.
- **Token-Fundament** (Radius-/Shadow-/Accent-/Surface-Skala) + **OLED-Variante** fürs Wandgerät (`styles.css:13-39`).

---

## 3. Die 7 Kernthemen (Root Causes)

Die 63 Befunde lassen sich auf sieben Ursachen verdichten. Hier liegt der Hebel.

### T1 — Das Designsystem ist nur halb systematisiert und noch nicht distinctive
Farbe/Radius/Schatten sind Tokens, **Typo (18 Ad-hoc-Größen auf Apple-only-Fontstack) und Spacing (ungerasterte Magic Numbers) sind freihändig** → der Rhythmus wirkt „eyeballed", nicht autorisiert. Schwarze Schatten auf Fast-Schwarz tragen kaum Tiefe; der einzige Browser-Default-Slider bricht die sonst custom Material-Sprache; und die Identität lehnt sich komplett an Spotifys geschütztes Logo an.
*Befunde: `type-scale-ad-hoc`, `spacing-radius-not-tokenized`, `invisible-shadow-elevation`, `native-range-slider`, `borrowed-spotify-brandmark`, `disc-visual-reads-as-spinner`*

### T2 — Feedback ist stumm und inkonsistent — für sehende *und* AT-Nutzer
Das Bestätigungsmodell unterscheidet sich pro Surface: Play/Pause optimistisch, Settings toastet bei *jedem* Toggle, das **Headline-Alarm-Save ist komplett still**. Der prominente grüne Play-Button ist im Idle ein stummes No-op; Taps bekommen auf dem touch-first-PWA **keine Press-Bestätigung**; der Volume-Slider kämpft gegen den Poll; Screenreader hören beim Umschalten nichts.
*Befunde: `alarm-save-silent-and-toggle-not-optimistic`, `idle-play-button-looks-enabled-but-disabled`, `no-press-active-feedback-touch`, `a11y-transport-state-not-announced`, `a11y-status-pill-not-live`, `volume-slider-poll-fight`, `toast-and-busy-feedback-polish`, `play-now-microcopy-leak`, `play-sheet-row-select-inert`, `a11y-custom-dropdown-label-association`*

### T3 — Der Always-on-Idle-Screen ist der meistgezeigte *und* teuerste — und der Monolith blockiert den Fix
Am Wandgerät (Kern-Use-Case) kommt der Ruhe-Dashboard nie zur Ruhe: ein **unendlicher Equalizer** treibt Dauer-Repaints durch **backdrop-blur auf ~9 Flächen** (der teuerste VideoCore-IV-Posten), das vorhandene `SPOTIPI_LOW_POWER`-Flag ist nur im Backend verdrahtet, und weil jeder Poll ein frisches Dashboard-Objekt allokiert, **re-rendert der ganze 3.365-Zeilen-App-Baum alle 4–6s** — auch wenn die Bytes identisch sind.
*Befunde: `perf-idle-blur-and-infinite-animation`, `motion-backdrop-filter-pi-cost`, `motion-idle-equalizer-runs-forever`, `perf-unconditional-dashboard-rerender`, `perf-playervolume-reset-every-poll`, `arch-app-monolith`, `perf-no-memo-on-sheets-and-inline-callbacks`, `perf-dual-polling-loop`, `perf-uncached-derived-render-work`*

### T4 — Die IA-Hierarchie ignoriert Nutzungshäufigkeit
Das Dashboard und die Sheets gewichten alles gleich statt nach „wie oft angefasst": Die meistgeänderte Eigenschaft (Weckzeit) hat keinen Fast-Edit-Pfad, das Alarm-Sheet ist ein langer Scroll aus Daily- + Set-once-Controls, Musik-Browsing ist verschüttet und dreifach dupliziert, Settings führt mit Einmal-Credentials vor Alltags-Prefs, und ein doppelter Status-Pill plus halb-leere Snapshot-Card verschenken Prime-Space.
*Befunde: `alarm-time-no-fast-edit`, `alarm-sheet-no-progressive-disclosure`, `alarm-sheet-no-explicit-done`, `music-library-buried-and-tripled`, `play-tile-weak-signifier`, `settings-credentials-before-prefs`, `snapshot-card-void`, `duplicate-status-pill`, `redundant-idle-status-signals`*

### T5 — Copy lebt in zwei driftenden Systemen; die UI ist bilingual-by-hardcoding
~196 inline `localized(en,de)`-Paare in `app.tsx` (plus dupliziertes Helper in 4 Hooks) koexistieren mit einer Legacy-Server-Tabelle, die für ~50 Keys konsultiert wird und die Code-Fallbacks **stumm überschreibt** → sichtbare Casing-Bugs (kleingeschriebene Tabs neben Title-Case), ~3 KB toter Keys an einen 512-MB-Pi, und „dritte Sprache" = 200+ Call-Sites umschreiben. Zeit wird auf dem einen Screen, dessen Job das Zeitanzeigen ist, **dreifach formatiert**.
*Befunde: `i18n-dual-system-hardcoded`, `table-overrides-cause-casing-bugs`, `time-format-inconsistency`, `dev-jargon-in-user-copy`, `snooze-copy-cryptic`, `german-anglicism-and-verb-inconsistency`, `accept-language-substring-match`, `empty-state-inconsistency`, `voice-inconsistency-dj-off-duty`*

### T6 — Motion-Fundament da, aber jeder Signatur-Moment ist unanimiert
Die Plumbing ist stark (Transition-Token, Reduced-Motion-Killswitch, optimistisches Play/Pause), doch die Momente mit Choreografie-Erwartung hard-cutten alle: das mobile Bottom-Sheet **teleportiert statt hochzugleiten**, Toasts poppen, Artwork blitzt zwischen Covern, Loading ist nackter Text statt Skeletons, Alarm-Dim/Undim und Countdown-Bar snappen pro Poll.
*Befunde: `motion-sheet-no-entrance`, `motion-toast-no-enter-exit`, `motion-artwork-hard-swap`, `motion-loading-text-not-skeletons`, `motion-alarm-toggle-content-snaps`, `motion-progress-bar-steps`*

### T7 — Das „installierbare, offline-fähige PWA"-Versprechen ist nicht eingelöst
Es gibt **keinen Service Worker**, und die App wird über **plain HTTP auf einer LAN-IP** ausgeliefert — kein Secure Context, also kann ein SW nie registrieren und Chrome bietet keinen echten Install an. Die UI sagt stolz „Offline, still usable", doch ein Cold-Launch gegen einen unerreichbaren Pi zeigt die Browser-Dino-Seite. Manifest ohne `shortcuts`/`screenshots`, `theme-color` folgt nie dem OLED-Theme, iOS ohne Splash, zwei Touch-Targets regressiert unter 44px.
*Befunde: `pwa-no-offline-shell-over-http`, `pwa-theme-color-not-synced-to-oled`, `pwa-manifest-missing-shortcuts-screenshots`, `ios-no-apple-touch-startup-image`, `mobile-bottom-safe-area-and-standard-meta-gaps`, `a11y-mobile-settings-gear-touch-target`, `touch-weekday-chips-below-44px`, `mobile-double-padding-gutter`*

---

## 4. Umsetzungsvorschlag — 3-Phasen-Roadmap

Legende: **Schwere** (med/low) = nach Verifikation · **Effort** S<2h · M=halber Tag · L=mehrtägig.

### Phase 1 — Quick Wins (CSS-only / wenige Zeilen, kein Pi-Rebuild-Risiko)
> Höchstes Impact-pro-Effort im ganzen Audit. Hebt gefühlte Qualität, killt die schlimmsten Always-on-Pi-Kosten, fixt sichtbare Bugs/Regressionen.

| # | ID | Schwere | Effort | Maßnahme |
|---|---|---|---|---|
| 1 | `no-press-active-feedback-touch` / `motion-no-active-press-feedback` | med | S | `:active { transform: scale(0.96) }` am gemeinsamen interaktiven Selektor — **größter Perceived-Responsiveness-Gewinn** am Touch-PWA, reduced-motion-safe. |
| 2 | `perf-idle-blur-and-infinite-animation` / `motion-idle-equalizer-runs-forever` | med | S | Idle-Equalizer hinter `dashboard.playback.is_playing` gaten → Wandgerät wird **statisch**. |
| 3 | `motion-backdrop-filter-pi-cost` | med | S | `backdrop-blur` per `data-low-power` kappen/abschalten (Fallback: solider `--surface`-Fill). Visuell ~identisch, großer GPU-Save. |
| 4 | `a11y-mobile-settings-gear-touch-target` | med | S | `min-height:44px` am mobilen Settings-Gear (aktuell ~20px hoch) — einzige mobile Nav. Pixel-7-Playwright deckt's ab. |
| 5 | `touch-weekday-chips-below-44px` | med | S | `min-height:44px` an den fingerdichten Wochentag-Chips. |
| 6 | `a11y-transport-state-not-announced` | med | S | Play/Pause-Accessible-Name spiegelt Aktion + `aria-pressed` → AT bekommt Bestätigung. |
| 7 | `a11y-status-pill-not-live` | med | S | Eine visually-hidden `role=status`-Live-Region spiegelt das Status-Label → Polling-Transitionen werden einmal angesagt. |
| 8 | `table-overrides-cause-casing-bugs` | med | S | Kleingeschriebene EN-Library-Tabs in `translations.py` fixen (oder Keys löschen) — sichtbarer Bug auf der Haupt-Picker-Fläche. |
| 9 | `native-range-slider` | low | S | Volume-Track/Thumb an die „Glass"-Sprache angleichen (Cross-Browser-Konsistenz; `.progress-bar` spiegeln). |
| 10 | `volume-slider-poll-fight` / `perf-playervolume-reset-every-poll` | med/low | S | Lokale Edits ~1,5s gegen Poll-Clobber schützen; Effekt auf den Skalar `volume_percent` statt aufs ganze `dashboard`-Objekt hängen. |
| 11 | `duplicate-status-pill` / `redundant-idle-status-signals` | low | S | Zweiten identischen Status-Pill aus der Player-Card entfernen (oder Rollen differenzieren). |
| 12 | `idle-play-button-looks-enabled-but-disabled` | med | S | Disabled-Idle-Play-Button entschärfen (neutral/outline + `title`/aria → „Play now"), damit die echte CTA primär liest. |
| 13 | `motion-sheet-no-entrance` / `motion-toast-no-enter-exit` | med | S | One-shot Keyframes: Bottom-Sheet Slide-up, Toast Fade/Slide. Compositor-billig, reduced-motion neutralisiert. |
| 14 | `motion-artwork-hard-swap` | med | S | Opacity-Crossfade per `src` — höchster Polish-pro-Byte am Dashboard. |
| 15 | `pwa-theme-color-not-synced-to-oled` | low | S | `theme-color`-Meta aus `useTheme` setzen (#000 OLED / #071018 default) → killt graues Statusbar-Band genau am OLED-Zielgerät. |
| 16 | `dev-jargon-in-user-copy` / `play-now-microcopy-leak` / `snooze-copy-cryptic` | med/low | S | „hydrate"/„Sleep flow"/„surface" + „Speaker list will hydrate here" + „Snooze armed/Pause = Snooze" durch Klartext ersetzen. |
| 17 | `german-anglicism-and-verb-inconsistency` / `accept-language-substring-match` | low | S | „Custom"→„Benutzerdefiniert", ein Stop-Verb; Accept-Language auf Primär-Subtag prüfen statt Substring. |
| 18 | `mobile-bottom-safe-area-and-standard-meta-gaps` | low | S | `env(safe-area-inset-bottom)` am App-Shell-Bottom + Standard-`mobile-web-app-capable`-Meta. |
| 19 | `mobile-double-padding-gutter` | med | S | **Mobile-spezifisch.** Card-Padding (28–30px) auf Phones reduzieren (~16px) und die doppelte Verschachtelung (Card-Padding + Innenbox-Padding) auf **eine** Gutter-Ebene zusammenführen → ~25–30% Content-Breite zurückgewonnen. Siehe Detail 5.9. |
| 20 | `perf-uncached-derived-render-work` | low | S | `primaryFlows` memoisieren, statische Icon-vnodes hoisten (greift v.a. nach #2 unten). |

### Phase 2 — Core UX (M-Effort: Designsystem fertig, Feedback konsistent, Flows nach Häufigkeit priorisieren)

| ID | Schwere | Effort | Maßnahme |
|---|---|---|---|
| `alarm-save-silent-and-toggle-not-optimistic` | med | M | Alarm-Toggle optimistisch wie Play/Pause; eine ruhige Bestätigung („Wecker an für 07:30"); Settings-Toast-Spam zugleich dämpfen → **ein** konsistentes Feedback-Modell. |
| `toast-and-busy-feedback-polish` | med | M | Error-Toasts länger/bis-Dismiss + Pause-on-hover; `busyAction` pro Element-ID statt global → Per-Item-Spinner. |
| `alarm-sheet-no-progressive-disclosure` | med | M | Progressive Disclosure: Zeit+Enable+Repeat+Speaker+Musik primär; Fade-in/Shuffle/Snooze hinter CSS-`<details>`-„Erweitert"; Library collapsed hinter Musik-Summary. |
| `alarm-time-no-fast-edit` | low | M | Quick-Time-Edit am Hero (Numerals deep-linken in Zeitfeld, oder ±15-Min-Chips über bestehenden `handleAlarmSave`). |
| `alarm-sheet-no-explicit-done` | low | S | Sticky „Fertig"/inline „Gespeichert" am Sheet-Fuß. |
| `play-sheet-row-select-inert` | med | M | Im Play-Sheet: Row-Body-Tap startet direkt (oder explizite sticky „Play"-CTA) + transientes „Starte…". |
| `music-library-buried-and-tripled` | low | M | Geteilte `LibraryPicker`-Komponente behalten, aber Default-Tab pro Kontext (Play→Recent/Search, Alarm→Playlists); Recents-Strip voranstellen. |
| `play-tile-weak-signifier` | low | S | Fette Zeile = Aktion/letzte Quelle statt Speaker-Count; Count in die Meta-Zeile. |
| `settings-credentials-before-prefs` | low | S | Preferences/Features nach oben, Credentials nach unten/hinter „Account"-Disclosure (Connected-State bekannt). |
| `snapshot-card-void` | low | S | Rechte Card bei deaktiviertem Sleep nicht leer lassen (Inhalt verteilen / nützliches Element promoten / Höhe an Inhalt koppeln). |
| `perf-unconditional-dashboard-rerender` | med | M | Setter-Short-circuit: bei struktureller Gleichheit `current` zurückgeben → Idle-Re-Render entfällt komplett. (Unabhängig von Decomposition shippbar.) |
| `type-scale-ad-hoc` | med | M | 5–7 Typo-Tokens (modulare Skala) + Cross-Platform-Stack (`system-ui` voran) oder **ein** self-hosted Subset-Variable-Font. 18 Literale auf ~6 Stufen kollabieren. |
| `spacing-radius-not-tokenized` | low | M | `--space-1..8` auf 4px-Raster; Literale snappen (15→16, 22→24, 30→32). |
| `invisible-shadow-elevation` | low | M | Tiefe aus Licht statt Schwarz: Top-Inset-Highlight + Hairline-Border; riesige Black-Blurs trimmen (Pi-Paint-Kosten). |
| `time-format-inconsistency` | low | M | Ein `formatClockTime(date, lang)` für Header **und** Alarm-Card mit expliziter `hour12`-Entscheidung (24h-Default). |
| `empty-state-inconsistency` | low | M | Ein Empty-State-Muster (Icon + freundliche Zeile + ggf. CTA) auf Alarm-Meta/Queue/Voids; Voice angleichen. |
| `motion-loading-text-not-skeletons` | med | M | Leichte (shimmer-freie) Skeletons in bestehenden Dimensionen; Hydrating- vs. Idle-Zustand visuell trennen. |
| `motion-alarm-toggle-content-snaps` | low | S | `transition: color/opacity 180ms` an Alarm-Card-Dim, damit Inhalt mit dem Thumb wandert. |
| `motion-progress-bar-steps` | low | S | `transition: width 400ms` (oder `scaleX`) an `.progress-bar span` → Countdown gleitet statt zu hüpfen. |
| `a11y-custom-dropdown-label-association` | low | S | Field-Label-`id` + `aria-labelledby` am Trigger-Button (Div ist nicht labelbar). |
| `a11y-listbox-name-and-controls` | low | S | `aria-label`/`id` an `role=listbox`, `aria-controls` am Trigger; optional Home/End + Type-ahead. |
| `a11y-dropdown-focus-ring-clipped` | low | S | Inset-Fokusring in der Optionsliste (Container clippt `overflow:hidden`). |
| `a11y-tab-aria-controls-dangling` | low | S | Tabpanel-Container in allen States rendern, damit `aria-controls` nie ins Leere zeigt. |
| `a11y-toast-timeout-and-manifest-lang` | low | S | Auto-Dismiss mit Länge skalieren/Pause-on-hover; Manifest-`lang` an Default angleichen. |

### Phase 3 — State-of-the-art (L / strukturell: Perf entsperren, echte PWA, eigene Identität)

| ID | Schwere | Effort | Maßnahme |
|---|---|---|---|
| `arch-app-monolith` | med | L | App-Monolith in memoisierte Subtrees zerlegen (PlayerCard, AlarmHero, SnapshotCard, je Sheet). **Voraussetzung**, damit gezielte Perf-Fixes überhaupt greifen. Budget-Headroom (~19 KiB) trägt die Extra-Komponenten. |
| `perf-no-memo-on-sheets-and-inline-callbacks` | low | M | Nach Decomposition `memo` + stabile Callbacks → offener Picker reagiert nicht mehr auf fremde Polls. |
| `arch-prop-drilling-t-language` | low | M | `{t, language}` via Context statt durch jede Komponente drillen (Sprache ändert nur per Reload → konstant). |
| `perf-dual-polling-loop` | low | M | Queue-Freshness in den Dashboard-Snapshot falten → ein Poll statt zwei unkoordinierter Timer. |
| `i18n-dual-system-hardcoded` | med | L | Auf **einen** Key-Katalog konsolidieren; EN+DE-Paare aus dem JS in den Server-Payload → **schrumpft `app.js`** (hilft `budget:check`). |
| `pwa-no-offline-shell-over-http` | med | L | Plattform-Story ehrlich entscheiden: lokales TLS (mkcert/Caddy/Tailscale) + winziger Cache-first-SW (Shell precache, zählt **nicht** aufs JS-Budget) **oder** „installable PWA"-Framing + „offline"-Copy zurücknehmen. |
| `pwa-manifest-missing-shortcuts-screenshots` | low | M | `shortcuts` (Alarm/Sleep/Play deep-link — braucht kleine Backend-Whitelist) + `screenshots` für die reichere Install-UI. |
| `ios-no-apple-touch-startup-image` | low | M | iOS-Splash-Images (dark #071018 + Mark) gegen den White-Flash beim Launch. |
| `borrowed-spotify-brandmark` | low | M | Eigene Single-Path-SVG-Marke (Glocke+Waveform/Monogramm); Spotify-Glyph nur fürs „Connect"-Affordance. |
| `disc-visual-reads-as-spinner` | low | M | Fallback-„Disc" die volle Quadrat-Silhouette geben (Cover-Skeleton/Vinyl), damit Empty & Loaded dasselbe Footprint teilen. |
| `voice-inconsistency-dj-off-duty` | low | S | Voice-Entscheidung: „DJ off duty" als System ausrollen *oder* angleichen. |

---

## 5. Top-Befunde im Detail (die wirkungsvollsten 8)

### 5.1 `idle-play-button-looks-enabled-but-disabled` — der prominenteste Button ist im Idle ein stummes No-op · **med / impact high / S**
Der zentrale grüne Play-Button ist `disabled={!playerReady || ...}` (`app.tsx:2449-2457`); `playerReady` ist im häufigen „No active playback"-Zustand `false` (`usePlaybackActions.ts:56-67`), aber er rendert mit vollem grünem Gradient+Glow und droppt disabled nur auf `opacity:0.58` — liest weiter als Haupt-CTA. Tap → `handlePlaybackCommand` early-returnt ohne Toast/Tooltip (`usePlaybackActions.ts:96-98`). Der echte Start-Pfad ist die separate „Play now"-Card.
**Fix:** Entweder den zentralen Button im Not-Ready in eine echte „Start playback"-Aktion verwandeln (öffnet Play-Sheet), oder ihn sichtbar zu Neutral/Outline degradieren + `title`/aria-Hinweis. *Sonos/Spotify Connect/Apple Home zeigen nie einen disabled-aber-lauten Primär-Control.*

### 5.2 `alarm-save-silent-and-toggle-not-optimistic` — schwächstes Feedback ausgerechnet beim Headline-Feature · **med / impact high / M**
`handleAlarmSave`-Success-Pfad ruft nur `setDashboard`, **kein** Success-Toast (`app.tsx:1963-1990`); Zeit/Device/Volume/Weekdays/Fade/Shuffle/Snooze auto-saven ohne jede Bestätigung. Der Inline-Toggle hängt an Server-State und ist während des Saves `disabled` → der Switch **dimmt und friert in der ALTEN Position** für den Pi-Roundtrip, dann snappt er. Inkonsistent zu Settings (toastet bei jedem Toggle) und Play/Pause (optimistisch).
**Fix:** Toggle optimistisch flippen + Revert-on-fail; eine knappe Bestätigung; Settings-Toast-Spam zugleich dämpfen. *iOS/Google Clock flippen Alarm-Switches sofort.*

### 5.3 `perf-unconditional-dashboard-rerender` — voller App-Baum re-rendert alle 4–6s, auch ohne Änderung · **med / impact high / M**
`mergeDashboard` macht immer `{ ...incoming }` (`useDashboardPolling.ts:32-49`) → neue Referenz pro Poll, egal ob sich was änderte. `dashboard` gehört der einen App-Komponente (`app.tsx:1401`), also re-läuft der ~2000-Zeilen-Baum inkl. aller Memos jeden Intervall. Idle-Gerät diff't die ganze App alle 4–6s, für immer.
**Fix:** Setter-Short-circuit (Feldvergleich auf alarm/sleep/playback_status/devices.length/track.name/volume) → `current` zurückgeben, Preact bailt aus. Low-risk, eliminiert den Idle-Render komplett.

### 5.4 `perf-idle-blur-and-infinite-animation` — der Ruhe-Screen rechnet ununterbrochen · **med / impact high / S**
`backdrop-filter: blur(20px)` auf **9 Selektoren** (`styles.css:103-114`) + `.player-artwork-fallback-bars` mit `animation: fallback-eq … infinite` (`styles.css:376-407`) — und dieser Fallback **ist** der Default-Idle-Zustand (`app.tsx:2408-2427`). Auf VideoCore IV ist Real-time-Blur der teuerste Effekt; ein Endlos-Loop erzwingt Dauer-Repaints durch große geblurrte Regionen.
**Fix:** Equalizer hinter `is_playing` gaten; Blur-Radius kappen/auf das offene Sheet beschränken; optional per `low_power` abschalten. → Idle-Wandgerät wird statisch.

### 5.5 `no-press-active-feedback-touch` — Taps wirken unquittiert · **med / impact high / S**
Nur `:hover { translateY(-1px) }` definiert; repo-weit **kein** `:active` (`styles.css:523-532` u.a.). Hover existiert auf Touch nicht → am Phone/Wandgerät ist die einzige Rückmeldung der (oft verzögerte) State-Change. Mit Pi-Latenz: Doppel-Taps, Gefühl von Trägheit.
**Fix:** `:active { transform: scale(0.97) }` am gemeinsamen Selektor — reine CSS, kein Bundle-Kosten, reduced-motion-safe. *Einzelner größter Perceived-Responsiveness-Gewinn.*

### 5.6 `a11y-transport-state-not-announced` + `a11y-status-pill-not-live` — die dynamische Schicht ist für AT stumm · **med / impact high–med / S**
Play/Pause hat fixen `aria-label` + tauscht nur das SVG, kein `aria-pressed`; Success-Pfad toastet nicht (`app.tsx:2449-2457`, `usePlaybackActions.ts:111-128`). `StatusPill` ist ein nacktes `<span>` ohne `role/aria-live` (`app.tsx:333-335`), dessen Label bei jedem Poll wechselt (Playing/Paused/Auth-required/Error/Offline). Screenreader erfahren weder, dass Playback umschaltete, noch dass die Session Re-Auth braucht.
**Fix:** Accessible-Name spiegelt Aktion + `aria-pressed`; **eine** visually-hidden `role=status`-Live-Region spiegelt `statusSnapshot.label` (sagt jede echte Transition genau einmal an).

### 5.7 `pwa-no-offline-shell-over-http` — kein echtes PWA, trotz Versprechen · **med / impact high / L**
Kein Service Worker (grep leer); `run.py:83-97` ohne `ssl_context` → plain HTTP auf LAN-IP = kein Secure Context. SW kann nie registrieren, Android-Chrome bietet keinen echten Install. Ohne SW kein Precache → Cold-Launch gegen unerreichbaren Pi = Browser-Fehlerseite, **direkt im Widerspruch** zum UI-Text „Offline, still usable" (`app.tsx:2260`).
**Fix:** Ehrlich entscheiden — lokales TLS + winziger Cache-first-SW (zählt nicht aufs JS-Budget) *oder* „installable/offline"-Framing zurücknehmen.

### 5.8 `i18n-dual-system-hardcoded` + `table-overrides-cause-casing-bugs` — zwei driftende Copy-Systeme mit sichtbarem Bug · **med / impact high / L (+ S Sofortfix)**
196 inline `localized()` in `app.tsx` + Helper in 4 Hooks vs. Legacy-`translations.py` (noch mit Font-Awesome-Markup-Resten, daher existiert `stripMarkup`). Wo die Tabelle greift, **gewinnt** ihr Wert über den Code-Fallback: kleingeschriebene EN-Tabs (`'songs':'songs'`) rendern neben Title-Case-Tabs → sichtbar inkonsistente Library-Fläche.
**Sofortfix (S):** EN-Werte in `translations.py` Title-Case fixen oder Keys löschen. **Strategisch (L):** auf einen Katalog konsolidieren → schrumpft `app.js`.

### 5.9 `mobile-double-padding-gutter` — doppelte Padding-Kette frisst ~30% Breite auf Phones · **med / impact high / S**
Der `≤780px`-Breakpoint (`styles.css:1681-1827`) reduziert nur `border-radius` und reflowt das Layout, **senkt aber nie das horizontale Padding** von `.player-card` (30px, `styles.css:289`), `.snapshot-card` (28px, `:842`) oder der verschachtelten Innenboxen `.alarm-hero-open` (18px, `:939`), `.snapshot-item` (16/18px, `:853`). Die Desktop-Werte werden 1:1 vererbt.

**Padding-Kette (Phone):** `Shell-Rand 9px` (`width: min(100vw - 18px, …)`, `:1683`) + `Card 28–30px` + `Innenbox 16–18px`, keine davon mobil reduziert.

**Gemessen:**
- Player-Card-Inhalt: `360px − 2×(9+30) = 282px` · auf 390px → 312px
- Wecker-/Play-Text (verschachtelt): `360px − 2×(9+28+18) = 250px` · auf 390px → 280px → **~110px ≈ 30% der Breite** sind Gutter, bevor Inhalt kommt.

**Wurzel:** kein Spacing-Token (vgl. `spacing-radius-not-tokenized`) → Magic-Number-Paddings, die im Mobile-Breakpoint vergessen wurden zu verdichten.

**Fix (empfohlen, S, CSS-only):**
1. **Eine Gutter-Ebene statt zwei:** auf `≤480px` Card-Padding auf dünnen Rahmen (~8–12px), Innenboxen rücken fast randlos ein und tragen das Padding allein (behält die Tap-Affordanz der Kacheln).
2. **Responsives Gutter-Token:** `--card-pad` mit `clamp(16px, 4vw, 30px)` statt Hard-Breakpoint — skaliert stufenlos, verheiratet sich mit dem `--space`-Token-Refactor aus Phase 2. Vertikal mitverdichten (Card 28–30 → ~16–20px, Grid-Gap 24 → ~16px).

*State-of-the-art: Mobile-First-Layouts nutzen ein responsives Gutter-Token und genau eine Padding-Ebene pro Container; verschachtelte Boxen erben den Gutter oder werden randlos, nie additiv.*

> Tie-in: Dieser Befund ist die mobil-konkrete Ausprägung von **T1** (`spacing-radius-not-tokenized`) und gehört zu **T7** (Mobile). Als Quick-Win in Phase 1, mit dem sauberen Token-Fix in Phase 2.

---

## 6. Offene Lücken (von keiner Linse abgedeckt — aber wichtig)

Diese Punkte hat keine der 8 Linsen besessen; mehrere sind für eine *Wecker*-App zentral:

1. **First-Run / Onboarding-Journey.** Niemand hat den End-to-End-„Connect Spotify"-OAuth-Pfad bzw. das Gefühl eines frischen, unkonfigurierten Dashboards geprüft — nur per-Component-`auth_required`-States. Der Weg von „leere Installation" → „funktionierender Wecker" ist unbewertet.
2. **Proaktive Fehlerkommunikation = das wichtigste Wecker-Thema.** Die App existiert, um pünktlich zu klingeln, warnt aber **nicht vor** einem Fehlschlag — z. B. wenn der gewählte Alarm-Speaker offline ist oder das Spotify-Token bald abläuft. (Das UI-Komplement zum bereits dokumentierten „device offline"-Backend-Issue.) **Empfehlung:** ein „Wird dieser Wecker klingeln?"-Pre-Flight-Check am aktivierten Alarm-Hero.
3. **Keine Messung auf echter Pi-Hardware.** Alle Perf-Befunde sind aus Code erschlossen, nicht auf Pi Zero W profiliert. Kein FPS/Long-Task-Baseline, kein Lighthouse/Web-Vitals-Budget, **kein automatischer axe-/Kontrast-Check in CI** (das Gate prüft nur Bundle-Bytes). Genau deshalb konnte die ~20px-Mobile-Gear-Regression durchrutschen.
4. **Gemessenes Kontrast-Audit.** Die A11y-Linse nennt Kontrast „largely solid" ohne Ratios; muted Text auf Fast-Schwarz (kleine Uhr, Empty-Copy) ist plausibel grenzwertig gegen 4,5:1 — verifizieren.
5. **Haptik / kurzer Audio-Tick** als zusätzlicher Bestätigungskanal — dient direkt dem „stummes Feedback"-Thema, gerade auf Touch mit Pi-Latenz.
6. **Nicht entschieden:** `forced-colors`/Windows-High-Contrast fürs Kiosk-Wandgerät; Light-Theme; Keyboard/Remote-Shortcuts (Space=Play/Pause) fürs Always-on-Display; Multi-Client-Concurrent-Edit (Phone + Wandgerät editieren dieselbe Config — aktuell stilles Last-write-wins).

> **Out of scope (korrekt nicht re-flagged):** Das LAN-Trust-Sicherheitsmodell (`SPOTIPI_TRUST_PRIVATE_NETWORK`) ist laut dokumentierter Projektentscheidung Absicht.

---

## 7. Methodik & Vertrauen

- **8 Linsen** (Visual, Interaction, IA, A11y, Mobile/PWA, Architektur/Perf, Microcopy/i18n, Motion), jede mit eigenem Reviewer auf dem realen Code + Live-Screenshot.
- **Adversariale Verifikation:** jeder Befund von einem separaten Skeptiker gegen die zitierte `file:line` geprüft. **2 Befunde verworfen**, weil Fehlinterpretation:
  - `clock-hierarchy-inversion` (Behauptung „Platzhalter größer als Uhr") — Fehllesung eines `clamp()`; die Alarm-Zeit `07:30` (2,6rem) ist tatsächlich das größte Zeit-Element. **Hierarchie ist hier korrekt.**
  - `enabled-alarm-no-speaker-no-music` (Behauptung „Wecker ohne Speaker klingelt still nicht") — der Save-Guard `return`t unbedingt und zeigt beim Aktivieren „Choose a speaker"; kein stiller Fehlschlag.
- Mehrere Schweregrade wurden durch die Verifikation **heruntergestuft** (z. B. Typo-Skala high→med, Duplicate-Pill med→low), einige Evidenz-Overstatements korrigiert (z. B. `native-range-slider`: auf Chrome malt `accent-color` bereits grünen Track+Thumb — es ist ein Cross-Browser-Konsistenz-, kein „kaputt"-Thema).

*Diese Datei ist eine Review-Dokumentation, kein Code. Uncommitted — nach Belieben behalten, anpassen oder via `/ship` aufnehmen.*

---

## Anhang A — Mobile-Layout-Konzept (Padding/Gutter)

Konkretisierung zu Befund `mobile-double-padding-gutter` (5.9). **Konzept, keine Implementierung.**

### Prinzip: „Card = Rahmen, Box = Gutter"
Auf Mobile übernimmt **eine** Schicht den Content-Abstand. Die Card wird zum dünnen Rahmen (nur noch Glass-Kante + Gradient), die verschachtelte Box trägt den Gutter. Das additive Doppel-Padding verschwindet, die „Kachel"-Affordanz der Tiles bleibt.

### Spacing-Tokens (responsiv via `clamp()`, kein harter Breakpoint)
| Token | Rolle | Desktop | Mobile ≤480 | `clamp()`-Vorschlag |
|---|---|---|---|---|
| `--shell-gap` | Screen → Card | 16px | 10px | `min(100vw - 20px, 1360px)` |
| `--card-pad` | Card-Innenrahmen | 28–30px | 12px | `clamp(12px, 3.5vw, 30px)` |
| `--box-pad` | Innenbox → Inhalt | 16–18px | 14px | `clamp(14px, 3vw, 18px)` |
| `--stack-gap` | zwischen Cards/Boxen | 22–24px | 14px | `clamp(14px, 3vw, 24px)` |

### Breitengewinn je Fläche (360px-Viewport)
| Fläche | Kette vorher | Kette nachher | Inhalt vorher → nachher |
|---|---|---|---|
| Player-Card-Text (direkt) | 9+30 = 39px | 10+12 = 22px | 282 → **316px** (+34) |
| Wecker-/Play-Text (verschachtelt) | 9+28+18 = 55px | 10+12+14 = 36px | 250 → **288px** (+38, +15%) |
| Sheet-Body | 6+20 = 26px | 8+16 = 24px | 308 → 312px *(war schon ok)* |

→ Die Sheets waren nie das Problem; die Dashboard-Cards sind die Täter.

### Kompoundierende Layout-Moves (über reines Padding hinaus)
1. **Artwork deckeln** — `.player-artwork` (`aspect-ratio:1/1`) ist im Mobile-Single-Column volle Breite → ~310px hohes Quadrat, das Transport/Queue/Volume unter den Fold drückt. Konzept: Phones `max-width: ~200px` zentriert (bleibt quadratisch). Im Idle = Einstieg in den „Clock-Mode" aus Abschnitt 3/Design.
2. **Doppelten Status-Pill auf Mobile entfernen** (`duplicate-status-pill`) — spart eine vertikale Zeile.

**Netto:** +15–17% Textbreite **+** kompaktere Vertikale → Dashboard rückt näher an „alles Wichtige auf einen Screen". Reine CSS, S-Effort, fügt sich in das `--space`-Token-Refactor (Phase 2) ein, liefert aber als Quick-Win (Phase 1).
