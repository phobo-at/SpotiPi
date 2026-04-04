/** @jsxImportSource preact */
import { useCallback, useEffect, useState } from "preact/hooks";

import { getJson } from "../lib/api";
import type {
  ArtistDrilldown,
  ArtistTracksPayload,
  CollectionState,
  LibraryItem,
  LibraryPayload,
  LibrarySection,
  SurfaceName
} from "../lib/types";

type TranslateFn = (
  key: string,
  fallback: string,
  params?: Record<string, string | number>
) => string;

interface UseLibraryDataOptions {
  enabled: boolean;
  surface: SurfaceName;
  language: string;
  t: TranslateFn;
}

interface UseLibraryDataResult {
  librarySection: LibrarySection;
  setLibrarySection: (section: LibrarySection) => void;
  collections: Record<LibrarySection, CollectionState>;
  artistDrilldown: ArtistDrilldown;
  setArtistDrilldown: (value: ArtistDrilldown) => void;
  ensureLibrarySection: (section: LibrarySection) => Promise<void>;
  openArtistTracks: (artist: LibraryItem) => Promise<void>;
  resetArtistDrilldown: () => void;
}

function localized(language: string, en: string, de: string): string {
  return language === "de" ? de : en;
}

function extractArtistId(uri: string): string | null {
  const segments = uri.split(":");
  if (segments.length === 3 && segments[1] === "artist") {
    return segments[2];
  }
  return null;
}

function createCollectionMap(): Record<LibrarySection, CollectionState> {
  return {
    playlists: { status: "idle", items: [] },
    albums: { status: "idle", items: [] },
    tracks: { status: "idle", items: [] },
    artists: { status: "idle", items: [] }
  };
}

export function useLibraryData({
  enabled,
  surface,
  language,
  t
}: UseLibraryDataOptions): UseLibraryDataResult {
  const [librarySection, setLibrarySection] = useState<LibrarySection>("playlists");
  const [collections, setCollections] = useState<Record<LibrarySection, CollectionState>>(
    createCollectionMap()
  );
  const [artistDrilldown, setArtistDrilldown] = useState<ArtistDrilldown>({
    artist: null,
    status: "idle",
    tracks: []
  });

  const ensureLibrarySection = useCallback(async (section: LibrarySection) => {
    if (!enabled) {
      return;
    }

    const existing = collections[section];
    if (existing.status === "loading" || existing.status === "ready") {
      return;
    }

    setCollections((current) => {
      const currentSection = current[section];
      if (currentSection.status === "loading" || currentSection.status === "ready") {
        return current;
      }
      return {
        ...current,
        [section]: {
          ...currentSection,
          status: "loading",
          errorMessage: undefined
        }
      };
    });

    try {
      const result = await getJson<LibraryPayload>(
        `/api/music-library/sections?sections=${section}&fields=basic`
      );
      if (result.status === 401 || result.body?.error_code === "auth_required") {
        setCollections((current) => ({
          ...current,
          [section]: {
            ...current[section],
            status: "auth_required"
          }
        }));
        return;
      }

      if (result.body?.success && result.body.data) {
        const items = result.body.data[section] || [];
        setCollections((current) => ({
          ...current,
          [section]: {
            status: items.length > 0 ? "ready" : "empty",
            items
          }
        }));
        return;
      }

      setCollections((current) => ({
        ...current,
        [section]: {
          ...current[section],
          status: "error",
          errorMessage:
            result.body?.message ||
            t("spotify_unavailable", localized(language, "Spotify unavailable", "Spotify nicht verfügbar"))
        }
      }));
    } catch (error) {
      setCollections((current) => ({
        ...current,
        [section]: {
          ...current[section],
          status: "offline",
          errorMessage:
            error instanceof Error
              ? error.message
              : localized(language, "Network error", "Netzwerkfehler")
        }
      }));
    }
  }, [collections, enabled, language, t]);

  useEffect(() => {
    if (surface === "alarm" || surface === "sleep" || surface === "play") {
      void ensureLibrarySection(librarySection);
    }
  }, [surface, librarySection, ensureLibrarySection]);

  const openArtistTracks = useCallback(async (artist: LibraryItem) => {
    const artistId = extractArtistId(artist.uri);
    if (!artistId) {
      return;
    }

    setArtistDrilldown({
      artist,
      status: "loading",
      tracks: []
    });

    try {
      const result = await getJson<ArtistTracksPayload>(`/api/artist-top-tracks/${artistId}`);
      if (result.status === 401 || result.body?.error_code === "auth_required") {
        setArtistDrilldown({
          artist,
          status: "auth_required",
          tracks: []
        });
        return;
      }

      if (result.body?.success && result.body.data) {
        setArtistDrilldown({
          artist,
          status: result.body.data.tracks.length ? "ready" : "empty",
          tracks: result.body.data.tracks
        });
        return;
      }

      setArtistDrilldown({
        artist,
        status: "error",
        tracks: [],
        errorMessage:
          result.body?.message ||
          localized(language, "Unable to load tracks", "Tracks konnten nicht geladen werden")
      });
    } catch (error) {
      setArtistDrilldown({
        artist,
        status: "offline",
        tracks: [],
        errorMessage:
          error instanceof Error
            ? error.message
            : localized(language, "Network error", "Netzwerkfehler")
      });
    }
  }, [language]);

  const resetArtistDrilldown = useCallback(() => {
    setArtistDrilldown({ artist: null, status: "idle", tracks: [] });
  }, []);

  return {
    librarySection,
    setLibrarySection,
    collections,
    artistDrilldown,
    setArtistDrilldown,
    ensureLibrarySection,
    openArtistTracks,
    resetArtistDrilldown
  };
}
