/** @jsxImportSource preact */
import { useCallback, useEffect, useState } from "preact/hooks";

import { getJson } from "../lib/api";
import type {
  ArtistDrilldown,
  ArtistAlbumsPayload,
  CollectionState,
  LibraryItem,
  LibraryPayload,
  LibrarySection,
  SearchResultsPayload,
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
  openArtistAlbums: (artist: LibraryItem) => Promise<void>;
  searchCatalog: (query: string) => Promise<void>;
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
    artists: { status: "idle", items: [] },
    recent: { status: "idle", items: [] },
    top: { status: "idle", items: [] },
    search: { status: "idle", items: [] }
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
    items: []
  });

  const ensureLibrarySection = useCallback(async (section: LibrarySection) => {
    if (!enabled) {
      return;
    }

    if (section === "search") {
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

  const openArtistAlbums = useCallback(async (artist: LibraryItem) => {
    const artistId = extractArtistId(artist.uri);
    if (!artistId) {
      return;
    }

    setArtistDrilldown({
      artist,
      status: "loading",
      items: []
    });

    try {
      const result = await getJson<ArtistAlbumsPayload>(`/api/artist-albums/${artistId}`);
      if (result.status === 401 || result.body?.error_code === "auth_required") {
        setArtistDrilldown({
          artist,
          status: "auth_required",
          items: []
        });
        return;
      }

      if (result.body?.success && result.body.data) {
        setArtistDrilldown({
          artist,
          status: result.body.data.albums.length ? "ready" : "empty",
          items: result.body.data.albums
        });
        return;
      }

      setArtistDrilldown({
        artist,
        status: "error",
        items: [],
        errorMessage:
          result.body?.message ||
          localized(language, "Unable to load albums", "Alben konnten nicht geladen werden")
      });
    } catch (error) {
      setArtistDrilldown({
        artist,
        status: "offline",
        items: [],
        errorMessage:
          error instanceof Error
            ? error.message
            : localized(language, "Network error", "Netzwerkfehler")
      });
    }
  }, [language]);

  const searchCatalog = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!enabled) {
      return;
    }

    if (trimmed.length < 3) {
      setCollections((current) => ({
        ...current,
        search: {
          status: "idle",
          items: []
        }
      }));
      return;
    }

    setCollections((current) => ({
      ...current,
      search: {
        ...current.search,
        status: "loading",
        errorMessage: undefined
      }
    }));

    try {
      const result = await getJson<SearchResultsPayload>(
        `/api/music-search?q=${encodeURIComponent(trimmed)}&types=track,album,artist,playlist&limit=5`
      );
      if (result.status === 401 || result.body?.error_code === "auth_required") {
        setCollections((current) => ({
          ...current,
          search: {
            ...current.search,
            status: "auth_required"
          }
        }));
        return;
      }
      if (result.body?.error_code === "insufficient_scope") {
        setCollections((current) => ({
          ...current,
          search: {
            ...current.search,
            status: "error",
            errorMessage: localized(
              language,
              "Spotify re-authentication required for search.",
              "Spotify-Neuanmeldung für Suche erforderlich."
            )
          }
        }));
        return;
      }

      if (result.body?.success && result.body.data) {
        const groups = result.body.data.results;
        const items = [
          ...(groups.tracks || []),
          ...(groups.albums || []),
          ...(groups.artists || []),
          ...(groups.playlists || [])
        ];
        setCollections((current) => ({
          ...current,
          search: {
            status: items.length ? "ready" : "empty",
            items
          }
        }));
        return;
      }

      setCollections((current) => ({
        ...current,
        search: {
          ...current.search,
          status: "error",
          errorMessage:
            result.body?.message ||
            localized(language, "Unable to search Spotify", "Spotify-Suche fehlgeschlagen")
        }
      }));
    } catch (error) {
      setCollections((current) => ({
        ...current,
        search: {
          ...current.search,
          status: "offline",
          errorMessage:
            error instanceof Error
              ? error.message
              : localized(language, "Network error", "Netzwerkfehler")
        }
      }));
    }
  }, [enabled, language]);

  const resetArtistDrilldown = useCallback(() => {
    setArtistDrilldown({ artist: null, status: "idle", items: [] });
  }, []);

  return {
    librarySection,
    setLibrarySection,
    collections,
    artistDrilldown,
    setArtistDrilldown,
    ensureLibrarySection,
    openArtistAlbums,
    searchCatalog,
    resetArtistDrilldown
  };
}
