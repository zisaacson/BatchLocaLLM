"""Integration tests for Label Studio client.

Tests the Label Studio API client with REAL Label Studio instance.
Skips if Label Studio is not running.

To run these tests:
1. Start Label Studio: docker compose -f docker-compose.postgres.yml up label-studio
2. Run tests: pytest tests/integration/test_label_studio_integration.py -v
"""

import json

import pytest
import requests

from curation_app.label_studio_client import LabelStudioClient

# Test configuration
LABEL_STUDIO_URL = "http://localhost:4015"
LABEL_STUDIO_API_KEY = None  # Set if your Label Studio requires auth


@pytest.fixture(scope="module")
def check_label_studio():
    """Check if Label Studio is running, skip tests if not."""
    try:
        response = requests.get(f"{LABEL_STUDIO_URL}/health", timeout=5)
        if response.status_code != 200:
            pytest.skip("Label Studio not healthy")
    except requests.exceptions.ConnectionError:
        pytest.skip("Label Studio not running on localhost:4015")


@pytest.fixture
def client():
    """Create a Label Studio client for testing."""
    return LabelStudioClient(
        base_url=LABEL_STUDIO_URL,
        api_key=LABEL_STUDIO_API_KEY
    )


class TestLabelStudioClient:
    """Integration tests for Label Studio client with REAL Label Studio."""

    def test_health_check(self, check_label_studio):
        """Test that Label Studio is accessible."""
        response = requests.get(f"{LABEL_STUDIO_URL}/health", timeout=5)
        assert response.status_code == 200

    # NOTE: Real integration tests with Label Studio would go here
    # These require Label Studio to be running and configured
    # For now, we just verify connectivity
    #
    # To add real integration tests:
    # 1. Create a test project in Label Studio
    # 2. Test creating tasks
    # 3. Test creating annotations
    # 4. Test exporting data
    # 5. Clean up test data
    #
    # Example:
    # def test_create_and_retrieve_task(self, check_label_studio, client):
    #     # Create project
    #     project = client.create_project(title="Test Project", ...)
    #     # Create task
    #     task = client.create_task(project_id=project['id'], ...)
    #     # Retrieve task
    #     retrieved = client.get_task(task['id'])
    #     assert retrieved['id'] == task['id']
    #     # Cleanup
    #     client.delete_task(task['id'])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

