// /static/js/modules/deviceManager.js
// Handles automatic device loading, change detection, and UI updates
import { refreshDevicesWithChangeDetection } from './api.js';
import { t } from './translation.js';

console.log("deviceManager.js loaded");

class DeviceManager {
    constructor() {
        this.currentDevices = [];
        this.isRefreshing = false;
        this.refreshInterval = null;
        this.refreshIntervalMs = 45000; // 45 seconds
        this.fastRefreshOnFocus = true;
        
        // Track device selectors for updates
        this.deviceSelectors = [];
        
        console.log('🔄 Device Manager initialized');
    }

    /**
     * Initialize device manager with automatic refresh
     */
    initialize() {
        // Find all device selectors on the page
        this.scanForDeviceSelectors();
        
        // Initial load
        this.refreshDevices(true);
        
        // Set up periodic refresh
        this.startPeriodicRefresh();
        
        // Refresh on page visibility change (user returns to tab)
        if (this.fastRefreshOnFocus) {
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    console.log('🔄 Page visible, refreshing devices');
                    this.refreshDevices();
                }
            });
        }
    }

    /**
     * Scan page for device selector elements
     */
    scanForDeviceSelectors() {
        const selectors = document.querySelectorAll('select[name="device_name"]');
        this.deviceSelectors = Array.from(selectors);
        console.log(`🔍 Found ${this.deviceSelectors.length} device selectors`);
        
        // Add focus listeners to refresh devices when user opens selector
        this.deviceSelectors.forEach(selector => {
            selector.addEventListener('focus', () => {
                console.log('🔄 Device selector focused, refreshing devices');
                this.refreshDevices();
            });
            
            // Add loading state support
            if (!selector.dataset.deviceManagerReady) {
                selector.dataset.deviceManagerReady = 'true';
            }
        });
    }

    /**
     * Start periodic device refresh
     */
    startPeriodicRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        this.refreshInterval = setInterval(() => {
            if (!document.hidden) {
                console.log('🔄 Periodic device refresh');
                this.refreshDevices();
            }
        }, this.refreshIntervalMs);
        
        console.log(`⏰ Periodic device refresh started (${this.refreshIntervalMs / 1000}s interval)`);
    }

    /**
     * Stop periodic refresh
     */
    stopPeriodicRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            console.log('⏰ Periodic device refresh stopped');
        }
    }

    /**
     * Refresh devices from Spotify API
     * @param {boolean} force - Force refresh even if already refreshing
     */
    async refreshDevices(force = false) {
        if (this.isRefreshing && !force) {
            console.log('⏳ Device refresh already in progress, skipping');
            return;
        }

        this.isRefreshing = true;
        this.setLoadingState(true);

        try {
            const result = await refreshDevicesWithChangeDetection(this.currentDevices);
            
            if (result.hasChanges || force) {
                this.currentDevices = result.devices;
                this.updateDeviceSelectors(result.devices);
                
                if (result.hasChanges) {
                    this.notifyDeviceChanges(result.devices);
                }
            }
            
        } catch (error) {
            console.error('❌ Device refresh failed:', error);
            this.handleRefreshError(error);
        } finally {
            this.isRefreshing = false;
            this.setLoadingState(false);
        }
    }

    /**
     * Update all device selector elements
     * @param {Array} devices - Array of device objects
     */
    updateDeviceSelectors(devices) {
        this.deviceSelectors.forEach(selector => {
            const currentValue = selector.value;
            
            // Clear existing options
            selector.innerHTML = '';
            
            if (devices.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = t('no_devices_found') || 'Keine Geräte gefunden';
                selector.appendChild(option);
                return;
            }

            // Add device options
            devices.forEach(device => {
                if (!device || !device.name) return;
                
                const option = document.createElement('option');
                option.value = device.name;
                option.textContent = `${device.name} (${device.type || '?'})`;
                
                // Mark active device with text indicator (HTML doesn't work in <option> tags)
                if (device.is_active) {
                    option.selected = true;
                    option.textContent += ' - active';
                }
                
                selector.appendChild(option);
            });

            // Restore previous selection if still available
            if (currentValue && Array.from(selector.options).some(o => o.value === currentValue)) {
                selector.value = currentValue;
            }
        });

        console.log(`✅ Updated ${this.deviceSelectors.length} device selectors with ${devices.length} devices`);
    }

    /**
     * Set loading state for device selectors
     * @param {boolean} isLoading - Whether devices are being loaded
     */
    setLoadingState(isLoading) {
        const activeElement = document.activeElement;

        this.deviceSelectors.forEach(selector => {
            if (isLoading) {
                selector.classList.add('loading');

                // Keep the actively used selector enabled so mobile dropdowns stay open
                const shouldDisable = selector !== activeElement;
                selector.disabled = shouldDisable;

                // Show loading indicator while options are being fetched
                if (selector.children.length === 0) {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = t('loading_devices') || 'Lade Geräte...';
                    selector.appendChild(option);
                }
            } else {
                selector.classList.remove('loading');
                selector.disabled = false;
            }
        });
    }

    /**
     * Handle device refresh errors
     * @param {Error} error - The error that occurred
     */
    handleRefreshError(error) {
        // Show fallback message in selectors
        this.deviceSelectors.forEach(selector => {
            if (selector.children.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = t('device_load_error') || 'Fehler beim Laden der Geräte';
                selector.appendChild(option);
            }
        });
    }

    /**
     * Notify about device changes (optional visual feedback)
     * @param {Array} devices - Current device list
     */
    notifyDeviceChanges(devices) {
        // Could add subtle UI notification here
        const activeDevice = devices.find(d => d.is_active);
        if (activeDevice) {
            console.log(`🎵 Active device: ${activeDevice.name}`);
        }
    }

    /**
     * Force refresh devices (public API)
     */
    async forceRefresh() {
        console.log('🔄 Force refresh requested');
        await this.refreshDevices(true);
    }

    /**
     * Get current devices (public API)
     * @returns {Array} Current device list
     */
    getCurrentDevices() {
        return [...this.currentDevices];
    }

    /**
     * Cleanup resources
     */
    destroy() {
        this.stopPeriodicRefresh();
        this.deviceSelectors = [];
        this.currentDevices = [];
        console.log('🔄 Device Manager destroyed');
    }
}

// Global device manager instance
let deviceManager = null;

/**
 * Initialize global device manager
 */
export function initializeDeviceManager() {
    if (deviceManager) {
        deviceManager.destroy();
    }
    
    deviceManager = new DeviceManager();
    deviceManager.initialize();
    
    // Make available globally for debugging
    window.deviceManager = deviceManager;
    
    return deviceManager;
}

/**
 * Get global device manager instance
 */
export function getDeviceManager() {
    return deviceManager;
}

/**
 * Force refresh devices via global manager
 */
export async function forceRefreshDevices() {
    if (deviceManager) {
        await deviceManager.forceRefresh();
    }
}
