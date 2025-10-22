"""
OpsToolKit - Integrated Tools Platform

Flask application factory for unified web application integrating 5 operational tools.
Per plan.md: Hybrid Flask + Node.js architecture with Bootstrap 5 frontend.
"""

import os
import logging
from pathlib import Path
from flask import Flask
from flask_session import Session

# Application version
__version__ = '0.1.0'


def create_app(config_name: str = None) -> Flask:
    """Flask application factory."""
    # Create Flask app
    app = Flask(__name__,
                instance_relative_config=True,
                template_folder='templates',
                static_folder='static')

    # Load configuration
    from app.config import get_config
    config = get_config(config_name)
    app.config.from_object(config)

    # Ensure directories exist
    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    log_file = Path(app.config['LOG_FILE'])
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    setup_logging(app)

    # Initialize extensions
    init_extensions(app)

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Initialize session management hooks
    from app.session_manager import init_session_hooks
    init_session_hooks(app)

    # Initialize concurrency management hooks
    from app.concurrency_manager import init_concurrency_hooks
    init_concurrency_hooks(app)

    app.logger.info(f"OpsToolKit v{__version__} initialized")

    return app


def setup_logging(app: Flask) -> None:
    """Configure application logging."""
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper(), logging.INFO)
    
    file_handler = logging.FileHandler(app.config['LOG_FILE'])
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s'
    ))
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(log_level)


def init_extensions(app: Flask) -> None:
    """Initialize Flask extensions."""
    Session(app)
    from app import auth
    auth.init_app(app)


def register_blueprints(app: Flask) -> None:
    """Register application blueprints (routes)."""
    from app.routes.landing import landing_bp
    from app.routes.tools.geolocation import geolocation_bp
    from app.routes.tools.summary_revision import summary_revision_bp
    from app.routes.tools.dr_tracker import dr_tracker_bp
    from app.routes.tools.chatbot import chatbot_bp

    app.register_blueprint(landing_bp)
    app.register_blueprint(geolocation_bp)
    app.register_blueprint(summary_revision_bp)
    app.register_blueprint(dr_tracker_bp)
    app.register_blueprint(chatbot_bp)
    app.logger.info("Blueprints registered: landing, geolocation, summary_revision, dr_tracker, chatbot")


def register_error_handlers(app: Flask) -> None:
    """Register error handlers per FR-014."""
    from flask import jsonify, request

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Authentication required', 'redirect': '/auth/login'}), 401

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found', 'path': request.path}), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
