/** @jsxImportSource preact */
import { Fragment } from "preact";
import type { JSX } from "preact";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";

import { getJson, postForm, postJson } from "./lib/api";
import { useDashboardPolling } from "./hooks/useDashboardPolling";
import { useLibraryData } from "./hooks/useLibraryData";
import { useNetworkStatus } from "./hooks/useNetworkStatus";
import { usePlaybackActions } from "./hooks/usePlaybackActions";
import { useSettingsMutations } from "./hooks/useSettingsMutations";
import { useTheme } from "./hooks/useTheme";
import { useToasts } from "./hooks/useToasts";
import type {
  AlarmFormState,
  AlarmSummary,
  AppBootstrap,
  ArtistDrilldown,
  AsyncStatus,
  CollectionState,
  DashboardData,
  LibraryItem,
  LibrarySection,
  PlayFormState,
  PlaybackQueuePayload,
  PrimaryFlowSnapshot,
  SettingsData,
  SleepFormState,
  SpotifyDevice,
  SpotifyProfile,
  SurfaceName,
  ToastItem
} from "./lib/types";
import {
  createAlarmFormModel,
  createPlayFormModel,
  createSleepFormModel,
  getPreferredDevice,
  SLEEP_DURATION_PRESETS,
  toPrimaryFlowSnapshot
} from "./lib/view_models";

const LIBRARY_SECTIONS: LibrarySection[] = ["playlists", "albums", "tracks", "artists", "recent", "top", "search"];
const DURATION_OPTIONS = SLEEP_DURATION_PRESETS;
const LAST_DEVICE_STORAGE_KEY = "spotipi.last_device_id";
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([type='hidden']):not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

interface AccountLoadState {
  status: AsyncStatus;
  profile?: SpotifyProfile;
  errorMessage?: string;
}

type TranslateFn = (
  key: string,
  fallback: string,
  params?: Record<string, string | number>
) => string;

const ICONS: Record<string, string> = {
  alarm: "M12 3a7 7 0 0 0-7 7v4.6l-1.8 2.4A1 1 0 0 0 4 19h16a1 1 0 0 0 .8-1.6L19 14.6V10a7 7 0 0 0-7-7Zm0 18a2.3 2.3 0 0 0 2.2-1.7H9.8A2.3 2.3 0 0 0 12 21Z",
  sleep: "M13.5 2.2a8.9 8.9 0 1 0 8.3 12.2A9.8 9.8 0 0 1 13.5 2.2Z",
  play: "M8 6.2v11.6a1 1 0 0 0 1.5.9l8.8-5.8a1 1 0 0 0 0-1.8L9.5 5.3a1 1 0 0 0-1.5.9Z",
  pause: "M7 5h4v14H7zm6 0h4v14h-4z",
  next: "M6.5 7.1v9.8l7-4.9-7-4.9Zm8.4 0H17v9.8h-2.1zm3.6 0h2v9.8h-2z",
  previous: "M17.5 7.1v9.8l-7-4.9 7-4.9Zm-8.4 0H7v9.8h2.1zm-5.1 0h2v9.8h-2z",
  settings: "M19.4 13a7.7 7.7 0 0 0 .1-1l2-1.5-1.8-3.1-2.4.8a7.8 7.8 0 0 0-1.7-1l-.3-2.5H8.7l-.3 2.5a7.8 7.8 0 0 0-1.7 1l-2.4-.8-1.8 3.1 2 1.5a7.7 7.7 0 0 0 0 2l-2 1.5 1.8 3.1 2.4-.8a7.8 7.8 0 0 0 1.7 1l.3 2.5h6.6l.3-2.5a7.8 7.8 0 0 0 1.7-1l2.4.8 1.8-3.1-2-1.5ZM12 15.2A3.2 3.2 0 1 1 12 8.8a3.2 3.2 0 0 1 0 6.4Z",
  library: "M8 5.6v10.1a3.4 3.4 0 1 0 2 3V9.8h8v-4.2H8Z",
  volume: "M4 9.5v5h3.2L11 18V6L7.2 9.5H4Zm10.7-2.8v2.2a3.8 3.8 0 0 1 0 6.2v2.2a5.9 5.9 0 0 0 0-10.6Zm2.9-2.7v2.1a7.7 7.7 0 0 1 0 11.8V20a9.8 9.8 0 0 0 0-16Z",
  device: "M5 4h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-5l2 3H8l2-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z",
  refresh: "M18.4 8A7 7 0 1 0 19 12h-2a5 5 0 1 1-1.4-3.5L13 11h7V4l-1.6 4Z",
  close: "M6.7 5.3 12 10.6l5.3-5.3 1.4 1.4L13.4 12l5.3 5.3-1.4 1.4L12 13.4l-5.3 5.3-1.4-1.4L10.6 12 5.3 6.7l1.4-1.4Z",
  check: "M9.5 16.2 5.3 12l1.4-1.4 2.8 2.8 7.8-7.8 1.4 1.4-9.2 9.2Z",
  lightning: "M13 2 5 13h5l-1 9 8-11h-5l1-9Z",
  arrow: "m8 5 8 7-8 7V5Z",
  spotify: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm4.5 14.5a.7.7 0 0 1-1 .2c-2.7-1.7-6.1-2.1-10-.9a.7.7 0 1 1-.4-1.4c4.3-1.3 8.1-.9 11.2 1.1.3.2.4.7.2 1Zm1.4-3a.9.9 0 0 1-1.2.3c-3.1-1.9-7.8-2.5-11.5-1.2a.9.9 0 0 1-.6-1.7c4.3-1.4 9.5-.8 13.1 1.4.4.3.6.8.2 1.2Zm.1-3.2C14.2 8.1 8 7.8 4.8 8.8A1 1 0 0 1 4.2 7c3.8-1.2 10.7-.9 14.8 1.7a1 1 0 1 1-1 1.6Z"
};

function localized(language: string, en: string, de: string): string {
  return language === "de" ? de : en;
}

