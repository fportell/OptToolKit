/**
 * Session Recovery - Browser Storage for Unsaved Work
 *
 * Per FR-003 clarifications: Preserves unsaved work in browser storage for recovery
 * after session timeout and re-login.
 *
 * Features:
 * - Auto-saves form data to localStorage on input changes (debounced)
 * - Restores saved data after successful re-authentication
 * - Clears saved data on successful form submission
 * - Handles multiple forms across different tools
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        DEBOUNCE_DELAY: 1000,        // 1 second debounce for saves
        STORAGE_PREFIX: 'opstoolkit_', // Prefix for localStorage keys
        EXPIRY_HOURS: 48,             // Clear saved data after 48 hours
        EXCLUDE_FIELDS: ['password', 'csrf_token', 'submit']  // Fields to never save
    };

    /**
     * Generate a unique storage key for a form
     * @param {HTMLFormElement} form - The form element
     * @returns {string} Storage key
     */
    function getFormStorageKey(form) {
        // Use form ID if available, otherwise use form action + method
        const formId = form.id || `${form.action}_${form.method}`;
        return `${CONFIG.STORAGE_PREFIX}form_${formId}`;
    }

    /**
     * Check if a field should be saved to localStorage
     * @param {HTMLElement} field - The form field
     * @returns {boolean} True if field should be saved
     */
    function shouldSaveField(field) {
        // Don't save excluded fields
        if (CONFIG.EXCLUDE_FIELDS.includes(field.name.toLowerCase())) {
            return false;
        }

        // Don't save password fields
        if (field.type === 'password') {
            return false;
        }

        // Don't save hidden fields (often contain CSRF tokens)
        if (field.type === 'hidden') {
            return false;
        }

        // Don't save submit buttons
        if (field.type === 'submit' || field.type === 'button') {
            return false;
        }

        return true;
    }

    /**
     * Get all form data as a plain object
     * @param {HTMLFormElement} form - The form element
     * @returns {Object} Form data
     */
    function getFormData(form) {
        const data = {};
        const elements = form.elements;

        for (let i = 0; i < elements.length; i++) {
            const field = elements[i];

            if (!field.name || !shouldSaveField(field)) {
                continue;
            }

            // Handle checkboxes
            if (field.type === 'checkbox') {
                data[field.name] = field.checked;
            }
            // Handle radio buttons
            else if (field.type === 'radio') {
                if (field.checked) {
                    data[field.name] = field.value;
                }
            }
            // Handle select-multiple
            else if (field.type === 'select-multiple') {
                const selected = [];
                for (let j = 0; j < field.options.length; j++) {
                    if (field.options[j].selected) {
                        selected.push(field.options[j].value);
                    }
                }
                data[field.name] = selected;
            }
            // Handle all other input types
            else {
                data[field.name] = field.value;
            }
        }

        return data;
    }

    /**
     * Save form data to localStorage
     * @param {HTMLFormElement} form - The form element
     */
    function saveFormData(form) {
        try {
            const storageKey = getFormStorageKey(form);
            const formData = getFormData(form);

            // Add metadata
            const savedData = {
                data: formData,
                timestamp: Date.now(),
                url: window.location.pathname
            };

            localStorage.setItem(storageKey, JSON.stringify(savedData));
            console.log(`[SessionRecovery] Saved form data for: ${storageKey}`);
        } catch (error) {
            console.error('[SessionRecovery] Error saving form data:', error);
            // localStorage might be full or disabled - fail silently
        }
    }

    /**
     * Restore form data from localStorage
     * @param {HTMLFormElement} form - The form element
     * @returns {boolean} True if data was restored
     */
    function restoreFormData(form) {
        try {
            const storageKey = getFormStorageKey(form);
            const savedDataStr = localStorage.getItem(storageKey);

            if (!savedDataStr) {
                return false;
            }

            const savedData = JSON.parse(savedDataStr);

            // Check if data is expired
            const ageHours = (Date.now() - savedData.timestamp) / (1000 * 60 * 60);
            if (ageHours > CONFIG.EXPIRY_HOURS) {
                console.log(`[SessionRecovery] Clearing expired data (${ageHours.toFixed(1)}h old)`);
                localStorage.removeItem(storageKey);
                return false;
            }

            // Check if we're on the same page
            if (savedData.url !== window.location.pathname) {
                console.log('[SessionRecovery] Saved data is for different page, ignoring');
                return false;
            }

            // Restore form fields
            const elements = form.elements;
            let restoredCount = 0;

            for (let i = 0; i < elements.length; i++) {
                const field = elements[i];

                if (!field.name || !shouldSaveField(field)) {
                    continue;
                }

                const savedValue = savedData.data[field.name];
                if (savedValue === undefined) {
                    continue;
                }

                // Restore based on field type
                if (field.type === 'checkbox') {
                    field.checked = savedValue;
                    restoredCount++;
                } else if (field.type === 'radio') {
                    if (field.value === savedValue) {
                        field.checked = true;
                        restoredCount++;
                    }
                } else if (field.type === 'select-multiple') {
                    for (let j = 0; j < field.options.length; j++) {
                        field.options[j].selected = savedValue.includes(field.options[j].value);
                    }
                    restoredCount++;
                } else {
                    field.value = savedValue;
                    restoredCount++;
                }
            }

            if (restoredCount > 0) {
                console.log(`[SessionRecovery] Restored ${restoredCount} fields from storage`);

                // Show notification to user
                showRecoveryNotification(form);
                return true;
            }

            return false;
        } catch (error) {
            console.error('[SessionRecovery] Error restoring form data:', error);
            return false;
        }
    }

    /**
     * Clear saved form data from localStorage
     * @param {HTMLFormElement} form - The form element
     */
    function clearFormData(form) {
        try {
            const storageKey = getFormStorageKey(form);
            localStorage.removeItem(storageKey);
            console.log(`[SessionRecovery] Cleared saved data for: ${storageKey}`);
        } catch (error) {
            console.error('[SessionRecovery] Error clearing form data:', error);
        }
    }

    /**
     * Show a notification that data was recovered
     * @param {HTMLFormElement} form - The form element
     */
    function showRecoveryNotification(form) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'alert alert-info alert-dismissible fade show';
        notification.setAttribute('role', 'alert');
        notification.innerHTML = `
            <strong>Work Restored!</strong> Your unsaved changes have been recovered.
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Insert before the form
        form.parentNode.insertBefore(notification, form);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    /**
     * Debounce function to limit save frequency
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Initialize session recovery for a form
     * @param {HTMLFormElement} form - The form element
     */
    function initializeForm(form) {
        // Skip login/logout forms
        if (form.action.includes('/auth/login') || form.action.includes('/auth/logout')) {
            return;
        }

        console.log(`[SessionRecovery] Initializing form: ${form.id || form.action}`);

        // Try to restore saved data on page load
        restoreFormData(form);

        // Create debounced save function
        const debouncedSave = debounce(() => saveFormData(form), CONFIG.DEBOUNCE_DELAY);

        // Add input listeners for auto-save
        form.addEventListener('input', debouncedSave);
        form.addEventListener('change', debouncedSave);

        // Clear saved data on successful submission
        form.addEventListener('submit', () => {
            // Wait a moment to ensure submission is successful
            // If submission fails (validation error), data remains saved
            setTimeout(() => {
                // Only clear if we're navigating away or form indicates success
                if (document.readyState === 'unloading' || !form.querySelector('.is-invalid')) {
                    clearFormData(form);
                }
            }, 100);
        });
    }

    /**
     * Clean up old/expired data from localStorage
     */
    function cleanupExpiredData() {
        try {
            const now = Date.now();
            const expiryMs = CONFIG.EXPIRY_HOURS * 60 * 60 * 1000;

            // Iterate through localStorage keys
            for (let i = localStorage.length - 1; i >= 0; i--) {
                const key = localStorage.key(i);

                // Only check our keys
                if (!key || !key.startsWith(CONFIG.STORAGE_PREFIX)) {
                    continue;
                }

                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    if (data && data.timestamp && (now - data.timestamp > expiryMs)) {
                        localStorage.removeItem(key);
                        console.log(`[SessionRecovery] Cleaned up expired data: ${key}`);
                    }
                } catch (e) {
                    // Invalid JSON, remove it
                    localStorage.removeItem(key);
                }
            }
        } catch (error) {
            console.error('[SessionRecovery] Error during cleanup:', error);
        }
    }

    /**
     * Initialize session recovery for all forms on the page
     */
    function initialize() {
        console.log('[SessionRecovery] Initializing session recovery...');

        // Clean up old data first
        cleanupExpiredData();

        // Initialize all forms
        const forms = document.querySelectorAll('form');
        forms.forEach(form => initializeForm(form));

        console.log(`[SessionRecovery] Initialized ${forms.length} form(s)`);
    }

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // Export for manual initialization if needed
    window.SessionRecovery = {
        initialize,
        saveFormData,
        restoreFormData,
        clearFormData
    };
})();
