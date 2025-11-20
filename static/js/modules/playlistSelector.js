// /static/js/modules/playlistSelector.js
import { fetchAPI } from './api.js';
import { t } from './translation.js';
import { saveAlarmSettings } from './settings.js';

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
              grid.innerHTML = `<div class="playlist-no-results">${t('error_loading_music') || 'Fehler beim Laden der Musik'}</div>`;
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
      
      // Tabs HTML generieren - clean ohne Loading-Indikatoren
      tabsContainer.innerHTML = tabs.map(tab => `
        <button class="playlist-tab tab-button ${this.currentTab === tab.id ? 'active' : ''}" data-tab="${tab.id}">
          ${tab.label}
        </button>
      `).join('');
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
      const previewImage = this.container.querySelector('#preview-image');
      const previewName = this.container.querySelector('#preview-name');
      const previewMeta = this.container.querySelector('#preview-meta');
      
      if (this.selectedItem) {
        if (previewImage) {
          if (this.selectedItem.image_url) {
            previewImage.style.backgroundImage = `url(${this.selectedItem.image_url})`;
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
        
        grid.innerHTML = `
          <div class="music-library-loader">
            <div class="music-library-spinner"></div>
            <div class="music-library-loader-text">${tabLabels[this.currentTab]} werden geladen...</div>
          </div>
        `;
        return;
      }
      
      // Show "no results" if tab is loaded but has no items
      if (hasItemsForCurrentTab === 0 || this.filteredItems.length === 0) {
        const emptyText = this.currentTab === 'playlists' ? 
          (t('playlist_no_results') || 'Keine Playlists gefunden') : 
          this.currentTab === 'albums' ? (t('no_music_found') || 'Keine Alben gefunden') : 
          this.currentTab === 'artists' ? (t('no_music_found') || 'Keine Artists gefunden') : (t('no_music_found') || 'Keine Songs gefunden');
        grid.innerHTML = `<div class="playlist-no-results">${emptyText}</div>`;
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
      grid.innerHTML = this.filteredItems.map(item => {
        const isSelected = this.selectedItem && this.selectedItem.uri === item.uri;
        const imageStyle = item.image_url 
          ? `background-image: url(${item.image_url})` 
          : '';
        const trackCount = item.track_count || 0;
        const trackText = item.type === 'album' ? 'Tracks' : 'Songs';
        
        // Unterschiedliche Anzeige je nach Typ
        let metaText = '';
        if (item.type === 'playlist') {
          const creator = item.artist || 'Spotify';
          metaText = `${creator} · ${trackCount} Songs`;
        } else if (item.type === 'album') {
          const artist = item.artist || 'Unknown Artist';
          metaText = `${artist} · ${trackCount} Tracks`;
        } else if (item.type === 'artist') {
          metaText = item.artist || ''; // Follower info from artist field, or empty
        } else if (item.type === 'track' && item.artist) {
          metaText = item.artist; // Artist for individual songs
        } else if (item.type !== 'artist') {
          metaText = `${trackCount} ${trackText}`;
        }
        
        return `
          <div class="playlist-item ${isSelected ? 'selected' : ''}" data-uri="${item.uri}">
            <div class="playlist-item-image" style="${imageStyle}">
              ${!item.image_url ? (item.type === 'album' ? '💿' : item.type === 'artist' ? '🎤' : '📋') : ''}
            </div>
            <div class="playlist-item-info">
              <div class="playlist-item-name">${item.name}</div>
              <div class="playlist-item-meta">${metaText}</div>
            </div>
          </div>
        `;
      }).join('');
      
      this.attachItemClickListeners(grid);
    }
    
    renderItemsAsync(grid) {
      // Show loading during async render
      grid.innerHTML = `
        <div class="music-library-loader">
          <div class="music-library-spinner"></div>
          <div class="music-library-loader-text">${t('rendering') || 'Rendering'} ${this.filteredItems.length} ${this.currentTab === 'tracks' ? (t('songs') || 'songs') : (t('entries') || 'entries')}...</div>
        </div>
      `;
      
      // Render in chunks um UI responsive zu halten
      setTimeout(() => {
        const chunkSize = 20;
        let html = '';
        
        for (let i = 0; i < this.filteredItems.length; i += chunkSize) {
          const chunk = this.filteredItems.slice(i, i + chunkSize);
          chunk.forEach(item => {
            const isSelected = this.selectedItem && this.selectedItem.uri === item.uri;
            const imageStyle = item.image_url 
              ? `background-image: url(${item.image_url})` 
              : '';
            const trackCount = item.track_count || 0;
            const trackText = item.type === 'album' ? 'Tracks' : 'Songs';
            
            // Unterschiedliche Anzeige je nach Typ
            let metaText = '';
            if (item.type === 'playlist') {
              const creator = item.artist || 'Spotify';
              metaText = `${creator} · ${trackCount} Songs`;
            } else if (item.type === 'album') {
              const artist = item.artist || 'Unknown Artist';
              metaText = `${artist} · ${trackCount} Tracks`;
            } else if (item.type === 'artist') {
              metaText = item.artist || ''; // Follower info from artist field, or empty
            } else if (item.type === 'track' && item.artist) {
              metaText = item.artist; // Artist for individual songs
            } else if (item.type !== 'artist') {
              metaText = `${trackCount} ${trackText}`;
            }
            
            html += `
              <div class="playlist-item ${isSelected ? 'selected' : ''}" data-uri="${item.uri}">
                <div class="playlist-item-image" style="${imageStyle}">
                  ${!item.image_url ? (item.type === 'album' ? '💿' : item.type === 'artist' ? '🎤' : '📋') : ''}
                </div>
                <div class="playlist-item-info">
                  <div class="playlist-item-name">${item.name}</div>
                  <div class="playlist-item-meta">${metaText}</div>
                </div>
              </div>
            `;
          });
          
          // Alle 100 Items UI update damit es responsive bleibt
          if (i > 0 && i % 100 === 0) {
            setTimeout(() => {}, 1); // Yield to browser
          }
        }
        
        grid.innerHTML = html;
        this.attachItemClickListeners(grid);
      }, 10);
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
        grid.innerHTML = `
          <div class="music-library-loader">
            <div class="music-library-spinner"></div>
            <div class="music-library-loader-text">Lade Top-Tracks von ${artist.name}...</div>
          </div>
        `;
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
          grid.innerHTML = `<div class="playlist-no-results">Fehler beim Laden der Songs von ${artist.name}</div>`;
        }
      } catch (error) {
        console.error('Error loading artist top tracks:', error);
        if (grid) {
          grid.innerHTML = `<div class="playlist-no-results">Fehler beim Laden der Songs von ${artist.name}</div>`;
        }
      }
    }
    
    showArtistTracks(artist, tracks) {
      console.log(`🎵 Showing ${tracks.length} top tracks for ${artist.name}`);
      
      // Update the grid with tracks
      const grid = this.container.querySelector('#playlist-grid');
      if (!grid) return;
      
      // Add a back button and title
      const backButton = `
        <div class="artist-tracks-header">
          <button class="artist-back-button" onclick="window.playlistSelectors.library.returnToArtists()">
            ← Zurück zu Künstlern
          </button>
          <div class="artist-tracks-title">
            <h3>Top-Tracks: ${artist.name}</h3>
            <p>${tracks.length} Songs</p>
          </div>
        </div>
      `;
      
      // Render tracks similar to normal tracks
      const tracksHtml = tracks.map((track, index) => {
        const imageStyle = track.image_url ? `background-image: url(${track.image_url})` : '';
        
        return `
          <div class="playlist-item track-item" data-uri="${track.uri}" data-track-index="${index}">
            <div class="playlist-item-image" style="${imageStyle}">
              ${!track.image_url ? '🎵' : ''}
            </div>
            <div class="playlist-item-info">
              <div class="playlist-item-name">${track.name}</div>
              <div class="playlist-item-meta">${track.artist}</div>
            </div>
          </div>
        `;
      }).join('');
      
      grid.innerHTML = backButton + `<div class="artist-tracks-grid">${tracksHtml}</div>`;
      
      // Add click listeners for tracks
      grid.querySelectorAll('.track-item').forEach(item => {
        item.addEventListener('click', () => {
          const uri = item.dataset.uri;
          const trackIndex = parseInt(item.dataset.trackIndex);
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
        grid.innerHTML = `
          <div class="music-library-loader">
            <div class="music-library-spinner"></div>
            <div class="music-library-loader-text">${t('loading') || 'Loading'} ${tabName === 'playlists' ? (t('playlists') || 'playlists') : tabName === 'albums' ? (t('albums') || 'albums') : tabName === 'artists' ? (t('artists') || 'artists') : (t('songs') || 'songs')}...</div>
          </div>
        `;
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
