// /static/js/modules/playlistSelector.js
import { fetchAPI } from './api.js';
import { t } from './translation.js';
import { saveAlarmSettings } from './settings.js';

function getSafeImageUrl(candidate) {
  if (typeof candidate !== 'string' || !candidate.trim()) {
    return '';
  }

  try {
    const parsed = new URL(candidate, window.location.origin);
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
      return parsed.href;
    }
  } catch {
    // Ignore malformed URLs and fall back to icon.
  }

  return '';
}

export class PlaylistSelector {
    constructor(containerId, options = {}) {
      this.container = document.getElementById(containerId);
      if (!this.container) {
        console.warn(`⚠️ PlaylistSelector: Container '${containerId}' not found. Selector will be inactive.`);
        return;
      }
      this.options = {
        onSelect: options.onSelect || (() => {}),
        searchPlaceholder: options.searchPlaceholder || 'Playlist suchen...',
        noResultsText: options.noResultsText || t('no_music_found') || 'Keine Playlists gefunden',
        ...options
      };
      
      this.playlists = [];
      this.albums = [];
      this.tracks = [];
      this.artists = [];
    // Track which sections have been loaded to support lazy loading per tab
    this.loadedSections = new Set();
	      this.currentTab = 'playlists';
	      this.selectedItem = null;
	      this.isOpen = false;
	      this.filteredItems = [];
	      this.renderToken = 0;
	      
	      this.init();
	    }
    
    init() {
      if (!this.container) {
        console.error('Playlist selector container not found');
        return;
      }
  
      // Verwende existierendes HTML aus Templates statt render()
      this.addModalToExistingHTML();
      this.attachEvents();
    }
    
    addModalToExistingHTML() {
      // Check if modal already exists
      if (this.container.querySelector('#playlist-modal')) {
        return;
      }
      
      // Add modal with correct CSS structure
      const modalHTML = `
        <div class="playlist-modal" id="playlist-modal">
          <div class="playlist-modal-header">
            <div class="playlist-tabs tab-container" id="playlist-tabs">
              <!-- Tabs werden dynamisch generiert -->
            </div>
            <div class="playlist-search">
              <input type="text" id="playlist-search" placeholder="${this.options.searchPlaceholder}" class="form-input">
              <button class="playlist-close-btn" id="playlist-close">✕</button>
            </div>
          </div>
          <div class="playlist-grid" id="playlist-grid">
            <div class="music-library-loader">
              <div class="music-library-spinner"></div>
              <div class="music-library-loader-text">Musik-Bibliothek wird geladen...</div>
            </div>
          </div>
        </div>
      `;
      
      this.container.insertAdjacentHTML('beforeend', modalHTML);
      console.log('✅ Modal added to container:', this.container.id);
    }
    
    setPlaylists(playlists) {
      this.playlists = playlists || [];
      this.updateCurrentTab();
    }
    
    setAlbums(albums) {
      this.albums = albums || [];
      this.updateCurrentTab();
    }
    
    setMusicLibrary(data, options = {}) {
      if (!this.container) {
        console.warn('⚠️ PlaylistSelector: Cannot set music library, container not found');
        return;
      }
	      if (data?.error) {
	          this.playlists = [];
	          this.albums = [];
	          this.tracks = [];
	          this.artists = [];
	          this.createTabs(); // Will show nothing
	          this.updateCurrentTab(); // Will show "no results"
	          const grid = this.container.querySelector('#playlist-grid');
	          if (grid) {
	              grid.replaceChildren(this.createMessageNode(t('error_loading_music') || 'Fehler beim Laden der Musik'));
	          }
	          return;
	      }

      // Support merge mode for progressive loading
      if (options.merge) {
          // Merge new data with existing data, but deduplicate by URI
          if (data.playlists) {
              const existingUris = new Set(this.playlists.map(p => p.uri));
              const newPlaylists = data.playlists.filter(p => !existingUris.has(p.uri));
              this.playlists = [...this.playlists, ...newPlaylists];
          }
          if (data.albums) {
              const existingUris = new Set(this.albums.map(a => a.uri));
              const newAlbums = data.albums.filter(a => !existingUris.has(a.uri));
              this.albums = [...this.albums, ...newAlbums];
          }
          if (data.tracks) {
              const existingUris = new Set(this.tracks.map(t => t.uri));
              const newTracks = data.tracks.filter(t => !existingUris.has(t.uri));
              this.tracks = [...this.tracks, ...newTracks];
          }
          if (data.artists) {
              const existingUris = new Set(this.artists.map(a => a.uri));
              const newArtists = data.artists.filter(a => !existingUris.has(a.uri));
              this.artists = [...this.artists, ...newArtists];
          }
          
          console.log(`🔄 Merged with deduplication: ${this.playlists.length} playlists, ${this.albums.length} albums, ${this.tracks.length} tracks, ${this.artists.length} artists`);
      } else {
          // Traditional replacement mode
          this.playlists = data.playlists || [];
          this.albums = data.albums || [];
          this.tracks = data.tracks || [];
          this.artists = data.artists || [];
      }
      
      if (this.playlists.length) this.loadedSections.add('playlists');
      if (this.albums.length) this.loadedSections.add('albums');
      if (this.tracks.length) this.loadedSections.add('tracks');
      if (this.artists.length) this.loadedSections.add('artists');
      this.createTabs();
      this.updateCurrentTab();
    }
    
