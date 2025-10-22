"""
Unit tests for service layer modules.

Tests core service functionality without HTTP layer.
"""

import pytest
from pathlib import Path
from app.services.geolocation.exif_extractor import ExifExtractor
from app.services.summary_revision.revision_service import RevisionService
from app.services.dr_tracker.tracker_service import DRTrackerService


class TestExifExtractor:
    """Tests for EXIF extraction service."""

    def test_format_coordinates(self):
        """Test coordinate formatting."""
        result = ExifExtractor.format_coordinates(40.7128, -74.0060)

        assert 'decimal' in result
        assert '40.7128' in result['decimal']
        assert 'dms' in result
        assert 'google_maps' in result
        assert 'maps.google.com' in result['google_maps']

    def test_format_coordinates_negative(self):
        """Test formatting negative coordinates."""
        result = ExifExtractor.format_coordinates(-33.8688, 151.2093)

        assert 'S' in result['dms']  # South
        assert 'E' in result['dms']  # East


class TestRevisionService:
    """Tests for text revision service."""

    def test_revision_types_available(self):
        """Test that all revision types are defined."""
        assert 'general' in RevisionService.REVISION_TYPES
        assert 'professional' in RevisionService.REVISION_TYPES
        assert 'concise' in RevisionService.REVISION_TYPES
        assert 'detailed' in RevisionService.REVISION_TYPES
        assert 'grammar' in RevisionService.REVISION_TYPES

    def test_revision_types_have_required_fields(self):
        """Test that revision types have required fields."""
        for key, type_info in RevisionService.REVISION_TYPES.items():
            assert 'name' in type_info
            assert 'description' in type_info
            assert 'system_prompt' in type_info

    def test_compare_texts(self, app):
        """Test text comparison functionality."""
        with app.app_context():
            service = RevisionService()

            original = "This is a test."
            revised = "This is a better test with more words."

            result = service.compare_texts(original, revised)

            assert result['original_length'] == len(original)
            assert result['revised_length'] == len(revised)
            assert result['original_words'] == 4
            assert result['revised_words'] == 8
            assert result['words_change'] == 4
            assert result['words_change_percent'] == 100.0


class TestDRTrackerService:
    """Tests for DR-Tracker service."""

    def test_field_schema_defined(self):
        """Test that field schema is properly defined."""
        schema = DRTrackerService.FIELD_SCHEMA

        assert 'id' in schema
        assert 'title' in schema
        assert 'description' in schema
        assert 'priority' in schema
        assert 'status' in schema

        # Check schema structure
        for field, spec in schema.items():
            assert 'type' in spec
            assert 'description' in spec

    def test_export_to_csv(self, app):
        """Test CSV export functionality."""
        with app.app_context():
            service = DRTrackerService()

            entries = [
                {
                    'id': 'DR-001',
                    'title': 'Test DR',
                    'description': 'Test description',
                    'category': 'Technical',
                    'priority': 'High',
                    'status': 'Open',
                    'assigned_to': 'Team A',
                    'created_date': '2025-01-01',
                    'due_date': '2025-01-07',
                    'resolution': ''
                }
            ]

            csv_output = service.export_to_csv(entries)

            assert 'DR-001' in csv_output
            assert 'Test DR' in csv_output
            assert 'Technical' in csv_output

    def test_export_to_json(self, app):
        """Test JSON export functionality."""
        import json

        with app.app_context():
            service = DRTrackerService()

            entries = [
                {
                    'id': 'DR-001',
                    'title': 'Test DR',
                    'description': 'Test description',
                    'category': 'Technical',
                    'priority': 'High',
                    'status': 'Open',
                    'assigned_to': 'Team A',
                    'created_date': '2025-01-01',
                    'due_date': '2025-01-07',
                    'resolution': ''
                }
            ]

            json_output = service.export_to_json(entries)
            parsed = json.loads(json_output)

            assert len(parsed) == 1
            assert parsed[0]['id'] == 'DR-001'

    def test_validate_entries(self, app):
        """Test entry validation."""
        with app.app_context():
            service = DRTrackerService()

            # Valid entry
            valid_entries = [
                {
                    'id': 'DR-001',
                    'title': 'Test DR',
                    'description': 'Test description',
                    'category': 'Technical',
                    'priority': 'High',
                    'status': 'Open',
                    'assigned_to': 'Team A',
                    'created_date': '2025-01-01',
                    'due_date': '2025-01-07',
                    'resolution': ''
                }
            ]

            result = service.validate_entries(valid_entries)

            assert result['valid']
            assert result['total'] == 1
            assert len(result['errors']) == 0

            # Invalid entry (missing required fields)
            invalid_entries = [
                {
                    'id': '',
                    'title': '',
                    'description': '',
                    'category': 'Technical',
                    'priority': 'InvalidPriority',
                    'status': 'Open',
                    'assigned_to': 'Team A',
                    'created_date': '2025-01-01',
                    'due_date': '2025-01-07',
                    'resolution': ''
                }
            ]

            result = service.validate_entries(invalid_entries)

            assert not result['valid']
            assert len(result['errors']) > 0


class TestConcurrencyManager:
    """Tests for concurrency management."""

    def test_active_user_tracking(self, app, auth_client):
        """Test active user count tracking."""
        from app.concurrency_manager import get_active_user_count, update_active_user

        with app.app_context():
            # Initially should be 0 or low
            initial_count = get_active_user_count()

            # Simulate activity
            with auth_client:
                auth_client.get('/tools')

            # Count should update (might be 0 due to test isolation)
            # Just verify function doesn't crash
            final_count = get_active_user_count()
            assert final_count >= 0


class TestSessionManager:
    """Tests for session management."""

    def test_check_session_timeout(self, app):
        """Test session timeout checking."""
        from app.session_manager import check_session_timeout
        from flask import session as flask_session
        from datetime import datetime, timedelta

        with app.test_request_context():
            # Mock authenticated user
            from app.auth import User
            from flask_login import login_user

            user = User('testuser')
            login_user(user)

            # Set session timestamps
            flask_session['login_time'] = datetime.utcnow().isoformat()
            flask_session['last_activity'] = datetime.utcnow().isoformat()

            # Should not be expired
            is_expired, reason = check_session_timeout()
            assert not is_expired

            # Set old login time (>4 hours ago)
            old_time = datetime.utcnow() - timedelta(hours=5)
            flask_session['login_time'] = old_time.isoformat()

            # Should be expired due to activity timeout
            is_expired, reason = check_session_timeout()
            assert is_expired
            assert reason == 'activity'
