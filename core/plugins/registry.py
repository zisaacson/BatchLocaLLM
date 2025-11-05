"""
Plugin Registry - Central registry for all plugins.

Handles plugin discovery, loading, and retrieval.
"""

import json
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type
import logging

from .base import (
    Plugin,
    SchemaPlugin,
    ParserPlugin,
    UIPlugin,
    ExportPlugin,
    RatingPlugin,
)

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry for all plugins"""
    
    def __init__(self, plugin_dir: Path):
        """
        Initialize plugin registry
        
        Args:
            plugin_dir: Path to plugins directory
        """
        self.plugin_dir = Path(plugin_dir)
        self.plugins: Dict[str, Plugin] = {}
        self.manifests: Dict[str, Dict] = {}
        self.enabled_plugins: List[str] = []
    
    def discover_plugins(self, enabled_only: bool = True):
        """
        Scan plugin directory and load all plugins
        
        Args:
            enabled_only: Only load enabled plugins (from config)
        """
        if not self.plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {self.plugin_dir}")
            return
        
        logger.info(f"Discovering plugins in {self.plugin_dir}")
        
        for plugin_path in self.plugin_dir.iterdir():
            if not plugin_path.is_dir():
                continue
            
            if plugin_path.name.startswith("_") or plugin_path.name.startswith("."):
                continue
            
            manifest_path = plugin_path / "plugin.json"
            if not manifest_path.exists():
                logger.debug(f"Skipping {plugin_path.name} - no plugin.json")
                continue
            
            try:
                self.load_plugin(plugin_path)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_path.name}: {e}")
    
    def load_plugin(self, plugin_path: Path):
        """
        Load a single plugin
        
        Args:
            plugin_path: Path to plugin directory
        """
        manifest_path = plugin_path / "plugin.json"
        manifest = json.loads(manifest_path.read_text())
        plugin_id = manifest["id"]
        
        logger.info(f"Loading plugin: {plugin_id}")
        
        # Store manifest
        self.manifests[plugin_id] = manifest
        
        # Import plugin module
        init_file = plugin_path / "__init__.py"
        if not init_file.exists():
            logger.warning(f"Plugin {plugin_id} has no __init__.py")
            return
        
        # Dynamic import
        spec = importlib.util.spec_from_file_location(
            f"plugins.{plugin_id}",
            init_file
        )
        if spec is None or spec.loader is None:
            logger.error(f"Failed to load plugin spec: {plugin_id}")
            return
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"plugins.{plugin_id}"] = module
        spec.loader.exec_module(module)
        
        # Get plugin class
        plugin_class_name = manifest.get("plugin_class", "Plugin")
        if not hasattr(module, plugin_class_name):
            logger.error(f"Plugin {plugin_id} missing class {plugin_class_name}")
            return
        
        plugin_class = getattr(module, plugin_class_name)
        plugin_instance = plugin_class(manifest.get("config", {}))
        
        self.plugins[plugin_id] = plugin_instance
        logger.info(f"✅ Loaded plugin: {plugin_id} v{plugin_instance.get_version()}")
    
    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """
        Get plugin by ID
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Plugin instance or None
        """
        return self.plugins.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: Type[Plugin]) -> List[Plugin]:
        """
        Get all plugins of a specific type
        
        Args:
            plugin_type: Plugin class type
            
        Returns:
            List of plugin instances
        """
        return [
            p for p in self.plugins.values()
            if isinstance(p, plugin_type)
        ]
    
    def get_schema_plugins(self) -> List[SchemaPlugin]:
        """Get all schema plugins"""
        return self.get_plugins_by_type(SchemaPlugin)
    
    def get_parser_plugins(self) -> List[ParserPlugin]:
        """Get all parser plugins"""
        return self.get_plugins_by_type(ParserPlugin)
    
    def get_ui_plugins(self) -> List[UIPlugin]:
        """Get all UI plugins"""
        return self.get_plugins_by_type(UIPlugin)
    
    def get_export_plugins(self) -> List[ExportPlugin]:
        """Get all export plugins"""
        return self.get_plugins_by_type(ExportPlugin)
    
    def get_rating_plugins(self) -> List[RatingPlugin]:
        """Get all rating plugins"""
        return self.get_plugins_by_type(RatingPlugin)
    
    def get_manifest(self, plugin_id: str) -> Optional[Dict]:
        """
        Get plugin manifest
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Manifest dictionary or None
        """
        return self.manifests.get(plugin_id)
    
    def list_plugins(self) -> List[Dict[str, str]]:
        """
        List all loaded plugins
        
        Returns:
            List of plugin info dictionaries
        """
        return [
            {
                "id": plugin.get_id(),
                "name": plugin.get_name(),
                "version": plugin.get_version(),
                "description": plugin.get_description(),
            }
            for plugin in self.plugins.values()
        ]
    
    def enable_plugin(self, plugin_id: str):
        """
        Enable a plugin
        
        Args:
            plugin_id: Plugin identifier
        """
        if plugin_id not in self.enabled_plugins:
            self.enabled_plugins.append(plugin_id)
            logger.info(f"Enabled plugin: {plugin_id}")
    
    def disable_plugin(self, plugin_id: str):
        """
        Disable a plugin
        
        Args:
            plugin_id: Plugin identifier
        """
        if plugin_id in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_id)
            logger.info(f"Disabled plugin: {plugin_id}")
    
    def is_enabled(self, plugin_id: str) -> bool:
        """
        Check if plugin is enabled
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            True if enabled, False otherwise
        """
        return plugin_id in self.enabled_plugins


# Global plugin registry instance
_global_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """
    Get global plugin registry instance
    
    Returns:
        Global PluginRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        from pathlib import Path
        plugin_dir = Path(__file__).parent.parent.parent / "plugins"
        _global_registry = PluginRegistry(plugin_dir)
        _global_registry.discover_plugins()
    return _global_registry


def reset_plugin_registry():
    """Reset global plugin registry (for testing)"""
    global _global_registry
    _global_registry = None

