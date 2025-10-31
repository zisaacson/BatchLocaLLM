"""
Conquest Schema Registry

Manages conquest type schemas and provides schema-driven functionality.
"""

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class DataSource(BaseModel):
    """Data source configuration"""
    id: str
    name: str
    type: str  # "text", "structured", "file"
    required: bool = True
    displayFormat: (str) | None = None  # "header", "list", "collapsible"


class Question(BaseModel):
    """Question configuration"""
    id: str
    text: str
    type: str  # "choice", "rating", "boolean", "text", "structured"
    options: (list[str]) | None = None
    required: bool = True
    helpText: (str) | None = None
    validation: (dict[str, Any]) | None = None


class RenderingConfig(BaseModel):
    """UI rendering configuration"""
    layout: str = "two-column"  # "single-column", "two-column", "grid"
    theme: str = "gradient"  # "gradient", "minimal", "professional"
    showLLMPrediction: bool = True
    showDataSources: bool = True
    showRubrics: bool = True
    customCSS: (str) | None = None


class ExportConfig(BaseModel):
    """Export format configuration"""
    iclFormat: (dict[str, str]) | None = None
    finetuningFormat: (dict[str, list[str]]) | None = None


class ConquestSchema(BaseModel):
    """Complete conquest schema"""
    id: str
    name: str
    description: str
    version: str
    dataSources: list[DataSource]
    questions: list[Question]
    rendering: RenderingConfig
    export: (ExportConfig) | None = None
    labelStudioConfig: (str) | None = None


class ConquestSchemaRegistry:
    """Registry for managing conquest schemas"""
    
    def __init__(self, schemas_dir: str = "conquest_schemas"):
        self.schemas_dir = Path(schemas_dir)
        self.schemas: dict[str, ConquestSchema] = {}
        self.load_schemas()
    
    def load_schemas(self) -> None:
        """Load all schemas from the schemas directory"""
        if not self.schemas_dir.exists():
            logger.warning(f"Schemas directory not found: {self.schemas_dir}")
            return
        
        for schema_file in self.schemas_dir.glob("*.json"):
            try:
                with open(schema_file, 'r') as f:
                    schema_data = json.load(f)
                    schema = ConquestSchema(**schema_data)
                    self.schemas[schema.id] = schema
                    logger.info(f"Loaded schema: {schema.id}")
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")
    
    def get_schema(self, conquest_type: str) -> (ConquestSchema]:
        """Get schema by conquest type ID"""
        return self.schemas.get(conquest_type)
    
    def list_schemas(self) -> list[ConquestSchema]:
        """List all available schemas"""
        return list(self.schemas.values())
    
    def generate_label_studio_config(self, schema: ConquestSchema) -> str:
        """
        Generate Label Studio XML config from conquest schema
        
        This is used internally by Label Studio but we don't use their UI.
        We generate it programmatically for API compatibility.
        """
        config_parts = ['<View>']
        
        # Add data source displays
        for ds in schema.dataSources:
            if ds.displayFormat == "header":
                config_parts.append(f'  <Header name="{ds.id}" value="${ds.id}"/>')
            elif ds.displayFormat == "list":
                config_parts.append(f'  <List name="{ds.id}" value="${ds.id}"/>')
            elif ds.displayFormat == "collapsible":
                config_parts.append(f'  <TextArea name="{ds.id}" value="${ds.id}" editable="false"/>')
            else:
                config_parts.append(f'  <Text name="{ds.id}" value="${ds.id}"/>')
        
        # Add questions
        for q in schema.questions:
            config_parts.append(f'  <Header value="{q.text}"/>')
            
            if q.type in ["choice", "rating", "boolean"]:
                config_parts.append(f'  <Choices name="{q.id}" toName="data" choice="single" required="{str(q.required).lower()}">')
                for option in (q.options or []):
                    config_parts.append(f'    <Choice value="{option}"/>')
                config_parts.append('  </Choices>')
            elif q.type == "text":
                config_parts.append(f'  <TextArea name="{q.id}" toName="data" required="{str(q.required).lower()}"/>')
        
        config_parts.append('</View>')
        
        return '\n'.join(config_parts)
    
    def validate_task_data(self, conquest_type: str, data: dict[str, Any]) -> bool:
        """Validate task data against schema"""
        schema = self.get_schema(conquest_type)
        if not schema:
            return False
        
        # Check required data sources
        for ds in schema.dataSources:
            if ds.required and ds.id not in data:
                logger.error(f"Missing required data source: {ds.id}")
                return False
        
        return True
    
    def validate_annotation(self, conquest_type: str, annotation: dict[str, Any]) -> bool:
        """Validate annotation against schema"""
        schema = self.get_schema(conquest_type)
        if not schema:
            return False
        
        # Check required questions
        for q in schema.questions:
            if q.required and q.id not in annotation:
                logger.error(f"Missing required question: {q.id}")
                return False
            
            # Validate choice/rating options
            if q.type in ["choice", "rating", "boolean"] and q.options:
                if annotation.get(q.id) not in q.options:
                    logger.error(f"Invalid option for {q.id}: {annotation.get(q.id)}")
                    return False
        
        return True
    
    def export_to_icl(self, tasks: list[dict[str, Any]], conquest_type: str) -> list[dict[str, Any]]:
        """
        Export tasks to In-Context Learning format
        
        Returns list of {"messages": [...]} objects for ICL
        """
        schema = self.get_schema(conquest_type)
        if not schema or not schema.export or not schema.export.iclFormat:
            raise ValueError(f"No ICL export config for {conquest_type}")
        
        icl_format = schema.export.iclFormat
        icl_examples = []
        
        for task in tasks:
            data = task.get('data', {})
            annotations = task.get('annotations', [])
            
            if not annotations:
                continue
            
            annotation = annotations[0].get('result', {})
            
            # Format user prompt
            user_prompt = icl_format['userPromptTemplate']
            for key, value in data.items():
                user_prompt = user_prompt.replace(f'{{{key}}}', str(value))
            
            # Format assistant response
            assistant_response = icl_format['assistantResponseTemplate']
            for key, value in annotation.items():
                assistant_response = assistant_response.replace(f'{{{key}}}', str(value))
            
            icl_examples.append({
                "messages": [
                    {"role": "system", "content": icl_format['systemPrompt']},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": assistant_response}
                ]
            })
        
        return icl_examples
    
    def export_to_finetuning(self, tasks: list[dict[str, Any]], conquest_type: str) -> list[dict[str, Any]]:
        """
        Export tasks to fine-tuning format
        
        Returns list of {"input": {...}, "output": {...}} objects
        """
        schema = self.get_schema(conquest_type)
        if not schema or not schema.export or not schema.export.finetuningFormat:
            raise ValueError(f"No fine-tuning export config for {conquest_type}")
        
        ft_format = schema.export.finetuningFormat
        ft_examples = []
        
        for task in tasks:
            data = task.get('data', {})
            annotations = task.get('annotations', [])
            
            if not annotations:
                continue
            
            annotation = annotations[0].get('result', {})
            
            # Extract input fields
            input_data = {k: data.get(k) for k in ft_format['inputFields'] if k in data}
            
            # Extract output fields
            output_data = {k: annotation.get(k) for k in ft_format['outputFields'] if k in annotation}
            
            ft_examples.append({
                "input": input_data,
                "output": output_data
            })
        
        return ft_examples


# Global registry instance
_registry = None

def get_registry() -> ConquestSchemaRegistry:
    """Get the global schema registry"""
    global _registry
    if _registry is None:
        _registry = ConquestSchemaRegistry()
    return _registry

