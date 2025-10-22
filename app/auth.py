"""
Authentication module for OpsToolKit Integrated Tools Platform.

Implements Flask-Login for single-user authentication with shared credentials.
Per FR-001, FR-002: Simple username/password authentication.
Per Constitution Exception: Basic auth approved for prototype/single-user scenario.
"""

import os
from flask_login import LoginManager, UserMixin
from typing import Optional


# Initialize Flask-Login manager
login_manager = LoginManager()
login_manager.login_view = 'landing.login'  # Redirect to login page if not authenticated
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


class User(UserMixin):
    """
    Simple user model for single-user authentication.

    Attributes:
        id (str): Username (serves as unique identifier)
    """

    def __init__(self, username: str):
        """
        Initialize user with username.

        Args:
            username (str): The username for this user
        """
        self.id = username

    def __repr__(self) -> str:
        return f'<User {self.id}>'


@login_manager.user_loader
def load_user(username: str) -> Optional[User]:
    """
    Flask-Login user loader callback.

    Loads a user by username. Since we have single-user authentication,
    we only verify the username matches the configured APP_USERNAME.

    Args:
        username (str): The username to load

    Returns:
        Optional[User]: User object if username matches configured username, None otherwise
    """
    configured_username = os.getenv('APP_USERNAME')

    if not configured_username:
        # Configuration error - no username configured
        return None

    if username == configured_username:
        return User(username)

    return None


def check_credentials(username: str, password: str) -> bool:
    """
    Validate user credentials against environment variables.

    Per FR-002: System MUST validate user credentials against stored
    single-user configuration (shared username and password).

    Args:
        username (str): Username to validate
        password (str): Password to validate

    Returns:
        bool: True if credentials match configured values, False otherwise

    Security:
        - Credentials stored in environment variables (never in code)
        - Uses constant-time comparison to prevent timing attacks
    """
    configured_username = os.getenv('APP_USERNAME')
    configured_password = os.getenv('APP_PASSWORD')

    # Check that configuration is present
    if not configured_username or not configured_password:
        return False

    # Validate credentials (constant-time comparison for password)
    username_valid = username == configured_username

    # Use secrets.compare_digest for timing-attack-resistant password comparison
    import secrets
    try:
        password_valid = secrets.compare_digest(password, configured_password)
    except TypeError:
        # If types don't match, they're not equal
        password_valid = False

    return username_valid and password_valid


def init_app(app):
    """
    Initialize authentication for Flask application.

    Args:
        app: Flask application instance
    """
    login_manager.init_app(app)
