// /static/js/modules/icons.js
// Lightweight icon system using SVG sprites

console.log("icons.js loaded");

// Icon name mapping (fa-* to SVG symbol ID)
const ICON_MAP = {
  'play': 'icon-play',
  'pause': 'icon-pause',
  'bell': 'icon-bell',
  'moon': 'icon-moon',
  'music': 'icon-music',
  'compact-disc': 'icon-disc',
  'volume-up': 'icon-volume',
  'random': 'icon-shuffle',
  'shuffle': 'icon-shuffle',
  'clock': 'icon-clock',
  'speaker': 'icon-speaker',
  'chevron-down': 'icon-chevron-down',
  'check': 'icon-check',
  'warning': 'icon-warning',
  'exclamation-triangle': 'icon-warning',
  'info-circle': 'icon-info',
  'info': 'icon-info'
};

// Inline SVG definitions for critical icons (no network request needed)
const INLINE_ICONS = {
  'icon-play': '<path d="M8 5v14l11-7z"/>',
  'icon-pause': '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>',
  'icon-bell': '<path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>',
  'icon-moon': '<path d="M12.43 2.3c-2.38-.59-4.68-.27-6.63.64-.35.16-.41.64-.1.86C8.3 5.6 10 8.6 10 12c0 3.4-1.7 6.4-4.3 8.2-.32.22-.26.7.09.86 1.28.6 2.71.94 4.21.94 6.05 0 10.85-5.38 9.87-11.6-.61-3.92-3.59-7.16-7.44-8.1z"/>',
  'icon-music': '<path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>',
  'icon-disc': '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z"/>'
};

/**
 * Creates an SVG icon element
 * @param {string} name - Icon name (e.g., 'play', 'pause', 'bell')
 * @param {Object} options - Options for the icon
 * @returns {string} - SVG HTML string
 */
export function icon(name, options = {}) {
  const { size = '', className = '' } = options;
  const symbolId = ICON_MAP[name] || `icon-${name}`;
  const sizeClass = size ? `icon-${size}` : '';
  const classes = ['icon', sizeClass, className].filter(Boolean).join(' ');
  
  // Use inline SVG for critical icons
  if (INLINE_ICONS[symbolId]) {
    return `<svg class="${classes}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${INLINE_ICONS[symbolId]}</svg>`;
  }
  
  // Fallback to sprite reference
  return `<svg class="${classes}" aria-hidden="true"><use href="/static/icons/icons.svg#${symbolId}"></use></svg>`;
}

/**
 * Returns play icon HTML
 */
export function playIcon() {
  return icon('play');
}

/**
 * Returns pause icon HTML
 */
export function pauseIcon() {
  return icon('pause');
}

/**
 * Replaces Font-Awesome icons with SVG icons
 * Called on page load to migrate existing fa-* elements
 */
export function migrateIcons() {
  // Find all Font-Awesome icons
  const faIcons = document.querySelectorAll('.fas, .far, .fa');
  
  faIcons.forEach(el => {
    // Extract icon name from class (e.g., fa-play -> play)
    const classes = Array.from(el.classList);
    const faClass = classes.find(c => c.startsWith('fa-') && c !== 'fa-fw');
    
    if (faClass) {
      const iconName = faClass.replace('fa-', '');
      const symbolId = ICON_MAP[iconName] || `icon-${iconName}`;
      
      // Check if we have this icon
      if (INLINE_ICONS[symbolId] || ICON_MAP[iconName]) {
        // Replace with SVG
        el.outerHTML = icon(iconName);
      }
      // If not found, Font-Awesome will handle it as fallback
    }
  });
}
