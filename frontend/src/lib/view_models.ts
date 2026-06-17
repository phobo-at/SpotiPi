import type {
  AlarmFormState,
  DashboardData,
  PlayFormState,
  PrimaryFlowSnapshot,
  SettingsData,
  SleepDefaults,
  SleepFormState,
  SpotifyDevice
} from "./types";

export const SLEEP_DURATION_PRESETS = [15, 30, 45, 60, 90, 120] as const;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function createAlarmFormModel(
  dashboard: DashboardData,
  settings: SettingsData
): AlarmFormState {
  return {
    enabled: dashboard.alarm.enabled,
    time: dashboard.alarm.time || "07:00",
    deviceName: dashboard.alarm.device_name || "",
    playlistUri: dashboard.alarm.playlist_uri || "",
    playlistName: dashboard.alarm.playlist_name || "",
    alarmVolume: clamp(
      Number(dashboard.alarm.alarm_volume || settings.app.default_volume || 50),
      0,
      100
    ),
    fadeIn: Boolean(dashboard.alarm.fade_in),
    shuffle: Boolean(dashboard.alarm.shuffle),
    weekdays: Array.isArray(dashboard.alarm.weekdays)
      ? dashboard.alarm.weekdays.filter((day) => Number.isInteger(day) && day >= 0 && day <= 6)
      : [],
    // Backend defaults snooze_enabled to true; mirror that for older payloads.
    snoozeEnabled: dashboard.alarm.snooze_enabled !== false
  };
}

export function createSleepFormModel(
  dashboard: DashboardData,
  defaults: SleepDefaults
): SleepFormState {
  const savedDuration =
    dashboard.sleep.total_duration_minutes ||
    (defaults.duration ? Number(defaults.duration) : 30);
  const isPresetDuration = SLEEP_DURATION_PRESETS.includes(
    savedDuration as (typeof SLEEP_DURATION_PRESETS)[number]
  );

  return {
    duration: isPresetDuration ? String(savedDuration) : "custom",
    customDuration: String(savedDuration),
    deviceName: dashboard.sleep.device_name || defaults.device_name || "",
    playlistUri: dashboard.sleep.playlist_uri || defaults.playlist_uri || "",
    volume: clamp(
      Number(dashboard.sleep.volume ?? defaults.volume ?? 30),
      0,
      100
    ),
    shuffle: Boolean(defaults.shuffle)
  };
}

export function getPreferredDevice(devices: SpotifyDevice[]): SpotifyDevice | undefined {
  return devices.find((device) => device.is_active) || devices[0];
}

export function createPlayFormModel(dashboard: DashboardData): PlayFormState {
  const activeDevice = getPreferredDevice(dashboard.devices);
  return {
    deviceId: activeDevice?.id || "",
    deviceName: activeDevice?.name || "",
    contextUri: ""
  };
}

export function toPrimaryFlowSnapshot(dashboard: DashboardData): PrimaryFlowSnapshot {
  return {
    alarmEnabled: Boolean(dashboard.alarm.enabled),
    alarmTime: dashboard.alarm.time || "",
    alarmDeviceName: dashboard.alarm.device_name || "",
    alarmPlaylistUri: dashboard.alarm.playlist_uri || "",
    alarmPlaylistName: dashboard.alarm.playlist_name || "",
    alarmVolume: clamp(Number(dashboard.alarm.alarm_volume || 0), 0, 100),
    alarmWeekdays: Array.isArray(dashboard.alarm.weekdays)
      ? dashboard.alarm.weekdays.filter((day) => Number.isInteger(day) && day >= 0 && day <= 6)
      : [],
    sleepActive: Boolean(dashboard.sleep.active),
    sleepRemainingSeconds: dashboard.sleep.remaining_seconds,
    availableDevices: Array.isArray(dashboard.devices) ? dashboard.devices.length : 0
  };
}
