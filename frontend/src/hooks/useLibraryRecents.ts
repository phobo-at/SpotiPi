/** @jsxImportSource preact */
import { useCallback, useState } from "preact/hooks";
import type { LibraryItem } from "../lib/types";

export type RecentScope = "alarm" | "sleep" | "play";

export interface RecentEntry {
  uri: string;
  name: string;
  image_url: string | null;
  meta: string;
  type: string;
  picked_at: number;
}

interface RecentsEnvelope {
  v: 1;
  items: RecentEntry[];
}

const STORAGE_PREFIX = "spotipi.recents.";
const MAX_ENTRIES = 5;
const TTL_MS = 60 * 24 * 60 * 60 * 1000;

function storageKey(scope: RecentScope): string {
  return `${STORAGE_PREFIX}${scope}`;
}

function readStorage(scope: RecentScope): RecentEntry[] {
  try {
    const raw = window.localStorage.getItem(storageKey(scope));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as Partial<RecentsEnvelope>;
    if (!parsed || parsed.v !== 1 || !Array.isArray(parsed.items)) {
      return [];
    }
    const cutoff = Date.now() - TTL_MS;
    return parsed.items.filter(
      (entry): entry is RecentEntry =>
        !!entry &&
        typeof entry.uri === "string" &&
        typeof entry.name === "string" &&
        typeof entry.picked_at === "number" &&
        entry.picked_at >= cutoff
    );
  } catch {
    return [];
  }
}

function writeStorage(scope: RecentScope, items: RecentEntry[]): void {
  try {
    const envelope: RecentsEnvelope = { v: 1, items };
    window.localStorage.setItem(storageKey(scope), JSON.stringify(envelope));
  } catch {
    // Ignore quota / serialization errors on constrained devices.
  }
}

export interface UseLibraryRecentsResult {
  recents: RecentEntry[];
  recordRecent: (item: LibraryItem, meta: string) => void;
  clearRecents: () => void;
}

export function useLibraryRecents(scope: RecentScope): UseLibraryRecentsResult {
  const [recents, setRecents] = useState<RecentEntry[]>(() => readStorage(scope));

  const recordRecent = useCallback(
    (item: LibraryItem, meta: string) => {
      if (!item?.uri) {
        return;
      }
      const entry: RecentEntry = {
        uri: item.uri,
        name: item.name,
        image_url: item.image_url ?? null,
        meta,
        type: item.type ?? "playlist",
        picked_at: Date.now()
      };
      setRecents((prev) => {
        const deduped = prev.filter((existing) => existing.uri !== entry.uri);
        const next = [entry, ...deduped].slice(0, MAX_ENTRIES);
        writeStorage(scope, next);
        return next;
      });
    },
    [scope]
  );

  const clearRecents = useCallback(() => {
    writeStorage(scope, []);
    setRecents([]);
  }, [scope]);

  return { recents, recordRecent, clearRecents };
}
