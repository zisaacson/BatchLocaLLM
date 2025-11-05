"""
Base classes for plugins.

All plugins must inherit from one or more of these base classes.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Plugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize plugin with configuration from plugin.json
        
        Args:
            config: Plugin configuration dictionary
        """
        self.config = config
    
    @abstractmethod
    def get_id(self) -> str:
        """
        Get unique plugin identifier
        
        Returns:
            Plugin ID (e.g., "candidate-evaluator")
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get human-readable plugin name
        
        Returns:
            Plugin name (e.g., "Candidate Evaluator")
        """
        pass
    
    def get_version(self) -> str:
        """Get plugin version"""
        return self.config.get("version", "1.0.0")
    
    def get_description(self) -> str:
        """Get plugin description"""
        return self.config.get("description", "")


class SchemaPlugin(Plugin):
    """
    Plugin that provides a custom data schema.
    
    Use this to define custom data structures for your workflow.
    
    Example:
        class CandidateSchema(SchemaPlugin):
            def get_schema(self):
                return {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"}
                    }
                }
    """
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for this data type
        
        Returns:
            JSON Schema dictionary
        """
        pass
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate data against schema
        
        Args:
            data: Data to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def get_default_values(self) -> Dict[str, Any]:
        """
        Get default values for schema fields
        
        Returns:
            Dictionary of default values
        """
        return {}


class ParserPlugin(Plugin):
    """
    Plugin that parses LLM responses into structured data.
    
    Use this to extract structured information from LLM outputs.
    
    Example:
        class CandidateParser(ParserPlugin):
            def parse_response(self, response: str) -> dict:
                # Extract candidate name, title, etc.
                return {"name": "...", "title": "..."}
    """
    
    @abstractmethod
    def parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured data
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Structured data dictionary
        """
        pass
    
    @abstractmethod
    def extract_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract display fields for table views
        
        Args:
            data: Parsed data dictionary
            
        Returns:
            Dictionary of display fields (name, title, company, etc.)
        """
        pass
    
    def format_for_display(self, data: Dict[str, Any]) -> str:
        """
        Format data for human-readable display
        
        Args:
            data: Parsed data dictionary
            
        Returns:
            Formatted string
        """
        fields = self.extract_fields(data)
        return " | ".join(f"{k}: {v}" for k, v in fields.items())


class UIPlugin(Plugin):
    """
    Plugin that provides custom UI components.
    
    Use this to create custom curation interfaces, table views, etc.
    
    Example:
        class CandidateUI(UIPlugin):
            def get_ui_routes(self):
                return [
                    {"path": "/curation", "file": "ui/curation.html"},
                    {"path": "/table", "file": "ui/table.html"}
                ]
    """
    
    @abstractmethod
    def get_ui_routes(self) -> List[Dict[str, str]]:
        """
        Return list of UI routes this plugin provides
        
        Returns:
            List of route dictionaries with 'path' and 'file' keys
            
        Example:
            [
                {"path": "/curation", "file": "ui/curation.html"},
                {"path": "/table", "file": "ui/table.html"}
            ]
        """
        pass
    
    @abstractmethod
    def get_ui_components(self) -> List[str]:
        """
        Return list of UI component IDs this plugin provides
        
        Returns:
            List of component IDs
            
        Example:
            ["rating-widget", "candidate-card", "table-row"]
        """
        pass
    
    def render_component(self, component_id: str, data: Dict[str, Any]) -> str:
        """
        Render a UI component with data
        
        Args:
            component_id: Component identifier
            data: Data to render
            
        Returns:
            Rendered HTML string
        """
        return f"<div>Component {component_id} not implemented</div>"


class ExportPlugin(Plugin):
    """
    Plugin that provides custom export formats.
    
    Use this to export data in custom formats (ICL, fine-tuning, etc.)
    
    Example:
        class QualityExporter(ExportPlugin):
            def export(self, tasks, format="icl", min_quality=9):
                # Filter by quality and export
                return filtered_tasks
    """
    
    @abstractmethod
    def export(self, tasks: List[Dict[str, Any]], format: str, **kwargs) -> str:
        """
        Export tasks in custom format
        
        Args:
            tasks: List of task dictionaries
            format: Export format identifier
            **kwargs: Additional export parameters
            
        Returns:
            Exported data as string (JSONL, CSV, etc.)
        """
        pass
    
    @abstractmethod
    def get_export_formats(self) -> List[Dict[str, Any]]:
        """
        Return list of supported export formats
        
        Returns:
            List of format dictionaries with 'id', 'name', and 'description'
            
        Example:
            [
                {
                    "id": "icl",
                    "name": "In-Context Learning",
                    "description": "Export high-quality examples for ICL"
                },
                {
                    "id": "finetuning",
                    "name": "Fine-tuning Dataset",
                    "description": "Export dataset for fine-tuning"
                }
            ]
        """
        pass
    
    def filter_by_criteria(self, tasks: List[Dict[str, Any]], **criteria) -> List[Dict[str, Any]]:
        """
        Filter tasks by criteria (quality, rating, etc.)
        
        Args:
            tasks: List of task dictionaries
            **criteria: Filter criteria
            
        Returns:
            Filtered list of tasks
        """
        return tasks


class RatingPlugin(Plugin):
    """
    Plugin that provides a rating system.
    
    Use this to implement custom rating systems (categorical, numeric, etc.)
    
    Example:
        class CategoricalRater(RatingPlugin):
            def get_rating_categories(self):
                return {
                    "recommendation": ["Strong Yes", "Yes", "Maybe", "No", "Strong No"]
                }
    """
    
    @abstractmethod
    def get_rating_categories(self) -> Dict[str, List[str]]:
        """
        Get rating categories for this plugin
        
        Returns:
            Dictionary mapping category names to list of rating values
            
        Example:
            {
                "recommendation": ["Strong Yes", "Yes", "Maybe", "No", "Strong No"],
                "quality": ["Exceptional", "Strong", "Good", "Average", "Weak"]
            }
        """
        pass
    
    @abstractmethod
    def validate_rating(self, category: str, value: str) -> bool:
        """
        Validate a rating value for a category
        
        Args:
            category: Rating category name
            value: Rating value to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def get_rating_display(self, category: str, value: str) -> Dict[str, str]:
        """
        Get display properties for a rating (color, icon, etc.)
        
        Args:
            category: Rating category name
            value: Rating value
            
        Returns:
            Dictionary with display properties
            
        Example:
            {
                "color": "#28a745",
                "icon": "⭐",
                "label": "Strong Yes"
            }
        """
        return {
            "color": "#6c757d",
            "icon": "",
            "label": value
        }

