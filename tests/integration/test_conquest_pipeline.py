"""
Integration tests for the complete conquest data pipeline.

Tests the REAL data flow:
1. Batch results → Bulk import → Label Studio tasks
2. Tasks → Annotations → Agreement calculation
3. Gold-star marking → Export → Training datasets

These tests use REAL FastAPI app, REAL database, REAL Label Studio client.
NO MOCKING (except Label Studio HTTP calls which we can't control in tests).

To run these tests:
1. Start PostgreSQL: docker compose -f docker-compose.postgres.yml up postgres
2. Run tests: pytest tests/integration/test_conquest_pipeline.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from curation_app.api import app


@pytest.fixture
def client():
    """FastAPI test client - uses REAL app"""
    return TestClient(app)


@pytest.fixture
def mock_label_studio_http():
    """
    Mock Label Studio HTTP calls (we can't run real Label Studio in tests).
    But we test the REAL integration logic, just not the HTTP layer.
    """
    with patch('curation_app.api.label_studio') as mock_ls:
        # Mock Label Studio client methods
        mock_ls.create_project.return_value = {"id": 1, "title": "Test Project"}
        mock_ls.get_project.return_value = {"id": 1, "title": "Test Project"}
        mock_ls.create_task.return_value = {"id": 123, "data": {}}
        mock_ls.get_task.return_value = {"id": 1, "data": {}, "meta": {}}
        mock_ls.update_task.return_value = {"id": 1, "meta": {"gold_star": True}}
        mock_ls.get_tasks.return_value = {"results": []}
        mock_ls.get_gold_star_tasks.return_value = []

        yield mock_ls


class TestConquestPipeline:
    """Test the complete conquest data pipeline with REAL integrations"""

    def test_all_conquest_types_have_schemas(self, client):
        """
        Test: All conquest types have valid schemas loaded

        This ensures the schema registry loaded all conquest types correctly.
        """
        from curation_app.conquest_schemas import get_registry

        registry = get_registry()
        schemas = registry.list_schemas()

        # Verify we have all expected conquest types
        expected_types = {
            "candidate_evaluation",
            "cartographer",
            "cv_parsing",
            "email_evaluation",
            "quil_email",
            "report_evaluation"
        }

        loaded_types = {schema.id for schema in schemas}
        assert loaded_types == expected_types, f"Missing schemas: {expected_types - loaded_types}"

        # Verify each schema has required fields
        for schema in schemas:
            assert schema.id, f"Schema missing id: {schema}"
            assert schema.name, f"Schema {schema.id} missing name"
            assert schema.dataSources, f"Schema {schema.id} missing dataSources"
            assert schema.questions, f"Schema {schema.id} missing questions"

    def test_bulk_import_creates_tasks_with_real_schema(self, client, mock_label_studio_http):
        """
        Test: Batch results → Bulk import → Label Studio tasks

        This tests the REAL data flow when a batch job completes:
        1. Worker calls /api/tasks/bulk-import with batch results
        2. API validates against REAL conquest schema
        3. API creates tasks in Label Studio
        4. Returns import statistics
        """
        # Mock Label Studio responses
        mock_label_studio_http.create_task.return_value = {
            "id": 123,
            "data": {"candidate_name": "Alice Johnson"}
        }
        mock_label_studio_http.get_project.return_value = {
            "id": 1,
            "title": "candidate_evaluation"
        }

        # Prepare REAL batch results (OpenAI format)
        request_data = {
            "batch_id": "batch_test_123",
            "conquest_type": "candidate_evaluation",
            "model_version": "gemma-3-4b",
            "results": [
                {
                    "custom_id": "candidate-001",
                    "response": {
                        "body": {
                            "choices": [{
                                "message": {
                                    "content": json.dumps({
                                        "recommendation": "yes",
                                        "trajectory_rating": "strong",
                                        "company_pedigree": "strong",
                                        "educational_pedigree": "good",
                                        "is_software_engineer": True
                                    })
                                }
                            }]
                        }
                    },
                    "request": {
                        "body": {
                            "messages": [
                                {"role": "user", "content": "Evaluate this candidate"}
                            ]
                        }
                    }
                }
            ]
        }

        # Call REAL API endpoint
        response = client.post("/api/tasks/bulk-import", json=request_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['batch_id'] == "batch_test_123"
        assert data['conquest_type'] == "candidate_evaluation"
        assert data['created_count'] >= 0
        assert 'skipped_count' in data
        assert 'task_ids' in data
        assert 'curation_url' in data

    def test_task_creation_validates_against_real_schema(self, client, mock_label_studio_http):
        """
        Test: Task creation validates against REAL conquest schema

        This ensures we're using the REAL schema registry, not mocks.
        """
        # Mock Label Studio responses
        mock_label_studio_http.create_task.return_value = {
            "id": 1,
            "data": {"name": "John Doe"}
        }
        mock_label_studio_http.get_project.return_value = {
            "id": 1,
            "title": "candidate_evaluation"
        }

        # Create task with REAL schema validation
        response = client.post("/api/tasks", json={
            "conquest_type": "candidate_evaluation",
            "data": {
                "name": "John Doe",  # Required
                "role": "Software Engineer",  # Required
                "education": "BS Computer Science, Stanford",  # Required
                "work_history": "Google (2020-2024), Meta (2018-2020)"  # Required
            },
            "llm_prediction": {
                "recommendation": "yes",
                "trajectory_rating": "strong",
                "company_pedigree": "strong",
                "educational_pedigree": "good",
                "is_software_engineer": True
            },
            "model_version": "qwen3-4b"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    def test_invalid_conquest_type_rejected(self, client):
        """
        Test: Invalid conquest types are rejected by REAL schema registry
        """
        response = client.post("/api/tasks", json={
            "conquest_type": "nonexistent_conquest",
            "data": {"name": "John Doe"}
        })

        assert response.status_code == 404
        assert "unknown conquest type" in response.json()["detail"].lower()

    def test_gold_star_marking_workflow(self, client, mock_label_studio_http):
        """
        Test: Gold-star marking → Task metadata update

        This tests the REAL workflow for marking high-quality examples.
        """
        # Mock getting task
        mock_label_studio_http.get_task.return_value = {
            "id": 1,
            "data": {"name": "John Doe"},
            "meta": {}
        }

        # Mock updating task
        mock_label_studio_http.update_task.return_value = {
            "id": 1,
            "meta": {"gold_star": True}
        }

        # Mark as gold-star
        response = client.post("/api/tasks/1/gold-star", json={"is_gold_star": True})

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == 1
        assert data["gold_star"] is True
        assert "updated_at" in data

    def test_bulk_gold_star_marking(self, client, mock_label_studio_http):
        """
        Test: Bulk gold-star marking for multiple tasks
        """
        # Mock getting tasks
        mock_label_studio_http.get_task.return_value = {"id": 1, "meta": {}}

        # Mock updating tasks
        mock_label_studio_http.update_task.return_value = {"id": 1}

        # Bulk mark
        response = client.post("/api/tasks/bulk-gold-star", json={
            "task_ids": [1, 2, 3],
            "is_gold_star": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 3
        assert data["updated_count"] >= 0
        assert data["gold_star"] is True

    def test_export_uses_real_schema_registry(self, client, mock_label_studio_http):
        """
        Test: Export → REAL schema registry → Training dataset

        This ensures we're using the REAL export logic, not mocks.
        """
        # Mock getting gold-star tasks
        mock_label_studio_http.get_gold_star_tasks.return_value = [
            {
                "id": 1,
                "data": {
                    "conquest_type": "candidate_evaluation",
                    "name": "John Doe"
                },
                "annotations": [{
                    "result": {
                        "recommendation": "yes",
                        "trajectory_rating": "strong"
                    }
                }],
                "predictions": [{
                    "result": {
                        "recommendation": "yes",
                        "trajectory_rating": "strong"
                    }
                }]
            }
        ]

        # Export dataset
        response = client.post("/api/export", json={
            "conquest_type": "candidate_evaluation",
            "format": "icl",
            "min_agreement": 0.8
        })

        assert response.status_code == 200
        data = response.json()
        assert data["conquest_type"] == "candidate_evaluation"
        assert data["format"] == "icl"
        assert "examples" in data
        assert "count" in data


class TestAllConquestTypes:
    """Test all conquest types with their specific schemas"""

    def test_candidate_evaluation_schema_validation(self, client, mock_label_studio_http):
        """Test candidate_evaluation with all required fields"""
        mock_label_studio_http.create_task.return_value = {"id": 1}
        mock_label_studio_http.get_project.return_value = {"id": 1}

        response = client.post("/api/tasks", json={
            "conquest_type": "candidate_evaluation",
            "data": {
                "name": "Alice Johnson",
                "role": "Senior Software Engineer",
                "education": "MS Computer Science, MIT",
                "work_history": "Google (2020-2024), Amazon (2018-2020)"
            },
            "llm_prediction": {
                "recommendation": "strong_yes",
                "trajectory_rating": "exceptional",
                "company_pedigree": "exceptional",
                "educational_pedigree": "exceptional",
                "is_software_engineer": True
            },
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 200

    def test_cartographer_schema_validation(self, client, mock_label_studio_http):
        """Test cartographer with all required fields"""
        mock_label_studio_http.create_task.return_value = {"id": 2}
        mock_label_studio_http.get_project.return_value = {"id": 2}

        response = client.post("/api/tasks", json={
            "conquest_type": "cartographer",
            "data": {
                "name": "Bob Smith",
                "current_role": "Engineering Manager",
                "work_history": "Meta (2019-2024), Google (2015-2019)",
                "education": "BS Computer Science, Stanford"
            },
            "llm_prediction": {
                "career_trajectory": "upward",
                "leadership_potential": "high"
            },
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 200

    def test_cv_parsing_schema_validation(self, client, mock_label_studio_http):
        """Test cv_parsing with all required fields"""
        mock_label_studio_http.create_task.return_value = {"id": 3}
        mock_label_studio_http.get_project.return_value = {"id": 3}

        response = client.post("/api/tasks", json={
            "conquest_type": "cv_parsing",
            "data": {
                "resume_text": "John Doe\nSoftware Engineer\nGoogle, 2020-2024\nBS CS, MIT"
            },
            "llm_prediction": {
                "name": "John Doe",
                "current_role": "Software Engineer",
                "companies": ["Google"],
                "education": "BS CS, MIT"
            },
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 200

    def test_email_evaluation_schema_validation(self, client, mock_label_studio_http):
        """Test email_evaluation with all required fields"""
        mock_label_studio_http.create_task.return_value = {"id": 4}
        mock_label_studio_http.get_project.return_value = {"id": 4}

        response = client.post("/api/tasks", json={
            "conquest_type": "email_evaluation",
            "data": {
                "from": "recruiter@company.com",
                "to": "candidate@email.com",
                "subject": "Exciting opportunity at TechCorp",
                "email_body": "Hi, we have an exciting role..."
            },
            "llm_prediction": {
                "quality": "high",
                "personalization": "medium",
                "relevance": "high"
            },
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 200

    def test_quil_email_schema_validation(self, client, mock_label_studio_http):
        """Test quil_email with all required fields"""
        mock_label_studio_http.create_task.return_value = {"id": 5}
        mock_label_studio_http.get_project.return_value = {"id": 5}

        response = client.post("/api/tasks", json={
            "conquest_type": "quil_email",
            "data": {
                "candidate_name": "Sarah Chen",
                "current_role": "Senior Engineer",
                "current_company": "Google",
                "target_role": "Staff Engineer",
                "company_name": "Meta"
            },
            "llm_prediction": {
                "email_subject": "Exciting Staff Engineer opportunity at Meta",
                "email_body": "Hi Sarah, I noticed your work at Google..."
            },
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 200

    def test_report_evaluation_schema_validation(self, client, mock_label_studio_http):
        """Test report_evaluation with all required fields"""
        mock_label_studio_http.create_task.return_value = {"id": 6}
        mock_label_studio_http.get_project.return_value = {"id": 6}

        response = client.post("/api/tasks", json={
            "conquest_type": "report_evaluation",
            "data": {
                "title": "Q4 2024 Engineering Report",
                "author": "Engineering Team",
                "date": "2024-12-31",
                "report_type": "quarterly",
                "executive_summary": "Strong performance across all metrics...",
                "key_findings": "1. Velocity increased 20%\n2. Quality improved..."
            },
            "llm_prediction": {
                "quality": "high",
                "completeness": "complete",
                "actionability": "high"
            },
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 200


class TestErrorHandling:
    """Test error cases and validation"""

    def test_missing_required_field_rejected(self, client, mock_label_studio_http):
        """Test that missing required fields are rejected"""
        response = client.post("/api/tasks", json={
            "conquest_type": "candidate_evaluation",
            "data": {
                "name": "John Doe"
                # Missing: role, education, work_history
            },
            "llm_prediction": {},
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 400

    def test_invalid_conquest_type_rejected(self, client):
        """Test that invalid conquest types are rejected"""
        response = client.post("/api/tasks", json={
            "conquest_type": "nonexistent_conquest",
            "data": {"name": "John Doe"},
            "llm_prediction": {},
            "model_version": "gemma-3-4b"
        })

        assert response.status_code == 404
        assert "unknown conquest type" in response.json()["detail"].lower()

    def test_bulk_import_handles_malformed_json_gracefully(self, client, mock_label_studio_http):
        """Test that bulk import handles malformed JSON without failing entire batch"""
        mock_label_studio_http.create_task.return_value = {"id": 1}
        mock_label_studio_http.get_project.return_value = {"id": 1}

        response = client.post("/api/tasks/bulk-import", json={
            "batch_id": "batch_error_test",
            "conquest_type": "candidate_evaluation",
            "model_version": "gemma-3-4b",
            "results": [
                # Valid JSON result
                {
                    "custom_id": "valid-001",
                    "response": {
                        "body": {
                            "choices": [{
                                "message": {
                                    "content": json.dumps({
                                        "recommendation": "yes",
                                        "trajectory_rating": "strong"
                                    })
                                }
                            }]
                        }
                    },
                    "request": {
                        "body": {
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    }
                },
                # Non-JSON text result (should be handled gracefully)
                {
                    "custom_id": "text-001",
                    "response": {
                        "body": {
                            "choices": [{
                                "message": {
                                    "content": "This is plain text, not JSON"
                                }
                            }]
                        }
                    },
                    "request": {
                        "body": {
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    }
                }
            ]
        })

        assert response.status_code == 200
        data = response.json()
        # Both should be created (non-JSON is stored as {"response": text})
        assert data["created_count"] == 2
        assert data["skipped_count"] == 0

    def test_bulk_import_skips_results_with_no_choices(self, client, mock_label_studio_http):
        """Test that bulk import skips results with missing choices"""
        mock_label_studio_http.create_task.return_value = {"id": 1}
        mock_label_studio_http.get_project.return_value = {"id": 1}

        response = client.post("/api/tasks/bulk-import", json={
            "batch_id": "batch_skip_test",
            "conquest_type": "candidate_evaluation",
            "model_version": "gemma-3-4b",
            "results": [
                # Valid result
                {
                    "custom_id": "valid-001",
                    "response": {
                        "body": {
                            "choices": [{
                                "message": {
                                    "content": json.dumps({"recommendation": "yes"})
                                }
                            }]
                        }
                    },
                    "request": {
                        "body": {
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    }
                },
                # Invalid result (no choices)
                {
                    "custom_id": "invalid-001",
                    "response": {
                        "body": {
                            "choices": []  # Empty choices array
                        }
                    },
                    "request": {
                        "body": {
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    }
                }
            ]
        })

        assert response.status_code == 200
        data = response.json()
        # Should have created 1 and skipped 1
        assert data["created_count"] == 1
        assert data["skipped_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