function stripMarkup(value: string): string {
  return value.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

function createTranslator(
  language: string,
  translations: Record<string, string>
): TranslateFn {
  return (key, fallback, params) => {
    const template = stripMarkup(translations[key] || fallback);
    if (!params) {
      return template;
    }

    return template.replace(/\{(\w+)\}/g, (_, token) => {
      if (token in params) {
        return String(params[token]);
      }
      return `{${token}}`;
    });
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeImageUrl(candidate: string | null | undefined): string | null {
  if (typeof candidate !== "string" || !candidate.trim()) {
    return null;
  }

  try {
    const parsed = new URL(candidate, window.location.origin);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return parsed.href;
    }
  } catch {
    return null;
  }

  return null;
}

function isValidTimeInput(value: string): boolean {
  return /^([01]\d|2[0-3]):([0-5]\d)$/.test(value);
}

function hasPassedToday(value: string): boolean {
  if (!isValidTimeInput(value)) {
    return false;
  }
  const [hour, minute] = value.split(":").map((segment) => Number(segment));
  const now = new Date();
  const selected = new Date(now);
  selected.setHours(hour, minute, 0, 0);
  return selected.getTime() <= now.getTime();
}

function readLastDeviceId(): string {
  try {
    return window.localStorage.getItem(LAST_DEVICE_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function writeLastDeviceId(deviceId: string): void {
  if (!deviceId) {
    return;
  }
  try {
    window.localStorage.setItem(LAST_DEVICE_STORAGE_KEY, deviceId);
  } catch {
    // Ignore quota/storage errors on constrained devices.
  }
}

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => {
    if (element.hasAttribute("disabled") || element.getAttribute("aria-hidden") === "true") {
      return false;
    }
    return element.tabIndex >= 0 && element.offsetParent !== null;
  });
}

function formatTimeLabel(value: string, language: string): string {
  if (!value) {
    return "--:--";
  }

  const [hour, minute] = value.split(":");
  return `${hour?.padStart(2, "0") || "--"}:${minute?.padStart(2, "0") || "--"}`;
}

function formatDateTime(now: Date, language: string): { date: string; time: string } {
  return {
    date: new Intl.DateTimeFormat(language, {
      weekday: "short",
      month: "short",
      day: "numeric"
    }).format(now),
    time: new Intl.DateTimeFormat(language, {
      hour: "2-digit",
      minute: "2-digit"
    }).format(now)
  };
}

function formatCountdown(value: number | undefined, language: string): string {
  const totalSeconds = Math.max(0, Math.floor(value || 0));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return language === "de"
      ? `${hours} Std ${minutes} Min`
      : `${hours}h ${minutes}m`;
  }

  if (minutes > 0) {
    return language === "de"
      ? `${minutes} Min ${seconds.toString().padStart(2, "0")} Sek`
      : `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
  }

  return language === "de" ? `${seconds} Sek` : `${seconds}s`;
}

function icon(name: string, className = "icon"): JSX.Element {
  return (
    <svg class={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

interface StatusPillProps {
  tone: "success" | "warning" | "muted" | "danger";
  label: string;
}

function StatusPill({ tone, label }: StatusPillProps) {
  return <span class={`status-pill status-pill-${tone}`}>{label}</span>;
}

interface ToastStackProps {
  items: ToastItem[];
  onDismiss: (id: number) => void;
  dismissLabel: string;
}

function ToastStack({ items, onDismiss, dismissLabel }: ToastStackProps) {
  return (
    <div class="toast-stack" aria-live="polite" aria-atomic="true">
      {items.map((item) => (
        <div class={`toast toast-${item.type}`} key={item.id}>
          <span>{item.message}</span>
          <button
            type="button"
            class="icon-button"
            aria-label={dismissLabel}
            onClick={() => onDismiss(item.id)}
          >
            {icon("close")}
          </button>
        </div>
      ))}
    </div>
  );
}

interface SheetProps {
  id: string;
  title: string;
  subtitle?: string;
  open: boolean;
  onClose: () => void;
  closeLabel: string;
  variant?: "default" | "settings";
  children: JSX.Element;
}

function Sheet({ id, title, subtitle, open, onClose, closeLabel, variant = "default", children }: SheetProps) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }

    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    const initialTarget =
      dialog.querySelector<HTMLElement>("[data-sheet-initial-focus]") || getFocusableElements(dialog)[0];
    if (initialTarget) {
      initialTarget.focus();
    } else {
      dialog.focus();
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusables = getFocusableElements(dialog);
      if (focusables.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      const currentIndex = active ? focusables.indexOf(active) : -1;

      if (event.shiftKey) {
        event.preventDefault();
        const previousIndex = currentIndex <= 0 ? focusables.length - 1 : currentIndex - 1;
        focusables[previousIndex]?.focus();
        return;
      }

      event.preventDefault();
      const nextIndex = currentIndex === -1 || currentIndex >= focusables.length - 1 ? 0 : currentIndex + 1;
      focusables[nextIndex]?.focus();
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      const opener = openerRef.current;
      if (opener && document.contains(opener)) {
        opener.focus();
      }
    };
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div class="sheet-backdrop" onClick={onClose}>
      <section
        id={id}
        ref={dialogRef}
        class={`sheet sheet-${variant}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <header class="sheet-header">
          <div>
            <p class="sheet-eyebrow">SpotiPi</p>
            <h2 id={`${id}-title`}>{title}</h2>
            {subtitle ? <p class="sheet-subtitle">{subtitle}</p> : null}
          </div>
          <button type="button" class="icon-button" aria-label={closeLabel} onClick={onClose}>
            {icon("close")}
          </button>
        </header>
        <div class="sheet-body">{children}</div>
      </section>
    </div>
  );
}

interface ToggleFieldProps {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function ToggleField({ label, description, checked, onChange }: ToggleFieldProps) {
  return (
    <label class="toggle-field">
      <span class="toggle-copy">
        <span class="toggle-title">{label}</span>
        {description ? <span class="toggle-description">{description}</span> : null}
      </span>
      <span class="toggle-control">
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange((event.currentTarget as HTMLInputElement).checked)}
        />
        <span class="toggle-track" aria-hidden="true" />
      </span>
    </label>
  );
}

interface DevicePickerProps {
  title: string;
  devices: SpotifyDevice[];
  selectedKey: string;
  status: string;
  offline: boolean;
  onSelect: (device: SpotifyDevice) => void;
  onRefresh: () => void;
  t: TranslateFn;
  language: string;
}

function DevicePicker({
  title,
  devices,
  selectedKey,
  status,
  offline,
  onSelect,
  onRefresh,
  t,
  language
}: DevicePickerProps) {
  const emptyMessage = offline
    ? t("status_offline", localized(language, "Offline mode", "Offline-Modus"))
    : status === "auth_required"
      ? t("status_auth_required", localized(language, "Spotify sign-in required", "Spotify-Anmeldung erforderlich"))
      : status === "pending"
        ? t("loading_devices", localized(language, "Loading speakers...", "Lautsprecher werden geladen..."))
        : status === "error"
          ? t("speaker_error", localized(language, "Error loading speakers", "Fehler beim Laden der Lautsprecher"))
          : t("no_devices_found", localized(language, "No speakers found", "Keine Lautsprecher gefunden"));

  return (
    <div class="field-group">
      <div class="field-label-row">
        <label class="field-label">{title}</label>
        <button type="button" class="ghost-button" onClick={onRefresh}>
          {icon("refresh")}
          <span>{localized(language, "Refresh", "Aktualisieren")}</span>
        </button>
      </div>
      {devices.length === 0 ? (
        <div class="state-card state-card-muted">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div class="device-grid" role="list">
          {devices.map((device) => {
            const deviceKey = device.id || device.name;
            const selected = deviceKey === selectedKey;
            return (
              <button
                key={deviceKey}
                type="button"
                class={`device-card ${selected ? "is-selected" : ""}`}
                aria-pressed={selected}
                onClick={() => onSelect(device)}
              >
                <div class="device-card-copy">
                  <span class="device-card-title">{device.name}</span>
                  <span class="device-card-meta">
                    {device.type || localized(language, "Spotify device", "Spotify-Gerät")}
                    {device.is_active ? ` · ${localized(language, "active", "aktiv")}` : ""}
                  </span>
                </div>
                {selected ? icon("check", "icon icon-check") : icon("device", "icon icon-muted")}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface LibraryPickerProps {
  enabled: boolean;
  offline: boolean;
  collections: Record<LibrarySection, CollectionState>;
  artistDrilldown: ArtistDrilldown;
  selectedUri: string;
  currentSection: LibrarySection;
  onSectionChange: (section: LibrarySection) => void;
  onEnsureSection: (section: LibrarySection) => void;
  onRetrySection: (section: LibrarySection) => void;
  onSelect: (item: LibraryItem) => void;
  onQuickPlay?: (item: LibraryItem) => void;
  quickPlayBusy?: boolean;
  quickPlayDisabled?: boolean;
  onOpenArtist: (artist: LibraryItem) => void;
  onSearchCatalog: (query: string) => void;
  onCloseArtist: () => void;
  t: TranslateFn;
  language: string;
}

function LibraryPicker({
  enabled,
  offline,
  collections,
  artistDrilldown,
  selectedUri,
  currentSection,
  onSectionChange,
  onEnsureSection,
  onRetrySection,
  onSelect,
  onQuickPlay,
  quickPlayBusy = false,
  quickPlayDisabled = false,
  onOpenArtist,
  onSearchCatalog,
  onCloseArtist,
  t,
  language
}: LibraryPickerProps) {
  const [query, setQuery] = useState("");
  const searchDebounceRef = useRef<number | null>(null);

  useEffect(() => {
    setQuery("");
  }, [currentSection, artistDrilldown.artist?.uri]);

  useEffect(() => {
    if (currentSection !== "search") {
      if (searchDebounceRef.current) {
        window.clearTimeout(searchDebounceRef.current);
      }
      return;
    }

    if (searchDebounceRef.current) {
      window.clearTimeout(searchDebounceRef.current);
    }
    searchDebounceRef.current = window.setTimeout(() => {
      onSearchCatalog(query);
    }, 300);

    return () => {
      if (searchDebounceRef.current) {
        window.clearTimeout(searchDebounceRef.current);
      }
    };
  }, [currentSection, onSearchCatalog, query]);

  if (!enabled) {
    return (
      <div class="state-card state-card-muted">
        <p>
          {localized(
            language,
            "Music browsing is disabled in Settings.",
            "Musik-Browsing ist in den Einstellungen deaktiviert."
          )}
        </p>
      </div>
    );
  }

  const currentCollection =
    currentSection === "artists" && artistDrilldown.artist
      ? {
          status: artistDrilldown.status,
          items: artistDrilldown.items,
          errorMessage: artistDrilldown.errorMessage
        }
      : collections[currentSection];

  const filteredItems =
    currentSection === "search"
      ? currentCollection.items
      : currentCollection.items.filter((item) => {
          const haystack = `${item.name} ${item.artist || ""}`.toLowerCase();
          return haystack.includes(query.toLowerCase());
        });

  const currentSectionIndex = Math.max(0, LIBRARY_SECTIONS.indexOf(currentSection));
  const resultRegionId = `library-results-${currentSection}`;
  const showOfflineState = offline || currentCollection.status === "offline";
  const searchGroupOrder: Array<{ type: string; label: string }> = [
    { type: "track", label: localized(language, "Tracks", "Titel") },
    { type: "album", label: localized(language, "Albums", "Alben") },
    { type: "artist", label: localized(language, "Artists", "Künstler") },
    { type: "playlist", label: localized(language, "Playlists", "Playlists") }
  ];

  const groupedSearchItems = searchGroupOrder
    .map((group) => ({
      ...group,
      items: filteredItems.filter((item) => item.type === group.type)
    }))
    .filter((group) => group.items.length > 0);

  function activateSection(section: LibrarySection) {
    onSectionChange(section);
    if (section !== "search") {
      onEnsureSection(section);
    }
  }

  function handleTabKeyNavigation(
    event: JSX.TargetedKeyboardEvent<HTMLButtonElement>,
    index: number
  ) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();

    let nextIndex = index;
    if (event.key === "ArrowRight") {
      nextIndex = (index + 1) % LIBRARY_SECTIONS.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (index - 1 + LIBRARY_SECTIONS.length) % LIBRARY_SECTIONS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = LIBRARY_SECTIONS.length - 1;
    }

    const nextSection = LIBRARY_SECTIONS[nextIndex];
    activateSection(nextSection);
    document.getElementById(`library-tab-${nextSection}`)?.focus();
  }

  function renderLibraryRow(item: LibraryItem, keySuffix = "") {
    const selected = selectedUri === item.uri;
    const isArtistRoot = currentSection === "artists" && !artistDrilldown.artist;
    const showActionButton = Boolean(onQuickPlay);
    const showInlineArtistArrow = isArtistRoot && !showActionButton;
    const safeImageUrl = normalizeImageUrl(item.image_url);
    const meta = item.artist
      ? item.artist
      : item.track_count
        ? localized(language, `${item.track_count} tracks`, `${item.track_count} Titel`)
        : item.type || "";

    return (
      <div key={`${item.uri}-${item.type || "item"}-${keySuffix}`} class={`library-row ${selected ? "is-selected" : ""}`}>
        <button
          type="button"
          class="library-row-main"
          aria-pressed={selected}
          onClick={() => (isArtistRoot ? onOpenArtist(item) : onSelect(item))}
        >
          {safeImageUrl ? (
            <img
              class="library-artwork"
              src={safeImageUrl}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          ) : (
            <span class="artwork-fallback artwork-fallback-compact" aria-hidden="true">
              {icon("library")}
            </span>
          )}
          <span class="library-row-copy">
            <span class="library-row-title">{item.name}</span>
            <span class="library-row-meta">{meta}</span>
          </span>
          {selected && !isArtistRoot ? icon("check", "icon icon-check") : null}
          {showInlineArtistArrow ? icon("arrow", "icon icon-muted") : null}
        </button>
        {showActionButton ? (
          <button
            type="button"
            class="library-row-action"
            disabled={isArtistRoot ? false : quickPlayDisabled || quickPlayBusy}
            data-testid="library-quick-play"
            aria-label={
              isArtistRoot
                ? localized(language, "Open artist", "Künstler öffnen")
                : localized(language, "Play now", "Jetzt abspielen")
            }
            onClick={() => {
              if (isArtistRoot) {
                onOpenArtist(item);
                return;
              }
              onQuickPlay?.(item);
            }}
          >
            {isArtistRoot ? icon("arrow") : icon("play")}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div class="field-group">
      <label class="field-label">
        {localized(language, "Choose music", "Musik auswählen")}
      </label>
      <div class="library-picker" data-testid="library-picker">
        <div class="section-tabs" role="tablist" aria-label={localized(language, "Music sections", "Musikbereiche")}>
          {LIBRARY_SECTIONS.map((section) => {
            const active = section === currentSection;
            return (
              <button
                key={section}
                id={`library-tab-${section}`}
                type="button"
                role="tab"
                class={`section-tab ${active ? "is-active" : ""}`}
                aria-selected={active}
                aria-controls={resultRegionId}
                tabIndex={active ? 0 : -1}
                onClick={() => activateSection(section)}
                onKeyDown={(event) => handleTabKeyNavigation(event, LIBRARY_SECTIONS.indexOf(section))}
              >
                {section === "playlists"
                  ? t("playlists", localized(language, "Playlists", "Playlists"))
                  : section === "albums"
                    ? t("albums", localized(language, "Albums", "Alben"))
                    : section === "tracks"
                      ? t("songs", localized(language, "Songs", "Songs"))
                      : section === "artists"
                        ? t("artists", localized(language, "Artists", "Künstler"))
                        : section === "recent"
                          ? localized(language, "Recent", "Zuletzt")
                          : section === "top"
                            ? localized(language, "Top", "Top")
                            : localized(language, "Search", "Suche")}
              </button>
            );
          })}
        </div>

        {currentSection === "artists" && artistDrilldown.artist ? (
          <button type="button" class="ghost-button" onClick={onCloseArtist}>
            {icon("arrow")}
            <span>{localized(language, "Back to artists", "Zurück zu Künstlern")}</span>
          </button>
        ) : null}

        <input
          type="search"
          class="field-input"
          aria-label={localized(language, "Search music", "Musik suchen")}
          placeholder={t(
            currentSection === "search" ? "search_music" : "playlist_search_placeholder",
            currentSection === "search"
              ? localized(language, "Search Spotify catalog...", "Spotify-Katalog durchsuchen...")
              : localized(language, "Search music...", "Musik suchen...")
          )}
          value={query}
          onInput={(event) => setQuery((event.currentTarget as HTMLInputElement).value)}
        />

        {currentSection === "search" && query.trim().length > 0 && query.trim().length < 3 ? (
          <div class="state-card state-card-muted">
            <p>{localized(language, "Type at least 3 characters.", "Mindestens 3 Zeichen eingeben.")}</p>
          </div>
        ) : null}

        {showOfflineState ? (
          <div class="state-card state-card-muted">
            <p>{localized(language, "Offline mode. Music list is unavailable.", "Offline-Modus. Musikliste ist nicht verfügbar.")}</p>
            <button
              type="button"
              class="ghost-button"
              onClick={() => {
                if (currentSection === "search") {
                  onSearchCatalog(query);
                  return;
                }
                onRetrySection(currentSection);
              }}
            >
              {icon("refresh")}
              <span>{localized(language, "Retry", "Erneut versuchen")}</span>
            </button>
          </div>
        ) : null}

        {!showOfflineState && (currentCollection.status === "loading" || currentCollection.status === "pending") ? (
          <div class="state-card state-card-muted">
            <p>{t("loading_music", localized(language, "Loading music...", "Musik wird geladen..."))}</p>
          </div>
        ) : null}

        {!showOfflineState && currentCollection.status === "auth_required" ? (
          <div class="state-card state-card-danger">
            <p>{t("status_auth_required", localized(language, "Spotify sign-in required", "Spotify-Anmeldung erforderlich"))}</p>
          </div>
        ) : null}

        {!showOfflineState && currentCollection.status === "error" ? (
          <div class="state-card state-card-danger">
            <p>{currentCollection.errorMessage || t("spotify_unavailable", localized(language, "Spotify unavailable", "Spotify nicht verfügbar"))}</p>
          </div>
        ) : null}

        {!showOfflineState && (currentCollection.status === "ready" || currentCollection.status === "empty") ? (
          filteredItems.length === 0 ? (
            <div class="state-card state-card-muted">
              <p>{t("playlist_no_results", localized(language, "No music found", "Keine Musik gefunden"))}</p>
            </div>
          ) : (
            <div
              id={resultRegionId}
              class="library-list"
              role="tabpanel"
              aria-labelledby={`library-tab-${LIBRARY_SECTIONS[currentSectionIndex]}`}
            >
              {currentSection === "search"
                ? groupedSearchItems.map((group) => (
                    <Fragment key={group.type}>
                      <p class="library-search-heading">{group.label}</p>
                      {group.items.map((item) => renderLibraryRow(item, group.type))}
                    </Fragment>
                  ))
                : filteredItems.map((item) => renderLibraryRow(item))}
            </div>
          )
        ) : null}
      </div>
    </div>
  );
}

interface ActionCardProps {
  title: string;
  summary: string;
  description: string;
  actionLabel: string;
  iconName: string;
  disabled?: boolean;
  onAction: () => void;
  testId: string;
}

function ActionCard({
  title,
  summary,
  description,
  actionLabel,
  iconName,
  disabled,
  onAction,
  testId
}: ActionCardProps) {
  return (
    <article class={`action-card ${disabled ? "is-disabled" : ""}`} data-testid={testId}>
      <div class="action-card-header">
        <span class="action-card-icon">{icon(iconName)}</span>
        <div>
          <h3>{title}</h3>
          <p>{summary}</p>
        </div>
      </div>
      <p class="action-card-description">{description}</p>
      <button type="button" class="primary-button" disabled={disabled} onClick={onAction}>
        {actionLabel}
      </button>
    </article>
  );
}

export function App({ bootstrap }: { bootstrap: AppBootstrap }) {
  const t = useMemo(
    () => createTranslator(bootstrap.language, bootstrap.translations),
    [bootstrap.language, bootstrap.translations]
  );
  const [settings, setSettings] = useState<SettingsData>(bootstrap.settings);
  const [surface, setSurface] = useState<SurfaceName>(
    bootstrap.app.initial_surface === "settings" ? "settings" : "none"
  );
  const [clock, setClock] = useState<Date>(() => new Date(bootstrap.app.now_iso));
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [alarmForm, setAlarmForm] = useState<AlarmFormState>(
    createAlarmFormModel(bootstrap.dashboard, bootstrap.settings)
  );
  const [sleepForm, setSleepForm] = useState<SleepFormState>(
    createSleepFormModel(bootstrap.dashboard, bootstrap.sleep_defaults)
  );
  const [playForm, setPlayForm] = useState<PlayFormState>(() => createPlayFormModel(bootstrap.dashboard));
  const [account, setAccount] = useState<AccountLoadState>({ status: "idle" });
  const [playbackQueue, setPlaybackQueue] = useState<LibraryItem[]>([]);
  const [queueStatus, setQueueStatus] = useState<AsyncStatus>("idle");
  const { toasts, pushToast, dismissToast } = useToasts({
    initialNotifications: bootstrap.notifications
  });
  const { networkStatus, setNetworkStatus } = useNetworkStatus("online");
  const { dashboard, setDashboard, refreshDashboard } = useDashboardPolling({
    initialDashboard: bootstrap.dashboard,
    lowPower: bootstrap.low_power,
    language: bootstrap.language,
    t,
    setNetworkStatus,
    pushToast
  });
  const {
    librarySection,
    setLibrarySection,
    collections,
    artistDrilldown,
    ensureLibrarySection,
    openArtistAlbums,
    searchCatalog,
    resetArtistDrilldown
  } = useLibraryData({
    enabled: settings.feature_flags.music_library,
    surface,
    language: bootstrap.language,
    t
  });
  const { oledTheme, setOledTheme } = useTheme();
  const {
    playerVolume,
    isPlayerReady: playerReady,
    handleVolumeInput,
    handlePlaybackCommand
  } = usePlaybackActions({
    dashboard,
    settings,
    networkStatus,
    language: bootstrap.language,
    t,
    setBusyAction,
    pushToast,
    refreshDashboard
  });
  const { updateSetting, handleClearCache } = useSettingsMutations({
    language: bootstrap.language,
    t,
    setSettings,
    setBusyAction,
    pushToast,
    refreshDashboard
  });

  useEffect(() => {
    const timer = window.setInterval(() => {
      setClock(new Date());
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (surface !== "settings" || account.status !== "idle") {
      return;
    }

    let cancelled = false;

    async function loadProfile() {
      setAccount({ status: "loading" });
      try {
        const result = await getJson<SpotifyProfile>("/api/spotify/profile");
        if (cancelled) {
          return;
        }
        if (result.body?.success && result.body.data) {
          setAccount({ status: "ready", profile: result.body.data });
          return;
        }
        if (result.status === 401 || result.body?.error_code === "auth_required") {
          setAccount({ status: "auth_required" });
          return;
        }
        setAccount({
          status: "error",
          errorMessage:
            result.body?.message ||
            t("account_error", localized(bootstrap.language, "Error loading account", "Fehler beim Laden des Kontos"))
        });
      } catch (error) {
        if (!cancelled) {
          setAccount({
            status: "offline",
            errorMessage:
              error instanceof Error
                ? error.message
                : localized(bootstrap.language, "Network error", "Netzwerkfehler")
          });
        }
      }
    }

    void loadProfile();
    return () => {
      cancelled = true;
    };
  }, [surface, account.status, bootstrap.language, t]);

  useEffect(() => {
    if (dashboard.devices.length === 0) {
      return;
    }

    const deviceStillAvailable = playForm.deviceId
      ? dashboard.devices.some((device) => device.id === playForm.deviceId)
      : false;
    if (deviceStillAvailable) {
      return;
    }

    const rememberedDeviceId = readLastDeviceId();
    const rememberedDevice = rememberedDeviceId
      ? dashboard.devices.find((device) => device.id === rememberedDeviceId)
      : undefined;
    const preferredDevice = rememberedDevice || getPreferredDevice(dashboard.devices);

    if (preferredDevice?.id) {
      setPlayForm((current) => ({
        ...current,
        deviceId: preferredDevice.id || "",
        deviceName: preferredDevice.name || ""
      }));
    }
  }, [dashboard.devices, playForm.deviceId]);

  useEffect(() => {
    let cancelled = false;
    let intervalId = 0;

    async function loadQueue() {
      if (networkStatus === "offline") {
        setQueueStatus("offline");
        setPlaybackQueue([]);
        return;
      }
      if (dashboard.playback_status === "auth_required") {
        setQueueStatus("auth_required");
        setPlaybackQueue([]);
        return;
      }

      setQueueStatus((current) => (current === "ready" ? current : "loading"));
      try {
        const result = await getJson<PlaybackQueuePayload>("/api/playback/queue");
        if (cancelled) {
          return;
        }
        if (result.status === 401 || result.body?.error_code === "auth_required") {
          setQueueStatus("auth_required");
          setPlaybackQueue([]);
          return;
        }
        if (result.body?.error_code === "insufficient_scope") {
          setQueueStatus("error");
          setPlaybackQueue([]);
          return;
        }
        if (result.body?.success && result.body.data) {
          const queueItems = (result.body.data.queue || []).slice(0, 5);
          setPlaybackQueue(queueItems);
          setQueueStatus(queueItems.length ? "ready" : "empty");
          return;
        }
        setQueueStatus("error");
        setPlaybackQueue([]);
      } catch {
        if (!cancelled) {
          setQueueStatus("offline");
          setPlaybackQueue([]);
        }
      }
    }

    void loadQueue();
    intervalId = window.setInterval(() => {
      void loadQueue();
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [dashboard.playback.current_track?.name, dashboard.playback_status, networkStatus]);

  function openSurface(nextSurface: SurfaceName) {
    if (nextSurface === "sleep" && !settings.feature_flags.sleep_timer) {
      return;
    }
    if (nextSurface === "play" && !settings.feature_flags.music_library) {
      return;
    }

    if (nextSurface === "alarm") {
      setAlarmForm(createAlarmFormModel(dashboard, settings));
    } else if (nextSurface === "sleep") {
      setSleepForm(createSleepFormModel(dashboard, bootstrap.sleep_defaults));
    } else if (nextSurface === "play") {
      setPlayForm((current) => ({
        ...createPlayFormModel(dashboard),
        contextUri: current.contextUri
      }));
    }

    setSurface(nextSurface);
  }

  function closeSurface() {
    setSurface("none");
  }

  function handleLibrarySelect(item: LibraryItem) {
    if (surface === "alarm") {
      setAlarmForm((current) => ({ ...current, playlistUri: item.uri }));
    } else if (surface === "sleep") {
      setSleepForm((current) => ({ ...current, playlistUri: item.uri }));
    } else if (surface === "play") {
      setPlayForm((current) => ({ ...current, contextUri: item.uri }));
    }
  }

  async function handleAlarmSave() {
    if (networkStatus === "offline") {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "You are offline. Reconnect before saving the alarm.",
          "Du bist offline. Bitte vor dem Speichern des Weckers wieder verbinden."
        )
      );
      return;
    }

    if (!isValidTimeInput(alarmForm.time)) {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "Enter a valid alarm time (HH:MM).",
          "Bitte eine gültige Weckzeit eingeben (HH:MM)."
        )
      );
      return;
    }

    if (!alarmForm.deviceName.trim()) {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "Choose a speaker for the alarm.",
          "Bitte einen Lautsprecher für den Wecker auswählen."
        )
      );
      return;
    }

    if (alarmForm.enabled && hasPassedToday(alarmForm.time)) {
      pushToast(
        "info",
        localized(
          bootstrap.language,
          "That time has already passed today. The alarm will ring tomorrow.",
          "Diese Uhrzeit ist heute bereits vorbei. Der Wecker klingelt morgen."
        )
      );
    }

    setBusyAction("alarm");

    const payload = new URLSearchParams();
    payload.set("enabled", alarmForm.enabled ? "on" : "off");
    payload.set("time", alarmForm.time);
    payload.set("device_name", alarmForm.deviceName);
    payload.set("playlist_uri", alarmForm.playlistUri);
    payload.set("alarm_volume", String(alarmForm.alarmVolume));
    payload.set("volume", String(playerVolume));
    payload.set("fade_in", alarmForm.fadeIn ? "on" : "off");
    payload.set("shuffle", alarmForm.shuffle ? "on" : "off");

    try {
      const result = await postForm<AlarmSummary>("/save_alarm", payload);
      if (result.body?.success && result.body.data) {
        setDashboard((current) => ({
          ...current,
          alarm: { ...current.alarm, ...result.body!.data! }
        }));
        pushToast(
          "success",
          result.body.message ||
            t("alarm_settings_saved", localized(bootstrap.language, "Alarm saved", "Wecker gespeichert"))
        );
        closeSurface();
        return;
      }

      pushToast(
        "error",
        result.body?.message ||
          t("save_failed", localized(bootstrap.language, "Save failed", "Speichern fehlgeschlagen"))
      );
    } catch (error) {
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(bootstrap.language, "Save failed", "Speichern fehlgeschlagen")
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSleepStart() {
    if (networkStatus === "offline") {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "You are offline. Reconnect before starting sleep timer.",
          "Du bist offline. Bitte vor dem Start des Sleep-Timers wieder verbinden."
        )
      );
      return;
    }

    if (!sleepForm.deviceName.trim()) {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "Choose a speaker before starting the timer.",
          "Bitte zuerst einen Lautsprecher auswählen."
        )
      );
      return;
    }

    if (sleepForm.duration === "custom") {
      const customDuration = Number(sleepForm.customDuration);
      if (!Number.isFinite(customDuration) || customDuration < 1 || customDuration > 480) {
        pushToast(
          "error",
          localized(
            bootstrap.language,
            "Custom duration must be between 1 and 480 minutes.",
            "Die benutzerdefinierte Dauer muss zwischen 1 und 480 Minuten liegen."
          )
        );
        return;
      }
    }

    setBusyAction("sleep");

    const payload = new URLSearchParams();
    payload.set("duration", sleepForm.duration);
    if (sleepForm.duration === "custom") {
      payload.set("custom_duration", sleepForm.customDuration);
    }
    payload.set("device_name", sleepForm.deviceName);
    payload.set("playlist_uri", sleepForm.playlistUri);
    payload.set("sleep_volume", String(sleepForm.volume));
    payload.set("shuffle", sleepForm.shuffle ? "on" : "off");

    try {
      const result = await postForm<Record<string, unknown>>("/sleep", payload);
      if (result.body?.success) {
        pushToast(
          "success",
          result.body.message ||
            t("sleep_start", localized(bootstrap.language, "Sleep started", "Sleep gestartet"))
        );
        await refreshDashboard(true);
        closeSurface();
        return;
      }

      pushToast(
        "error",
        result.body?.message ||
          t("failed_start_sleep", localized(bootstrap.language, "Failed to start sleep", "Sleep konnte nicht gestartet werden"))
      );
    } catch (error) {
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(bootstrap.language, "Sleep failed", "Sleep fehlgeschlagen")
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSleepStop() {
    setBusyAction("sleep-stop");
    try {
      const result = await postForm<Record<string, unknown>>("/stop_sleep", new URLSearchParams());
      if (result.body?.success) {
        pushToast(
          "success",
          result.body.message ||
            t("sleep_stopped", localized(bootstrap.language, "Sleep stopped", "Sleep-Timer gestoppt"))
        );
        await refreshDashboard(true);
        closeSurface();
        return;
      }
      pushToast(
        "error",
        result.body?.message ||
          t("failed_stop_sleep", localized(bootstrap.language, "Failed to stop sleep", "Sleep-Timer konnte nicht gestoppt werden"))
      );
    } catch (error) {
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(bootstrap.language, "Sleep failed", "Sleep fehlgeschlagen")
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handlePlayNow(contextUriOverride?: string) {
    const contextUri = contextUriOverride || playForm.contextUri;
    const deviceId = playForm.deviceId;

    if (networkStatus === "offline") {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "You are offline. Reconnect before starting playback.",
          "Du bist offline. Bitte vor dem Start der Wiedergabe wieder verbinden."
        )
      );
      return;
    }

    if (!contextUri || !deviceId) {
      pushToast(
        "error",
        localized(
          bootstrap.language,
          "Choose both a speaker and music first.",
          "Bitte zuerst Lautsprecher und Musik auswählen."
        )
      );
      return;
    }

    if (contextUriOverride && contextUriOverride !== playForm.contextUri) {
      setPlayForm((current) => ({ ...current, contextUri: contextUriOverride }));
    }

    setBusyAction("play");
    try {
      const result = await postJson<Record<string, unknown>>("/play", {
        context_uri: contextUri,
        device_id: deviceId
      });
      if (result.body?.success) {
        writeLastDeviceId(deviceId);
        pushToast(
          "success",
          result.body.message ||
            t("playback_started", localized(bootstrap.language, "Playback started", "Wiedergabe gestartet"))
        );
        await refreshDashboard(true);
        closeSurface();
        return;
      }

      pushToast(
        "error",
        result.body?.message ||
          t("failed_start_playback", localized(bootstrap.language, "Failed to start playback", "Wiedergabe konnte nicht gestartet werden"))
      );
    } catch (error) {
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(bootstrap.language, "Playback failed", "Wiedergabe fehlgeschlagen")
      );
    } finally {
      setBusyAction(null);
    }
  }

  const isPlaybackInitialHydration =
    dashboard.playback_status === "pending" ||
    (dashboard.hydration.playback.pending && !dashboard.hydration.playback.has_data);

  const statusSnapshot = useMemo(() => {
    if (networkStatus === "offline") {
      return {
        label: t("status_offline", localized(bootstrap.language, "Offline mode", "Offline-Modus")),
        tone: "warning" as const
      };
    }
    if (isPlaybackInitialHydration && !dashboard.playback.current_track) {
      return {
        label: t("status_pending", localized(bootstrap.language, "Waiting for Spotify", "Warte auf Spotify")),
        tone: "muted" as const
      };
    }
    if (dashboard.playback_status === "auth_required") {
      return {
        label: t("status_auth_required", localized(bootstrap.language, "Spotify sign-in required", "Spotify-Anmeldung erforderlich")),
        tone: "danger" as const
      };
    }
    if (dashboard.playback_status === "error") {
      return {
        label: t("spotify_error", localized(bootstrap.language, "Spotify error", "Spotify-Fehler")),
        tone: "danger" as const
      };
    }
    if (dashboard.playback.current_track) {
      return {
        label: dashboard.playback.is_playing
          ? t("currently_playing", localized(bootstrap.language, "Currently playing", "Aktuell läuft"))
          : t("paused", localized(bootstrap.language, "Paused", "Pausiert")),
        tone: "success" as const
      };
    }
    return {
      label: t("no_active_playback", localized(bootstrap.language, "No active playback", "Keine aktive Wiedergabe")),
      tone: "muted" as const
    };
  }, [dashboard, isPlaybackInitialHydration, networkStatus, t, bootstrap.language]);

  const clockLabel = formatDateTime(clock, bootstrap.language);
  const currentTrack = dashboard.playback.current_track;
  const safeCurrentTrackImage = normalizeImageUrl(currentTrack?.album_image);
  const safeAccountAvatar = normalizeImageUrl(account.profile?.avatar_url);
  const dismissToastLabel = localized(bootstrap.language, "Dismiss notification", "Hinweis schließen");
  const closeSheetLabel = localized(bootstrap.language, "Close panel", "Panel schließen");
  const playerTitle = currentTrack?.name
    ? currentTrack.name
    : networkStatus === "offline"
      ? localized(bootstrap.language, "Offline, still usable", "Offline, aber bedienbar")
      : dashboard.playback_status === "auth_required"
        ? localized(bootstrap.language, "Spotify sign-in needed", "Spotify-Anmeldung nötig")
        : dashboard.playback_status === "error"
          ? localized(bootstrap.language, "Spotify is unavailable", "Spotify ist gerade nicht erreichbar")
          : isPlaybackInitialHydration
            ? localized(bootstrap.language, "Spotify is waking up", "Spotify wacht auf")
            : localized(bootstrap.language, "Ready to play", "Bereit zum Abspielen");
  const playerSubtitle = currentTrack?.artist
    ? currentTrack.artist
    : networkStatus === "offline"
      ? localized(
          bootstrap.language,
          "Your last snapshot stays visible while the next connection check runs.",
          "Der letzte Snapshot bleibt sichtbar, während die nächste Verbindungsprüfung läuft."
        )
      : dashboard.playback_status === "auth_required"
        ? localized(
            bootstrap.language,
            "Connect Spotify in Settings, then playback controls become active here.",
            "Verbinde Spotify in den Einstellungen, dann wird die Wiedergabe hier aktiv."
          )
        : dashboard.playback_status === "error"
          ? localized(
              bootstrap.language,
              "Try syncing again or switch devices once Spotify responds.",
              "Synchronisiere erneut oder wechsle das Gerät, sobald Spotify wieder antwortet."
            )
          : isPlaybackInitialHydration
            ? localized(
                bootstrap.language,
                "Playback controls appear here as soon as the next Spotify snapshot lands.",
                "Die Wiedergabe erscheint hier, sobald der nächste Spotify-Snapshot angekommen ist."
              )
            : localized(
                bootstrap.language,
                "Use Alarm, Sleep or Play now to start music from the home surface.",
                "Starte Musik direkt über Alarm, Sleep oder Jetzt abspielen auf der Startseite."
              );
  const playerHasPlaceholderCopy = !currentTrack?.name;
  const primaryFlows: PrimaryFlowSnapshot = toPrimaryFlowSnapshot(dashboard);
  const devicesStatus = dashboard.devices_meta.status || "pending";
  const alarmSummary = primaryFlows.alarmEnabled
    ? `${formatTimeLabel(primaryFlows.alarmTime, bootstrap.language)} · ${primaryFlows.alarmDeviceName || localized(bootstrap.language, "No speaker", "Kein Lautsprecher")}`
    : localized(bootstrap.language, "No alarm scheduled", "Kein Wecker geplant");
  const sleepSummary = primaryFlows.sleepActive
    ? formatCountdown(primaryFlows.sleepRemainingSeconds, bootstrap.language)
    : localized(bootstrap.language, "No sleep timer running", "Kein Sleep-Timer aktiv");
  const playSummary = primaryFlows.availableDevices
    ? localized(
        bootstrap.language,
        `${primaryFlows.availableDevices} speaker${primaryFlows.availableDevices === 1 ? "" : "s"} ready`,
        `${primaryFlows.availableDevices} Lautsprecher bereit`
      )
    : localized(bootstrap.language, "Speaker list will hydrate here", "Lautsprecherliste lädt hier");
  return (
    <Fragment>
      <div class="app-shell">
        <ToastStack
          items={toasts}
          dismissLabel={dismissToastLabel}
          onDismiss={dismissToast}
        />

        <header class="app-header">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">
              {icon("spotify")}
            </span>
            <div>
              <h1>SpotiPi</h1>
            </div>
          </div>

          <div class="header-meta">
            <StatusPill tone={statusSnapshot.tone} label={statusSnapshot.label} />
            <div class="clock-panel">
              <span class="clock-time">{clockLabel.time}</span>
              <span class="clock-separator" aria-hidden="true">·</span>
              <span class="clock-date">{clockLabel.date}</span>
            </div>
            <button
              type="button"
              class="icon-button icon-button-strong"
              aria-label={localized(bootstrap.language, "Open settings", "Einstellungen öffnen")}
              onClick={() => openSurface("settings")}
              data-testid="settings-trigger"
            >
              {icon("settings")}
            </button>
          </div>
        </header>

        {networkStatus === "offline" ? (
          <section class="banner banner-warning">
            <strong>{localized(bootstrap.language, "Offline", "Offline")}</strong>
            <span>
              {localized(
                bootstrap.language,
                "The dashboard stays usable while the next connection check runs.",
                "Das Dashboard bleibt nutzbar, während die nächste Verbindungsprüfung läuft."
              )}
            </span>
          </section>
        ) : null}

        {dashboard.sleep.active ? (
          <section class="banner banner-success" data-testid="sleep-active-banner">
            <strong>{localized(bootstrap.language, "Sleep timer running", "Sleep-Timer läuft")}</strong>
            <span>{formatCountdown(dashboard.sleep.remaining_seconds, bootstrap.language)}</span>
            <div class="banner-actions">
              <button
                type="button"
                class="ghost-button"
                onClick={() => openSurface("sleep")}
              >
                {localized(bootstrap.language, "Manage", "Verwalten")}
              </button>
              <button
                type="button"
                class="ghost-button"
                disabled={busyAction === "sleep-stop"}
                onClick={() => void handleSleepStop()}
              >
                {busyAction === "sleep-stop"
                  ? localized(bootstrap.language, "Stopping...", "Stoppt...")
                  : localized(bootstrap.language, "Stop", "Stoppen")}
              </button>
            </div>
          </section>
        ) : null}

        <main class="dashboard-grid">
          <section class="player-card" data-testid="player-card">
            <div class="player-artwork">
              {safeCurrentTrackImage ? (
                <img src={safeCurrentTrackImage} alt="" loading="lazy" referrerPolicy="no-referrer" />
              ) : (
                <span class="artwork-fallback">{icon("library", "icon icon-xl")}</span>
              )}
            </div>

            <div class="player-copy">
              <div class="player-heading">
                <StatusPill tone={statusSnapshot.tone} label={statusSnapshot.label} />
              </div>

              <h2 class={playerHasPlaceholderCopy ? "player-title-placeholder" : undefined}>{playerTitle}</h2>
              <p class={playerHasPlaceholderCopy ? "player-subtitle-placeholder" : undefined}>{playerSubtitle}</p>

              <div class="player-controls" role="group" aria-label={t("playback_controls", localized(bootstrap.language, "Playback controls", "Wiedergabe-Steuerung"))}>
                <button
                  type="button"
                  class="control-button"
                  disabled={!playerReady || busyAction === "previous"}
                  onClick={() => void handlePlaybackCommand("/api/playback/previous", "previous")}
                  aria-label={t("previous_track", localized(bootstrap.language, "Previous track", "Vorheriger Titel"))}
                >
                  {icon("previous")}
                </button>
                <button
                  type="button"
                  class="control-button control-button-primary"
                  disabled={!playerReady || busyAction === "toggle"}
                  onClick={() => void handlePlaybackCommand("/toggle_play_pause", "toggle")}
                  aria-label={t("play_pause", localized(bootstrap.language, "Play or pause", "Play/Pause"))}
                >
                  {icon(dashboard.playback.is_playing ? "pause" : "play")}
                </button>
                <button
                  type="button"
                  class="control-button"
                  disabled={!playerReady || busyAction === "next"}
                  onClick={() => void handlePlaybackCommand("/api/playback/next", "next")}
                  aria-label={t("next_track", localized(bootstrap.language, "Next track", "Nächster Titel"))}
                >
                  {icon("next")}
                </button>
              </div>

              <div class="player-queue" data-testid="player-queue">
                <div class="field-label-row">
                  <label class="field-label">{localized(bootstrap.language, "Up next", "Als Nächstes")}</label>
                </div>
                {queueStatus === "loading" ? (
                  <p class="player-queue-placeholder">{localized(bootstrap.language, "Loading queue...", "Lade Warteschlange...")}</p>
                ) : null}
                {queueStatus === "auth_required" ? (
                  <p class="player-queue-placeholder">{localized(bootstrap.language, "Spotify sign-in required", "Spotify-Anmeldung erforderlich")}</p>
                ) : null}
                {queueStatus === "error" ? (
                  <p class="player-queue-placeholder">{localized(bootstrap.language, "Queue unavailable", "Warteschlange nicht verfügbar")}</p>
                ) : null}
                {queueStatus === "empty" ? (
                  <p class="player-queue-placeholder">{localized(bootstrap.language, "Queue is empty", "Warteschlange ist leer")}</p>
                ) : null}
                {queueStatus === "ready" ? (
                  <ul class="player-queue-list">
                    {playbackQueue.map((item) => (
                      <li key={`${item.uri}-${item.type || "item"}`} class="player-queue-item">
                        <span class="player-queue-title">{item.name}</span>
                        <span class="player-queue-meta">{item.artist || item.type || ""}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>

              <div class="range-field">
                <div class="field-label-row">
                  <label class="field-label">{t("volume_label", localized(bootstrap.language, "Volume", "Lautstärke"))}</label>
                  <strong>{playerVolume}%</strong>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={playerVolume}
                  aria-label={t("volume_label", localized(bootstrap.language, "Volume", "Lautstärke"))}
                  onInput={(event) => handleVolumeInput(Number((event.currentTarget as HTMLInputElement).value))}
                />
              </div>
            </div>
          </section>

          <section class="snapshot-card">
            <div class="snapshot-header">
              <h2>{localized(bootstrap.language, "Today at a glance", "Heute auf einen Blick")}</h2>
            </div>

            <div class="snapshot-grid">
              <div class="snapshot-item">
                <span>{icon("alarm")}</span>
                <div>
                  <small>{localized(bootstrap.language, "Alarm", "Wecker")}</small>
                  <strong>{alarmSummary}</strong>
                </div>
              </div>
              <div class="snapshot-item">
                <span>{icon("sleep")}</span>
                <div>
                  <small>{localized(bootstrap.language, "Sleep", "Sleep")}</small>
                  <strong>{sleepSummary}</strong>
                </div>
              </div>
              <div class="snapshot-item">
                <span>{icon("device")}</span>
                <div>
                  <small>{localized(bootstrap.language, "Devices", "Geräte")}</small>
                  <strong>{playSummary}</strong>
                </div>
              </div>
            </div>

          </section>
        </main>

        <section class="actions-section">
          <div class="action-grid">
            <ActionCard
              title={localized(bootstrap.language, "Set alarm", "Wecker setzen")}
              summary={alarmSummary}
              description={localized(
                bootstrap.language,
                "Tune time, speaker, volume and wake-up music in one focused flow.",
                "Zeit, Lautsprecher, Lautstärke und Weckmusik in einem fokussierten Flow einstellen."
              )}
              actionLabel={localized(bootstrap.language, "Edit alarm", "Wecker bearbeiten")}
              iconName="alarm"
              onAction={() => openSurface("alarm")}
              testId="alarm-card"
            />
            <ActionCard
              title={localized(bootstrap.language, "Start sleep", "Sleep starten")}
              summary={sleepSummary}
              description={localized(
                bootstrap.language,
                "Kick off a timer without leaving the home surface, then stop it from the same sheet.",
                "Einen Timer starten, ohne die Startseite zu verlassen, und im selben Sheet wieder stoppen."
              )}
              actionLabel={
                dashboard.sleep.active
                  ? localized(bootstrap.language, "Manage sleep", "Sleep verwalten")
                  : localized(bootstrap.language, "Open sleep flow", "Sleep-Flow öffnen")
              }
              iconName="sleep"
              disabled={!settings.feature_flags.sleep_timer}
              onAction={() => openSurface("sleep")}
              testId="sleep-card"
            />
            <ActionCard
              title={localized(bootstrap.language, "Play now", "Jetzt abspielen")}
              summary={playSummary}
              description={localized(
                bootstrap.language,
                "Choose music and a device inside a mobile-friendly sheet, then start playback instantly.",
                "Musik und Gerät in einem mobilen Sheet wählen und die Wiedergabe sofort starten."
              )}
              actionLabel={localized(bootstrap.language, "Choose music", "Musik wählen")}
              iconName="play"
              disabled={!settings.feature_flags.music_library}
              onAction={() => openSurface("play")}
              testId="play-card"
            />
          </div>
        </section>

        <footer class="app-footer">
          <span>{bootstrap.app.info}</span>
        </footer>
      </div>

      <Sheet
        id="alarm-sheet"
        open={surface === "alarm"}
        onClose={closeSurface}
        closeLabel={closeSheetLabel}
        title={localized(bootstrap.language, "Alarm flow", "Wecker-Flow")}
        subtitle={localized(
          bootstrap.language,
          "Everything required to create a reliable morning flow without tab-hopping.",
          "Alles, was für einen verlässlichen Morgen-Flow nötig ist, ohne Tab-Hopping."
        )}
      >
        <div class="sheet-stack" data-testid="alarm-sheet">
          <div class="field-group">
            <label class="field-label" for="alarm-time-input">
              {t("alarm_time_label", localized(bootstrap.language, "Alarm time", "Weckzeit"))}
            </label>
            <input
              id="alarm-time-input"
              data-sheet-initial-focus="true"
              class="field-input field-input-large"
              type="time"
              value={alarmForm.time}
              onInput={(event) =>
                setAlarmForm((current) => ({
                  ...current,
                  time: (event.currentTarget as HTMLInputElement).value
                }))
              }
            />
          </div>

          <DevicePicker
            title={t("device_label", localized(bootstrap.language, "Speaker", "Lautsprecher"))}
            devices={dashboard.devices}
            selectedKey={alarmForm.deviceName}
            status={devicesStatus}
            offline={networkStatus === "offline"}
            onSelect={(device) =>
              setAlarmForm((current) => ({ ...current, deviceName: device.name }))
            }
            onRefresh={() => void refreshDashboard(true)}
            t={t}
            language={bootstrap.language}
          />

          <div class="range-field">
            <div class="field-label-row">
              <label class="field-label">
                {t("alarm_volume", localized(bootstrap.language, "Alarm volume", "Wecker-Lautstärke"))}
              </label>
              <strong>{alarmForm.alarmVolume}%</strong>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={alarmForm.alarmVolume}
              aria-label={t("alarm_volume", localized(bootstrap.language, "Alarm volume", "Wecker-Lautstärke"))}
              onInput={(event) =>
                setAlarmForm((current) => ({
                  ...current,
                  alarmVolume: Number((event.currentTarget as HTMLInputElement).value)
                }))
              }
            />
          </div>

          <LibraryPicker
            enabled={settings.feature_flags.music_library}
            offline={networkStatus === "offline"}
            collections={collections}
            artistDrilldown={artistDrilldown}
            selectedUri={alarmForm.playlistUri}
            currentSection={librarySection}
            onSectionChange={(section) => {
              setLibrarySection(section);
              resetArtistDrilldown();
            }}
            onEnsureSection={(section) => void ensureLibrarySection(section)}
            onRetrySection={(section) => void ensureLibrarySection(section)}
            onSelect={handleLibrarySelect}
            onOpenArtist={(artist) => void openArtistAlbums(artist)}
            onSearchCatalog={(value) => void searchCatalog(value)}
            onCloseArtist={resetArtistDrilldown}
            t={t}
            language={bootstrap.language}
          />

          <ToggleField
            label={t("enable_alarm", localized(bootstrap.language, "Enable alarm", "Wecker aktivieren"))}
            checked={alarmForm.enabled}
            onChange={(checked) => setAlarmForm((current) => ({ ...current, enabled: checked }))}
          />
          <ToggleField
            label={t("fade_in", localized(bootstrap.language, "Fade in", "Fade-In"))}
            checked={alarmForm.fadeIn}
            onChange={(checked) => setAlarmForm((current) => ({ ...current, fadeIn: checked }))}
          />
          <ToggleField
            label={t("shuffle", localized(bootstrap.language, "Shuffle", "Shuffle"))}
            checked={alarmForm.shuffle}
            onChange={(checked) => setAlarmForm((current) => ({ ...current, shuffle: checked }))}
          />

          <div class={`state-card ${alarmForm.enabled ? "state-card-active" : "state-card-muted"}`}>
            <p>
              {alarmForm.enabled
                ? localized(
                    bootstrap.language,
                    `Alarm active for ${formatTimeLabel(alarmForm.time, bootstrap.language)}.`,
                    `Wecker aktiv für ${formatTimeLabel(alarmForm.time, bootstrap.language)}.`
                  )
                : localized(
                    bootstrap.language,
                    "Alarm is currently disabled.",
                    "Der Wecker ist aktuell deaktiviert."
                  )}
            </p>
          </div>

          <div class="sheet-actions">
            <button type="button" class="secondary-button" onClick={closeSurface}>
              {localized(bootstrap.language, "Cancel", "Abbrechen")}
            </button>
            <button
              type="button"
              class="primary-button"
              disabled={busyAction === "alarm"}
              onClick={() => void handleAlarmSave()}
            >
              {busyAction === "alarm"
                ? localized(bootstrap.language, "Saving...", "Speichert...")
                : localized(bootstrap.language, "Save alarm", "Wecker speichern")}
            </button>
          </div>
        </div>
      </Sheet>

      <Sheet
        id="sleep-sheet"
        open={surface === "sleep"}
        onClose={closeSurface}
        closeLabel={closeSheetLabel}
        title={localized(bootstrap.language, "Sleep flow", "Sleep-Flow")}
        subtitle={localized(
          bootstrap.language,
          "Fast setup for tonight, plus an obvious stop path when the timer is already running.",
          "Schnelles Setup für heute Abend und ein klarer Stop-Pfad, wenn der Timer bereits läuft."
        )}
      >
        <div class="sheet-stack">
          {dashboard.sleep.active ? (
            <div class="state-card state-card-active">
              <h3>{localized(bootstrap.language, "Sleep timer is running", "Sleep-Timer läuft")}</h3>
              <p>{formatCountdown(dashboard.sleep.remaining_seconds, bootstrap.language)}</p>
              <div class="progress-bar" aria-hidden="true">
                <span style={`width:${clamp(Number(dashboard.sleep.progress_percent || 0), 0, 100)}%`} />
              </div>
              <button
                type="button"
                data-sheet-initial-focus="true"
                class="primary-button button-danger"
                disabled={busyAction === "sleep-stop"}
                onClick={() => void handleSleepStop()}
              >
                {busyAction === "sleep-stop"
                  ? localized(bootstrap.language, "Stopping...", "Stoppt...")
                  : t("sleep_stop", localized(bootstrap.language, "Stop sleep", "Sleep stoppen"))}
              </button>
            </div>
          ) : (
            <Fragment>
              <div class="field-group">
                <label class="field-label">
                  {t("duration_label", localized(bootstrap.language, "Duration", "Dauer"))}
                </label>
                <div class="chip-row">
                  {DURATION_OPTIONS.map((option) => {
                    const active = sleepForm.duration === String(option);
                    return (
                      <button
                        key={option}
                        type="button"
                        data-sheet-initial-focus={option === DURATION_OPTIONS[0] ? "true" : undefined}
                        class={`choice-chip ${active ? "is-active" : ""}`}
                        onClick={() =>
                          setSleepForm((current) => ({
                            ...current,
                            duration: String(option),
                            customDuration: String(option)
                          }))
                        }
                      >
                        {option}m
                      </button>
                    );
                  })}
                  <button
                    type="button"
                    class={`choice-chip ${sleepForm.duration === "custom" ? "is-active" : ""}`}
                    onClick={() =>
                      setSleepForm((current) => ({
                        ...current,
                        duration: "custom"
                      }))
                    }
                  >
                    {localized(bootstrap.language, "Custom", "Custom")}
                  </button>
                </div>
                {sleepForm.duration === "custom" ? (
                  <input
                    class="field-input"
                    type="number"
                    min="1"
                    max="480"
                    aria-label={localized(bootstrap.language, "Custom duration in minutes", "Benutzerdefinierte Dauer in Minuten")}
                    value={sleepForm.customDuration}
                    onInput={(event) =>
                      setSleepForm((current) => ({
                        ...current,
                        customDuration: (event.currentTarget as HTMLInputElement).value
                      }))
                    }
                  />
                ) : null}
              </div>

              <DevicePicker
                title={t("device_label", localized(bootstrap.language, "Speaker", "Lautsprecher"))}
                devices={dashboard.devices}
                selectedKey={sleepForm.deviceName}
                status={devicesStatus}
                offline={networkStatus === "offline"}
                onSelect={(device) =>
                  setSleepForm((current) => ({ ...current, deviceName: device.name }))
                }
                onRefresh={() => void refreshDashboard(true)}
                t={t}
                language={bootstrap.language}
              />

              <div class="range-field">
                <div class="field-label-row">
                  <label class="field-label">
                    {localized(bootstrap.language, "Sleep volume", "Sleep-Lautstärke")}
                  </label>
                  <strong>{sleepForm.volume}%</strong>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={sleepForm.volume}
                  aria-label={localized(bootstrap.language, "Sleep volume", "Sleep-Lautstärke")}
                  onInput={(event) =>
                    setSleepForm((current) => ({
                      ...current,
                      volume: Number((event.currentTarget as HTMLInputElement).value)
                    }))
                  }
                />
              </div>

              <LibraryPicker
                enabled={settings.feature_flags.music_library}
                offline={networkStatus === "offline"}
                collections={collections}
                artistDrilldown={artistDrilldown}
                selectedUri={sleepForm.playlistUri}
                currentSection={librarySection}
                onSectionChange={(section) => {
                  setLibrarySection(section);
                  resetArtistDrilldown();
                }}
                onEnsureSection={(section) => void ensureLibrarySection(section)}
                onRetrySection={(section) => void ensureLibrarySection(section)}
                onSelect={handleLibrarySelect}
                onOpenArtist={(artist) => void openArtistAlbums(artist)}
                onSearchCatalog={(value) => void searchCatalog(value)}
                onCloseArtist={resetArtistDrilldown}
                t={t}
                language={bootstrap.language}
              />

              <ToggleField
                label={t("shuffle", localized(bootstrap.language, "Shuffle", "Shuffle"))}
                checked={sleepForm.shuffle}
                onChange={(checked) => setSleepForm((current) => ({ ...current, shuffle: checked }))}
              />

              <div class="sheet-actions">
                <button type="button" class="secondary-button" onClick={closeSurface}>
                  {localized(bootstrap.language, "Cancel", "Abbrechen")}
                </button>
                <button
                  type="button"
                  class="primary-button"
                  disabled={busyAction === "sleep"}
                  onClick={() => void handleSleepStart()}
                >
                  {busyAction === "sleep"
                    ? localized(bootstrap.language, "Starting...", "Startet...")
                    : t("sleep_start", localized(bootstrap.language, "Start sleep", "Sleep starten"))}
                </button>
              </div>
            </Fragment>
          )}
        </div>
      </Sheet>

      <Sheet
        id="play-sheet"
        open={surface === "play"}
        onClose={closeSurface}
        closeLabel={closeSheetLabel}
        title={localized(bootstrap.language, "Play now", "Jetzt abspielen")}
        subtitle={localized(
          bootstrap.language,
          "A single sheet for speaker selection and instant playback.",
          "Ein einziges Sheet für Lautsprecher-Auswahl und sofortige Wiedergabe."
        )}
      >
        <div class="sheet-stack">
          <DevicePicker
            title={t("device_label", localized(bootstrap.language, "Speaker", "Lautsprecher"))}
            devices={dashboard.devices}
            selectedKey={playForm.deviceId}
            status={devicesStatus}
            offline={networkStatus === "offline"}
            onSelect={(device) =>
              setPlayForm((current) => {
                const nextDeviceId = device.id || "";
                writeLastDeviceId(nextDeviceId);
                return {
                  ...current,
                  deviceId: nextDeviceId,
                  deviceName: device.name
                };
              })
            }
            onRefresh={() => void refreshDashboard(true)}
            t={t}
            language={bootstrap.language}
          />

          <LibraryPicker
            enabled={settings.feature_flags.music_library}
            offline={networkStatus === "offline"}
            collections={collections}
            artistDrilldown={artistDrilldown}
            selectedUri={playForm.contextUri}
            currentSection={librarySection}
            onSectionChange={(section) => {
              setLibrarySection(section);
              resetArtistDrilldown();
            }}
            onEnsureSection={(section) => void ensureLibrarySection(section)}
            onRetrySection={(section) => void ensureLibrarySection(section)}
            onSelect={handleLibrarySelect}
            onQuickPlay={(item) => void handlePlayNow(item.uri)}
            quickPlayBusy={busyAction === "play"}
            quickPlayDisabled={networkStatus === "offline" || !playForm.deviceId}
            onOpenArtist={(artist) => void openArtistAlbums(artist)}
            onSearchCatalog={(value) => void searchCatalog(value)}
            onCloseArtist={resetArtistDrilldown}
            t={t}
            language={bootstrap.language}
          />

          <div class="sheet-actions sheet-actions-single">
            <button type="button" class="secondary-button" onClick={closeSurface}>
              {localized(bootstrap.language, "Cancel", "Abbrechen")}
            </button>
          </div>
        </div>
      </Sheet>

      <Sheet
        id="settings-sheet"
        open={surface === "settings"}
        onClose={closeSurface}
        closeLabel={closeSheetLabel}
        variant="settings"
        title={localized(bootstrap.language, "Settings", "Einstellungen")}
        subtitle={localized(
          bootstrap.language,
          "Secondary controls stay here so the home surface keeps its focus.",
          "Sekundäre Steuerung bleibt hier, damit die Startseite fokussiert bleibt."
        )}
      >
        <div class="sheet-stack" data-testid="settings-sheet">
          <section class="settings-group settings-group-account">
            <h3>{t("spotify_account", localized(bootstrap.language, "Spotify account", "Spotify-Konto"))}</h3>
            {account.status === "loading" ? (
              <div class="state-card state-card-muted">
                <p>{t("loading_account", localized(bootstrap.language, "Loading account...", "Lade Konto..."))}</p>
              </div>
            ) : null}
            {account.status === "auth_required" ? (
              <div class="state-card state-card-danger">
                <p>{t("status_auth_required", localized(bootstrap.language, "Spotify sign-in required", "Spotify-Anmeldung erforderlich"))}</p>
              </div>
            ) : null}
            {account.status === "offline" || account.status === "error" ? (
              <div class="state-card state-card-danger">
                <p>{account.errorMessage || t("account_error", localized(bootstrap.language, "Error loading account", "Fehler beim Laden des Kontos"))}</p>
              </div>
            ) : null}
            {account.status === "ready" && account.profile ? (
              <div class="account-card">
                <div class="account-avatar">
                  {safeAccountAvatar ? (
                    <img src={safeAccountAvatar} alt="" loading="lazy" referrerPolicy="no-referrer" />
                  ) : (
                    icon("spotify", "icon icon-xl")
                  )}
                </div>
                <div>
                  <strong>{account.profile.display_name || "Spotify"}</strong>
                  <p>{account.profile.email || localized(bootstrap.language, "Connected account", "Verbundenes Konto")}</p>
                </div>
                {account.profile.product === "premium" ? (
                  <StatusPill tone="success" label="Premium" />
                ) : null}
              </div>
            ) : null}
          </section>

          <section class="settings-group settings-group-features">
            <h3>{t("feature_flags", localized(bootstrap.language, "Features", "Funktionen"))}</h3>
            <ToggleField
              label={localized(bootstrap.language, "Sleep timer surface", "Sleep-Timer Oberfläche")}
              description={localized(
                bootstrap.language,
                "Keep the dedicated sleep flow visible on the dashboard.",
                "Die dedizierte Sleep-Oberfläche im Dashboard sichtbar halten."
              )}
              checked={settings.feature_flags.sleep_timer}
              onChange={(checked) => void updateSetting("feature_flags.sleep_timer", checked)}
            />
            <ToggleField
              label={localized(bootstrap.language, "Music browsing", "Musik-Browsing")}
              description={localized(
                bootstrap.language,
                "Enable the quick music picker used by alarm, sleep and play now.",
                "Den schnellen Musik-Picker für Wecker, Sleep und Jetzt abspielen aktivieren."
              )}
              checked={settings.feature_flags.music_library}
              onChange={(checked) => void updateSetting("feature_flags.music_library", checked)}
            />
          </section>

          <section class="settings-group settings-group-preferences">
            <h3>{localized(bootstrap.language, "Preferences", "Präferenzen")}</h3>
            <div class="field-group">
              <label class="field-label" for="settings-language">
                {t("language_label", localized(bootstrap.language, "Language", "Sprache"))}
              </label>
              <select
                id="settings-language"
                class="field-input"
                value={settings.app.language}
                onChange={(event) =>
                  void updateSetting("app.language", (event.currentTarget as HTMLSelectElement).value)
                }
              >
                <option value="de">Deutsch</option>
                <option value="en">English</option>
              </select>
            </div>

            <div class="range-field">
              <div class="field-label-row">
                <label class="field-label">
                  {t("default_volume_label", localized(bootstrap.language, "Default volume", "Standard-Lautstärke"))}
                </label>
                <strong>{settings.app.default_volume}%</strong>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={settings.app.default_volume}
                aria-label={t("default_volume_label", localized(bootstrap.language, "Default volume", "Standard-Lautstärke"))}
                onInput={(event) =>
                  setSettings((current) => ({
                    ...current,
                    app: {
                      ...current.app,
                      default_volume: Number((event.currentTarget as HTMLInputElement).value)
                    }
                  }))
                }
                onChange={(event) =>
                  void updateSetting(
                    "app.default_volume",
                    Number((event.currentTarget as HTMLInputElement).value)
                  )
                }
              />
            </div>

            <ToggleField
              label={t("oled_mode_label", localized(bootstrap.language, "OLED mode", "OLED-Modus"))}
              description={localized(
                bootstrap.language,
                "Switch the palette to deeper blacks for always-on displays.",
                "Die Palette für Always-on-Displays auf tiefere Schwarztöne umstellen."
              )}
              checked={oledTheme}
              onChange={(checked) => setOledTheme(checked)}
            />
          </section>

          <section class="settings-group settings-group-maintenance">
            <h3>{localized(bootstrap.language, "Maintenance", "Wartung")}</h3>
            <button
              type="button"
              class="secondary-button"
              disabled={busyAction === "clear-cache"}
              onClick={() => void handleClearCache()}
            >
              {busyAction === "clear-cache"
                ? localized(bootstrap.language, "Clearing cache...", "Cache wird geleert...")
                : t("clear_cache_btn", localized(bootstrap.language, "Clear cache", "Cache leeren"))}
            </button>
            <div class="meta-list">
              <span>{localized(bootstrap.language, "Environment", "Umgebung")}: {settings.environment}</span>
              <span>{localized(bootstrap.language, "Version", "Version")}: {bootstrap.app.version}</span>
            </div>
          </section>
        </div>
      </Sheet>
    </Fragment>
  );
}
