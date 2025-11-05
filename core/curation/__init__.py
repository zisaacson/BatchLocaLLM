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

# Singleton registry instance
_registry: TaskRegistry | None = None


def get_registry(schemas_dir: str | None = None) -> TaskRegistry:
    """
    Get the global schema registry instance.

    Args:
        schemas_dir: Optional path to schemas directory. If not provided,
                    uses a default empty registry.

    Returns:
        TaskRegistry instance
    """
    global _registry
    if _registry is None:
        if schemas_dir:
            _registry = TaskRegistry(schemas_dir)
        else:
            # Create empty registry - integrations can add schemas later
            import tempfile
            from pathlib import Path
            temp_dir = Path(tempfile.mkdtemp())
            _registry = TaskRegistry(temp_dir)
    return _registry


__all__ = [
    "DataSource",
    "ExportConfig",
    "Question",
    "RenderingConfig",
    "TaskSchema",
    "TaskRegistry",
    "get_registry",
]

