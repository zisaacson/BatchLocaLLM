# Plugin Development Guide

Learn how to extend vLLM Batch Server with custom result handlers.

---

## 🎯 **What Are Result Handlers?**

Result handlers are plugins that process batch results when jobs complete. They enable you to:

- **Sync results to external databases** (PostgreSQL, MySQL, MongoDB)
- **Send notifications** (Slack, Discord, email, webhooks)
- **Cache results** (Redis, Memcached)
- **Upload to cloud storage** (S3, GCS, Azure Blob)
- **Trigger downstream workflows** (Airflow, Prefect, n8n)
- **Custom business logic** (anything you can code!)

---

## 🏗️ **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    BATCH COMPLETION                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              RESULT HANDLER REGISTRY                        │
│  (Executes handlers in priority order)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Priority 10      │ │ Priority 50  │ │ Priority 100     │
│ Your Handler     │ │ Webhook      │ │ Database Sync    │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

**Key Concepts**:
- Handlers run **independently** (one failure doesn't affect others)
- Handlers run in **priority order** (lower number = runs first)
- Handlers can **skip execution** by returning `False` from `enabled()`
- Errors are **logged** but don't stop other handlers

---

## 📝 **Creating a Handler**

### **Step 1: Create Handler Class**

```python
from typing import Dict, Any, List, Optional
from core.result_handlers.base import ResultHandler

class MyCustomHandler(ResultHandler):
    """
    My custom result handler.
    
    This handler does X, Y, and Z when batch jobs complete.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize handler with configuration.
        
        Args:
            config: Handler configuration dict
                - api_key: Your API key
                - endpoint: Your endpoint URL
                - priority: Execution priority (default: 100)
        """
        super().__init__(config)
        
        # Extract config
        self.api_key = self.config.get('api_key')
        self.endpoint = self.config.get('endpoint')
        
        # Validate required config
        if not self.api_key:
            raise ValueError("api_key is required in config")
    
    def name(self) -> str:
        """Return handler name (used in logs)."""
        return "my_custom_handler"
    
    def enabled(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if handler should run for this batch.
        
        Args:
            metadata: Batch metadata (optional)
            
        Returns:
            True if handler should run, False to skip
        """
        # Example: Only run if api_key is configured
        return bool(self.api_key)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Process batch results.
        
        Args:
            batch_id: Unique batch identifier
            results: List of result dictionaries
            metadata: Batch metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Your custom logic here
            for result in results:
                custom_id = result.get('custom_id')
                response = result.get('response', {})
                
                # Process each result
                self.logger.info(f"Processing {custom_id}")
                # ... your code ...
            
            self.logger.info(
                f"Processed {len(results)} results",
                extra={'batch_id': batch_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"Failed to process results: {e}",
                extra={'batch_id': batch_id},
                exc_info=True
            )
            return False
    
    def on_error(self, error: Exception) -> None:
        """
        Handle errors (optional).
        
        Args:
            error: Exception that occurred
        """
        self.logger.error(
            f"Handler error: {error}",
            extra={'handler': self.name()},
            exc_info=True
        )
```

### **Step 2: Register Handler**

```python
from core.result_handlers.base import get_registry

# Create handler instance
handler = MyCustomHandler(config={
    'api_key': 'YOUR_API_KEY',
    'endpoint': 'https://api.example.com',
    'priority': 50  # Lower = runs first
})

# Register handler
registry = get_registry()
registry.register(handler)
```

### **Step 3: Test Handler**

```python
# Test with sample data
sample_results = [
    {
        'custom_id': 'req_001',
        'response': {
            'status_code': 200,
            'body': {
                'choices': [{
                    'message': {
                        'content': 'Sample response'
                    }
                }]
            }
        }
    }
]

sample_metadata = {
    'user_id': 'user_123',
    'project': 'test_project'
}

# Process results
success = registry.process_results(
    batch_id='test_batch_001',
    results=sample_results,
    metadata=sample_metadata
)

print(f"Success: {success}")
```

---

## 🔧 **Handler Configuration**

### **Configuration Options**

All handlers support these base config options:

```python
config = {
    'priority': 100,  # Execution priority (lower = runs first)
    'enabled': True,  # Enable/disable handler
    'log_level': 'INFO',  # Logging level
}
```

### **Environment Variables**

You can use environment variables in config:

```python
import os

handler = MyCustomHandler(config={
    'api_key': os.getenv('MY_API_KEY'),
    'endpoint': os.getenv('MY_ENDPOINT'),
})
```

### **Dynamic Configuration**

Load config from file:

```python
import json

with open('handler_config.json') as f:
    config = json.load(f)

handler = MyCustomHandler(config=config)
```

---

## 📚 **Examples**

### **Example 1: Webhook Handler**

Send results to HTTP endpoint:

```python
import requests
from core.result_handlers.base import ResultHandler

class WebhookHandler(ResultHandler):
    def handle(self, batch_id, results, metadata):
        payload = {
            'batch_id': batch_id,
            'total_results': len(results),
            'metadata': metadata
        }
        
        response = requests.post(
            self.config.get('webhook_url'),
            json=payload,
            headers={'Authorization': f"Bearer {self.config.get('api_key')}"}
        )
        
        response.raise_for_status()
        return True
```

### **Example 2: Database Sync Handler**

Sync results to PostgreSQL:

```python
from sqlalchemy import create_engine, Table, Column, String, Text, MetaData
from core.result_handlers.base import ResultHandler

class PostgresSyncHandler(ResultHandler):
    def __init__(self, config):
        super().__init__(config)
        self.engine = create_engine(config.get('db_url'))
    
    def handle(self, batch_id, results, metadata):
        with self.engine.begin() as conn:
            for result in results:
                conn.execute(
                    "INSERT INTO results (batch_id, custom_id, response) VALUES (%s, %s, %s)",
                    (batch_id, result['custom_id'], json.dumps(result['response']))
                )
        return True
```

### **Example 3: S3 Upload Handler**

Upload results to S3:

```python
import boto3
import json
from core.result_handlers.base import ResultHandler

class S3UploadHandler(ResultHandler):
    def __init__(self, config):
        super().__init__(config)
        self.s3 = boto3.client('s3')
    
    def handle(self, batch_id, results, metadata):
        key = f"batches/{batch_id}/results.json"
        
        self.s3.put_object(
            Bucket=self.config.get('bucket'),
            Key=key,
            Body=json.dumps(results),
            ContentType='application/json'
        )
        
        self.logger.info(f"Uploaded to s3://{self.config.get('bucket')}/{key}")
        return True
```

---

## 🎓 **Best Practices**

### **1. Error Handling**

Always wrap your logic in try/except:

```python
def handle(self, batch_id, results, metadata):
    try:
        # Your logic
        return True
    except Exception as e:
        self.logger.error(f"Error: {e}", exc_info=True)
        return False
```

### **2. Logging**

Use structured logging with context:

```python
self.logger.info(
    "Processed results",
    extra={
        'batch_id': batch_id,
        'count': len(results),
        'handler': self.name()
    }
)
```

### **3. Configuration Validation**

Validate config in `__init__`:

```python
def __init__(self, config):
    super().__init__(config)
    
    required = ['api_key', 'endpoint']
    for key in required:
        if not self.config.get(key):
            raise ValueError(f"{key} is required in config")
```

### **4. Idempotency**

Make handlers idempotent (safe to run multiple times):

```python
def handle(self, batch_id, results, metadata):
    # Use upsert instead of insert
    # Check if already processed
    # Use unique constraints
    pass
```

### **5. Performance**

Batch operations for efficiency:

```python
def handle(self, batch_id, results, metadata):
    # Bad: One request per result
    for result in results:
        requests.post(url, json=result)
    
    # Good: Batch request
    requests.post(url, json={'results': results})
```

---

## 🚀 **Advanced Topics**

See [examples/handlers/](../examples/handlers/) for complete working examples:
- PostgreSQL sync with schema mapping
- Webhook with retries
- Slack/Discord notifications
- Redis caching
- Email notifications

---

## 🤝 **Contributing**

Have a useful handler? Submit a PR!

1. Add handler to `examples/handlers/`
2. Include docstring with use cases
3. Add tests
4. Update this guide

---

## 📝 **License**

Apache 2.0 - See [LICENSE](../LICENSE) for details.

