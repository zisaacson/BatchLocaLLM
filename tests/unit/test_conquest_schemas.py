"""
Tests for Conquest Schema Registry

Tests schema loading, validation, and export functionality.
"""

import json
import tempfile
from pathlib import Path

import pytest

from curation_app.conquest_schemas import (
    ConquestSchemaRegistry,
)


@pytest.fixture
def temp_schemas_dir():
    """Create temporary schemas directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        schemas_dir = Path(tmpdir) / "schemas"
        schemas_dir.mkdir()
        yield schemas_dir


@pytest.fixture
def sample_schema():
    """Sample conquest schema"""
    return {
        "id": "test_conquest",
        "name": "Test Conquest",
        "description": "Test conquest for unit tests",
        "version": "1.0.0",
        "dataSources": [
            {
                "id": "name",
                "name": "Name",
                "type": "text",
                "required": True,
                "displayFormat": "header"
            },
            {
                "id": "description",
                "name": "Description",
                "type": "text",
                "required": False
            }
        ],
        "questions": [
            {
                "id": "rating",
                "text": "Overall Rating",
                "type": "choice",
                "options": ["Excellent", "Good", "Average", "Poor"],
                "required": True,
                "helpText": "Rate the overall quality"
            },
            {
                "id": "is_valid",
                "text": "Is Valid?",
                "type": "boolean",
                "options": ["Yes", "No"],
                "required": True
            },
            {
                "id": "notes",
                "text": "Additional Notes",
                "type": "text",
                "required": False
            }
        ],
        "rendering": {
            "layout": "two-column",
            "theme": "gradient",
            "showLLMPrediction": True,
            "showDataSources": True,
            "showRubrics": True,
            "customCSS": ".test { color: red; }"
        },
        "export": {
            "iclFormat": {
                "systemPrompt": "You are a test evaluator.",
                "userPromptTemplate": "Evaluate: {name}",
                "assistantResponseTemplate": "Rating: {rating}"
            },
            "finetuningFormat": {
                "inputFields": ["name", "description"],
                "outputFields": ["rating", "is_valid"]
            }
        }
    }


@pytest.fixture
def registry_with_schema(temp_schemas_dir, sample_schema):
    """Registry with a loaded schema"""
    schema_file = temp_schemas_dir / "test_conquest.json"
    with open(schema_file, 'w') as f:
        json.dump(sample_schema, f)

    return ConquestSchemaRegistry(schemas_dir=str(temp_schemas_dir))


class TestConquestSchemaRegistry:
    """Test conquest schema registry"""

    def test_load_schemas(self, temp_schemas_dir, sample_schema):
        """Test loading schemas from directory"""
        schema_file = temp_schemas_dir / "test_conquest.json"
        with open(schema_file, 'w') as f:
            json.dump(sample_schema, f)

        registry = ConquestSchemaRegistry(schemas_dir=str(temp_schemas_dir))

        assert len(registry.schemas) == 1
        assert "test_conquest" in registry.schemas
        assert registry.schemas["test_conquest"].name == "Test Conquest"

    def test_load_multiple_schemas(self, temp_schemas_dir, sample_schema):
        """Test loading multiple schemas"""
        # Create two schema files
        for i in range(2):
            schema = sample_schema.copy()
            schema["id"] = f"test_conquest_{i}"
            schema["name"] = f"Test Conquest {i}"

            schema_file = temp_schemas_dir / f"test_conquest_{i}.json"
            with open(schema_file, 'w') as f:
                json.dump(schema, f)

        registry = ConquestSchemaRegistry(schemas_dir=str(temp_schemas_dir))

        assert len(registry.schemas) == 2
        assert "test_conquest_0" in registry.schemas
        assert "test_conquest_1" in registry.schemas

    def test_load_invalid_schema(self, temp_schemas_dir):
        """Test handling of invalid schema"""
        schema_file = temp_schemas_dir / "invalid.json"
        with open(schema_file, 'w') as f:
            f.write("invalid json{")

        registry = ConquestSchemaRegistry(schemas_dir=str(temp_schemas_dir))

        # Should not crash, just skip invalid schema
        assert len(registry.schemas) == 0

    def test_get_schema(self, registry_with_schema):
        """Test getting a schema by ID"""
        schema = registry_with_schema.get_schema("test_conquest")

        assert schema is not None
        assert schema.id == "test_conquest"
        assert schema.name == "Test Conquest"

    def test_get_nonexistent_schema(self, registry_with_schema):
        """Test getting a non-existent schema"""
        schema = registry_with_schema.get_schema("nonexistent")

        assert schema is None

    def test_list_schemas(self, registry_with_schema):
        """Test listing all schemas"""
        schemas = registry_with_schema.list_schemas()

        assert len(schemas) == 1
        assert schemas[0].id == "test_conquest"

    def test_generate_label_studio_config(self, registry_with_schema):
        """Test generating Label Studio XML config"""
        schema = registry_with_schema.get_schema("test_conquest")
        config = registry_with_schema.generate_label_studio_config(schema)

        assert "<View>" in config
        assert "</View>" in config
        assert 'name="name"' in config
        assert 'name="rating"' in config
        assert "<Choices" in config
        assert '<Choice value="Excellent"/>' in config

    def test_validate_task_data_valid(self, registry_with_schema):
        """Test validating valid task data"""
        data = {
            "name": "John Doe",
            "description": "Test description"
        }

        is_valid = registry_with_schema.validate_task_data("test_conquest", data)

        assert is_valid is True

    def test_validate_task_data_missing_required(self, registry_with_schema):
        """Test validating task data with missing required field"""
        data = {
            "description": "Test description"
            # Missing required "name" field
        }

        is_valid = registry_with_schema.validate_task_data("test_conquest", data)

        assert is_valid is False

    def test_validate_task_data_missing_optional(self, registry_with_schema):
        """Test validating task data with missing optional field"""
        data = {
            "name": "John Doe"
            # Missing optional "description" field
        }

        is_valid = registry_with_schema.validate_task_data("test_conquest", data)

        assert is_valid is True

    def test_validate_annotation_valid(self, registry_with_schema):
        """Test validating valid annotation"""
        annotation = {
            "rating": "Excellent",
            "is_valid": "Yes",
            "notes": "Great work"
        }

        is_valid = registry_with_schema.validate_annotation("test_conquest", annotation)

        assert is_valid is True

    def test_validate_annotation_missing_required(self, registry_with_schema):
        """Test validating annotation with missing required field"""
        annotation = {
            "rating": "Excellent"
            # Missing required "is_valid" field
        }

        is_valid = registry_with_schema.validate_annotation("test_conquest", annotation)

        assert is_valid is False

    def test_validate_annotation_invalid_option(self, registry_with_schema):
        """Test validating annotation with invalid option"""
        annotation = {
            "rating": "Invalid Option",  # Not in options list
            "is_valid": "Yes"
        }

        is_valid = registry_with_schema.validate_annotation("test_conquest", annotation)

        assert is_valid is False

    def test_export_to_icl(self, registry_with_schema):
        """Test exporting to ICL format"""
        tasks = [
            {
                "data": {
                    "name": "John Doe",
                    "description": "Test person"
                },
                "annotations": [
                    {
                        "result": {
                            "rating": "Excellent",
                            "is_valid": "Yes"
                        }
                    }
                ]
            },
            {
                "data": {
                    "name": "Jane Smith",
                    "description": "Another test"
                },
                "annotations": [
                    {
                        "result": {
                            "rating": "Good",
                            "is_valid": "Yes"
                        }
                    }
                ]
            }
        ]

        examples = registry_with_schema.export_to_icl(tasks, "test_conquest")

        assert len(examples) == 2
        assert examples[0]["messages"][0]["role"] == "system"
        assert examples[0]["messages"][1]["role"] == "user"
        assert examples[0]["messages"][2]["role"] == "assistant"
        assert "John Doe" in examples[0]["messages"][1]["content"]
        assert "Excellent" in examples[0]["messages"][2]["content"]

    def test_export_to_icl_no_annotations(self, registry_with_schema):
        """Test exporting to ICL with tasks that have no annotations"""
        tasks = [
            {
                "data": {"name": "John Doe"},
                "annotations": []  # No annotations
            }
        ]

        examples = registry_with_schema.export_to_icl(tasks, "test_conquest")

        assert len(examples) == 0

    def test_export_to_finetuning(self, registry_with_schema):
        """Test exporting to fine-tuning format"""
        tasks = [
            {
                "data": {
                    "name": "John Doe",
                    "description": "Test person"
                },
                "annotations": [
                    {
                        "result": {
                            "rating": "Excellent",
                            "is_valid": "Yes"
                        }
                    }
                ]
            }
        ]

        examples = registry_with_schema.export_to_finetuning(tasks, "test_conquest")

        assert len(examples) == 1
        assert examples[0]["input"] == {"name": "John Doe", "description": "Test person"}
        assert examples[0]["output"] == {"rating": "Excellent", "is_valid": "Yes"}

    def test_export_to_finetuning_partial_fields(self, registry_with_schema):
        """Test exporting to fine-tuning with partial fields"""
        tasks = [
            {
                "data": {
                    "name": "John Doe"
                    # Missing "description"
                },
                "annotations": [
                    {
                        "result": {
                            "rating": "Excellent"
                            # Missing "is_valid"
                        }
                    }
                ]
            }
        ]

        examples = registry_with_schema.export_to_finetuning(tasks, "test_conquest")

        assert len(examples) == 1
        assert examples[0]["input"] == {"name": "John Doe"}
        assert examples[0]["output"] == {"rating": "Excellent"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

