/** @jsxImportSource preact */
import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { postForm } from "../lib/api";
import type { DashboardData, SettingsData, ToastItem } from "../lib/types";

type TranslateFn = (
  key: string,
  fallback: string,
  params?: Record<string, string | number>
) => string;

interface UsePlaybackActionsOptions {
  dashboard: DashboardData;
  settings: SettingsData;
  networkStatus: "online" | "offline";
  language: string;
  t: TranslateFn;
  setBusyAction: (action: string | null) => void;
  pushToast: (type: ToastItem["type"], message: string) => void;
  refreshDashboard: (force?: boolean) => Promise<boolean>;
  setDashboard: (update: DashboardData | ((current: DashboardData) => DashboardData)) => void;
}

interface UsePlaybackActionsResult {
  playerVolume: number;
  setPlayerVolume: (value: number) => void;
  isPlayerReady: boolean;
  handleVolumeInput: (value: number) => void;
  handlePlaybackCommand: (endpoint: string, actionName: string) => Promise<void>;
}

function localized(language: string, en: string, de: string): string {
  return language === "de" ? de : en;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function currentVolume(dashboard: DashboardData, settings: SettingsData): number {
  return clamp(
    Number(dashboard.playback.device?.volume_percent ?? settings.app.default_volume ?? 20),
    0,
    100
  );
}

function isPlaybackInitialHydration(dashboard: DashboardData): boolean {
  return (
    dashboard.playback_status === "pending" ||
    (dashboard.hydration.playback.pending && !dashboard.hydration.playback.has_data)
  );
}

function isPlaybackReady(dashboard: DashboardData, networkStatus: "online" | "offline"): boolean {
  if (networkStatus === "offline") {
    return false;
  }
  if (isPlaybackInitialHydration(dashboard)) {
    return false;
  }
  if (dashboard.playback_status === "auth_required" || dashboard.playback_status === "error") {
    return false;
  }
  return Boolean(dashboard.playback.current_track || dashboard.playback.device);
}

export function usePlaybackActions({
  dashboard,
  settings,
  networkStatus,
  language,
  t,
  setBusyAction,
  pushToast,
  refreshDashboard,
  setDashboard
}: UsePlaybackActionsOptions): UsePlaybackActionsResult {
  const [playerVolume, setPlayerVolume] = useState<number>(() => currentVolume(dashboard, settings));
  const volumeTimerRef = useRef<number | null>(null);
  const isPlayerReady = isPlaybackReady(dashboard, networkStatus);

  useEffect(() => {
    setPlayerVolume(currentVolume(dashboard, settings));
  }, [dashboard, settings]);

  const setIsPlaying = useCallback((isPlaying: boolean) => {
    setDashboard((current) => ({
      ...current,
      playback: { ...current.playback, is_playing: isPlaying }
    }));
  }, [setDashboard]);

  const handlePlaybackCommand = useCallback(async (endpoint: string, actionName: string) => {
    if (!isPlaybackReady(dashboard, networkStatus)) {
      return;
    }

    // Play/pause is the only command whose result we can predict, so flip the icon
    // optimistically for instant feedback and reconcile (or revert) from the response.
    const isToggle = endpoint === "/toggle_play_pause";
    const previousIsPlaying = Boolean(dashboard.playback.is_playing);
    if (isToggle) {
      setIsPlaying(!previousIsPlaying);
    }

    setBusyAction(actionName);
    try {
      const result = await postForm<{ action?: string }>(endpoint, new URLSearchParams());
      if (result.body?.success) {
        if (isToggle) {
          const action = result.body.data?.action;
          if (action === "playing" || action === "paused") {
            setIsPlaying(action === "playing");
          }
        }
        window.setTimeout(() => {
          void refreshDashboard(true);
        }, 350);
      } else {
        if (isToggle) {
          setIsPlaying(previousIsPlaying);
        }
        if (result.body?.message) {
          pushToast("error", result.body.message);
        }
      }
    } catch (error) {
      if (isToggle) {
        setIsPlaying(previousIsPlaying);
      }
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(language, "Playback failed", "Wiedergabe fehlgeschlagen")
      );
    } finally {
      setBusyAction(null);
    }
  }, [dashboard, language, networkStatus, pushToast, refreshDashboard, setBusyAction, setIsPlaying]);

  const handleVolumeInput = useCallback((value: number) => {
    const nextValue = clamp(value, 0, 100);
    setPlayerVolume(nextValue);

    if (volumeTimerRef.current) {
      window.clearTimeout(volumeTimerRef.current);
    }

    volumeTimerRef.current = window.setTimeout(async () => {
      const payload = new URLSearchParams();
      payload.set("volume", String(nextValue));
      if (dashboard.playback.device?.id) {
        payload.set("device_id", dashboard.playback.device.id);
      }

      try {
        const result = await postForm<Record<string, unknown>>("/volume", payload);
        if (!result.body?.success && result.body?.message) {
          pushToast("error", result.body.message);
        }
      } catch (error) {
        pushToast(
          "error",
          error instanceof Error
            ? error.message
            : t("volume_set_error", localized(language, "Volume update failed", "Lautstärke konnte nicht gesetzt werden"))
        );
      }
    }, 160);
  }, [dashboard.playback.device?.id, language, pushToast, t]);

  useEffect(() => {
    return () => {
      if (volumeTimerRef.current) {
        window.clearTimeout(volumeTimerRef.current);
      }
    };
  }, []);

  return {
    playerVolume,
    setPlayerVolume,
    isPlayerReady,
    handleVolumeInput,
    handlePlaybackCommand
  };
}
