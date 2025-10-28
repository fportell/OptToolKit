"""
Configuration module for OpsToolKit Integrated Tools Platform.

Loads configuration from environment variables and provides default values.
Per plan.md: Session timeouts, file limits, concurrent users configuration.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).parent.parent


class Config:
    """Base configuration class with defaults."""

    # =========================================================================
    # Flask Configuration
    # =========================================================================
    SECRET_KEY = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # =========================================================================
    # Session Management (per FR-003, clarifications)
    # =========================================================================
    SESSION_TYPE = os.getenv('SESSION_TYPE', 'null')  # Use 'null' for cookie-based sessions
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Session timeouts (in seconds)
    # Per clarification: 4 hours of activity OR 30 minutes of inactivity
    SESSION_ACTIVITY_TIMEOUT = int(os.getenv('SESSION_ACTIVITY_TIMEOUT', '14400'))  # 4 hours
    SESSION_INACTIVITY_TIMEOUT = int(os.getenv('SESSION_INACTIVITY_TIMEOUT', '1800'))  # 30 minutes

    # For filesystem session storage (if SESSION_TYPE='filesystem')
    SESSION_FILE_DIR = BASE_DIR / 'instance' / 'flask_session'
    SESSION_FILE_THRESHOLD = 500

    # For Redis session storage (if SESSION_TYPE='redis')
    SESSION_REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    SESSION_REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    SESSION_REDIS_DB = int(os.getenv('REDIS_DB', '0'))

    # =========================================================================
    # Authentication (per FR-001, FR-002)
    # =========================================================================
    # Note: Actual credentials loaded from environment in auth.py
    # This is just for validation
    REQUIRE_AUTH_CONFIG = True

    # =========================================================================
    # Concurrency Control (per FR-016, clarifications)
    # =========================================================================
    MAX_CONCURRENT_USERS = int(os.getenv('MAX_CONCURRENT_USERS', '5'))
    OPENAI_QUEUE_ENABLED = os.getenv('OPENAI_QUEUE_ENABLED', 'true').lower() == 'true'

    # =========================================================================
    # File Upload Limits (per FR-009, clarifications)
    # =========================================================================
    MAX_UPLOAD_SIZE_MB = int(os.getenv('MAX_UPLOAD_SIZE_MB', '10'))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Flask expects bytes

    # DR-Tracker configuration (Daily Report processing)
    DR_TRACKER_TIMEOUT = int(os.getenv('DR_TRACKER_TIMEOUT', '120'))  # OpenAI timeout in seconds
    DR_TRACKER_MAX_FILE_SIZE = int(os.getenv('DR_TRACKER_MAX_FILE_SIZE', str(5 * 1024 * 1024)))  # 5MB max
    DR_TRACKER_VBA_PATH = os.getenv('DR_TRACKER_VBA_PATH', 'app/data/dr_tracker/vbaProject.bin')
    DR_TRACKER_SESSION_TIMEOUT = int(os.getenv('DR_TRACKER_SESSION_TIMEOUT', '7200'))  # 2 hours

    # Chatbot upload configuration
    CHATBOT_UPLOAD_TIMEOUT = int(os.getenv('CHATBOT_UPLOAD_TIMEOUT', '6000'))  # 10 minutes for large uploads
    CHATBOT_BATCH_THRESHOLD = int(os.getenv('CHATBOT_BATCH_THRESHOLD', '2000'))  # Use batch API for 2000+ chunks (direct API can handle up to 2048 in one call)

    # =========================================================================
    # OpenAI Configuration (per FR-006, FR-008, FR-009)
    # =========================================================================
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    # Model defaults
    SUMMARY_REVISION_MODEL = os.getenv('SUMMARY_REVISION_MODEL', 'gpt-4.1')
    DR_TRACKER_MODEL = os.getenv('DR_TRACKER_MODEL', 'gpt-4.1')
    CHATBOT_MODEL = os.getenv('CHATBOT_MODEL', 'gpt-4.1')

    # =========================================================================
    # Data Asset Paths
    # =========================================================================
    GEOLOCATION_DB_PATH = BASE_DIR / os.getenv(
        'GEOLOCATION_DB_PATH',
        'app/services/geolocation/data/geolocations_db.tsv'
    )

    CHATBOT_KNOWLEDGE_BASE_PATH = BASE_DIR / os.getenv(
        'CHATBOT_KNOWLEDGE_BASE_PATH',
        'app/services/chatbot/data/DR_database_PBI.xlsx'
    )

    # DR-Tracker data files (hazards, program areas, VBA, preprompt)
    DR_TRACKER_DATA_DIR = BASE_DIR / 'app' / 'data' / 'dr_tracker'

    # =========================================================================
    # RSS Manager Configuration (Integrated Python/Flask)
    # =========================================================================
    RSS_DATABASE_PATH = BASE_DIR / os.getenv(
        'RSS_DATABASE_PATH',
        'app/data/rss_subscriptions.db'
    )

    # =========================================================================
    # Security (per constitution and plan.md)
    # =========================================================================
    HTTPS_ENABLED = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true'
    SECURE_COOKIES = os.getenv('SECURE_COOKIES', 'false').lower() == 'true'

    # Rate limiting (requests per minute)
    RATE_LIMIT_LOGIN = int(os.getenv('RATE_LIMIT_LOGIN', '5'))
    RATE_LIMIT_AI_OPERATIONS = int(os.getenv('RATE_LIMIT_AI_OPERATIONS', '20'))

    # =========================================================================
    # Logging
    # =========================================================================
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = BASE_DIR / os.getenv('LOG_FILE', 'logs/opstoolkit.log')

    # =========================================================================
    # Development Tools (per constitution)
    # =========================================================================
    ENABLE_MYPY = os.getenv('ENABLE_MYPY', 'true').lower() == 'true'
    ENABLE_PYTEST_COV = os.getenv('ENABLE_PYTEST_COV', 'true').lower() == 'true'
    COVERAGE_THRESHOLD = int(os.getenv('COVERAGE_THRESHOLD', '80'))

    # =========================================================================
    # Tools Configuration (per FR-005, T047)
    # =========================================================================
    TOOLS = [
        {
            'id': 'geolocation',
            'name': 'Geolocation Tool',
            'description': 'Country/region selection and area attribution for standardized reporting. Uses UN M49 regional standards to determine reporting language.',
            'icon': 'bi-geo-alt-fill',
            'color': 'primary',
            'url': '/tools/geolocation',
            'status': 'active'
        },
        {
            'id': 'summary-revision',
            'name': 'Summary Revision',
            'description': 'AI-powered content revision using OpenAI GPT-4. Review, improve, and refine text with intelligent suggestions.',
            'icon': 'bi-file-text',
            'color': 'success',
            'url': '/tools/summary-revision',
            'status': 'active'
        },
        {
            'id': 'dr-tracker',
            'name': 'DR-Tracker Builder',
            'description': 'Generate structured DR-Tracker reports from text prompts. Supports multiple output formats (CSV, JSON, XLSX).',
            'icon': 'bi-table',
            'color': 'warning',
            'url': '/tools/dr-tracker',
            'status': 'active'
        },
        {
            'id': 'chatbot',
            'name': 'DR Knowledge Chatbot',
            'description': 'Interactive chatbot powered by sentence-transformers and OpenAI. Query DR database with natural language.',
            'icon': 'bi-chat-dots',
            'color': 'info',
            'url': '/tools/chatbot',
            'status': 'active'
        },
        {
            'id': 'rss-manager',
            'name': 'RSS Manager',
            'description': 'Manage RSS feed subscriptions. Add, view, update, and delete feeds from a centralized dashboard.',
            'icon': 'bi-rss',
            'color': 'danger',
            'url': '/tools/rss-manager',
            'status': 'active'
        }
    ]

    @staticmethod
    def validate_config() -> Dict[str, Any]:
        """
        Validate that required configuration is present.

        Returns:
            Dict[str, Any]: Dictionary with 'valid' boolean and 'errors' list

        Example:
            result = Config.validate_config()
            if not result['valid']:
                for error in result['errors']:
                    print(f"Config error: {error}")
        """
        errors = []

        # Check required environment variables
        if not os.getenv('SESSION_SECRET'):
            errors.append("SESSION_SECRET not set - generate with: python -c \"import secrets; print(secrets.token_hex(32))\"")

        if not os.getenv('APP_USERNAME'):
            errors.append("APP_USERNAME not set")

        if not os.getenv('APP_PASSWORD'):
            errors.append("APP_PASSWORD not set")

        if not os.getenv('OPENAI_API_KEY'):
            errors.append("OPENAI_API_KEY not set")

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class DevelopmentConfig(Config):
    """Development-specific configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production-specific configuration."""
    DEBUG = False
    TESTING = False
    SECURE_COOKIES = True  # Force secure cookies in production
    HTTPS_ENABLED = True   # Force HTTPS in production


class TestingConfig(Config):
    """Testing-specific configuration."""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env: str = None) -> Config:
    """
    Get configuration object based on environment.

    Args:
        env (str, optional): Environment name. Defaults to FLASK_ENV environment variable.

    Returns:
        Config: Configuration object
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')

    return config.get(env, config['default'])
