"""
Session management with timeout tracking.

Implements 4-hour activity timeout and 30-minute inactivity timeout.
Per FR-003 clarifications: Sessions expire after 4h activity OR 30min inactivity,
with unsaved work preserved in browser storage for recovery.
"""

from datetime import datetime, timedelta
from flask import session, request, current_app
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)


def check_session_timeout() -> tuple[bool, str]:
    """
    Check if current session has exceeded timeout limits.

    Per FR-003: Sessions expire after 4 hours of activity OR 30 minutes of inactivity.

    Returns:
        tuple[bool, str]: (is_expired, reason)
            - is_expired: True if session should be terminated
            - reason: 'activity' or 'inactivity' or None
    """
    if not current_user.is_authenticated:
        return (False, None)

    # Get session timestamps
    login_time_str = session.get('login_time')
    last_activity_str = session.get('last_activity')

    if not login_time_str or not last_activity_str:
        # Missing timestamps - session is invalid
        logger.warning(f"Session for {current_user.id} missing timestamps")
        return (True, 'invalid')

    try:
        login_time = datetime.fromisoformat(login_time_str)
        last_activity = datetime.fromisoformat(last_activity_str)
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing session timestamps: {e}")
        return (True, 'invalid')

    now = datetime.utcnow()

    # Get timeout thresholds from config
    activity_timeout = timedelta(seconds=current_app.config['SESSION_ACTIVITY_TIMEOUT'])
    inactivity_timeout = timedelta(seconds=current_app.config['SESSION_INACTIVITY_TIMEOUT'])

    # Check activity timeout (4 hours since login)
    time_since_login = now - login_time
    if time_since_login > activity_timeout:
        logger.info(f"Session for {current_user.id} exceeded activity timeout ({time_since_login})")
        return (True, 'activity')

    # Check inactivity timeout (30 minutes since last activity)
    time_since_activity = now - last_activity
    if time_since_activity > inactivity_timeout:
        logger.info(f"Session for {current_user.id} exceeded inactivity timeout ({time_since_activity})")
        return (True, 'inactivity')

    return (False, None)


def update_last_activity():
    """
    Update last_activity timestamp in session.

    Should be called on every request to track user activity.
    """
    if current_user.is_authenticated:
        session['last_activity'] = datetime.utcnow().isoformat()


def get_session_info() -> dict:
    """
    Get session information for debugging or display.

    Returns:
        dict: Session information including login time, last activity, and time remaining
    """
    if not current_user.is_authenticated:
        return {'authenticated': False}

    login_time_str = session.get('login_time')
    last_activity_str = session.get('last_activity')

    if not login_time_str or not last_activity_str:
        return {'authenticated': True, 'valid': False}

    try:
        login_time = datetime.fromisoformat(login_time_str)
        last_activity = datetime.fromisoformat(last_activity_str)
    except (ValueError, TypeError):
        return {'authenticated': True, 'valid': False}

    now = datetime.utcnow()

    # Calculate time remaining
    activity_timeout = timedelta(seconds=current_app.config['SESSION_ACTIVITY_TIMEOUT'])
    inactivity_timeout = timedelta(seconds=current_app.config['SESSION_INACTIVITY_TIMEOUT'])

    time_until_activity_timeout = activity_timeout - (now - login_time)
    time_until_inactivity_timeout = inactivity_timeout - (now - last_activity)

    # Time remaining is whichever comes first
    time_remaining = min(time_until_activity_timeout, time_until_inactivity_timeout)

    return {
        'authenticated': True,
        'valid': True,
        'username': current_user.id,
        'login_time': login_time.isoformat(),
        'last_activity': last_activity.isoformat(),
        'time_remaining_seconds': int(time_remaining.total_seconds()),
        'expires_reason': 'activity' if time_until_activity_timeout < time_until_inactivity_timeout else 'inactivity'
    }


def init_session_hooks(app):
    """
    Initialize session management hooks for Flask app.

    Registers before_request handler to check session timeouts and update activity.
    Per T027-T028: Add before_request hooks for session management.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def before_request_handler():
        """
        Check session timeout and update activity on every request.

        Per FR-003: Sessions expire after 4 hours of activity OR 30 minutes of inactivity.
        """
        # Skip for static files
        if request.endpoint and request.endpoint == 'static':
            return

        # Skip for login/logout endpoints (avoid redirect loops)
        if request.endpoint in ['landing.login', 'landing.logout', 'landing.index']:
            return

        # Check session timeout
        if current_user.is_authenticated:
            is_expired, reason = check_session_timeout()

            if is_expired:
                # Log user out due to timeout
                from flask_login import logout_user
                from flask import flash, redirect, url_for

                logout_user()
                session.clear()

                # Set message based on timeout reason
                if reason == 'activity':
                    message = 'Your session has expired after 4 hours of activity. Please log in again.'
                elif reason == 'inactivity':
                    message = 'Your session has expired after 30 minutes of inactivity. Please log in again.'
                else:
                    message = 'Your session has expired. Please log in again.'

                flash(message, 'warning')
                logger.info(f"Session expired due to {reason}, redirecting to login")

                return redirect(url_for('landing.login', next=request.url))

            # Update activity timestamp
            update_last_activity()

    app.logger.info("Session management hooks initialized (4h activity / 30min inactivity timeouts)")
