"""
Task Schema Registry

Manages task schemas and provides schema-driven functionality.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .schemas import TaskSchema

logger = logging.getLogger(__name__)


class TaskRegistry:
    """
    Registry for managing task schemas.
    
    Loads schemas from a directory and provides access to them.
    Integrations can provide their own schema directories.
    """

    def __init__(self, schemas_dir: str | Path):
        """
        Initialize the registry.
        
        Args:
            schemas_dir: Path to directory containing schema JSON files
        """
        self.schemas_dir = Path(schemas_dir)
        self.schemas: dict[str, TaskSchema] = {}
        self.load_schemas()

    def load_schemas(self) -> None:
        """Load all schemas from the schemas directory"""
        if not self.schemas_dir.exists():
            logger.warning(f"Schemas directory not found: {self.schemas_dir}")
            return

        for schema_file in self.schemas_dir.glob("*.json"):
            try:
                with open(schema_file) as f:
                    schema_data = json.load(f)
                    schema = TaskSchema(**schema_data)
                    self.schemas[schema.id] = schema
                    logger.info(f"Loaded schema: {schema.id} from {schema_file.name}")
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")

    def get_schema(self, task_type: str) -> TaskSchema | None:
        """
        Get schema by task type ID.
        
        Args:
            task_type: The task type identifier
            
        Returns:
            TaskSchema if found, None otherwise
        """
        return self.schemas.get(task_type)

    def list_schemas(self) -> list[TaskSchema]:
        """
        List all available schemas.
        
        Returns:
            List of all loaded TaskSchema objects
        """
        return list(self.schemas.values())

    def validate_task_data(self, task_type: str, data: dict[str, Any]) -> bool:
        """
        Validate task data against schema.
        
        Args:
            task_type: The task type identifier
            data: The task data to validate
            
        Returns:
            True if valid, False otherwise
        """
        schema = self.get_schema(task_type)
        if not schema:
            logger.error(f"Schema not found for task type: {task_type}")
            return False

        # Basic validation: check that all required data sources are present
        required_sources = [ds.id for ds in schema.dataSources if ds.required]
        for source_id in required_sources:
            if source_id not in data:
                logger.error(f"Missing required data source: {source_id}")
                return False

        return True

    def generate_label_studio_config(self, schema: TaskSchema) -> str:
        """
        Generate Label Studio XML config from task schema.
        
        Args:
            schema: The TaskSchema to generate config for
            
        Returns:
            Label Studio XML configuration string
        """
        # If schema has pre-defined Label Studio config, use it
        if schema.labelStudioConfig:
            return schema.labelStudioConfig

        # Otherwise, generate basic config from schema
        xml_parts = ['<View>']

        # Add data sources as text displays
        for source in schema.dataSources:
            if source.type == "text":
                xml_parts.append(f'  <Text name="{source.id}" value="${source.id}"/>')
            elif source.type == "structured":
                xml_parts.append(f'  <HyperText name="{source.id}" value="${source.id}"/>')

        # Add questions as choices/ratings
        for question in schema.questions:
            if question.type == "choice" and question.options:
                xml_parts.append(f'  <Choices name="{question.id}" toName="data" choice="single">')
                for option in question.options:
                    xml_parts.append(f'    <Choice value="{option}"/>')
                xml_parts.append('  </Choices>')
            elif question.type == "rating":
                xml_parts.append(f'  <Rating name="{question.id}" toName="data" maxRating="5"/>')
            elif question.type == "text":
                xml_parts.append(f'  <TextArea name="{question.id}" toName="data"/>')

        xml_parts.append('</View>')
        return '\n'.join(xml_parts)

