# vLLM Batch Server - Developer Guide

This guide explains the architecture, APIs, and how to extend the vLLM Batch Server.

---

## 📚 **Table of Contents**

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Core Concepts](#core-concepts)
4. [API Reference](#api-reference)
5. [Extending the System](#extending-the-system)
6. [Testing](#testing)
7. [Deployment](#deployment)

---

## 🏗️ **Architecture Overview**

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                     vLLM Batch Server                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Batch API  │  │ Fine-Tuning  │  │  Conquest    │      │
│  │   (OpenAI)   │  │     API      │  │   Viewer     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                           │                                  │
│                  ┌────────▼────────┐                         │
│                  │   Core Engine   │                         │
│                  │  - Model Mgmt   │                         │
│                  │  - Job Queue    │                         │
│                  │  - Result Proc  │                         │
│                  └────────┬────────┘                         │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │               │
│    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐          │
│    │  vLLM   │      │ Unsloth │      │  Label  │          │
│    │ Engine  │      │ Training│      │ Studio  │          │
│    └─────────┘      └─────────┘      └─────────┘          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### **Design Principles**

1. **Generic Core**: Core functionality is application-agnostic
2. **Pluggable Integrations**: Application-specific code in `integrations/`
3. **OpenAI Compatibility**: Batch API follows OpenAI spec
4. **Extensibility**: Easy to add new models, backends, and result handlers

---

## 📁 **Project Structure**

```
vllm-batch-server/
├── core/                      # Generic, reusable core
│   ├── batch_app/             # Batch processing application
│   │   ├── api_server.py      # FastAPI server
│   │   ├── batch_processor.py # Batch job processing
│   │   ├── fine_tuning.py     # Fine-tuning API
│   │   ├── conquest_api.py    # Conquest viewer API
│   │   └── model_loader.py    # Model loading into vLLM
│   ├── curation/              # Generic curation interfaces
│   │   ├── schemas.py         # Task schemas
│   │   └── registry.py        # Task type registry
│   ├── result_handlers/       # Result processing
│   │   ├── base.py            # Abstract base class
│   │   ├── label_studio.py    # Label Studio handler
│   │   └── webhook.py         # Webhook handler
│   └── training/              # Training abstraction
│       ├── base.py            # Abstract backend interface
│       ├── unsloth.py         # Unsloth implementation
│       ├── axolotl.py         # Axolotl implementation
│       └── openai.py          # OpenAI implementation
├── integrations/              # Application-specific code
│   └── aris/                  # Aris (Aristotle) integration
│       ├── conquest_schemas/  # Conquest-specific schemas
│       ├── curation_app/      # Curation web app
│       └── static/            # Static files
├── static/                    # Generic web UI
│   ├── fine-tuning.html       # Fine-tuning dashboard
│   ├── conquest-viewer.html   # Conquest viewer
│   ├── model-management.html  # Model management
│   └── js/                    # JavaScript files
├── docker/                    # Docker configuration
│   └── docker-compose.yml     # Service orchestration
├── docs/                      # Documentation
│   ├── USER_GUIDE.md          # User guide
│   ├── DEVELOPER_GUIDE.md     # This file
│   └── API_REFERENCE.md       # API documentation
└── tests/                     # Tests
    ├── unit/                  # Unit tests
    └── integration/           # Integration tests
```

---

## 🧩 **Core Concepts**

### **1. Batch Jobs**

Batch jobs process multiple LLM requests in parallel:

```python
# Database model
class BatchJob(Base):
    id: str                    # Unique job ID
    status: str                # validating, in_progress, completed, failed
    input_file_id: str         # Input JSONL file
    output_file_id: str        # Output JSONL file
    request_counts: dict       # {total, completed, failed}
    created_at: datetime
    completed_at: datetime
```

**Lifecycle**:
1. `validating` - Validating input file
2. `in_progress` - Processing requests
3. `completed` - All requests processed
4. `failed` - Job failed
5. `cancelled` - Job cancelled by user

### **2. Fine-Tuning**

Fine-tuning trains custom models on curated data:

```python
# Database model
class FineTuningJob(Base):
    id: str                    # Unique job ID
    model: str                 # Base model name
    training_file: str         # Training dataset path
    backend: str               # unsloth, axolotl, openai, huggingface
    hyperparameters: dict      # Training config
    status: str                # pending, running, succeeded, failed
    fine_tuned_model: str      # Output model name
```

**Training Backends**:
- **Unsloth**: Fast LoRA/QLoRA training (recommended)
- **Axolotl**: Flexible training framework
- **OpenAI**: Cloud-based fine-tuning
- **HuggingFace**: Transformers-based training

### **3. Result Handlers**

Result handlers process batch job results:

```python
class ResultHandler(ABC):
    @abstractmethod
    async def handle_result(self, result: BatchResult) -> None:
        """Process a batch result"""
        pass
```

**Built-in Handlers**:
- `LabelStudioHandler`: Export to Label Studio
- `WebhookHandler`: Send to webhook URL
- `DatabaseHandler`: Store in database

### **4. Curation System**

The curation system provides a generic interface for data annotation:

```python
class TaskSchema(BaseModel):
    """Generic task schema"""
    id: str
    type: str                  # Task type (e.g., "candidate_analysis")
    data: dict                 # Task-specific data
    metadata: dict             # Additional metadata
```

**Task Registry**:
```python
# Register custom task types
task_registry.register("my_task_type", MyTaskSchema)
```

---

## 🔌 **API Reference**

### **Batch API (OpenAI-Compatible)**

**Upload File**:
```http
POST /v1/files
Content-Type: multipart/form-data

file: <JSONL file>
purpose: "batch"
```

**Create Batch**:
```http
POST /v1/batches
Content-Type: application/json

{
  "input_file_id": "file_abc123",
  "endpoint": "/v1/chat/completions",
  "completion_window": "24h"
}
```

**Get Batch Status**:
```http
GET /v1/batches/{batch_id}
```

**Download Results**:
```http
GET /v1/files/{file_id}/content
```

### **Fine-Tuning API**

**List Fine-Tuning Jobs**:
```http
GET /v1/fine_tuning/jobs
```

**Create Fine-Tuning Job**:
```http
POST /v1/fine_tuning/jobs
Content-Type: application/json

{
  "model": "gemma-3-12b",
  "training_file": "path/to/dataset.jsonl",
  "backend": "unsloth",
  "hyperparameters": {
    "lora_r": 16,
    "lora_alpha": 32,
    "learning_rate": 2e-4,
    "num_train_epochs": 3
  }
}
```

**Get Fine-Tuning Job**:
```http
GET /v1/fine_tuning/jobs/{job_id}
```

**Deploy Model to vLLM**:
```http
POST /v1/fine_tuning/jobs/{job_id}/deploy
```

### **Conquest API**

**List Conquests**:
```http
GET /v1/conquests?status=COMPLETED&result=VICTORY&limit=100
```

**Get Conquest**:
```http
GET /v1/conquests/{conquest_id}
```

**Annotate Conquest**:
```http
POST /v1/conquests/{conquest_id}/annotate
Content-Type: application/json

{
  "isGoldStar": true,
  "rating": 5,
  "feedback": "Excellent analysis",
  "improvementNotes": null
}
```

---

## 🔧 **Extending the System**

### **Adding a Custom Integration**

1. **Create integration directory**:
   ```bash
   mkdir -p integrations/my_app
   ```

2. **Define custom schemas**:
   ```python
   # integrations/my_app/schemas.py
   from pydantic import BaseModel
   
   class MyTaskSchema(BaseModel):
       id: str
       type: str = "my_task"
       prompt: str
       completion: str
       metadata: dict
   ```

3. **Register task type**:
   ```python
   # integrations/my_app/__init__.py
   from core.curation.registry import task_registry
   from .schemas import MyTaskSchema
   
   task_registry.register("my_task", MyTaskSchema)
   ```

4. **Create custom result handler**:
   ```python
   # integrations/my_app/handlers.py
   from core.result_handlers.base import ResultHandler
   
   class MyResultHandler(ResultHandler):
       async def handle_result(self, result):
           # Custom processing logic
           pass
   ```

### **Adding a Training Backend**

1. **Implement backend interface**:
   ```python
   # core/training/my_backend.py
   from .base import TrainingBackend
   
   class MyBackend(TrainingBackend):
       def train(self, config):
           # Training logic
           pass
       
       def get_status(self, job_id):
           # Status check logic
           pass
   ```

2. **Register backend**:
   ```python
   # core/training/__init__.py
   from .my_backend import MyBackend
   
   BACKENDS = {
       "my_backend": MyBackend
   }
   ```

### **Adding a Result Handler**

1. **Implement handler**:
   ```python
   # core/result_handlers/my_handler.py
   from .base import ResultHandler
   
   class MyHandler(ResultHandler):
       async def handle_result(self, result):
           # Process result
           pass
   ```

2. **Register handler**:
   ```python
   # core/batch_app/batch_processor.py
   from core.result_handlers.my_handler import MyHandler
   
   result_handlers.append(MyHandler())
   ```

---

## 🧪 **Testing**

### **Running Tests**

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=core --cov-report=html
```

### **Writing Tests**

```python
# tests/unit/test_batch_processor.py
import pytest
from core.batch_app.batch_processor import BatchProcessor

def test_batch_processor():
    processor = BatchProcessor()
    result = processor.process_batch(...)
    assert result.status == "completed"
```

---

## 🚀 **Deployment**

### **Docker Deployment**

```bash
# Build images
docker compose build

# Start services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### **Production Configuration**

```yaml
# docker-compose.prod.yml
services:
  vllm-batch-server:
    environment:
      - ENVIRONMENT=production
      - SENTRY_DSN=https://...
      - ENABLE_RATE_LIMITING=true
      - MAX_CONCURRENT_BATCHES=10
```

### **Monitoring**

- **Prometheus**: Metrics at `/metrics`
- **Sentry**: Error tracking
- **Logs**: Structured JSON logs

---

## 📖 **Additional Resources**

- **User Guide**: [USER_GUIDE.md](USER_GUIDE.md)
- **API Reference**: [API_REFERENCE.md](API_REFERENCE.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Happy coding!** 🚀

