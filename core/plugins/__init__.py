"""
Plugin System for vLLM Batch Server

Enables users to build custom workflows without forking the codebase.

Example:
    from core.plugins import PluginRegistry
    
    registry = PluginRegistry("plugins/")
    registry.discover_plugins()
    
    parser = registry.get_plugin("candidate-evaluator")
    data = parser.parse_response(llm_response)
"""

from .base import (
    Plugin,
    SchemaPlugin,
    ParserPlugin,
    UIPlugin,
    ExportPlugin,
    RatingPlugin,
)
from .registry import PluginRegistry
from .hooks import HookRegistry, hook_registry

__all__ = [
    "Plugin",
    "SchemaPlugin",
    "ParserPlugin",
    "UIPlugin",
    "ExportPlugin",
    "RatingPlugin",
    "PluginRegistry",
    "HookRegistry",
    "hook_registry",
]