    createTabs() {
      if (!this.container) return;
      
      const tabsContainer = this.container.querySelector('#playlist-tabs');
      if (!tabsContainer) return;

      // Always show all 4 tabs with loading indicators
      const tabs = [
        {
          id: 'playlists',
          icon: '',
          label: 'Playlists',
          count: this.playlists.length,
          isLoaded: this.loadedSections.has('playlists')
        },
        {
          id: 'albums', 
          icon: '',
          label: 'Alben',
          count: this.albums.length,
          isLoaded: this.loadedSections.has('albums')
        },
        {
          id: 'tracks',
          icon: '',
          label: 'Songs',
          count: this.tracks.length,
          isLoaded: this.loadedSections.has('tracks')
        },
        {
          id: 'artists',
          icon: '',
          label: t('artists') || 'Artists',
          count: this.artists.length,
          isLoaded: this.loadedSections.has('artists')
        }
      ];
      
      // If current tab is not set, default to first tab
      if (!this.currentTab) {
        this.currentTab = 'playlists';
      }
      
	      tabsContainer.replaceChildren();
	      const fragment = document.createDocumentFragment();
	      tabs.forEach(tab => {
	        const button = document.createElement('button');
	        button.className = `playlist-tab tab-button${this.currentTab === tab.id ? ' active' : ''}`;
	        button.dataset.tab = tab.id;
	        button.type = 'button';
	        button.textContent = tab.label;
	        fragment.appendChild(button);
	      });
	      tabsContainer.appendChild(fragment);
	    }
    
    setSelected(itemUri) {
      // Find in playlists, albums, tracks, and artists
      this.selectedItem = this.playlists.find(p => p.uri === itemUri) || 
                         this.albums.find(a => a.uri === itemUri) ||
                         this.tracks.find(t => t.uri === itemUri) ||
                         this.artists.find(ar => ar.uri === itemUri) || null;
      this.updatePreview();
      this.updateModal();
    }
    
