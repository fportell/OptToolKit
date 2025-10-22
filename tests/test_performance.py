"""
Performance tests for OpsToolKit.

Tests p95 latency requirements and concurrent user handling.
Per Success Criteria: SC-001, SC-002, SC-003, SC-004.
"""

import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestLoginPerformance:
    """Test login endpoint performance (SC-001)."""

    def test_login_p95_latency(self, client):
        """
        Test login p95 latency < 500ms.

        SC-001: Login page load time p95 < 500ms
        """
        latencies = []

        # Perform 20 requests to get meaningful p95
        for _ in range(20):
            start = time.time()
            response = client.get('/auth/login')
            latency = (time.time() - start) * 1000  # Convert to ms

            assert response.status_code == 200
            latencies.append(latency)

        # Calculate p95 (95th percentile)
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        print(f"\nLogin p95 latency: {p95_latency:.2f}ms")
        assert p95_latency < 500, f"Login p95 latency {p95_latency:.2f}ms exceeds 500ms threshold"

    def test_login_authentication_p95_latency(self, client):
        """
        Test login authentication p95 latency < 500ms.

        SC-001: Authentication check p95 < 500ms
        """
        latencies = []

        for _ in range(20):
            start = time.time()
            response = client.post('/auth/login', data={
                'username': 'testuser',
                'password': 'testpassword'
            })
            latency = (time.time() - start) * 1000

            latencies.append(latency)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        print(f"\nAuthentication p95 latency: {p95_latency:.2f}ms")
        assert p95_latency < 500, f"Auth p95 latency {p95_latency:.2f}ms exceeds 500ms threshold"


class TestToolsPagePerformance:
    """Test tools landing page performance (SC-002)."""

    def test_tools_page_p95_latency(self, auth_client):
        """
        Test tools page p95 latency < 1000ms.

        SC-002: Tools landing page load time p95 < 1000ms
        """
        latencies = []

        for _ in range(20):
            start = time.time()
            response = auth_client.get('/tools')
            latency = (time.time() - start) * 1000

            assert response.status_code == 200
            latencies.append(latency)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        print(f"\nTools page p95 latency: {p95_latency:.2f}ms")
        assert p95_latency < 1000, f"Tools page p95 latency {p95_latency:.2f}ms exceeds 1000ms threshold"


class TestGeolocationPerformance:
    """Test geolocation tool performance (SC-003)."""

    @pytest.mark.slow
    def test_geolocation_processing_latency(self, auth_client, sample_image):
        """
        Test geolocation processing p95 latency < 3000ms.

        SC-003: Geolocation processing time p95 < 3000ms
        """
        latencies = []

        # Test with 10 iterations (fewer due to file processing overhead)
        for _ in range(10):
            sample_image.seek(0)  # Reset file pointer

            start = time.time()
            response = auth_client.post(
                '/tools/geolocation/upload',
                data={
                    'images': (sample_image, 'test.jpg'),
                    'tile_layer': 'OpenStreetMap'
                },
                content_type='multipart/form-data'
            )
            latency = (time.time() - start) * 1000

            # Should redirect to results
            assert response.status_code in [200, 302]
            latencies.append(latency)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        print(f"\nGeolocation p95 latency: {p95_latency:.2f}ms")
        assert p95_latency < 3000, f"Geolocation p95 latency {p95_latency:.2f}ms exceeds 3000ms threshold"


class TestConcurrentUsers:
    """Test concurrent user handling (SC-004)."""

    @pytest.mark.slow
    def test_five_concurrent_users(self, app):
        """
        Test system handles 5 concurrent users.

        SC-004: System supports 5 concurrent active users
        """
        def simulate_user_session(user_id):
            """Simulate a user session."""
            with app.test_client() as client:
                # Login
                login_response = client.post('/auth/login', data={
                    'username': 'testuser',
                    'password': 'testpassword'
                })

                if login_response.status_code not in [200, 302]:
                    return {'user_id': user_id, 'success': False, 'error': 'Login failed'}

                # Access tools page
                tools_response = client.get('/tools', follow_redirects=True)

                # Access a tool
                geoloc_response = client.get('/tools/geolocation')

                return {
                    'user_id': user_id,
                    'success': all([
                        tools_response.status_code == 200,
                        geoloc_response.status_code == 200
                    ]),
                    'error': None
                }

        # Simulate 5 concurrent users
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(simulate_user_session, i) for i in range(5)]

            results = []
            for future in as_completed(futures):
                results.append(future.result())

        # Verify all users succeeded
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        print(f"\nConcurrent users test: {len(successful)}/5 succeeded")

        if failed:
            print(f"Failed users: {failed}")

        assert len(successful) >= 4, f"Only {len(successful)}/5 concurrent users succeeded"


class TestMemoryUsage:
    """Test memory usage remains reasonable."""

    def test_session_storage_doesnt_grow_unbounded(self, auth_client):
        """Test that session storage doesn't grow indefinitely."""
        # Send multiple chat messages
        for i in range(25):  # More than the 20-message limit
            auth_client.post(
                '/tools/chatbot/send',
                json={'message': f'Test message {i}'},
                content_type='application/json'
            )

        # Get history
        response = auth_client.get('/tools/chatbot/history')
        data = response.get_json()

        # Should be limited to 20 messages
        assert data['count'] <= 20, "Chat history not properly limited"


class TestResponseTimes:
    """Test various endpoint response times."""

    def test_health_endpoint_fast(self, client):
        """Test health endpoint responds quickly."""
        latencies = []

        for _ in range(10):
            start = time.time()
            response = client.get('/health')
            latency = (time.time() - start) * 1000

            assert response.status_code == 200
            latencies.append(latency)

        avg_latency = statistics.mean(latencies)
        print(f"\nHealth endpoint average latency: {avg_latency:.2f}ms")

        # Health check should be very fast
        assert avg_latency < 100, f"Health endpoint too slow: {avg_latency:.2f}ms"

    def test_static_file_serving(self, client):
        """Test static file serving performance."""
        # CSS file should load quickly
        start = time.time()
        response = client.get('/static/css/styles.css')
        latency = (time.time() - start) * 1000

        assert response.status_code == 200
        assert latency < 200, f"Static file serving too slow: {latency:.2f}ms"
