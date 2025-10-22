"""
Integration tests for application routes.

Tests all tool routes and core functionality.
Per FR-005, FR-006, FR-007, FR-008, FR-009, FR-010.
"""

import pytest
import json
from io import BytesIO


class TestLandingRoutes:
    """Tests for landing page and core routes."""

    def test_root_redirect_unauthenticated(self, client):
        """Test root redirects to login when not authenticated."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_root_redirect_authenticated(self, auth_client):
        """Test root redirects to tools when authenticated."""
        response = auth_client.get('/', follow_redirects=True)
        assert response.status_code == 200
        assert b'tools' in response.data.lower()

    def test_tools_page_displays_all_tools(self, auth_client):
        """Test tools landing page shows all 5 tools (FR-005)."""
        response = auth_client.get('/tools')

        assert response.status_code == 200
        assert b'geolocation' in response.data.lower()
        assert b'summary' in response.data.lower() or b'revision' in response.data.lower()
        assert b'dr-tracker' in response.data.lower() or b'dr tracker' in response.data.lower()
        assert b'chatbot' in response.data.lower()
        assert b'rss' in response.data.lower()

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/health')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'version' in data


class TestGeolocationTool:
    """Tests for Geolocation tool (FR-006)."""

    def test_geolocation_page_access(self, auth_client):
        """Test accessing geolocation tool page."""
        response = auth_client.get('/tools/geolocation')
        assert response.status_code == 200
        assert b'geolocation' in response.data.lower()

    def test_geolocation_upload_no_files(self, auth_client):
        """Test upload with no files."""
        response = auth_client.post('/tools/geolocation/upload')

        assert response.status_code == 302  # Redirect
        # Should show error message

    def test_geolocation_upload_with_file(self, auth_client, sample_image):
        """Test uploading an image file."""
        data = {
            'images': (sample_image, 'test.jpg'),
            'tile_layer': 'OpenStreetMap',
            'cluster_markers': 'off',
            'show_path': 'off'
        }

        response = auth_client.post(
            '/tools/geolocation/upload',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )

        assert response.status_code == 200


class TestSummaryRevision:
    """Tests for Summary Revision tool (FR-007)."""

    def test_summary_revision_page_access(self, auth_client):
        """Test accessing summary revision tool page."""
        response = auth_client.get('/tools/summary-revision')
        assert response.status_code == 200
        assert b'revision' in response.data.lower()

    def test_revision_no_text(self, auth_client):
        """Test revision with no text input."""
        response = auth_client.post('/tools/summary-revision/revise', data={
            'text_input': '',
            'revision_type': 'general'
        })

        assert response.status_code == 302  # Redirect

    def test_revision_with_text(self, auth_client, sample_text, mock_openai):
        """Test text revision with valid input."""
        response = auth_client.post(
            '/tools/summary-revision/revise',
            data={
                'text_input': sample_text,
                'revision_type': 'general',
                'get_suggestions': 'off'
            },
            follow_redirects=True
        )

        assert response.status_code == 200


class TestDRTracker:
    """Tests for DR-Tracker Builder (FR-008)."""

    def test_dr_tracker_page_access(self, auth_client):
        """Test accessing DR-Tracker tool page."""
        response = auth_client.get('/tools/dr-tracker')
        assert response.status_code == 200
        assert b'dr' in response.data.lower()

    def test_dr_generation_no_prompt(self, auth_client):
        """Test DR generation with no prompt."""
        response = auth_client.post('/tools/dr-tracker/generate', data={
            'prompt': ''
        })

        assert response.status_code == 302  # Redirect

    def test_dr_generation_with_prompt(self, auth_client, sample_dr_prompt, mock_openai):
        """Test DR generation with valid prompt."""
        response = auth_client.post(
            '/tools/dr-tracker/generate',
            data={'prompt': sample_dr_prompt},
            follow_redirects=True
        )

        assert response.status_code == 200


class TestChatbot:
    """Tests for DR Knowledge Chatbot (FR-009)."""

    def test_chatbot_page_access(self, auth_client):
        """Test accessing chatbot page."""
        response = auth_client.get('/tools/chatbot')
        assert response.status_code == 200
        assert b'chatbot' in response.data.lower() or b'chat' in response.data.lower()

    def test_send_message_no_message(self, auth_client):
        """Test sending empty message."""
        response = auth_client.post(
            '/tools/chatbot/send',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_send_message_valid(self, auth_client, mock_openai):
        """Test sending valid message."""
        response = auth_client.post(
            '/tools/chatbot/send',
            json={'message': 'What are the most common DR types?'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'response' in data

    def test_clear_history(self, auth_client):
        """Test clearing chat history."""
        response = auth_client.post('/tools/chatbot/clear')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success']

    def test_get_stats(self, auth_client):
        """Test getting chatbot statistics."""
        response = auth_client.get('/tools/chatbot/stats')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'loaded' in data


class TestRSSManager:
    """Tests for RSS Manager (FR-010)."""

    def test_rss_manager_page_access(self, auth_client):
        """Test accessing RSS Manager page."""
        response = auth_client.get('/tools/rss-manager')
        assert response.status_code == 200
        assert b'rss' in response.data.lower()

    def test_get_feeds(self, auth_client):
        """Test getting RSS feeds list."""
        # Note: This will fail if Node.js service is not running
        # In real testing, you'd mock the requests
        response = auth_client.get('/tools/rss-manager/api/feeds')

        # Should return 503 if service not available, or 200 if available
        assert response.status_code in [200, 503]


class TestErrorHandlers:
    """Tests for error handling (FR-014)."""

    def test_404_handler(self, client):
        """Test 404 error handler."""
        response = client.get('/nonexistent-page')

        # 404 should return JSON with error
        assert response.status_code == 404

    def test_401_handler(self, client):
        """Test 401 unauthorized handler."""
        response = client.get('/tools')  # Protected route

        # Should redirect to login
        assert response.status_code == 302
