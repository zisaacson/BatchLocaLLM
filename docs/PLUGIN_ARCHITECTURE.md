# Plugin Architecture for Customizable Workflows

## Vision

**Enable users to build custom workflows as powerful as Aris without forking the codebase.**

Inspired by:
- **VS Code** - Extensions for everything
- **Obsidian** - Community plugins
- **Label Studio** - Custom labeling interfaces
- **WordPress** - Themes and plugins

## Architecture Overview

```
vllm-batch-server/
├── core/                          # OSS Core (Generic)
│   ├── batch_app/                 # Batch processing engine
│   ├── curation/                  # Generic curation system
│   └── plugins/                   # Plugin system
│       ├── registry.py            # Plugin registry
│       ├── base.py                # Base plugin classes
│       └── hooks.py               # Plugin hooks
│
├── plugins/                       # Plugin Directory
│   ├── README.md                  # Plugin development guide
│   ├── candidate-evaluator/      # Example: Aris candidate workflow
│   │   ├── plugin.json            # Plugin metadata
│   │   ├── schema.py              # Custom data schema
│   │   ├── parser.py              # Custom response parser
│   │   ├── ui/                    # Custom UI components
│   │   │   ├── curation.html      # Custom curation interface
│   │   │   ├── table-view.html    # Custom table view
│   │   │   └── components.js      # Reusable UI components
│   │   └── exports.py             # Custom export formats
│   │
│   ├── quality-rater/             # Example: Quality rating plugin
│   │   ├── plugin.json
│   │   ├── ratings.py             # Rating system (categorical)
│   │   ├── ui/
│   │   │   └── rating-widget.html
│   │   └── exports.py             # Export by quality threshold
│   │
│   └── batch-submitter/           # Example: Batch submission plugin
│       ├── plugin.json
│       ├── ui/
│       │   └── submit-form.html
│       └── validators.py
│
└── integrations/                  # Private Integrations (Aris-specific)
    └── aris/
        ├── conquest_api.py        # Aris API endpoints
        └── plugins/               # Aris uses plugins too!
            └── candidate-evaluator -> ../../plugins/candidate-evaluator
```

## Core Concepts

### 1. Plugin Manifest (`plugin.json`)

```json
{
  "id": "candidate-evaluator",
  "name": "Candidate Evaluator",
  "version": "1.0.0",
  "description": "Evaluate candidates with categorical ratings",
  "author": "Aris Team",
  "license": "MIT",
  
  "provides": {
    "schema": "candidate_evaluation",
    "parser": "CandidateParser",
    "ui_components": [
      "curation-interface",
      "table-view",
      "rating-widget"
    ],
    "export_formats": ["icl", "finetuning", "raw"]
  },
  
  "hooks": {
    "on_task_create": "validate_candidate_data",
    "on_annotation_submit": "parse_ratings",
    "on_export": "filter_by_quality"
  },
  
  "dependencies": {
    "core": ">=1.0.0"
  },
  
  "config": {
    "rating_categories": {
      "recommendation": ["Strong Yes", "Yes", "Maybe", "No", "Strong No"],
      "trajectory": ["Exceptional", "Strong", "Good", "Average", "Weak"],
      "company_pedigree": ["Exceptional", "Strong", "Good", "Average", "Weak"],
      "educational_pedigree": ["Exceptional", "Strong", "Good", "Average", "Weak"]
    },
    "export_thresholds": {
      "icl": {"min_recommendation": "Yes"},
      "finetuning": {"min_recommendation": "Maybe"}
    }
  }
}
```

### 2. Plugin Base Classes

