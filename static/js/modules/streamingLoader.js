// /static/js/modules/streamingLoader.js
// Progressive music library loading for instant UI updates
import { fetchAPI } from './api.js';

console.log("streamingLoader.js loaded");

// Unified constants
const DEFAULT_SECTIONS = ['playlists', 'albums', 'tracks', 'artists'];
const PRIORITY_ORDER = {
    'alarm_setup': ['playlists', 'albums', 'tracks', 'artists'],
    'sleep_timer': ['playlists', 'albums', 'tracks', 'artists'],  
    'music_browser': ['albums', 'playlists', 'artists', 'tracks'],
    'general': ['playlists', 'albums', 'tracks', 'artists']
};

/**
 * Progressive Music Library Loader - simplified and efficient
 */
class ProgressiveMusicLoader {
    constructor() {
        this.isLoading = false;
        this.userContext = this.detectUserContext();
        console.log('⚡ Progressive loader initialized');
    }
    
    /**
     * Load music library progressively section by section
     * @param {Object} options - Loading options
     * @returns {Promise<void>}
     */
    async loadProgressively(options = {}) {
        const {
            sections = DEFAULT_SECTIONS,
            onSectionLoaded = null,
            onProgress = null,
            onComplete = null,
            onError = null
        } = options;
        
        if (this.isLoading) {
            console.log('⚡ Loading already in progress, skipping');
            return;
        }
        
        this.isLoading = true;
        
        try {
            const sectionsToLoad = this.getSectionsByPriority(sections);
            console.log(`⚡ Loading ${sectionsToLoad.length} sections in batches...`);

            const batches = this.createBatches(sectionsToLoad);
            let completed = 0;

            for (const batch of batches) {
                const query = batch.join(',');
                console.log(`📋 Loading batch: ${query}`);

                try {
                    const response = await fetchAPI(`/api/music-library?sections=${encodeURIComponent(query)}&fields=basic`);

                    if (response?.success && response?.data) {
                        batch.forEach((section, index) => {
                            const sectionData = response.data[section] || [];
                            console.log(`✅ Loaded ${section}: ${sectionData.length} items`);

                            if (onSectionLoaded) {
                                onSectionLoaded(section, sectionData, {
                                    hasMetadata: true,
                                    sectionIndex: completed + index + 1,
                                    totalSections: sectionsToLoad.length,
                                    parallel: batch.length > 1
                                });
                            }

                            if (onProgress) {
                                onProgress({
                                    completed: completed + index + 1,
                                    total: sectionsToLoad.length,
                                    percentage: ((completed + index + 1) / sectionsToLoad.length) * 100
                                });
                            }
                        });
                    } else {
                        console.warn(`⚠️ No data received for batch ${query}`);
                    }
                } catch (error) {
                    console.error(`❌ Failed to load batch ${query}:`, error);
                }

                completed += batch.length;
            }

            console.log(`⚡ Batched loading completed: ${completed}/${sectionsToLoad.length} sections loaded`);
            if (onComplete) onComplete();

        } catch (error) {
            console.error('❌ Progressive loading failed:', error);
            if (onError) onError(error);
        } finally {
            this.isLoading = false;
        }
    }
    
    /**
     * Detect user context for prioritized loading
     */
    detectUserContext() {
        const hash = window.location.hash;
        
        if (hash.includes('alarm') || document.querySelector('#alarm-interface:not([style*="none"])')) {
            return 'alarm_setup';
        } else if (hash.includes('sleep') || document.querySelector('#sleep-interface:not([style*="none"])')) {
            return 'sleep_timer';
        } else if (hash.includes('library') || document.querySelector('#library-interface:not([style*="none"])')) {
            return 'music_browser';
        }
        
        return 'general';
    }
    
    /**
     * Get sections ordered by user context priority
     */
    getSectionsByPriority(sections) {
        const preferredOrder = PRIORITY_ORDER[this.userContext] || PRIORITY_ORDER['general'];
        
        // Return sections in preferred order
        const orderedSections = [];
        
        for (const section of preferredOrder) {
            if (sections.includes(section)) {
                orderedSections.push(section);
            }
        }
        
        // Add any remaining sections
        for (const section of sections) {
            if (!orderedSections.includes(section)) {
                orderedSections.push(section);
            }
        }
        
        return orderedSections;
    }

    /**
     * Create batched groups of sections to reduce HTTP round trips
     */
    createBatches(sections) {
        if (!Array.isArray(sections) || sections.length === 0) {
            return [];
        }

        // Heuristic: if more than 2 sections remain, fetch them two at a time; otherwise as singletons
        const batches = [];
        const queue = [...sections];
        
        while (queue.length > 0) {
            if (queue.length >= 2) {
                batches.push(queue.splice(0, 2));
            } else {
                batches.push([queue.shift()]);
            }
        }

        return batches;
    }
}

// Global loader instance
let progressiveLoader = null;

/**
 * Initialize global progressive loader
 */
export function initializeStreamingLoader() {
    progressiveLoader = new ProgressiveMusicLoader();
    window.streamingLoader = progressiveLoader; // For debugging
    return progressiveLoader;
}

/**
 * Get global progressive loader instance
 */
export function getStreamingLoader() {
    if (!progressiveLoader) {
        progressiveLoader = initializeStreamingLoader();
    }
    return progressiveLoader;
}

/**
 * Load music library progressively for playlist selectors
 * @param {Object} selectors - Object containing playlist selectors
 * @param {Object} options - Loading options
 */
export async function loadMusicLibraryProgressively(selectors = {}, options = {}) {
    const loader = getStreamingLoader();
    
    const loadingOptions = {
        sections: options.sections || DEFAULT_SECTIONS,
        
        onSectionLoaded: (section, data, meta) => {
            console.log(`📊 Section loaded: ${section} (${data.length} items)`);
            
            // Update all active selectors immediately
            const sectionData = { [section]: data };
            
            Object.values(selectors).forEach(selector => {
                if (selector) {
                    selector.setMusicLibrary(sectionData, { merge: true, source: 'progressive' });
                }
            });
        },
        
        onProgress: options.onProgress,
        onComplete: options.onComplete,
        onError: options.onError
    };
    
    await loader.loadProgressively(loadingOptions);
}
