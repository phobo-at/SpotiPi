/** @jsxImportSource preact */
import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { getJson, NetworkRequestError } from "../lib/api";
import type { DashboardData, ToastItem } from "../lib/types";

type TranslateFn = (
  key: string,
  fallback: string,
  params?: Record<string, string | number>
) => string;

interface UseDashboardPollingOptions {
  initialDashboard: DashboardData;
  lowPower: boolean;
  language: string;
  t: TranslateFn;
  setNetworkStatus: (status: "online" | "offline") => void;
  pushToast: (type: ToastItem["type"], message: string) => void;
}

interface UseDashboardPollingResult {
  dashboard: DashboardData;
  setDashboard: (update: DashboardData | ((current: DashboardData) => DashboardData)) => void;
  refreshDashboard: (force?: boolean) => Promise<boolean>;
}

function localized(language: string, en: string, de: string): string {
  return language === "de" ? de : en;
}

function mergeDashboard(current: DashboardData, incoming: DashboardData): DashboardData {
  const next = { ...incoming };

  if (next.playback_status === "pending" && !incoming.playback.current_track && current.playback.current_track) {
    next.playback = current.playback;
  }

  if (
    next.hydration.devices.pending &&
    (!incoming.devices || incoming.devices.length === 0) &&
    current.devices.length > 0
  ) {
    next.devices = current.devices;
    next.devices_meta = current.devices_meta;
  }

  return next;
}

export function useDashboardPolling({
  initialDashboard,
  lowPower,
  language,
  t,
  setNetworkStatus,
  pushToast
}: UseDashboardPollingOptions): UseDashboardPollingResult {
  const [dashboard, setDashboard] = useState<DashboardData>(initialDashboard);
  const connectionWasLostRef = useRef(false);

  const refreshDashboard = useCallback(
    async (force = false): Promise<boolean> => {
      try {
        const suffix = force ? "?refresh=1" : "";
        const result = await getJson<DashboardData>(`/api/dashboard/status${suffix}`);
        if (result.body?.success && result.body.data) {
          const incoming = result.body.data;
          setDashboard((current) => mergeDashboard(current, incoming));
          setNetworkStatus("online");
          if (connectionWasLostRef.current) {
            connectionWasLostRef.current = false;
            pushToast(
              "success",
              t("connection_restored", localized(language, "Connection restored", "Verbindung wiederhergestellt"))
            );
          }
          // Signal "snapshot still warming" so the caller can fast-retry instead of waiting
          // a full poll interval. Keyed on the RAW response status — not the merged/hydration
          // state — so a preserved stale track or a sub-TTL snapshot never traps us in a loop.
          return incoming.playback_status === "pending";
        }
        return false;
      } catch (error) {
        if (error instanceof NetworkRequestError) {
          setNetworkStatus("offline");
          if (!connectionWasLostRef.current) {
            connectionWasLostRef.current = true;
            pushToast(
              "error",
              t("connection_lost", localized(language, "Connection lost", "Verbindung verloren"))
            );
          }
        }
        return false;
      }
    },
    [language, pushToast, setNetworkStatus, t]
  );

  useEffect(() => {
    const visibleInterval = lowPower ? 6000 : 4000;
    const hiddenInterval = lowPower ? 45000 : 30000;
    // While the server snapshot is still warming, re-poll quickly instead of waiting a
    // full interval — collapses cold-open time-to-artwork from ~2 intervals to ~1s.
    const fastRetryMs = lowPower ? 1000 : 700;
    const FAST_RETRY_CAP = 3;

    let intervalHandle: number | null = null;
    let fastTimeoutHandle: number | null = null;
    let fastRetryBudget = FAST_RETRY_CAP;
    let cancelled = false;

    const clearFastRetry = () => {
      if (fastTimeoutHandle) {
        window.clearTimeout(fastTimeoutHandle);
        fastTimeoutHandle = null;
      }
    };

    // One poll cycle. Non-forced by default: a cold/stale snapshot still triggers a
    // server-side background refresh, while a warm one returns instantly with no extra
    // Spotify call. Re-arms the fast-retry budget only on a settled (non-pending) result
    // so an unauthenticated Pi (perpetually "pending") fast-polls once, then quiesces.
    const poll = async () => {
      const stillPending = await refreshDashboard();
      if (cancelled || document.visibilityState !== "visible") {
        return;
      }
      if (stillPending) {
        if (fastRetryBudget > 0) {
          fastRetryBudget -= 1;
          clearFastRetry();
          fastTimeoutHandle = window.setTimeout(() => {
            void poll();
          }, fastRetryMs);
        }
      } else {
        fastRetryBudget = FAST_RETRY_CAP;
      }
    };

    const startInterval = () => {
      if (intervalHandle) {
        window.clearInterval(intervalHandle);
      }
      const intervalMs = document.visibilityState === "visible" ? visibleInterval : hiddenInterval;
      intervalHandle = window.setInterval(() => {
        void poll();
      }, intervalMs);
    };

    const onVisibilityChange = () => {
      startInterval();
      if (document.visibilityState === "visible") {
        fastRetryBudget = FAST_RETRY_CAP;
        void poll();
      } else {
        clearFastRetry();
      }
    };

    startInterval();
    // Eager first poll on mount: don't wait a full interval (4-6s) for the first request.
    void poll();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelled = true;
      if (intervalHandle) {
        window.clearInterval(intervalHandle);
      }
      clearFastRetry();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [lowPower, refreshDashboard]);

  return {
    dashboard,
    setDashboard,
    refreshDashboard
  };
}