```python
# core/plugins/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class Plugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def get_id(self) -> str:
        """Unique plugin identifier"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Human-readable plugin name"""
        pass


class SchemaPlugin(Plugin):
    """Plugin that provides a custom data schema"""
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for this data type"""
        pass
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate data against schema"""
        pass


class ParserPlugin(Plugin):
    """Plugin that parses LLM responses"""
    
    @abstractmethod
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured data"""
        pass
    
    @abstractmethod
    def extract_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract display fields (name, title, etc.)"""
        pass


class UIPlugin(Plugin):
    """Plugin that provides custom UI components"""
    
    @abstractmethod
    def get_ui_routes(self) -> List[Dict[str, str]]:
        """Return list of UI routes this plugin provides"""
        pass
    
    @abstractmethod
    def render_component(self, component_id: str, data: Dict[str, Any]) -> str:
        """Render a UI component with data"""
        pass


class ExportPlugin(Plugin):
    """Plugin that provides custom export formats"""
    
    @abstractmethod
    def export(self, tasks: List[Dict[str, Any]], format: str, **kwargs) -> str:
        """Export tasks in custom format"""
        pass
    
    @abstractmethod
    def get_export_formats(self) -> List[str]:
        """Return list of supported export formats"""
        pass
```

### 3. Plugin Registry

```python
# core/plugins/registry.py

import json
from pathlib import Path
from typing import Dict, List, Optional
from .base import Plugin

class PluginRegistry:
    """Central registry for all plugins"""
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, Plugin] = {}
        self.manifests: Dict[str, Dict] = {}
    
    def discover_plugins(self):
        """Scan plugin directory and load all plugins"""
        for plugin_path in self.plugin_dir.iterdir():
            if not plugin_path.is_dir():
                continue
            
            manifest_path = plugin_path / "plugin.json"
            if not manifest_path.exists():
                continue
            
            self.load_plugin(plugin_path)
    
    def load_plugin(self, plugin_path: Path):
        """Load a single plugin"""
        manifest = json.loads((plugin_path / "plugin.json").read_text())
        plugin_id = manifest["id"]
        
        # Import plugin module
        # ... (dynamic import logic)
        
        self.manifests[plugin_id] = manifest
        # self.plugins[plugin_id] = plugin_instance
    
    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get plugin by ID"""
        return self.plugins.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: str) -> List[Plugin]:
        """Get all plugins of a specific type"""
        return [
            p for p in self.plugins.values()
            if isinstance(p, plugin_type)
        ]
```

### 4. Plugin Hooks System

```python
# core/plugins/hooks.py

from typing import Any, Callable, Dict, List

class HookRegistry:
    """Registry for plugin hooks"""
    
    def __init__(self):
        self.hooks: Dict[str, List[Callable]] = {}
    
    def register(self, hook_name: str, callback: Callable):
        """Register a callback for a hook"""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)
    
    def trigger(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Trigger all callbacks for a hook"""
        results = []
        for callback in self.hooks.get(hook_name, []):
            result = callback(*args, **kwargs)
            results.append(result)
        return results

# Available hooks:
# - on_task_create: Before creating a task
# - on_task_update: Before updating a task
# - on_annotation_submit: After annotation is submitted
# - on_export: Before exporting data
# - on_batch_complete: After batch job completes
# - on_model_load: Before loading a model
```

## Example: Candidate Evaluator Plugin

### Plugin Structure

```
plugins/candidate-evaluator/
├── plugin.json                    # Manifest
├── __init__.py                    # Plugin entry point
├── schema.py                      # Data schema
├── parser.py                      # Response parser
├── ratings.py                     # Rating system
├── exports.py                     # Export logic
└── ui/
    ├── curation.html              # Curation interface
    ├── table-view.html            # Table view
    ├── rating-widget.html         # Rating widget component
    └── candidate-card.html        # Candidate card component
```

### Schema Definition

