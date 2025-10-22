"""
RSS Manager Tool Routes.

Integrates with existing Node.js RSS Manager service.
Per FR-010: Manage RSS feed subscriptions through unified interface.
"""

import logging
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

# Create blueprint
rss_manager_bp = Blueprint('rss_manager', __name__, url_prefix='/tools/rss-manager')


def get_rss_service_url():
    """Get the RSS Manager service base URL from config."""
    return current_app.config.get('RSS_MANAGER_URL', 'http://localhost:3001')


def check_rss_service() -> bool:
    """
    Check if RSS Manager Node.js service is running.

    Returns:
        bool: True if service is available
    """
    try:
        response = requests.get(f"{get_rss_service_url()}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


@rss_manager_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display RSS Manager interface.

    Returns:
        Rendered RSS Manager template
    """
    logger.info(f"User {current_user.id} accessed RSS Manager")

    # Check if service is running
    service_available = check_rss_service()

    if not service_available:
        flash(
            'RSS Manager service is not running. Please start the Node.js service on port ' +
            str(current_app.config.get('RSS_MANAGER_PORT', 3001)),
            'warning'
        )

    return render_template(
        'tools/rss_manager.html',
        service_available=service_available,
        service_url=get_rss_service_url()
    )


@rss_manager_bp.route('/api/feeds', methods=['GET'])
@login_required
def get_feeds():
    """
    Get all RSS feeds from Node.js service.

    Returns:
        JSON response with feeds list
    """
    try:
        response = requests.get(f"{get_rss_service_url()}/api/feeds", timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Error fetching feeds: {e}")
        return jsonify({'error': 'Failed to fetch feeds from RSS service'}), 503


@rss_manager_bp.route('/api/feeds', methods=['POST'])
@login_required
def add_feed():
    """
    Add new RSS feed via Node.js service.

    Returns:
        JSON response with result
    """
    try:
        data = request.get_json()
        response = requests.post(
            f"{get_rss_service_url()}/api/feeds",
            json=data,
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Error adding feed: {e}")
        return jsonify({'error': 'Failed to add feed to RSS service'}), 503


@rss_manager_bp.route('/api/feeds/<int:feed_id>', methods=['PUT'])
@login_required
def update_feed(feed_id: int):
    """
    Update RSS feed via Node.js service.

    Args:
        feed_id: Feed ID to update

    Returns:
        JSON response with result
    """
    try:
        data = request.get_json()
        response = requests.put(
            f"{get_rss_service_url()}/api/feeds/{feed_id}",
            json=data,
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Error updating feed: {e}")
        return jsonify({'error': 'Failed to update feed in RSS service'}), 503


@rss_manager_bp.route('/api/feeds/<int:feed_id>', methods=['DELETE'])
@login_required
def delete_feed(feed_id: int):
    """
    Delete RSS feed via Node.js service.

    Args:
        feed_id: Feed ID to delete

    Returns:
        JSON response with result
    """
    try:
        response = requests.delete(
            f"{get_rss_service_url()}/api/feeds/{feed_id}",
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Error deleting feed: {e}")
        return jsonify({'error': 'Failed to delete feed from RSS service'}), 503


@rss_manager_bp.route('/api/feeds/<int:feed_id>/entries', methods=['GET'])
@login_required
def get_feed_entries(feed_id: int):
    """
    Get entries for specific RSS feed via Node.js service.

    Args:
        feed_id: Feed ID

    Returns:
        JSON response with feed entries
    """
    try:
        response = requests.get(
            f"{get_rss_service_url()}/api/feeds/{feed_id}/entries",
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        logger.error(f"Error fetching feed entries: {e}")
        return jsonify({'error': 'Failed to fetch feed entries from RSS service'}), 503
