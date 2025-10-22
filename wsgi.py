"""
WSGI entry point for OpsToolKit application.

This file is used by WSGI servers (gunicorn, uWSGI, etc.) to run the application.

Usage:
    Development:
        python wsgi.py

    Production with gunicorn:
        gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

    Production with uWSGI:
        uwsgi --http :5000 --wsgi-file wsgi.py --callable app --processes 4
"""

import os
from app import create_app

# Create application instance
# Environment determined by FLASK_ENV (default: development)
env = os.getenv('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    # Run development server
    debug = env == 'development'
    port = int(os.getenv('PORT', 5000))

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
