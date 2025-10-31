# Example Integrations

This directory contains example integrations showing how to extend the core vLLM batch server.

---

## 📦 Structure

```
integrations/examples/
├── README.md                  # This file
├── custom_handler.py          # Example custom result handler
└── custom_schema.json         # Example custom schema
```

---

## 🎯 Purpose

These examples demonstrate:

1. **Custom Result Handlers** - Process batch results your way
2. **Custom Schemas** - Define your own evaluation schemas
3. **Integration Patterns** - Best practices for extending the core

---

## 📝 Example: Custom Result Handler

```python
# integrations/examples/custom_handler.py
from core.result_handlers.base import ResultHandler
from typing import Dict, List, Any

class CustomHandler(ResultHandler):
    """Example custom result handler."""
    
    @property
    def name(self) -> str:
        return "custom_handler"
    
    @property
    def enabled(self) -> bool:
        # Enable via environment variable
        import os
        return os.getenv("ENABLE_CUSTOM_HANDLER", "false").lower() == "true"
    
    def handle(self, batch_id: str, results: List[Dict], metadata: Dict) -> bool:
        """Process batch results."""
        print(f"Processing {len(results)} results for batch {batch_id}")
        
        # Your custom logic here
        for result in results:
            custom_id = result.get("custom_id")
            response = result.get("response", {}).get("body", {})
            
            # Example: Save to database
            # Example: Send to webhook
            # Example: Upload to S3
            # Example: Update external system
            
        return True
    
    def on_error(self, batch_id: str, error: Exception) -> None:
        """Handle errors."""
        print(f"Error processing batch {batch_id}: {error}")
```

---

## 📝 Example: Custom Schema

```json
{
  "conquest_type": "custom_evaluation",
  "version": "1.0.0",
  "description": "Example custom evaluation schema",
  "data_sources": [
    {
      "id": "input_text",
      "name": "Input Text",
      "type": "text",
      "required": true
    }
  ],
  "questions": [
    {
      "id": "quality",
      "text": "How would you rate the quality?",
      "type": "rating",
      "options": ["Poor", "Fair", "Good", "Excellent"],
      "required": true
    },
    {
      "id": "category",
      "text": "What category does this belong to?",
      "type": "choice",
      "options": ["Category A", "Category B", "Category C"],
      "required": true
    }
  ]
}
```

---

## 🚀 Usage

### **1. Create Your Integration**

```bash
# Create your integration directory
mkdir -p integrations/my_integration

# Copy example files
cp integrations/examples/custom_handler.py integrations/my_integration/
cp integrations/examples/custom_schema.json integrations/my_integration/
```

### **2. Register Your Handler**

```python
# In your integration code
from core.result_handlers.base import get_registry
from .custom_handler import CustomHandler

# Register handler
registry = get_registry()
registry.register(CustomHandler())
```

### **3. Configure**

```bash
# .env
ENABLE_CUSTOM_HANDLER=true
```

### **4. Run**

```bash
# Start batch server with your integration
python -m core.batch_app.api_server
python -m core.batch_app.worker
```

---

## 🔧 Integration Patterns

### **Pattern 1: Result Handler**

Best for: Processing batch results

```python
from core.result_handlers.base import ResultHandler

class MyHandler(ResultHandler):
    def handle(self, batch_id, results, metadata):
        # Your logic here
        pass
```

### **Pattern 2: Custom API Endpoint**

Best for: Adding new API functionality

```python
from fastapi import FastAPI
from core.batch_app.api_server import app

@app.get("/my-custom-endpoint")
async def my_endpoint():
    return {"message": "Hello from custom endpoint"}
```

### **Pattern 3: Database Extension**

Best for: Adding custom tables

```python
from sqlalchemy import Column, String
from core.batch_app.database import Base

class MyCustomTable(Base):
    __tablename__ = "my_custom_table"
    
    id = Column(String, primary_key=True)
    data = Column(String)
```

---

## 📚 Best Practices

### **1. Keep Integrations Separate**

```
✅ Good:
integrations/my_integration/
├── __init__.py
├── handlers.py
├── schemas.py
└── README.md

❌ Bad:
core/batch_app/my_custom_code.py  # Don't modify core!
```

### **2. Use Environment Variables**

```python
import os

ENABLE_MY_FEATURE = os.getenv("ENABLE_MY_FEATURE", "false").lower() == "true"
```

### **3. Import from Core**

```python
# ✅ Good
from core.config import settings
from core.batch_app.database import BatchJob

# ❌ Bad
from config import settings  # Won't work with monorepo structure
```

### **4. Document Your Integration**

Create a README.md in your integration directory explaining:
- What it does
- How to configure it
- How to use it
- Dependencies

---

## 🔗 Resources

- **Core Documentation:** `core/README.md`
- **Result Handler Base:** `core/result_handlers/base.py`
- **Example Handlers:** `core/result_handlers/examples/`
- **API Server:** `core/batch_app/api_server.py`
- **Worker:** `core/batch_app/worker.py`

---

## 💡 Ideas for Integrations

- **Slack Notifications** - Send batch completion alerts to Slack
- **Email Reports** - Email results to stakeholders
- **Data Warehouse** - Sync results to Snowflake/BigQuery
- **Monitoring** - Custom Grafana dashboards
- **Quality Checks** - Automated quality validation
- **A/B Testing** - Compare model outputs
- **Cost Tracking** - Track inference costs per project

---

## 🤝 Contributing

If you create a useful integration, consider:

1. Anonymizing any private data
2. Adding it to `integrations/examples/`
3. Submitting a PR to help others

---

**Happy integrating!** 🚀

