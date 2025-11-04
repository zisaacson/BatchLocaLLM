"""
Core Curation Module

Generic task curation system for batch inference results.
Integrates with Label Studio for human annotation and quality control.

This module provides:
- TaskSchema: Generic schema for defining task types
- TaskRegistry: Registry for managing task schemas
- CurationAPI: Generic FastAPI application for task curation

Integrations (like Aris) can extend this core functionality.
"""

from .schemas import (
    DataSource,
    ExportConfig,
    Question,
    RenderingConfig,
    TaskSchema,
)
from .registry import TaskRegistry

__all__ = [
    "DataSource",
    "ExportConfig",
    "Question",
    "RenderingConfig",
    "TaskSchema",
    "TaskRegistry",
]

