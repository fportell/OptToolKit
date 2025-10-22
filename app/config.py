"""
Configuration module for OpsToolKit Integrated Tools Platform.

Loads configuration from environment variables and provides default values.
Per plan.md: Session timeouts, file limits, concurrent users configuration.
"""

import os
from pathlib import Path
from typing import Dict, Any


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
    SESSION_TYPE = os.getenv('SESSION_TYPE', 'filesystem')  # or 'redis'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True

    # Session timeouts (in seconds)
    # Per clarification: 4 hours of activity OR 30 minutes of inactivity
    SESSION_ACTIVITY_TIMEOUT = int(os.getenv('SESSION_ACTIVITY_TIMEOUT', '14400'))  # 4 hours
    SESSION_INACTIVITY_TIMEOUT = int(os.getenv('SESSION_INACTIVITY_TIMEOUT', '1800'))  # 30 minutes

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

    # DR-Tracker timeout (in seconds)
    DR_TRACKER_TIMEOUT_SECONDS = int(os.getenv('DR_TRACKER_TIMEOUT_SECONDS', '120'))  # 2 minutes

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

    DR_TRACKER_DATA_PATH = BASE_DIR / os.getenv(
        'DR_TRACKER_DATA_PATH',
        'app/services/dr_tracker/data/'
    )

    # =========================================================================
    # RSS Manager Configuration (Node.js Express)
    # =========================================================================
    RSS_MANAGER_PORT = int(os.getenv('RSS_MANAGER_PORT', '3001'))
    RSS_MANAGER_URL = f"http://localhost:{RSS_MANAGER_PORT}"

    RSS_DATABASE_PATH = BASE_DIR / os.getenv(
        'RSS_DATABASE_PATH',
        'legacy_code/rss-manager/database/rss_subscriptions.db'
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
