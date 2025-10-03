// /static/js/modules/state.js
// Manages the application's state

console.log("state.js loaded");

export const CONFIG = {
    SYNC_COOLDOWN: 2000,          // 2 seconds cooldown after user interaction
    UPDATE_INTERVALS: {
      DASHBOARD: 4000,            // Combined dashboard refresh interval (ms)
      SLEEP_TICK: 1000            // Local countdown tick interval (ms)
    }
};

// Mutable state variables
export let userIsDragging = false;
export let lastUserInteraction = 0;
let activeDeviceInfo = { id: null, name: null, type: null };

export function setUserIsDragging(value) {
    userIsDragging = value;
}

export function setLastUserInteraction(value) {
    lastUserInteraction = value;
}

export function setActiveDevice(device) {
    if (device && typeof device === 'object') {
        activeDeviceInfo = {
            id: device.id || null,
            name: device.name || null,
            type: device.type || null
        };
    } else {
        activeDeviceInfo = { id: null, name: null, type: null };
    }
}

export function getActiveDevice() {
    return activeDeviceInfo;
}


// Central DOM element cache for frequently used elements
export const DOM = {
    getElement(id) {
        if (!this._cache) this._cache = {};
        if (!this._cache[id]) this._cache[id] = document.getElementById(id);
        return this._cache[id];
    },

    getElements(selectors) {
        const elements = {};
        for (const key in selectors) {
            if (selectors[key].startsWith('#')) {
                // ID-Selector
                elements[key] = this.getElement(selectors[key].substring(1));
            } else {
                // General CSS selector
                elements[key] = document.querySelector(selectors[key]);
            }
        }
        return elements;
    },

    clearCache() {
        this._cache = {};
    }
};
