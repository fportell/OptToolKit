"""
Tests for authentication module.

Tests login, logout, session management, and user loading.
Per FR-001, FR-002, FR-003, FR-015.
"""

import pytest
from flask import session
from app.auth import User, check_credentials, load_user


class TestUserModel:
    """Tests for User model."""

    def test_user_creation(self):
        """Test creating a User instance."""
        user = User('testuser')
        assert user.id == 'testuser'
        assert user.is_authenticated
        assert user.is_active
        assert not user.is_anonymous

    def test_user_representation(self):
        """Test User __repr__ method."""
        user = User('testuser')
        assert repr(user) == '<User testuser>'


class TestCredentialValidation:
    """Tests for credential validation."""

    def test_valid_credentials(self, app):
        """Test validation with correct credentials."""
        with app.app_context():
            assert check_credentials('testuser', 'testpassword')

    def test_invalid_username(self, app):
        """Test validation with wrong username."""
        with app.app_context():
            assert not check_credentials('wronguser', 'testpassword')

    def test_invalid_password(self, app):
        """Test validation with wrong password."""
        with app.app_context():
            assert not check_credentials('testuser', 'wrongpassword')

    def test_empty_credentials(self, app):
        """Test validation with empty credentials."""
        with app.app_context():
            assert not check_credentials('', '')
            assert not check_credentials('testuser', '')
            assert not check_credentials('', 'testpassword')


class TestUserLoader:
    """Tests for Flask-Login user loader."""

    def test_load_valid_user(self, app):
        """Test loading a valid user."""
        with app.app_context():
            user = load_user('testuser')
            assert user is not None
            assert user.id == 'testuser'

    def test_load_invalid_user(self, app):
        """Test loading an invalid user."""
        with app.app_context():
            user = load_user('invaliduser')
            assert user is None


class TestAuthenticationFlow:
    """Tests for complete authentication flows."""

    def test_login_success(self, client):
        """Test successful login flow (FR-001, FR-002)."""
        response = client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpassword'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'tools' in response.data.lower()

    def test_login_failure_wrong_password(self, client):
        """Test login with wrong password."""
        response = client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert b'invalid' in response.data.lower()

    def test_login_failure_empty_fields(self, client):
        """Test login with empty fields."""
        response = client.post('/auth/login', data={
            'username': '',
            'password': ''
        })

        assert response.status_code == 200
        assert b'enter both' in response.data.lower()

    def test_logout(self, auth_client):
        """Test logout flow (FR-015)."""
        response = auth_client.post('/auth/logout', follow_redirects=True)

        assert response.status_code == 200
        assert b'logged out' in response.data.lower()

    def test_protected_route_requires_auth(self, client):
        """Test that protected routes redirect unauthenticated users."""
        response = client.get('/tools')

        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_authenticated_access_to_tools(self, auth_client):
        """Test authenticated user can access tools page."""
        response = auth_client.get('/tools')

        assert response.status_code == 200
        assert b'tools' in response.data.lower()


class TestSessionManagement:
    """Tests for session timeout and management (FR-003)."""

    def test_session_timestamps_created_on_login(self, client):
        """Test that login creates session timestamps."""
        with client:
            client.post('/auth/login', data={
                'username': 'testuser',
                'password': 'testpassword'
            })

            # Check session has timestamps
            assert 'login_time' in session
            assert 'last_activity' in session

    def test_session_cleared_on_logout(self, auth_client):
        """Test that logout clears session data."""
        with auth_client:
            # Verify session exists
            auth_client.get('/tools')
            assert 'login_time' in session

            # Logout
            auth_client.post('/auth/logout')

            # Verify session cleared
            assert 'login_time' not in session
            assert 'last_activity' not in session
