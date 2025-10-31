"""
Tests for Label Studio Client

Tests the Label Studio API wrapper functionality.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from curation_app.label_studio_client import LabelStudioClient


@pytest.fixture
def mock_session():
    """Mock requests session"""
    with patch('curation_app.label_studio_client.requests.Session') as mock:
        session = MagicMock()
        mock.return_value = session
        yield session


@pytest.fixture
def client(mock_session):
    """Label Studio client with mocked session"""
    return LabelStudioClient(base_url="http://localhost:8080", api_key="test-key")


class TestLabelStudioClient:
    """Test Label Studio client"""

    def test_init_with_api_key(self, mock_session):
        """Test client initialization with API key"""
        client = LabelStudioClient(base_url="http://localhost:8080", api_key="test-key")

        assert client.base_url == "http://localhost:8080"
        assert client.api_key == "test-key"
        mock_session.headers.update.assert_called_once_with({
            'Authorization': 'Token test-key'
        })

    def test_init_without_api_key(self, mock_session):
        """Test client initialization without API key"""
        client = LabelStudioClient(base_url="http://localhost:8080")

        assert client.base_url == "http://localhost:8080"
        assert client.api_key is None

    def test_create_project(self, client, mock_session):
        """Test creating a project"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "title": "Test Project"}
        mock_session.post.return_value = mock_response

        result = client.create_project(
            title="Test Project",
            description="Test Description",
            label_config="<View></View>"
        )

        assert result == {"id": 1, "title": "Test Project"}
        mock_session.post.assert_called_once_with(
            "http://localhost:8080/api/projects",
            json={
                "title": "Test Project",
                "description": "Test Description",
                "label_config": "<View></View>"
            },
            timeout=30
        )

    def test_get_project(self, client, mock_session):
        """Test getting a project"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "title": "Test Project"}
        mock_session.get.return_value = mock_response

        result = client.get_project(project_id=1)

        assert result == {"id": 1, "title": "Test Project"}
        mock_session.get.assert_called_once_with("http://localhost:8080/api/projects/1", timeout=30)

    def test_create_task(self, client, mock_session):
        """Test creating a task"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "data": {"name": "John"}}
        mock_session.post.return_value = mock_response

        result = client.create_task(
            project_id=1,
            data={"name": "John"},
            predictions=[{"result": {"rating": "Strong"}}],
            meta={"source": "vllm"}
        )

        assert result == {"id": 1, "data": {"name": "John"}}
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://localhost:8080/api/tasks"
        assert call_args[1]["json"]["data"] == {"name": "John"}
        assert call_args[1]["json"]["predictions"] == [{"result": {"rating": "Strong"}}]

    def test_get_task(self, client, mock_session):
        """Test getting a task"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "data": {"name": "John"}}
        mock_session.get.return_value = mock_response

        result = client.get_task(task_id=1)

        assert result == {"id": 1, "data": {"name": "John"}}
        mock_session.get.assert_called_once_with("http://localhost:8080/api/tasks/1", timeout=30)

    def test_get_tasks_with_filters(self, client, mock_session):
        """Test getting tasks with filters"""
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_session.get.return_value = mock_response

        result = client.get_tasks(
            project_id=1,
            filters={"agreement_score__gte": 0.8},
            page=2,
            page_size=50
        )

        assert result == [{"id": 1}, {"id": 2}]
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert call_args[1]["params"]["project"] == 1
        assert call_args[1]["params"]["page"] == 2
        assert call_args[1]["params"]["page_size"] == 50
        assert call_args[1]["params"]["agreement_score__gte"] == 0.8

    def test_create_annotation(self, client, mock_session):
        """Test creating an annotation"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "task": 1}
        mock_session.post.return_value = mock_response

        result = client.create_annotation(
            task_id=1,
            result=[{"rating": "Strong"}],
            completed_by=1,
            lead_time=45.5
        )

        assert result == {"id": 1, "task": 1}
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["task"] == 1
        assert call_args[1]["json"]["result"] == [{"rating": "Strong"}]
        assert call_args[1]["json"]["completed_by"] == 1
        assert call_args[1]["json"]["lead_time"] == 45.5

    def test_get_annotations(self, client, mock_session):
        """Test getting annotations for a task"""
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_session.get.return_value = mock_response

        result = client.get_annotations(task_id=1)

        assert result == [{"id": 1}, {"id": 2}]
        mock_session.get.assert_called_once_with(
            "http://localhost:8080/api/tasks/1/annotations",
            timeout=30
        )

    def test_update_annotation(self, client, mock_session):
        """Test updating an annotation"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "result": [{"rating": "Weak"}]}
        mock_session.patch.return_value = mock_response

        result = client.update_annotation(
            annotation_id=1,
            result=[{"rating": "Weak"}]
        )

        assert result == {"id": 1, "result": [{"rating": "Weak"}]}
        mock_session.patch.assert_called_once_with(
            "http://localhost:8080/api/annotations/1",
            json={"result": [{"rating": "Weak"}]},
            timeout=30
        )

    def test_delete_task(self, client, mock_session):
        """Test deleting a task"""
        mock_response = Mock()
        mock_session.delete.return_value = mock_response

        client.delete_task(task_id=1)

        mock_session.delete.assert_called_once_with("http://localhost:8080/api/tasks/1", timeout=30)

    def test_export_tasks(self, client, mock_session):
        """Test exporting tasks"""
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1, "data": {}}]
        mock_session.get.return_value = mock_response

        result = client.export_tasks(
            project_id=1,
            export_type="JSON",
            filters={"agreement_score__gte": 0.8}
        )

        assert result == [{"id": 1, "data": {}}]
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert call_args[1]["params"]["exportType"] == "JSON"
        assert call_args[1]["params"]["agreement_score__gte"] == 0.8

    def test_calculate_agreement_perfect(self, client):
        """Test agreement calculation with perfect match"""
        prediction = {"rating": "Strong", "pedigree": "Exceptional"}
        annotation = {"rating": "Strong", "pedigree": "Exceptional"}

        agreement = client.calculate_agreement(1, prediction, annotation)

        assert agreement == 1.0

    def test_calculate_agreement_partial(self, client):
        """Test agreement calculation with partial match"""
        prediction = {"rating": "Strong", "pedigree": "Exceptional", "trajectory": "Good"}
        annotation = {"rating": "Strong", "pedigree": "Weak", "trajectory": "Good"}

        agreement = client.calculate_agreement(1, prediction, annotation)

        assert agreement == pytest.approx(2/3, 0.01)

    def test_calculate_agreement_no_match(self, client):
        """Test agreement calculation with no match"""
        prediction = {"rating": "Strong"}
        annotation = {"rating": "Weak"}

        agreement = client.calculate_agreement(1, prediction, annotation)

        assert agreement == 0.0

    def test_calculate_agreement_empty(self, client):
        """Test agreement calculation with empty data"""
        agreement = client.calculate_agreement(1, {}, {})

        assert agreement == 0.0

    def test_get_gold_star_tasks(self, client, mock_session):
        """Test getting gold-star tasks"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "predictions": [{"result": {"rating": "Strong"}}],
                "annotations": [{"result": {"rating": "Strong"}}]
            },
            {
                "id": 2,
                "predictions": [{"result": {"rating": "Weak"}}],
                "annotations": [{"result": {"rating": "Strong"}}]
            },
            {
                "id": 3,
                "predictions": [{"result": {"rating": "Strong"}}],
                "annotations": [{"result": {"rating": "Strong"}}]
            }
        ]
        mock_session.get.return_value = mock_response

        result = client.get_gold_star_tasks(
            project_id=1,
            min_agreement=0.8,
            min_annotations=1
        )

        # Should return tasks 1 and 3 (perfect agreement)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 3
        assert all("agreement_score" in task for task in result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

