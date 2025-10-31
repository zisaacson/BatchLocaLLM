"""
Tests for Curation API

Tests the FastAPI endpoints for the curation system.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from curation_app.api import app, get_or_create_project


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_label_studio():
    """Mock Label Studio client"""
    with patch('curation_app.api.label_studio') as mock:
        yield mock


@pytest.fixture
def mock_schema_registry():
    """Mock schema registry"""
    with patch('curation_app.api.schema_registry') as mock:
        # Create a mock schema with proper nested objects
        mock_rendering = Mock()
        mock_rendering.layout = "two-column"
        mock_rendering.theme = "gradient"
        mock_rendering.showLLMPrediction = True
        mock_rendering.showDataSources = True
        mock_rendering.showRubrics = True
        mock_rendering.customCSS = ""

        mock_export = Mock()
        mock_export.iclFormat = {}
        mock_export.finetuningFormat = {}

        mock_schema = Mock()
        mock_schema.id = "test_conquest"
        mock_schema.name = "Test Conquest"
        mock_schema.description = "Test"
        mock_schema.version = "1.0.0"
        mock_schema.questions = [{"id": "q1", "text": "Question 1", "type": "choice"}]
        mock_schema.dataSources = [{"id": "ds1", "name": "Data Source 1", "type": "text"}]
        mock_schema.rendering = mock_rendering
        mock_schema.export = mock_export
        mock_schema.labelStudioConfig = "<View></View>"

        mock.get_schema.return_value = mock_schema
        mock.list_schemas.return_value = [mock_schema]
        mock.validate_task_data.return_value = True
        mock.validate_annotation.return_value = True

        yield mock


class TestCurationAPI:
    """Test curation API endpoints"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint serves HTML"""
        response = client.get("/")
        
        # Should return 404 since static file doesn't exist in test
        # In production, this would serve the HTML file
        assert response.status_code in [200, 404]
    
    def test_list_schemas(self, client, mock_schema_registry):
        """Test listing all schemas"""
        response = client.get("/api/schemas")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test_conquest"
        assert data[0]["name"] == "Test Conquest"
        assert data[0]["questionCount"] == 1
        assert data[0]["dataSourceCount"] == 1
    
    def test_get_schema(self, client, mock_schema_registry):
        """Test getting a specific schema"""
        response = client.get("/api/schemas/test_conquest")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_conquest"
    
    def test_get_nonexistent_schema(self, client, mock_schema_registry):
        """Test getting a non-existent schema"""
        mock_schema_registry.get_schema.return_value = None
        
        response = client.get("/api/schemas/nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_create_task(self, client, mock_label_studio, mock_schema_registry):
        """Test creating a task"""
        mock_label_studio.create_task.return_value = {
            "id": 1,
            "data": {"name": "John Doe"},
            "predictions": []
        }
        
        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.post("/api/tasks", json={
                "conquest_type": "test_conquest",
                "data": {"name": "John Doe"},
                "llm_prediction": {"rating": "Strong"},
                "model_version": "qwen3-4b"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        mock_label_studio.create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_task_invalid_schema(self, client, mock_schema_registry):
        """Test creating a task with invalid schema"""
        mock_schema_registry.get_schema.return_value = None
        
        response = client.post("/api/tasks", json={
            "conquest_type": "nonexistent",
            "data": {"name": "John Doe"}
        })
        
        assert response.status_code == 404
        assert "unknown conquest type" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_create_task_invalid_data(self, client, mock_schema_registry):
        """Test creating a task with invalid data"""
        mock_schema_registry.validate_task_data.return_value = False
        
        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.post("/api/tasks", json={
                "conquest_type": "test_conquest",
                "data": {"invalid": "data"}
            })
        
        assert response.status_code == 400
        assert "invalid task data" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, client, mock_label_studio):
        """Test listing tasks"""
        mock_label_studio.get_tasks.return_value = [
            {"id": 1, "data": {}},
            {"id": 2, "data": {}}
        ]
        
        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.get("/api/tasks?conquest_type=test_conquest&page=1&page_size=50")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 50
    
    def test_get_task(self, client, mock_label_studio):
        """Test getting a specific task"""
        mock_label_studio.get_task.return_value = {
            "id": 1,
            "data": {"name": "John Doe"}
        }
        
        response = client.get("/api/tasks/1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
    
    def test_submit_annotation(self, client, mock_label_studio, mock_schema_registry):
        """Test submitting an annotation"""
        mock_label_studio.get_task.return_value = {
            "id": 1,
            "data": {"conquest_type": "test_conquest"},
            "predictions": [{"result": {"rating": "Strong"}}]
        }
        mock_label_studio.create_annotation.return_value = {
            "id": 1,
            "task": 1,
            "result": [{"rating": "Strong"}]
        }
        mock_label_studio.calculate_agreement.return_value = 1.0
        
        response = client.post("/api/annotations", json={
            "task_id": 1,
            "result": {"rating": "Strong"},
            "time_spent_seconds": 45.5
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["agreement_score"] == 1.0
    
    def test_submit_annotation_missing_conquest_type(self, client, mock_label_studio):
        """Test submitting annotation for task without conquest_type"""
        mock_label_studio.get_task.return_value = {
            "id": 1,
            "data": {}  # Missing conquest_type
        }
        
        response = client.post("/api/annotations", json={
            "task_id": 1,
            "result": {"rating": "Strong"}
        })
        
        assert response.status_code == 400
        assert "missing conquest_type" in response.json()["detail"].lower()
    
    def test_submit_annotation_invalid(self, client, mock_label_studio, mock_schema_registry):
        """Test submitting invalid annotation"""
        mock_label_studio.get_task.return_value = {
            "id": 1,
            "data": {"conquest_type": "test_conquest"}
        }
        mock_schema_registry.validate_annotation.return_value = False
        
        response = client.post("/api/annotations", json={
            "task_id": 1,
            "result": {"invalid": "data"}
        })
        
        assert response.status_code == 400
        assert "invalid annotation" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_export_dataset_icl(self, client, mock_label_studio, mock_schema_registry):
        """Test exporting dataset in ICL format"""
        mock_label_studio.get_gold_star_tasks.return_value = [
            {"id": 1, "data": {}, "annotations": []}
        ]
        mock_schema_registry.export_to_icl.return_value = [
            {"messages": [{"role": "user", "content": "test"}]}
        ]
        
        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.post("/api/export", json={
                "conquest_type": "test_conquest",
                "format": "icl",
                "min_agreement": 0.8,
                "min_annotations": 1
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["conquest_type"] == "test_conquest"
        assert data["format"] == "icl"
        assert data["count"] == 1
        assert len(data["examples"]) == 1
    
    @pytest.mark.asyncio
    async def test_export_dataset_finetuning(self, client, mock_label_studio, mock_schema_registry):
        """Test exporting dataset in fine-tuning format"""
        mock_label_studio.get_gold_star_tasks.return_value = [
            {"id": 1, "data": {}, "annotations": []}
        ]
        mock_schema_registry.export_to_finetuning.return_value = [
            {"input": {}, "output": {}}
        ]
        
        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.post("/api/export", json={
                "conquest_type": "test_conquest",
                "format": "finetuning",
                "min_agreement": 0.8
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "finetuning"
    
    @pytest.mark.asyncio
    async def test_export_dataset_invalid_format(self, client, mock_label_studio):
        """Test exporting with invalid format"""
        mock_label_studio.get_gold_star_tasks.return_value = []
        
        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.post("/api/export", json={
                "conquest_type": "test_conquest",
                "format": "invalid_format"
            })
        
        assert response.status_code == 400
        assert "unknown export format" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_stats(self, client, mock_label_studio):
        """Test getting curation statistics"""
        mock_label_studio.get_tasks.return_value = [
            {
                "id": 1,
                "annotations": [{"result": [{"rating": "Strong"}]}],
                "predictions": [{"result": {"rating": "Strong"}}]
            },
            {
                "id": 2,
                "annotations": [],
                "predictions": []
            }
        ]
        mock_label_studio.calculate_agreement.return_value = 1.0

        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.get("/api/stats?conquest_type=test_conquest")

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 2
        assert data["annotated_tasks"] == 1
        assert data["pending_tasks"] == 1
        assert data["gold_star_tasks"] == 1

    def test_mark_gold_star(self, client, mock_label_studio):
        """Test marking a task as gold-star"""
        mock_label_studio.get_task.return_value = {
            "id": 1,
            "data": {"name": "John Doe"},
            "meta": {}
        }
        mock_label_studio.update_task.return_value = {
            "id": 1,
            "meta": {"gold_star": True}
        }

        response = client.post("/api/tasks/1/gold-star", json={"is_gold_star": True})

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == 1
        assert data["gold_star"] is True
        assert "updated_at" in data
        mock_label_studio.update_task.assert_called_once()

    def test_unmark_gold_star(self, client, mock_label_studio):
        """Test unmarking a task as gold-star"""
        mock_label_studio.get_task.return_value = {
            "id": 1,
            "data": {"name": "John Doe"},
            "meta": {"gold_star": True}
        }
        mock_label_studio.update_task.return_value = {
            "id": 1,
            "meta": {"gold_star": False}
        }

        response = client.post("/api/tasks/1/gold-star", json={"is_gold_star": False})

        assert response.status_code == 200
        data = response.json()
        assert data["gold_star"] is False

    def test_bulk_mark_gold_star(self, client, mock_label_studio):
        """Test bulk marking tasks as gold-star"""
        mock_label_studio.get_task.side_effect = [
            {"id": 1, "meta": {}},
            {"id": 2, "meta": {}},
            {"id": 3, "meta": {}}
        ]
        mock_label_studio.update_task.return_value = {"id": 1}

        response = client.post(
            "/api/tasks/bulk-gold-star",
            json={"task_ids": [1, 2, 3], "is_gold_star": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 3
        assert data["updated_count"] == 3
        assert data["failed_count"] == 0
        assert data["gold_star"] is True
        assert mock_label_studio.update_task.call_count == 3

    def test_bulk_mark_gold_star_partial_failure(self, client, mock_label_studio):
        """Test bulk gold-star with some failures"""
        def get_task_side_effect(task_id):
            if task_id == 2:
                raise Exception("Task not found")
            return {"id": task_id, "meta": {}}

        mock_label_studio.get_task.side_effect = get_task_side_effect
        mock_label_studio.update_task.return_value = {"id": 1}

        response = client.post(
            "/api/tasks/bulk-gold-star",
            json={"task_ids": [1, 2, 3], "is_gold_star": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 3
        assert data["updated_count"] == 2
        assert data["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_bulk_import_tasks(self, client, mock_label_studio, mock_schema_registry):
        """Test bulk importing batch results"""
        mock_label_studio.create_task.return_value = {"id": 1}

        with patch('curation_app.api.get_or_create_project', return_value=1):
            response = client.post("/api/tasks/bulk-import", json={
                "batch_id": "batch_123",
                "conquest_type": "test_conquest",
                "model_version": "gemma-3-4b",
                "results": [
                    {
                        "custom_id": "req-1",
                        "response": {
                            "body": {
                                "choices": [
                                    {"message": {"content": '{"rating": "Strong"}'}}
                                ]
                            }
                        },
                        "request": {
                            "body": {
                                "messages": [
                                    {"role": "user", "content": "Test"}
                                ]
                            }
                        }
                    }
                ]
            })

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "batch_123"
        assert data["created_count"] == 1
        assert data["skipped_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

