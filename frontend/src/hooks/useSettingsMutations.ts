/** @jsxImportSource preact */
import { useCallback } from "preact/hooks";

import { patchJson, postForm } from "../lib/api";
import type { SettingsData, ToastItem } from "../lib/types";

type TranslateFn = (
  key: string,
  fallback: string,
  params?: Record<string, string | number>
) => string;

interface UseSettingsMutationsOptions {
  language: string;
  t: TranslateFn;
  setSettings: (next: SettingsData | ((current: SettingsData) => SettingsData)) => void;
  setBusyAction: (action: string | null) => void;
  pushToast: (type: ToastItem["type"], message: string) => void;
  refreshDashboard: (force?: boolean) => Promise<void>;
}

interface UseSettingsMutationsResult {
  updateSetting: (path: string, value: boolean | number | string) => Promise<void>;
  handleClearCache: () => Promise<void>;
}

function localized(language: string, en: string, de: string): string {
  return language === "de" ? de : en;
}

function applySettingChange(
  current: SettingsData,
  category: string,
  key: string,
  value: boolean | number | string
): SettingsData {
  if (category === "feature_flags") {
    return {
      ...current,
      feature_flags: {
        ...current.feature_flags,
        [key]: Boolean(value)
      }
    };
  }

  return {
    ...current,
    app: {
      ...current.app,
      [key]: value
    }
  };
}

export function useSettingsMutations({
  language,
  t,
  setSettings,
  setBusyAction,
  pushToast,
  refreshDashboard
}: UseSettingsMutationsOptions): UseSettingsMutationsResult {
  const updateSetting = useCallback(async (path: string, value: boolean | number | string) => {
    const [category, key] = path.split(".");
    const payload = {
      [category]: {
        [key]: value
      }
    };
    let previousSettings: SettingsData | null = null;

    setSettings((current) => {
      previousSettings = current;
      return applySettingChange(current, category, key, value);
    });

    setBusyAction(path);
    try {
      const result = await patchJson<Record<string, unknown>>("/api/settings", payload);
      if (result.body?.success) {
        pushToast(
          "success",
          result.body.message ||
            t("settings_saved", localized(language, "Settings saved", "Einstellungen gespeichert"))
        );

        if (path === "app.language") {
          window.setTimeout(() => window.location.reload(), 350);
        }
        return;
      }

      if (previousSettings) {
        setSettings(previousSettings);
      }
      pushToast(
        "error",
        result.body?.message ||
          t("settings_save_error", localized(language, "Save failed", "Speichern fehlgeschlagen"))
      );
    } catch (error) {
      if (previousSettings) {
        setSettings(previousSettings);
      }
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(language, "Save failed", "Speichern fehlgeschlagen")
      );
    } finally {
      setBusyAction(null);
    }
  }, [language, pushToast, setBusyAction, setSettings, t]);

  const handleClearCache = useCallback(async () => {
    setBusyAction("clear-cache");
    try {
      const result = await postForm<Record<string, unknown>>(
        "/api/settings/cache/clear",
        new URLSearchParams()
      );
      if (result.body?.success) {
        pushToast(
          "success",
          result.body.message ||
            localized(language, "Cache cleared", "Cache geleert")
        );
        await refreshDashboard(true);
      } else {
        pushToast(
          "error",
          result.body?.message ||
            localized(language, "Unable to clear cache", "Cache konnte nicht geleert werden")
        );
      }
    } catch (error) {
      pushToast(
        "error",
        error instanceof Error ? error.message : localized(language, "Unable to clear cache", "Cache konnte nicht geleert werden")
      );
    } finally {
      setBusyAction(null);
    }
  }, [language, pushToast, refreshDashboard, setBusyAction]);

  return { updateSetting, handleClearCache };
}
