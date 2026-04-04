/** @jsxImportSource preact */
import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import type { AppNotification, ToastItem } from "../lib/types";

interface UseToastsOptions {
  initialNotifications?: AppNotification[];
}

interface UseToastsResult {
  toasts: ToastItem[];
  pushToast: (type: ToastItem["type"], message: string) => void;
  dismissToast: (id: number) => void;
}

export function useToasts({ initialNotifications = [] }: UseToastsOptions = {}): UseToastsResult {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastCounterRef = useRef(0);
  const hydratedRef = useRef(false);

  const dismissToast = useCallback((id: number) => {
    setToasts((items) => items.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback((type: ToastItem["type"], message: string) => {
    const id = ++toastCounterRef.current;
    setToasts((items) => [...items, { id, type, message }]);
    window.setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id));
    }, 4200);
  }, []);

  useEffect(() => {
    if (hydratedRef.current) {
      return;
    }
    hydratedRef.current = true;
    initialNotifications.forEach((notification) => {
      pushToast(notification.type === "error" ? "error" : "success", notification.message);
    });
  }, [initialNotifications, pushToast]);

  return { toasts, pushToast, dismissToast };
}
