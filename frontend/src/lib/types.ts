export type SurfaceName = "none" | "alarm" | "sleep" | "play" | "settings";
export type LibrarySection = "playlists" | "albums" | "tracks" | "artists" | "recent" | "top" | "search";
export type AsyncStatus =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "pending"
  | "auth_required"
  | "error"
  | "offline";

export interface ApiEnvelope<T> {
  success: boolean;
  timestamp: string;
  request_id: string;
  message?: string;
  error_code?: string;
  data?: T;
}

export interface ApiResult<T> {
  status: number;
  ok: boolean;
  body: ApiEnvelope<T> | null;
}

export interface SnapshotHydration {
  fresh: boolean;
  pending: boolean;
  refreshing: boolean;
  has_data: boolean;
  last_refresh: string | null;
  last_error: string | null;
  last_error_at: string | null;
  pending_reason: string | null;
  ttl: number | null;
}

export interface TrackInfo {
  name?: string;
  artist?: string;
  album_image?: string | null;
  is_playing?: boolean;
}

export interface PlaybackDevice {
  id?: string;
  name?: string;
  type?: string;
  is_active?: boolean;
  volume_percent?: number;
}

export interface PlaybackState {
  current_track?: TrackInfo;
  device?: PlaybackDevice;
  is_playing?: boolean;
}

export interface AlarmSummary {
  enabled: boolean;
  time: string;
  alarm_volume: number;
  next_alarm: string;
  playlist_uri: string;
  playlist_name?: string;
  device_name: string;
  fade_in?: boolean;
  shuffle?: boolean;
  weekdays?: number[] | null;
  snooze_enabled?: boolean;
}

export interface SnoozeStatus {
  active: boolean;
  state?: "armed" | "snoozing" | string;
  snooze_count?: number;
  resume_in_seconds?: number;
  resume_at?: number;
  window_end?: number;
  window_remaining_seconds?: number;
  snooze_minutes?: number;
}

export interface AlarmFormState {
  enabled: boolean;
  time: string;
  deviceName: string;
  playlistUri: string;
  playlistName: string;
  alarmVolume: number;
  fadeIn: boolean;
  shuffle: boolean;
  weekdays: number[];
  snoozeEnabled: boolean;
}

export interface SleepFormState {
  duration: string;
  customDuration: string;
  deviceName: string;
  playlistUri: string;
  volume: number;
  shuffle: boolean;
}

export interface PlayFormState {
  deviceId: string;
  deviceName: string;
  contextUri: string;
}

export interface SleepSummary {
  active: boolean;
  remaining_seconds?: number;
  remaining_time?: number;
  total_duration_seconds?: number;
  total_duration_minutes?: number;
  progress_percent?: number;
  playlist_uri?: string;
  device_name?: string;
  device_id?: string;
  volume?: number;
  start_time?: number;
  end_time?: number;
  error?: string;
  error_code?: string;
}

export interface SpotifyDevice {
  id?: string;
  name: string;
  type?: string;
  is_active?: boolean;
  volume_percent?: number;
}

export interface DashboardData {
  timestamp: string;
  alarm: AlarmSummary;
  sleep: SleepSummary;
  snooze?: SnoozeStatus;
  playback: PlaybackState;
  playback_status: string;
  playback_error?: string;
  devices: SpotifyDevice[];
  devices_meta: {
    status: string;
    cache?: Record<string, unknown>;
    fetched_at?: string | null;
  };
  hydration: {
    dashboard: SnapshotHydration;
    playback: SnapshotHydration;
    devices: SnapshotHydration;
  };
}

export interface PrimaryFlowSnapshot {
  alarmEnabled: boolean;
  alarmTime: string;
  alarmDeviceName: string;
  alarmPlaylistUri: string;
  alarmPlaylistName: string;
  sleepActive: boolean;
  sleepRemainingSeconds?: number;
  availableDevices: number;
}

export interface SettingsData {
  feature_flags: {
    sleep_timer: boolean;
    music_library: boolean;
  };
  app: {
    language: string;
    default_volume: number;
    debug: boolean;
  };
  environment: string;
}

export interface SleepDefaults {
  duration: number;
  volume: number;
  playlist_uri: string;
  device_name: string;
  shuffle: boolean;
}

export interface AppNotification {
  type: "success" | "error";
  message: string;
}

export interface ToastItem {
  id: number;
  type: "success" | "error" | "info";
  message: string;
}

export interface AppBootstrap {
  language: string;
  translations: Record<string, string>;
  low_power: boolean;
  app: {
    version: string;
    info: string;
    initial_surface: "home" | "settings";
    now_iso: string;
  };
  dashboard: DashboardData;
  settings: SettingsData;
  sleep_defaults: SleepDefaults;
  notifications: AppNotification[];
}

export interface LibraryItem {
  uri: string;
  name: string;
  image_url?: string | null;
  track_count?: number;
  type?: string;
  artist?: string;
  duration_ms?: number;
  album?: string;
}

export interface LibraryPayload {
  playlists?: LibraryItem[];
  albums?: LibraryItem[];
  tracks?: LibraryItem[];
  artists?: LibraryItem[];
  recent?: LibraryItem[];
  top?: LibraryItem[];
  sections?: string[];
  partial?: boolean;
}

export interface ArtistAlbumsPayload {
  artist_id: string;
  albums: LibraryItem[];
  total: number;
}

export interface SearchResultsPayload {
  query: string;
  types: string[];
  results: {
    tracks: LibraryItem[];
    albums: LibraryItem[];
    artists: LibraryItem[];
    playlists: LibraryItem[];
  };
  total: number;
}

export interface PlaybackQueuePayload {
  currently_playing?: LibraryItem | null;
  queue: LibraryItem[];
  total: number;
}

export interface SpotifyProfile {
  display_name?: string;
  email?: string;
  avatar_url?: string;
  product?: string;
}

export interface SpotifyCredentialField {
  set: boolean;
  masked: string;
  value?: string;
}

export interface SpotifyCredentialsPayload {
  client_id: SpotifyCredentialField;
  client_secret: SpotifyCredentialField;
  refresh_token: SpotifyCredentialField;
  username: SpotifyCredentialField;
}

export type SpotifyConnectionStatus =
  | "missing_credentials"
  | "auth_required"
  | "connected"
  | "offline"
  | "error";

export interface SpotifyConnectionPayload {
  status: SpotifyConnectionStatus;
  message?: string;
  profile?: SpotifyProfile | null;
}

export interface SpotifyOAuthPayload {
  start_url: string;
  callback_url: string;
  scopes: string[];
}

export interface SpotifySettingsPayload {
  credentials: SpotifyCredentialsPayload;
  connection: SpotifyConnectionPayload;
  oauth: SpotifyOAuthPayload;
}

export interface CollectionState {
  status: AsyncStatus;
  items: LibraryItem[];
  errorMessage?: string;
}

export interface ArtistDrilldown {
  artist: LibraryItem | null;
  status: AsyncStatus;
  items: LibraryItem[];
  errorMessage?: string;
}
