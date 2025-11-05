# Plugins Directory

This directory contains plugins that extend the vLLM Batch Server with custom workflows.

## What are Plugins?

Plugins let you customize the batch server without forking the codebase. You can:

- Define custom data schemas
- Parse LLM responses into structured data
- Create custom UI components
- Implement rating systems
- Export data in custom formats

## Plugin Structure

Each plugin is a directory with this structure:

```
plugins/my-plugin/
├── plugin.json          # Plugin metadata and configuration
├── __init__.py          # Plugin entry point
├── schema.py            # (Optional) Custom data schema
├── parser.py            # (Optional) Response parser
├── ratings.py           # (Optional) Rating system
├── exports.py           # (Optional) Export formats
└── ui/                  # (Optional) Custom UI components
    ├── curation.html
    ├── table-view.html
    └── components.js
```

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
  "plugin_class": "MyPlugin",
  
  "provides": {
    "schema": "my_schema",
    "parser": "MyParser",
    "ui_components": ["my-curation-ui"],
    "export_formats": ["my-format"]
  },
  
  "config": {
    "custom_setting": "value"
  }
}
```

### 3. Create `__init__.py`

```python
from core.plugins.base import Plugin, ParserPlugin

class MyPlugin(Plugin, ParserPlugin):
    def get_id(self) -> str:
        return "my-plugin"
    
    def get_name(self) -> str:
        return "My Plugin"
    
    def parse_response(self, response: str) -> dict:
        # Your parsing logic here
        return {"parsed": "data"}
    
    def extract_fields(self, data: dict) -> dict:
        # Extract display fields
        return {"field1": data.get("parsed")}
```

### 4. Enable Plugin

Add to `.env`:

```bash
ENABLED_PLUGINS=my-plugin
```

Or enable programmatically:

```python
from core.plugins import get_plugin_registry

registry = get_plugin_registry()
registry.enable_plugin("my-plugin")
```

## Available Plugins

### candidate-evaluator
Evaluate candidates with categorical ratings (Strong Yes/Yes/Maybe/No/Strong No).

**Features:**
- Parse candidate info (name, title, company)
- Categorical rating system
- Custom curation UI
- Export by quality threshold

**Use case:** Recruiting, candidate evaluation

### quality-rater
Rate any data with customizable categorical ratings.

**Features:**
- Configurable rating categories
- Export by quality threshold
- Rating widget UI component

**Use case:** Data curation, quality control

### batch-submitter
Submit batch jobs through a web form.

**Features:**
- File upload interface
- Model selection
- Parameter configuration
- Validation

**Use case:** Non-technical users, easy batch submission

## Plugin Types

### SchemaPlugin
Define custom data structures.

```python
from core.plugins.base import SchemaPlugin

class MySchema(SchemaPlugin):
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "number"}
            }
        }
    
    def validate(self, data: dict) -> bool:
        # Validation logic
        return True
```

### ParserPlugin
Parse LLM responses.

```python
from core.plugins.base import ParserPlugin

class MyParser(ParserPlugin):
    def parse_response(self, response: str) -> dict:
        # Extract structured data from response
        return {"parsed": "data"}
    
    def extract_fields(self, data: dict) -> dict:
        # Extract display fields for tables
        return {"name": data.get("name")}
```

### UIPlugin
Provide custom UI components.

```python
from core.plugins.base import UIPlugin

class MyUI(UIPlugin):
    def get_ui_routes(self):
        return [
            {"path": "/my-ui", "file": "ui/my-ui.html"}
        ]
    
    def get_ui_components(self):
        return ["my-widget", "my-table"]
```

### ExportPlugin
Export data in custom formats.

```python
from core.plugins.base import ExportPlugin

class MyExporter(ExportPlugin):
    def export(self, tasks: list, format: str, **kwargs) -> str:
        # Export logic
        return "exported data"
    
    def get_export_formats(self):
        return [
            {
                "id": "my-format",
                "name": "My Format",
                "description": "Custom export format"
            }
        ]
```

### RatingPlugin
Implement rating systems.

```python
from core.plugins.base import RatingPlugin

class MyRater(RatingPlugin):
    def get_rating_categories(self):
        return {
            "quality": ["Excellent", "Good", "Fair", "Poor"]
        }
    
    def validate_rating(self, category: str, value: str) -> bool:
        categories = self.get_rating_categories()
        return value in categories.get(category, [])
```

## Plugin Hooks

Plugins can hook into lifecycle events:

```python
from core.plugins.hooks import hook_registry

def on_task_created(task_data):
    # Do something when task is created
    print(f"Task created: {task_data['id']}")
    return task_data

hook_registry.register("on_task_create", on_task_created)
```

Available hooks:
- `on_task_create` - Before creating a task
- `on_task_update` - Before updating a task
- `on_annotation_submit` - After annotation is submitted
- `on_export` - Before exporting data
- `on_batch_complete` - After batch job completes
- `on_model_load` - Before loading a model
- `on_response_parse` - When parsing LLM response
- `on_quality_rate` - When rating quality

## Best Practices

1. **Keep plugins focused** - One plugin = one workflow
2. **Use semantic versioning** - Follow semver for versions
3. **Document your plugin** - Add README.md to plugin directory
4. **Test thoroughly** - Test with real data
5. **Handle errors gracefully** - Don't crash the server
6. **Make UI responsive** - Support mobile/tablet
7. **Follow naming conventions** - Use kebab-case for IDs

## Examples

See the included plugins for examples:
- `candidate-evaluator/` - Full-featured candidate evaluation workflow
- `quality-rater/` - Simple quality rating system
- `batch-submitter/` - Batch submission form

## Contributing

To contribute a plugin:

1. Create your plugin in `plugins/your-plugin/`
2. Test thoroughly
3. Add documentation
4. Submit a pull request

## Support

For help with plugin development:
- Read the docs: `docs/PLUGIN_ARCHITECTURE.md`
- Check examples in `plugins/`
- Open an issue on GitHub

## License

Plugins can have their own licenses. Specify in `plugin.json`.

