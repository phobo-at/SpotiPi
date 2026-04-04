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
  refreshDashboard: (force?: boolean) => Promise<void>;
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
    async (force = false) => {
      try {
        const suffix = force ? "?refresh=1" : "";
        const result = await getJson<DashboardData>(`/api/dashboard/status${suffix}`);
        if (result.body?.success && result.body.data) {
          setDashboard((current) => mergeDashboard(current, result.body!.data!));
          setNetworkStatus("online");
          if (connectionWasLostRef.current) {
            connectionWasLostRef.current = false;
            pushToast(
              "success",
              t("connection_restored", localized(language, "Connection restored", "Verbindung wiederhergestellt"))
            );
          }
        }
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
      }
    },
    [language, pushToast, setNetworkStatus, t]
  );

  useEffect(() => {
    const visibleInterval = lowPower ? 6000 : 4000;
    const hiddenInterval = lowPower ? 45000 : 30000;
    let intervalHandle: number | null = null;

    const startInterval = () => {
      if (intervalHandle) {
        window.clearInterval(intervalHandle);
      }
      const intervalMs = document.visibilityState === "visible" ? visibleInterval : hiddenInterval;
      intervalHandle = window.setInterval(() => {
        void refreshDashboard();
      }, intervalMs);
    };

    const onVisibilityChange = () => {
      startInterval();
      if (document.visibilityState === "visible") {
        void refreshDashboard();
      }
    };

    startInterval();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      if (intervalHandle) {
        window.clearInterval(intervalHandle);
      }
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [lowPower, refreshDashboard]);

  return {
    dashboard,
    setDashboard,
    refreshDashboard
  };
}