    attachEvents() {
      const input = this.container.querySelector('.playlist-input');
      
      console.log('🔧 Attaching events for:', this.container.id);
      console.log('📋 Input found:', !!input);
      
      // Toggle Modal
      input?.addEventListener('click', (e) => {
        console.log('🎵 Playlist input clicked!');
        e.preventDefault();
        this.toggle();
      });
      
      // Tab switching
      this.container.addEventListener('click', (e) => {
        if (e.target.classList.contains('tab-button')) {
          const newTab = e.target.dataset.tab;
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();
          this.switchTab(newTab);
          return false;
        } else if (e.target.id === 'playlist-close' || e.target.classList.contains('playlist-close-btn')) {
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();
          this.close();
          return false;
        }
      });
      
      this.container.querySelector('#playlist-search')?.addEventListener('input', (e) => {
        this.filterItems(e.target.value);
      });
      
      // ESC key to close
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.close();
        }
      });
    }
    
    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }
    
    open() {
      const input = this.container.querySelector('.playlist-input');
      const modal = this.container.querySelector('#playlist-modal');
      
      console.log('🎵 Opening modal...');
      console.log('📋 Input for toggle:', !!input);
      console.log('📋 Modal for toggle:', !!modal);
      
      input?.classList.add('active', 'modal-open');
      modal?.classList.add('show');
      this.isOpen = true;
      
      // iOS Safari scroll fix - multiple approaches
      setTimeout(() => {
        const container = this.container.querySelector('.form-group');
        if (container) {
          // Force layout recalculation
          container.offsetHeight;
          
          // Method 1: Try scrollIntoView with various options
          try {
            container.scrollIntoView({ 
              behavior: 'smooth', 
              block: 'start',
              inline: 'nearest'
            });
          } catch (e) {
            console.log('scrollIntoView failed:', e);
          }
          
          // Method 2: Direct element focus (iOS sometimes responds to this)
          setTimeout(() => {
            try {
              const rect = container.getBoundingClientRect();
              const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
              const elementTop = rect.top + scrollTop - 20;
              
              // Force scroll with multiple methods
              window.scrollTo({
                top: elementTop,
                behavior: 'smooth'
              });
              
              // Fallback for iOS
              document.documentElement.scrollTop = elementTop;
              document.body.scrollTop = elementTop;
              
            } catch (e) {
              console.log('Manual scroll failed:', e);
            }
          }, 100);
          
          // Method 3: iOS specific - focus an input to trigger scroll
          setTimeout(() => {
            const searchInput = this.container.querySelector('#playlist-search');
            if (searchInput) {
              searchInput.focus();
              searchInput.blur();
              searchInput.focus();
            }
          }, 200);
        }
      }, 200);
      
      // Focus search field after all scroll attempts
      setTimeout(() => {
        const search = this.container.querySelector('#playlist-search');
        if (search) {
          search.focus();
        }
      }, 500);
    }
    
    close() {
      const input = this.container.querySelector('.playlist-input');
      const modal = this.container.querySelector('#playlist-modal');
      const search = this.container.querySelector('#playlist-search');
      
      input?.classList.remove('active', 'modal-open');
      modal?.classList.remove('show');
      this.isOpen = false;
      
      // Clear search
      if (search) search.value = '';
      this.updateCurrentTab();
    }
    
	    updatePreview() {
	      const previewImage = this.container.querySelector('.playlist-preview-image');
	      const previewName = this.container.querySelector('.playlist-preview-name');
	      const previewMeta = this.container.querySelector('.playlist-preview-meta');
	      
	      if (this.selectedItem) {
	        if (previewImage) {
	          const safeImageUrl = getSafeImageUrl(this.selectedItem.image_url);
	          if (safeImageUrl) {
	            previewImage.style.backgroundImage = `url("${safeImageUrl}")`;
	            previewImage.textContent = '';
	          } else {
	            previewImage.style.backgroundImage = '';
	            previewImage.textContent = this.selectedItem.type === 'album' ? '💿' : '';
	          }
        }
        
        if (previewName) {
          previewName.textContent = this.selectedItem.name;
        }
        
        if (previewMeta) {
          if (this.selectedItem.type === 'playlist') {
            const trackCount = this.selectedItem.track_count || 0;
            const creator = this.selectedItem.artist || 'Spotify';
            previewMeta.textContent = `${creator} · ${trackCount} Songs`;
          } else if (this.selectedItem.type === 'album') {
            const trackCount = this.selectedItem.track_count || 0;
            const artist = this.selectedItem.artist || 'Unknown Artist';
            previewMeta.textContent = `${artist} · ${trackCount} Tracks`;
          } else if (this.selectedItem.type === 'artist') {
            // For artists, show follower count (stored in artist field)
            previewMeta.textContent = this.selectedItem.artist || '';
          } else if (this.selectedItem.type === 'track' && this.selectedItem.artist) {
            previewMeta.textContent = this.selectedItem.artist;
          } else {
            const trackCount = this.selectedItem.track_count || 0;
            const trackText = this.selectedItem.type === 'album' ? 'Tracks' : 'Songs';
            previewMeta.textContent = `${trackCount} ${trackText}`;
          }
        }
      } else {
        if (previewImage) {
          previewImage.style.backgroundImage = '';
          previewImage.textContent = '';
        }
        if (previewName) previewName.textContent = t('playlist_select_text') || 'Select music';
        if (previewMeta) previewMeta.textContent = '';
      }
    }
    
	    updateHiddenInput() {
	      const hiddenInput = this.container.querySelector('#playlist_uri');
	      if (hiddenInput) {
	        hiddenInput.value = this.selectedItem ? this.selectedItem.uri : '';
	      }
	    }

	    createLoaderNode(message) {
	      const loader = document.createElement('div');
	      loader.className = 'music-library-loader';

	      const spinner = document.createElement('div');
	      spinner.className = 'music-library-spinner';

	      const text = document.createElement('div');
	      text.className = 'music-library-loader-text';
	      text.textContent = message;

	      loader.appendChild(spinner);
	      loader.appendChild(text);
	      return loader;
	    }

	    createMessageNode(message) {
	      const messageNode = document.createElement('div');
	      messageNode.className = 'playlist-no-results';
	      messageNode.textContent = message;
	      return messageNode;
	    }

	    buildMetaText(item) {
	      const trackCount = item.track_count || 0;
	      const trackText = item.type === 'album' ? 'Tracks' : 'Songs';

	      if (item.type === 'playlist') {
	        const creator = item.artist || 'Spotify';
	        return `${creator} · ${trackCount} Songs`;
	      }
	      if (item.type === 'album') {
	        const artist = item.artist || 'Unknown Artist';
	        return `${artist} · ${trackCount} Tracks`;
	      }
	      if (item.type === 'artist') {
	        return item.artist || '';
	      }
	      if (item.type === 'track' && item.artist) {
	        return item.artist;
	      }
	      if (item.type !== 'artist') {
	        return `${trackCount} ${trackText}`;
	      }

	      return '';
	    }

	    createPlaylistItemElement(item, options = {}) {
	      const { isSelected = false, classNames = [], fallbackIcon = null } = options;
	      const root = document.createElement('div');
	      root.className = `playlist-item${isSelected ? ' selected' : ''}${classNames.length ? ` ${classNames.join(' ')}` : ''}`;
	      if (item?.uri) {
	        root.dataset.uri = item.uri;
	      }

	      const image = document.createElement('div');
	      image.className = 'playlist-item-image';
	      const safeImageUrl = getSafeImageUrl(item?.image_url);
	      if (safeImageUrl) {
	        image.style.backgroundImage = `url("${safeImageUrl}")`;
	      } else {
	        const iconText = fallbackIcon ?? (item?.type === 'album' ? '💿' : item?.type === 'artist' ? '🎤' : '📋');
	        image.textContent = iconText;
	      }

	      const info = document.createElement('div');
	      info.className = 'playlist-item-info';

	      const name = document.createElement('div');
	      name.className = 'playlist-item-name';
	      name.textContent = item?.name || '';

	      const meta = document.createElement('div');
	      meta.className = 'playlist-item-meta';
	      meta.textContent = this.buildMetaText(item || {});

	      info.appendChild(name);
	      info.appendChild(meta);
	      root.appendChild(image);
	      root.appendChild(info);
	      return root;
	    }
	    
	    updateModal() {
	      const grid = this.container.querySelector('#playlist-grid');
	      if (!grid) return;

      // Check if current tab section is still loading
      const currentTabLoaded = this.loadedSections.has(this.currentTab);
      const hasItemsForCurrentTab = this.filteredItems.length > 0;
      
      // Show loading state for current tab if not loaded yet
	      if (!currentTabLoaded) {
	        const tabLabels = {
	          playlists: 'Playlists',
	          albums: 'Alben', 
	          tracks: 'Songs',
	          artists: 'Artists'
	        };
	        grid.replaceChildren(this.createLoaderNode(`${tabLabels[this.currentTab]} werden geladen...`));
	        return;
	      }
	      
	      // Show "no results" if tab is loaded but has no items
	      if (hasItemsForCurrentTab === 0 || this.filteredItems.length === 0) {
	        const emptyText = this.currentTab === 'playlists' ? 
	          (t('playlist_no_results') || 'Keine Playlists gefunden') : 
	          this.currentTab === 'albums' ? (t('no_music_found') || 'Keine Alben gefunden') : 
	          this.currentTab === 'artists' ? (t('no_music_found') || 'Keine Artists gefunden') : (t('no_music_found') || 'Keine Songs gefunden');
	        grid.replaceChildren(this.createMessageNode(emptyText));
	        return;
	      }
      
      // Performance-Optimierung: Bei vielen Items (>100) asynchron rendern
      if (this.filteredItems.length > 100) {
        this.renderItemsAsync(grid);
        return;
      }
      
      // Standard rendering for smaller lists
	      this.renderItemsSync(grid);
	    }
	    
	    renderItemsSync(grid) {
	      const renderToken = ++this.renderToken;
	      const fragment = document.createDocumentFragment();
	      this.filteredItems.forEach(item => {
	        const isSelected = Boolean(this.selectedItem && this.selectedItem.uri === item.uri);
	        fragment.appendChild(this.createPlaylistItemElement(item, { isSelected }));
	      });

	      if (renderToken !== this.renderToken) {
	        return;
	      }

	      grid.replaceChildren(fragment);
	      
	      this.attachItemClickListeners(grid);
	    }
	    
	    renderItemsAsync(grid) {
	      const total = this.filteredItems.length;
	      const itemLabel = this.currentTab === 'tracks' ? (t('songs') || 'songs') : (t('entries') || 'entries');
	      grid.replaceChildren(this.createLoaderNode(`${t('rendering') || 'Rendering'} ${total} ${itemLabel}...`));

	      const renderToken = ++this.renderToken;
	      const items = [...this.filteredItems];
	      const chunkSize = 30;
	      let index = 0;

	      const renderChunk = () => {
	        if (renderToken !== this.renderToken) {
	          return;
	        }

	        if (index === 0) {
	          grid.replaceChildren();
	        }

	        const chunk = document.createDocumentFragment();
	        const end = Math.min(index + chunkSize, items.length);
	        for (let i = index; i < end; i += 1) {
	          const item = items[i];
	          const isSelected = Boolean(this.selectedItem && this.selectedItem.uri === item.uri);
	          chunk.appendChild(this.createPlaylistItemElement(item, { isSelected }));
	        }
	        grid.appendChild(chunk);
	        index = end;

	        if (index < items.length) {
	          requestAnimationFrame(renderChunk);
	          return;
	        }

	        this.attachItemClickListeners(grid);
	      };

	      requestAnimationFrame(renderChunk);
	    }
    
    attachItemClickListeners(grid) {
      grid.querySelectorAll('.playlist-item').forEach(item => {
        item.addEventListener('click', async () => {
    const uri = item.dataset.uri; // used to resolve selectedItem below
          const selectedItem = this.filteredItems.find(p => p.uri === uri);
          
          // Special handling for artists - load their top tracks
          if (selectedItem && selectedItem.type === 'artist' && selectedItem.artist_id) {
            await this.loadArtistTopTracks(selectedItem);
          } else {
            this.selectItem(selectedItem);
          }
        });
      });
    }
    
	    async loadArtistTopTracks(artist) {
	      console.log('🎤 Loading top tracks for artist:', artist.name);
	      
	      // Show loading state
	      const grid = this.container.querySelector('#playlist-grid');
	      if (grid) {
	        grid.replaceChildren(this.createLoaderNode(`Lade Top-Tracks von ${artist.name}...`));
	      }
      
      try {
        const response = await fetchAPI(`/api/artist-top-tracks/${artist.artist_id}`);
        
    // Support unified + legacy response shapes
	        if (response?.tracks || (response?._meta?.success && response?.tracks)) {
          // Create a special "artist tracks" view
          this.currentArtistTracks = {
            artist: artist,
            tracks: response.tracks
          };
          
          // Switch to a special artist-tracks mode
          this.showArtistTracks(artist, response.tracks);
	        } else {
	          console.error('Failed to load artist top tracks:', response);
	          if (grid) {
	            grid.replaceChildren(this.createMessageNode(`Fehler beim Laden der Songs von ${artist.name}`));
	          }
	        }
	      } catch (error) {
	        console.error('Error loading artist top tracks:', error);
	        if (grid) {
	          grid.replaceChildren(this.createMessageNode(`Fehler beim Laden der Songs von ${artist.name}`));
	        }
	      }
	    }
	    
	    showArtistTracks(artist, tracks) {
	      console.log(`🎵 Showing ${tracks.length} top tracks for ${artist.name}`);
      
	      // Update the grid with tracks
	      const grid = this.container.querySelector('#playlist-grid');
	      if (!grid) return;

	      const header = document.createElement('div');
	      header.className = 'artist-tracks-header';

	      const backButton = document.createElement('button');
	      backButton.className = 'artist-back-button';
	      backButton.type = 'button';
	      backButton.textContent = '← Zurück zu Künstlern';
	      backButton.addEventListener('click', () => this.returnToArtists());

	      const titleWrap = document.createElement('div');
	      titleWrap.className = 'artist-tracks-title';
	      const title = document.createElement('h3');
	      title.textContent = `Top-Tracks: ${artist.name}`;
	      const subtitle = document.createElement('p');
	      subtitle.textContent = `${tracks.length} Songs`;
	      titleWrap.appendChild(title);
	      titleWrap.appendChild(subtitle);

	      header.appendChild(backButton);
	      header.appendChild(titleWrap);

	      const tracksGrid = document.createElement('div');
	      tracksGrid.className = 'artist-tracks-grid';
	      tracks.forEach((track, index) => {
	        const trackNode = this.createPlaylistItemElement(track, {
	          classNames: ['track-item'],
	          fallbackIcon: '🎵'
	        });
	        trackNode.dataset.trackIndex = String(index);
	        tracksGrid.appendChild(trackNode);
	      });

	      grid.replaceChildren(header, tracksGrid);
	      
	      // Add click listeners for tracks
	      grid.querySelectorAll('.track-item').forEach(item => {
	        item.addEventListener('click', () => {
	          const uri = item.dataset.uri;
	          const trackIndex = parseInt(item.dataset.trackIndex, 10);
	          const track = tracks[trackIndex];
          
          // Select the track for playback
          this.selectItem(track);
        });
      });
    }
    
    returnToArtists() {
      console.log('🔙 Returning to artists view');
      this.currentArtistTracks = null;
      this.currentTab = 'artists';
      this.updateCurrentTab();
    }
    
	    switchTab(tabName) {
      this.currentTab = tabName;
      
      // Update tab buttons
      const tabs = this.container.querySelectorAll('.tab-button');
      tabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
      });
      
	      // Show loading immediately for new tabs
	      const grid = this.container.querySelector('#playlist-grid');
	      if (grid) {
	        const tabLabel = tabName === 'playlists'
	          ? (t('playlists') || 'playlists')
	          : tabName === 'albums'
	            ? (t('albums') || 'albums')
	            : tabName === 'artists'
	              ? (t('artists') || 'artists')
	              : (t('songs') || 'songs');
	        grid.replaceChildren(this.createLoaderNode(`${t('loading') || 'Loading'} ${tabLabel}...`));
	      }
      
      // Small delay for UI update
      setTimeout(() => {
        this.updateCurrentTab();
      }, 50);
    }
    
    updateCurrentTab() {
      let items;
      switch (this.currentTab) {
        case 'playlists':
          items = this.playlists;
          break;
        case 'albums':
          items = this.albums;
          break;
        case 'tracks':
          items = this.tracks;
          break;
        case 'artists':
          items = this.artists;
          break;
        default:
          items = this.playlists;
      }
      this.filteredItems = [...items];
      this.updateModal();
    }
    
    filterItems(searchTerm) {
      let currentItems;
      switch (this.currentTab) {
        case 'playlists':
          currentItems = this.playlists;
          break;
        case 'albums':
          currentItems = this.albums;
          break;
        case 'tracks':
          currentItems = this.tracks;
          break;
        case 'artists':
          currentItems = this.artists;
          break;
        default:
          currentItems = this.playlists;
      }
      
      if (!searchTerm) {
        this.filteredItems = [...currentItems];
      } else {
        const term = searchTerm.toLowerCase();
        this.filteredItems = currentItems.filter(item =>
          item.name.toLowerCase().includes(term) ||
          (item.artist?.toLowerCase().includes(term))
        );
      }
      this.updateModal();
    }
    
    selectItem(item) {
      this.selectedItem = item;
      this.updatePreview();
      this.updateHiddenInput();
      this.close();
      
      // Trigger callback
      if (this.options.onSelect) {
        this.options.onSelect(item);
      }
      
      // Jetzt MANUELL speichern, da wir das automatische Change-Event deaktiviert haben
      saveAlarmSettings();
    }
  }