```python
# plugins/candidate-evaluator/schema.py

from core.plugins.base import SchemaPlugin

class CandidateEvaluatorSchema(SchemaPlugin):
    def get_id(self) -> str:
        return "candidate-evaluator"
    
    def get_name(self) -> str:
        return "Candidate Evaluator"
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "candidate": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "company": {"type": "string"},
                        "linkedin_url": {"type": "string"}
                    }
                },
                "evaluation": {
                    "type": "object",
                    "properties": {
                        "recommendation": {
                            "enum": ["Strong Yes", "Yes", "Maybe", "No", "Strong No"]
                        },
                        "trajectory_rating": {
                            "enum": ["Exceptional", "Strong", "Good", "Average", "Weak"]
                        },
                        "company_pedigree": {
                            "enum": ["Exceptional", "Strong", "Good", "Average", "Weak"]
                        },
                        "educational_pedigree": {
                            "enum": ["Exceptional", "Strong", "Good", "Average", "Weak"]
                        },
                        "is_software_engineer": {"type": "boolean"},
                        "reasoning": {"type": "string"}
                    }
                }
            }
        }
```

### Response Parser

```python
# plugins/candidate-evaluator/parser.py

from core.plugins.base import ParserPlugin
import re

class CandidateParser(ParserPlugin):
    def parse_response(self, response: str) -> dict:
        """Parse LLM response into structured candidate data"""
        # Extract candidate info
        name_match = re.search(r'\*\*Candidate:\*\*\s*(.+)', response)
        title_match = re.search(r'\*\*Title:\*\*\s*(.+)', response)
        company_match = re.search(r'\*\*Company:\*\*\s*(.+)', response)
        
        # Extract ratings
        rec_match = re.search(r'Recommendation:\s*(Strong Yes|Yes|Maybe|No|Strong No)', response)
        traj_match = re.search(r'Trajectory:\s*(Exceptional|Strong|Good|Average|Weak)', response)
        
        return {
            "candidate": {
                "name": name_match.group(1) if name_match else "Unknown",
                "title": title_match.group(1) if title_match else "",
                "company": company_match.group(1) if company_match else ""
            },
            "evaluation": {
                "recommendation": rec_match.group(1) if rec_match else "Maybe",
                "trajectory_rating": traj_match.group(1) if traj_match else "Average"
            }
        }
    
    def extract_fields(self, data: dict) -> dict:
        """Extract display fields for table view"""
        return {
            "name": data.get("candidate", {}).get("name", "Unknown"),
            "title": data.get("candidate", {}).get("title", ""),
            "company": data.get("candidate", {}).get("company", ""),
            "recommendation": data.get("evaluation", {}).get("recommendation", "")
        }
```

## How Users Build Custom Workflows

### Step 1: Create Plugin Directory

```bash
mkdir -p plugins/my-custom-workflow
cd plugins/my-custom-workflow
```

### Step 2: Define Plugin Manifest

```json
{
  "id": "my-custom-workflow",
  "name": "My Custom Workflow",
  "version": "1.0.0",
  "provides": {
    "schema": "my_schema",
    "parser": "MyParser",
    "ui_components": ["my-curation-ui"]
  }
}
```

### Step 3: Implement Plugin

```python
# plugins/my-custom-workflow/__init__.py

from core.plugins.base import SchemaPlugin, ParserPlugin

class MySchema(SchemaPlugin):
    # ... implement your schema
    pass

class MyParser(ParserPlugin):
    # ... implement your parser
    pass
```

### Step 4: Create Custom UI

```html
<!-- plugins/my-custom-workflow/ui/curation.html -->
<div class="my-custom-ui">
    <!-- Your custom curation interface -->
</div>
```

### Step 5: Enable Plugin

```bash
# In .env or config
ENABLED_PLUGINS=candidate-evaluator,my-custom-workflow
```

## Benefits

1. **OSS Core Stays Clean** - No Aris-specific code in core
2. **Users Get Full Power** - Can build workflows as complex as ours
3. **No Forking Required** - Plugins are separate from core
4. **Easy Sharing** - Publish plugins to npm/PyPI
5. **Version Control** - Plugins have their own versions
6. **Hot Reload** - Enable/disable plugins without restart

## Next Steps

1. Build plugin system infrastructure
2. Extract Aris features into plugins
3. Create plugin development guide
4. Build example plugins
5. Create plugin marketplace (future)

This is how we get all our features back AND make it available to everyone! 🚀

