# Plugin Development Guide

Complete guide to building custom plugins for the vLLM Batch Server.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Plugin Types](#plugin-types)
4. [Creating Your First Plugin](#creating-your-first-plugin)
5. [Plugin Manifest](#plugin-manifest)
6. [API Reference](#api-reference)
7. [Best Practices](#best-practices)
8. [Examples](#examples)
9. [Testing](#testing)
10. [Distribution](#distribution)

---

## Overview

The plugin system allows you to extend the vLLM Batch Server with custom workflows without forking the codebase. Plugins can:

- Define custom data schemas
- Parse LLM responses in custom formats
- Provide custom UI components
- Export data in custom formats
- Implement custom rating systems

**Benefits:**
- ✅ No need to fork the codebase
- ✅ Hot-reload support
- ✅ Easy distribution via npm/PyPI
- ✅ Clean separation of concerns
- ✅ Version control for custom workflows

---

## Quick Start

### 1. Create Plugin Directory

```bash
mkdir -p plugins/my-plugin
cd plugins/my-plugin
```

### 2. Create `plugin.json`

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "My custom workflow plugin",
  "author": "Your Name",
  "license": "MIT",
  
  "provides": {
    "schema": "my_schema",
    "parser": "MyParser",
    "ui_components": ["my-ui"],
    "export_formats": ["my-format"],
    "ratings": "my-ratings"
  },
  
  "config": {
    "custom_setting": "value"
  }
}
```

### 3. Create `__init__.py`

```python
from typing import Dict, List, Any
from core.plugins.base import SchemaPlugin, ParserPlugin

class MyPlugin(SchemaPlugin, ParserPlugin):
    def __init__(self):
        self.id = "my-plugin"
        self.name = "My Plugin"
        self.version = "1.0.0"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "number"}
            }
        }
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        # Your parsing logic here
        return {"field1": "value", "field2": 42}

# Plugin instance
plugin = MyPlugin()
```

### 4. Enable Plugin

Add to `.env`:

```bash
ENABLED_PLUGINS=my-plugin
```

Or enable via API:

```bash
curl -X POST http://localhost:4080/api/plugins/my-plugin/enable
```

---

## Plugin Types

### 1. SchemaPlugin

Define custom data schemas for your workflow.

```python
from core.plugins.base import SchemaPlugin

class MySchemaPlugin(SchemaPlugin):
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for your data"""
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "number"}
            },
            "required": ["name"]
        }
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate data against schema"""
        return "name" in data
```

### 2. ParserPlugin

Parse LLM responses in custom formats.

```python
from core.plugins.base import ParserPlugin

class MyParserPlugin(ParserPlugin):
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response text"""
        # Example: Extract JSON from markdown
        import json
        import re
        
        json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        return {}
    
    def extract_fields(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific fields for display"""
        return {
            "title": parsed_data.get("name", "Unknown"),
            "value": parsed_data.get("score", 0)
        }
```

### 3. UIPlugin

Provide custom UI components.

```python
from core.plugins.base import UIPlugin

class MyUIPlugin(UIPlugin):
    def get_ui_routes(self) -> List[Dict[str, str]]:
        """Return UI routes"""
        return [
            {"path": "/my-ui", "template": "plugins/my-plugin/ui/main.html"}
        ]
    
    def get_ui_components(self) -> List[Dict[str, str]]:
        """Return embeddable components"""
        return [
            {
                "id": "my-widget",
                "template": "plugins/my-plugin/ui/widget.html",
                "description": "My custom widget"
            }
        ]
```

### 4. ExportPlugin

Export data in custom formats.

```python
from core.plugins.base import ExportPlugin

class MyExportPlugin(ExportPlugin):
    def export(self, tasks: List[Dict[str, Any]], format: str, options: Dict[str, Any]) -> bytes:
        """Export tasks to custom format"""
        if format == "my-format":
            import json
            data = [self.transform_task(t) for t in tasks]
            return json.dumps(data, indent=2).encode('utf-8')
        
        raise ValueError(f"Unsupported format: {format}")
    
    def get_export_formats(self) -> List[str]:
        """Return supported formats"""
        return ["my-format", "my-other-format"]
    
    def transform_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Transform task for export"""
        return {
            "id": task.get("id"),
            "data": task.get("data")
        }
```

### 5. RatingPlugin

Implement custom rating systems.

```python
from core.plugins.base import RatingPlugin

class MyRatingPlugin(RatingPlugin):
    def get_rating_categories(self) -> Dict[str, List[str]]:
        """Return rating categories"""
        return {
            "quality": ["Excellent", "Good", "Fair", "Poor"],
            "relevance": ["High", "Medium", "Low"]
        }
    
    def validate_rating(self, rating: Dict[str, Any]) -> bool:
        """Validate rating submission"""
        category = rating.get("category")
        value = rating.get("value")
        
        if category not in self.get_rating_categories():
            return False
        
        return value in self.get_rating_categories()[category]
    
    def get_rating_display(self, rating: Dict[str, Any]) -> Dict[str, str]:
        """Get display properties"""
        value = rating.get("value")
        
        colors = {
            "Excellent": "green",
            "Good": "blue",
            "Fair": "yellow",
            "Poor": "red"
        }
        
        return {
            "color": colors.get(value, "gray"),
            "icon": "⭐" if value == "Excellent" else "•",
            "badge_class": f"badge-{colors.get(value, 'gray')}"
        }
```

---

## Creating Your First Plugin

Let's create a complete plugin for evaluating blog posts.

### Step 1: Create Directory Structure

```bash
plugins/blog-evaluator/
├── __init__.py
├── plugin.json
└── ui/
    ├── curation.html
    └── components/
        └── rating-widget.html
```

### Step 2: Define Plugin Manifest

`plugin.json`:

```json
{
  "id": "blog-evaluator",
  "name": "Blog Post Evaluator",
  "version": "1.0.0",
  "description": "Evaluate blog posts for quality and relevance",
  "author": "Your Name",
  "license": "MIT",
  
  "provides": {
    "schema": "blog_evaluation",
    "parser": "BlogParser",
    "ui_components": ["blog-curation"],
    "export_formats": ["high-quality-blogs"],
    "ratings": "blog-ratings"
  },
  
  "config": {
    "rating_categories": {
      "quality": ["Excellent", "Good", "Fair", "Poor"],
      "relevance": ["High", "Medium", "Low"],
      "originality": ["Very Original", "Somewhat Original", "Not Original"]
    },
    "export_thresholds": {
      "high_quality": {
        "min_quality": "Good",
        "min_relevance": "Medium"
      }
    }
  },
  
  "hooks": {
    "on_annotation_submit": ["validate_blog_rating"],
    "on_export": ["filter_by_quality"]
  }
}
```

### Step 3: Implement Plugin

`__init__.py`:

```python
from typing import Dict, List, Any
from core.plugins.base import SchemaPlugin, ParserPlugin, RatingPlugin, ExportPlugin

class BlogEvaluatorPlugin(SchemaPlugin, ParserPlugin, RatingPlugin, ExportPlugin):
    def __init__(self):
        self.id = "blog-evaluator"
        self.name = "Blog Post Evaluator"
        self.version = "1.0.0"
        
        self.rating_categories = {
            "quality": ["Excellent", "Good", "Fair", "Poor"],
            "relevance": ["High", "Medium", "Low"],
            "originality": ["Very Original", "Somewhat Original", "Not Original"]
        }
    
    # SchemaPlugin methods
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "quality": {"type": "string", "enum": self.rating_categories["quality"]},
                "relevance": {"type": "string", "enum": self.rating_categories["relevance"]},
                "originality": {"type": "string", "enum": self.rating_categories["originality"]}
            },
            "required": ["title", "content"]
        }
    
    def validate(self, data: Dict[str, Any]) -> bool:
        return "title" in data and "content" in data
    
    # ParserPlugin methods
    def parse_response(self, response: str) -> Dict[str, Any]:
        import json
        import re
        
        # Try to extract JSON
        json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Fallback: parse as plain text
        return {"raw_response": response}
    
    def extract_fields(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": parsed_data.get("title", "Unknown"),
            "quality": parsed_data.get("quality", "Unknown"),
            "relevance": parsed_data.get("relevance", "Unknown")
        }
    
    # RatingPlugin methods
    def get_rating_categories(self) -> Dict[str, List[str]]:
        return self.rating_categories
    
    def validate_rating(self, rating: Dict[str, Any]) -> bool:
        category = rating.get("category")
        value = rating.get("value")
        
        if category not in self.rating_categories:
            return False
        
        return value in self.rating_categories[category]
    
    # ExportPlugin methods
    def export(self, tasks: List[Dict[str, Any]], format: str, options: Dict[str, Any]) -> bytes:
        if format == "high-quality-blogs":
            filtered = [t for t in tasks if self.is_high_quality(t)]
            import json
            return json.dumps(filtered, indent=2).encode('utf-8')
        
        raise ValueError(f"Unsupported format: {format}")
    
    def get_export_formats(self) -> List[str]:
        return ["high-quality-blogs"]
    
    def is_high_quality(self, task: Dict[str, Any]) -> bool:
        data = task.get("data", {})
        quality = data.get("quality")
        relevance = data.get("relevance")
        
        return quality in ["Excellent", "Good"] and relevance in ["High", "Medium"]

# Plugin instance
plugin = BlogEvaluatorPlugin()
```

---

## Plugin Manifest

The `plugin.json` file defines your plugin's metadata and capabilities.

### Required Fields

```json
{
  "id": "unique-plugin-id",
  "name": "Human Readable Name",
  "version": "1.0.0"
}
```

### Optional Fields

```json
{
  "description": "What your plugin does",
  "author": "Your Name",
  "license": "MIT",
  "homepage": "https://github.com/you/plugin",
  
  "provides": {
    "schema": "schema_name",
    "parser": "ParserClassName",
    "ui_components": ["component-id"],
    "export_formats": ["format-name"],
    "ratings": "rating-system-name"
  },
  
  "config": {
    "custom_setting": "value"
  },
  
  "hooks": {
    "on_task_create": ["hook_function_name"],
    "on_annotation_submit": ["hook_function_name"],
    "on_export": ["hook_function_name"]
  },
  
  "dependencies": {
    "python": ">=3.9",
    "packages": ["numpy", "pandas"]
  }
}
```

---

## API Reference

### Base Classes

All plugins inherit from `Plugin` base class:

```python
class Plugin(ABC):
    def get_id(self) -> str
    def get_name(self) -> str
    def get_version(self) -> str
    def get_description(self) -> str
```

### Plugin Registry

Access the global plugin registry:

```python
from core.plugins.registry import get_plugin_registry

registry = get_plugin_registry()

# Get all plugins
plugins = registry.list_plugins()

# Get specific plugin
plugin = registry.get_plugin("my-plugin")

# Get plugins by type
parsers = registry.get_parser_plugins()
ui_plugins = registry.get_ui_plugins()

# Enable/disable
registry.enable_plugin("my-plugin")
registry.disable_plugin("my-plugin")
```

### HTTP API

```bash
# List all plugins
GET /api/plugins

# Get plugin details
GET /api/plugins/{plugin_id}

# Enable plugin
POST /api/plugins/{plugin_id}/enable

# Disable plugin
POST /api/plugins/{plugin_id}/disable

# Get UI components
GET /api/plugins/{plugin_id}/ui-components

# Get plugins by type
GET /api/plugins/by-type/{type}
```

---

## Best Practices

### 1. Naming Conventions

- Plugin IDs: `kebab-case` (e.g., `blog-evaluator`)
- Class names: `PascalCase` (e.g., `BlogEvaluatorPlugin`)
- File names: `snake_case` (e.g., `blog_parser.py`)

### 2. Error Handling

Always handle errors gracefully:

```python
def parse_response(self, response: str) -> Dict[str, Any]:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse response: {response[:100]}")
        return {"error": "Invalid JSON", "raw": response}
```

### 3. Configuration

Use the manifest for configuration:

```python
def __init__(self, config: Dict[str, Any] = None):
    self.config = config or {}
    self.threshold = self.config.get("threshold", 0.5)
```

### 4. Documentation

Document your plugin thoroughly:

```python
class MyPlugin(SchemaPlugin):
    """
    My Plugin - Does amazing things
    
    Features:
    - Feature 1
    - Feature 2
    
    Configuration:
    - setting1: Description
    - setting2: Description
    
    Example:
        plugin = MyPlugin({"setting1": "value"})
        result = plugin.parse_response(response)
    """
```

### 5. Testing

Write tests for your plugin:

```python
def test_parse_response():
    plugin = MyPlugin()
    result = plugin.parse_response('{"key": "value"}')
    assert result["key"] == "value"
```

---

## Examples

See the included example plugins:

1. **candidate-evaluator** - Evaluate candidates with categorical ratings
2. **quality-rater** - Generic quality rating system
3. **batch-submitter** - Web form for batch submission

---

## Testing

Test your plugin locally:

```bash
# 1. Create test file
cat > test_my_plugin.py << 'EOF'
from plugins.my_plugin import plugin

def test_parse():
    result = plugin.parse_response('test')
    assert result is not None

if __name__ == "__main__":
    test_parse()
    print("✅ All tests passed!")
EOF

# 2. Run tests
python test_my_plugin.py
```

---

## Distribution

### Option 1: Git Repository

```bash
# Users can install via git
git clone https://github.com/you/my-plugin plugins/my-plugin
```

### Option 2: PyPI Package

```bash
# Package structure
my-plugin/
├── setup.py
├── my_plugin/
│   ├── __init__.py
│   └── plugin.json

# Install
pip install my-plugin
```

### Option 3: npm Package

```bash
# Package structure
my-plugin/
├── package.json
├── index.js
└── plugin.json

# Install
npm install my-plugin
```

---

## Support

- **Documentation**: See `docs/PLUGIN_ARCHITECTURE.md`
- **Examples**: Check `plugins/` directory
- **Issues**: Open an issue on GitHub
- **Community**: Join our Discord

---

**Happy Plugin Development! 🚀**

