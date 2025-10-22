"""
Landing page and authentication routes.

Implements login/logout functionality and tools landing page.
Per FR-001, FR-002, FR-005: Authentication and landing page display.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import User, check_credentials
import logging

logger = logging.getLogger(__name__)

# Create blueprint
landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def index():
    """
    Root route - redirect to landing page or login.

    Returns:
        Redirect to tools landing page if authenticated, otherwise to login.
    """
    if current_user.is_authenticated:
        return redirect(url_for('landing.tools'))
    return redirect(url_for('landing.login'))


@landing_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    """
    Login page and authentication handler.

    Per FR-001: System MUST provide a login page that accepts username and password.
    Per FR-002: System MUST validate user credentials against stored single-user configuration.

    GET: Display login form
    POST: Validate credentials and create session

    Returns:
        GET: Rendered login template
        POST: Redirect to tools page on success, or redisplay form with error
    """
    # If already authenticated, redirect to tools
    if current_user.is_authenticated:
        logger.info(f"User {current_user.id} already authenticated, redirecting to tools")
        return redirect(url_for('landing.tools'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Validate input
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            logger.warning("Login attempt with missing credentials")
            return render_template('login.html')

        # Check credentials
        if check_credentials(username, password):
            # Create user object and log in
            user = User(username)
            login_user(user, remember=False)

            # Initialize session timestamps (will be used by session_manager in T024-T031)
            from datetime import datetime
            session['login_time'] = datetime.utcnow().isoformat()
            session['last_activity'] = datetime.utcnow().isoformat()

            logger.info(f"User {username} logged in successfully from {request.remote_addr}")
            flash('Login successful!', 'success')

            # Redirect to originally requested page or tools landing
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('landing.tools'))
        else:
            # Invalid credentials
            flash('Invalid username or password. Please try again.', 'danger')
            logger.warning(f"Failed login attempt for username: {username} from {request.remote_addr}")
            return render_template('login.html')

    # GET request - display login form
    return render_template('login.html')


@landing_bp.route('/auth/logout', methods=['POST', 'GET'])
@login_required
def logout():
    """
    Logout handler.

    Per FR-015: System MUST support logout functionality that clears session and returns to login.

    Returns:
        Redirect to login page
    """
    username = current_user.id if current_user.is_authenticated else 'unknown'

    # Clear session and log out
    logout_user()
    session.clear()

    logger.info(f"User {username} logged out from {request.remote_addr}")
    flash('You have been logged out successfully.', 'info')

    return redirect(url_for('landing.login'))


@landing_bp.route('/tools')
@login_required
def tools():
    """
    Tools landing page displaying all 5 available tools.

    Per FR-005: System MUST provide a tools landing page displaying all five tools
    with names and descriptions.

    Returns:
        Rendered landing page with tool cards
    """
    from flask import current_app

    from app.concurrency_manager import get_active_user_count, should_display_performance_warning

    # Get tool definitions from config (will be defined in T047)
    tools_list = current_app.config.get('TOOLS', [])

    # Get concurrent user count (T032-T037)
    concurrent_user_count = get_active_user_count()
    show_warning = should_display_performance_warning()

    logger.info(f"User {current_user.id} accessed tools landing page")

    return render_template('landing.html',
                          tools=tools_list,
                          concurrent_user_count=concurrent_user_count,
                          show_warning=show_warning)


@landing_bp.route('/api/session/info')
@login_required
def session_info():
    """
    Get current session information for session timer.

    Returns:
        JSON response with session details
    """
    from flask import jsonify
    from app.session_manager import get_session_info

    info = get_session_info()
    return jsonify(info), 200


@landing_bp.route('/health')
def health():
    """
    Health check endpoint for monitoring.

    Returns:
        JSON response with service status
    """
    from flask import jsonify, current_app
    from datetime import datetime

    # Check if essential services are configured
    status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': current_app.config.get('VERSION', '0.1.0'),
        'services': {
            'flask': 'up',
            'openai_configured': bool(current_app.config.get('OPENAI_API_KEY')),
        }
    }

    return jsonify(status), 200
