// /static/js/modules/translation.js
// Handles language translations

console.log("translation.js loaded");

/**
 * Translation function for JavaScript
 * @param {string} key - The key of the string to be translated
 * @param {Object} params - Parameters for replacing placeholders in the translation
 * @returns {string} - The translated string or the key itself if no translation was found
 */
export function t(key, params = {}) {
  if (!window.TRANSLATIONS || !window.TRANSLATIONS[key]) {
    console.warn(`Translation missing for key: ${key}`);
    return key; // Fallback
  }
  
  let translation = window.TRANSLATIONS[key];
  
  // Replace placeholders - robust implementation
  try {
    Object.keys(params).forEach(param => {
      const regex = new RegExp(`\\{${param}\\}`, 'g');
      translation = translation.replace(regex, params[param]);
    });
  } catch (error) {
    console.error(`Error in translation for key ${key}:`, error);
    return key;
  }
  
  return translation;
}
