/**
 * OpsToolKit - Main JavaScript
 *
 * Session timer, loading states, and UI utilities
 * Per FR-003: Display session timer and handle timeouts gracefully
 */

(function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const CONFIG = {
        SESSION_CHECK_INTERVAL: 60000,  // Check session every 60 seconds
        SESSION_WARNING_THRESHOLD: 300, // Warn when 5 minutes remaining
        LOADING_MIN_DISPLAY: 500        // Minimum time to show loading (ms)
    };

    // =========================================================================
    // Session Timer (T042)
    // =========================================================================

    /**
     * Format seconds into human-readable time string
     * @param {number} seconds - Number of seconds
     * @returns {string} Formatted time string
     */
    function formatTime(seconds) {
        if (seconds < 0) {
            return 'Expired';
        }

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) {
            return `${hours}h ${minutes}m remaining`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s remaining`;
        } else {
            return `${secs}s remaining`;
        }
    }

    /**
     * Update session timer display
     */
    async function updateSessionTimer() {
        const timerElement = document.getElementById('session-timer');

        if (!timerElement) {
            return;
        }

        try {
            // Fetch session info from backend
            const response = await fetch('/api/session/info');

            if (!response.ok) {
                timerElement.textContent = 'Session status unavailable';
                return;
            }

            const data = await response.json();

            if (!data.authenticated || !data.valid) {
                timerElement.textContent = 'Session expired';
                return;
            }

            const timeRemaining = data.time_remaining_seconds;
            const expiresReason = data.expires_reason;

            // Update timer display
            timerElement.textContent = formatTime(timeRemaining);

            // Add warning styling if time is low
            if (timeRemaining <= CONFIG.SESSION_WARNING_THRESHOLD) {
                timerElement.classList.add('text-warning');
                timerElement.classList.remove('text-muted');

                // Show warning notification once
                if (!window._sessionWarningShown) {
                    showSessionWarning(timeRemaining, expiresReason);
                    window._sessionWarningShown = true;
                }
            } else {
                timerElement.classList.remove('text-warning');
                timerElement.classList.add('text-muted');
            }

        } catch (error) {
            console.error('Error fetching session info:', error);
            timerElement.textContent = 'Session status unavailable';
        }
    }

    /**
     * Show session expiration warning
     * @param {number} timeRemaining - Seconds remaining
     * @param {string} reason - 'activity' or 'inactivity'
     */
    function showSessionWarning(timeRemaining, reason) {
        const message = reason === 'activity'
            ? `Your session will expire in ${formatTime(timeRemaining)} due to maximum activity time. Please save your work.`
            : `Your session will expire in ${formatTime(timeRemaining)} due to inactivity. Any activity will reset the timer.`;

        showNotification(message, 'warning', 10000);
    }

    /**
     * Initialize session timer
     */
    function initSessionTimer() {
        // Update immediately
        updateSessionTimer();

        // Update periodically
        setInterval(updateSessionTimer, CONFIG.SESSION_CHECK_INTERVAL);

        console.log('[SessionTimer] Session timer initialized');
    }

    // =========================================================================
    // Loading Overlay (T041)
    // =========================================================================

    let loadingTimeout = null;

    /**
     * Show loading overlay
     * @param {string} message - Optional loading message
     */
    function showLoading(message = 'Processing...') {
        const overlay = document.getElementById('loading-overlay');
        const messageElement = document.getElementById('loading-message');

        if (overlay && messageElement) {
            messageElement.textContent = message;
            overlay.classList.remove('d-none');

            // Ensure minimum display time for UX consistency
            loadingTimeout = Date.now();
        }
    }

    /**
     * Hide loading overlay
     */
    function hideLoading() {
        const overlay = document.getElementById('loading-overlay');

        if (!overlay) {
            return;
        }

        const minDisplayTime = CONFIG.LOADING_MIN_DISPLAY;
        const elapsed = Date.now() - (loadingTimeout || 0);
        const remaining = Math.max(0, minDisplayTime - elapsed);

        setTimeout(() => {
            overlay.classList.add('d-none');
        }, remaining);
    }

    /**
     * Show loading state on button
     * @param {HTMLButtonElement} button - Button element
     */
    function setButtonLoading(button, loading = true) {
        if (loading) {
            button.classList.add('btn-loading');
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = 'Processing...';
        } else {
            button.classList.remove('btn-loading');
            button.disabled = false;
            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        }
    }

    // =========================================================================
    // Progress Bar (T042)
    // =========================================================================

    /**
     * Update progress bar
     * @param {string} progressBarId - ID of progress bar element
     * @param {number} percentage - Progress percentage (0-100)
     * @param {string} label - Optional label text
     */
    function updateProgress(progressBarId, percentage, label = null) {
        const progressBar = document.getElementById(progressBarId);

        if (!progressBar) {
            return;
        }

        // Clamp percentage between 0 and 100
        percentage = Math.max(0, Math.min(100, percentage));

        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);

        if (label !== null) {
            progressBar.textContent = label;
        } else {
            progressBar.textContent = `${Math.round(percentage)}%`;
        }
    }

    // =========================================================================
    // Notifications
    // =========================================================================

    /**
     * Show a notification alert
     * @param {string} message - Message to display
     * @param {string} type - Alert type (success, danger, warning, info)
     * @param {number} duration - Duration to show (ms), 0 for permanent
     */
    function showNotification(message, type = 'info', duration = 5000) {
        const container = document.querySelector('.container');

        if (!container) {
            console.warn('No container found for notification');
            return;
        }

        // Create alert element
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.setAttribute('role', 'alert');

        // Add icon based on type
        let icon = 'info-circle-fill';
        if (type === 'success') icon = 'check-circle-fill';
        else if (type === 'danger' || type === 'error') icon = 'x-circle-fill';
        else if (type === 'warning') icon = 'exclamation-triangle-fill';

        alert.innerHTML = `
            <i class="bi bi-${icon}"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Insert at top of container
        container.insertBefore(alert, container.firstChild);

        // Auto-dismiss if duration is set
        if (duration > 0) {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, duration);
        }
    }

    // =========================================================================
    // Form Utilities
    // =========================================================================

    /**
     * Auto-show loading on form submit
     */
    function initFormLoadingHandlers() {
        const forms = document.querySelectorAll('form[data-loading="true"]');

        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                const submitButton = form.querySelector('button[type="submit"]');

                if (submitButton) {
                    setButtonLoading(submitButton, true);
                }

                const loadingMessage = form.dataset.loadingMessage || 'Processing...';
                showLoading(loadingMessage);
            });
        });
    }

    /**
     * File upload drag-and-drop enhancement
     */
    function initFileUploadHandlers() {
        const fileUploadAreas = document.querySelectorAll('.file-upload-area');

        fileUploadAreas.forEach(area => {
            const input = area.querySelector('input[type="file"]');

            if (!input) {
                return;
            }

            // Prevent default drag behaviors
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                area.addEventListener(eventName, preventDefaults, false);
            });

            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            // Highlight drop area
            ['dragenter', 'dragover'].forEach(eventName => {
                area.addEventListener(eventName, () => {
                    area.classList.add('dragover');
                });
            });

            ['dragleave', 'drop'].forEach(eventName => {
                area.addEventListener(eventName, () => {
                    area.classList.remove('dragover');
                });
            });

            // Handle dropped files
            area.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;

                input.files = files;

                // Trigger change event
                const event = new Event('change', { bubbles: true });
                input.dispatchEvent(event);
            });

            // Click area to open file dialog
            area.addEventListener('click', () => {
                input.click();
            });
        });
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize all UI utilities
     */
    function initialize() {
        console.log('[OpsToolKit] Initializing UI utilities...');

        // Initialize session timer if user is authenticated
        if (document.getElementById('session-timer')) {
            initSessionTimer();
        }

        // Initialize form loading handlers
        initFormLoadingHandlers();

        // Initialize file upload handlers
        initFileUploadHandlers();

        console.log('[OpsToolKit] UI utilities initialized');
    }

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // =========================================================================
    // Global Exports
    // =========================================================================

    window.OpsToolKit = {
        showLoading,
        hideLoading,
        setButtonLoading,
        updateProgress,
        showNotification,
        updateSessionTimer
    };
})();
