"""
Pytest configuration and fixtures for OpsToolKit tests.

Provides shared fixtures for testing Flask application and services.
"""

import pytest
import tempfile
import os
from pathlib import Path
from app import create_app
from app.config import TestingConfig


@pytest.fixture
def app():
    """
    Create and configure a new app instance for each test.

    Returns:
        Flask: Test Flask application instance
    """
    # Create temporary directories for testing
    test_instance_path = tempfile.mkdtemp()
    test_upload_path = tempfile.mkdtemp()

    # Override config for testing
    class TestConfig(TestingConfig):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'test-secret-key'

        # Test credentials
        APP_USERNAME = 'testuser'
        APP_PASSWORD = 'testpassword'

        # Test OpenAI (will be mocked)
        OPENAI_API_KEY = 'test-api-key'

        # Test paths
        UPLOAD_FOLDER = test_upload_path

        # Disable queue for testing
        OPENAI_QUEUE_ENABLED = False

        # Test session config
        SESSION_TYPE = 'filesystem'
        SESSION_ACTIVITY_TIMEOUT = 3600
        SESSION_INACTIVITY_TIMEOUT = 600

    app = create_app('testing')
    app.config.from_object(TestConfig)

    yield app

    # Cleanup
    import shutil
    shutil.rmtree(test_instance_path, ignore_errors=True)
    shutil.rmtree(test_upload_path, ignore_errors=True)


@pytest.fixture
def client(app):
    """
    Create a test client for the app.

    Args:
        app: Flask application fixture

    Returns:
        FlaskClient: Test client for making requests
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    Create a test CLI runner for the app.

    Args:
        app: Flask application fixture

    Returns:
        FlaskCliRunner: Test CLI runner
    """
    return app.test_cli_runner()


@pytest.fixture
def auth_client(client):
    """
    Create an authenticated test client.

    Args:
        client: Flask test client fixture

    Returns:
        FlaskClient: Authenticated test client
    """
    # Login
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpassword'
    })

    return client


@pytest.fixture
def sample_image():
    """
    Create a sample image file for testing.

    Returns:
        BytesIO: Sample image data
    """
    from PIL import Image
    import io

    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)

    return img_bytes


@pytest.fixture
def sample_text():
    """
    Sample text for revision testing.

    Returns:
        str: Sample text
    """
    return """
    This is a sample text that needs revision. It have some grammatical errors
    and could be improved. The text is not very clear and needs better structure.
    """


@pytest.fixture
def sample_dr_prompt():
    """
    Sample DR prompt for testing.

    Returns:
        str: Sample DR generation prompt
    """
    return """
    Create 2 DRs:
    1. Critical server issue in datacenter A - high priority
    2. Documentation error in user manual - medium priority
    """


@pytest.fixture
def mock_openai(monkeypatch):
    """
    Mock OpenAI API responses.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    class MockChoice:
        def __init__(self, content):
            self.message = type('Message', (), {'content': content})()

    class MockUsage:
        prompt_tokens = 100
        completion_tokens = 50
        total_tokens = 150

    class MockResponse:
        def __init__(self, content):
            self.choices = [MockChoice(content)]
            self.usage = MockUsage()

    def mock_create(*args, **kwargs):
        messages = kwargs.get('messages', [])
        last_message = messages[-1]['content'] if messages else ''

        # Return different responses based on context
        if 'revise' in str(messages).lower():
            return MockResponse('This is the revised text with improvements.')
        elif 'DR' in last_message or 'discrepancy' in last_message.lower():
            return MockResponse('[{"id":"DR-001","title":"Test DR","description":"Test description","category":"Technical","priority":"High","status":"Open","assigned_to":"Test Team","created_date":"2025-01-01","due_date":"2025-01-07","resolution":""}]')
        else:
            return MockResponse('This is a test response from the AI assistant.')

    # Mock the OpenAI client
    from unittest.mock import MagicMock
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    import openai
    monkeypatch.setattr(openai, 'OpenAI', lambda *args, **kwargs: mock_client)

    return mock_client
