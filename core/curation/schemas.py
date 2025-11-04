"""
Task Schema Definitions

Generic schema models for defining task types in the curation system.
"""

from typing import Any

from pydantic import BaseModel


class DataSource(BaseModel):
    """Data source configuration for a task"""
    id: str
    name: str
    type: str  # "text", "structured", "file"
    required: bool = True
    displayFormat: str | None = None  # "header", "list", "collapsible"


class Question(BaseModel):
    """Question configuration for task annotation"""
    id: str
    text: str
    type: str  # "choice", "rating", "boolean", "text", "structured"
    options: list[str] | None = None
    required: bool = True
    helpText: str | None = None
    validation: dict[str, Any] | None = None


class RenderingConfig(BaseModel):
    """UI rendering configuration"""
    layout: str = "two-column"  # "single-column", "two-column", "grid"
    theme: str = "gradient"  # "gradient", "minimal", "professional"
    showLLMPrediction: bool = True
    showDataSources: bool = True
    showRubrics: bool = True
    customCSS: str | None = None


class ExportConfig(BaseModel):
    """Export format configuration"""
    iclFormat: dict[str, str] | None = None
    finetuningFormat: dict[str, list[str]] | None = None


class TaskSchema(BaseModel):
    """
    Complete task schema definition.
    
    Defines the structure, questions, and rendering for a task type.
    Used to generate Label Studio configs and UI components.
    """
    id: str
    name: str
    description: str
    version: str
    dataSources: list[DataSource]
    questions: list[Question]
    rendering: RenderingConfig
    export: ExportConfig | None = None
    labelStudioConfig: str | None = None

