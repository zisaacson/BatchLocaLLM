# Test Suite for vLLM Batch Server + Curation System

Comprehensive test suite covering all workflows and components.

## 📊 Test Coverage Overview

### **Unit Tests** (90 tests) ✅
- API validation
- Database models
- Input validation
- Metrics calculation
- Result handlers
- Webhooks
- Worker error handling

### **Integration Tests** (NEW!) ✅
- **Core Workflows** - Batch processing, Label Studio, curation, webhooks
- **Conquest Workflows** - Data parsing, gold stars, bidirectional sync
- **Full Pipeline** - End-to-end data flow

### **Manual Tests** (40+ tests)
- Model-specific tests (Gemma, Llama, Qwen, OLMo, etc.)
- Performance benchmarks
- GPU optimization tests

---

## 🧪 Integration Tests (NEW!)

### **Test Suite 1: Core Workflows** (`test_all_workflows.py`)

Tests fundamental system workflows:

1. **Batch Processing Workflow** ✅
   - Upload file → Create batch → Process → Download results
   - Verifies complete batch lifecycle
   - Tests result structure and data integrity

2. **Label Studio Auto-Import Workflow** ✅
   - Batch completes → Auto-import to Label Studio → Verify tasks
   - Tests metadata extraction and task creation
   - Verifies candidate data parsing

3. **Curation Workflow** ✅
   - Access curation UI → View tasks → Verify data
   - Tests UI accessibility and data display

4. **Webhook Workflow** ✅
   - Batch completes → Webhook sent → Verify payload
   - Tests webhook configuration and metadata

### **Test Suite 2: Conquest Workflows** (`test_conquest_workflows.py`)

Tests Aristotle-specific data flows:

1. **Conquest Data Parsing Workflow** ✅
   - Conquest request → Parse metadata → Extract candidate data
   - Tests custom_id parsing (email_domain_id format)
   - Verifies philosopher, domain, conquest_id extraction

2. **Gold Star Sync Workflow** ✅
   - Mark gold star in Label Studio → Sync to Aristotle database
   - Tests curation API endpoints
   - Verifies bidirectional sync infrastructure

3. **Victory Conquest Sync Workflow** ✅
   - Mark VICTORY in Aristotle → Sync to Label Studio
   - Tests webhook endpoints
   - Verifies conquest status updates

4. **Bidirectional Sync Workflow** ✅
   - Complete bidirectional sync between systems
   - Tests required metadata fields
   - Verifies sync infrastructure

5. **Complete Conquest Curation Workflow** ✅
   - Conquest → Process → Curate → Export
   - Tests all components together
   - Verifies end-to-end data flow

### **Test Suite 3: Full Pipeline** (`test_full_pipeline.py`)

Tests complete system integration:
- API → Worker → PostgreSQL → Curation
- Real service dependencies
- End-to-end verification

---

## 🚀 Running Integration Tests

### **Quick Start**

Run all integration tests:
```bash
./core/tests/integration/run_all_workflows.sh
```

This script:
- ✅ Checks all required services are running
- ✅ Runs all integration test suites
- ✅ Provides detailed summary report

### **Run Individual Test Suites**

```bash
# Core workflows (batch, Label Studio, curation, webhooks)
pytest core/tests/integration/test_all_workflows.py -v -s

# Conquest workflows (data parsing, gold stars, sync)
pytest core/tests/integration/test_conquest_workflows.py -v -s

# Full pipeline (requires all services)
pytest core/tests/integration/test_full_pipeline.py -v -s
```

### **Run Specific Tests**

```bash
# Run only batch processing workflow test
pytest core/tests/integration/test_all_workflows.py::TestBatchProcessingWorkflow -v -s

# Run only conquest data parsing test
pytest core/tests/integration/test_conquest_workflows.py::TestConquestDataParsingWorkflow -v -s
```

---

## 📋 Prerequisites

### **Required Services**

Integration tests require these services to be running:

1. **Batch API Server** (port 4080)
   ```bash
   python -m core.batch_app.api_server
   ```

2. **Worker Process**
   ```bash
   python -m core.batch_app.worker
   ```

3. **Label Studio** (port 4115)
   ```bash
   docker-compose up label-studio
   ```

4. **Curation App** (port 8001)
   ```bash
   cd integrations/aris/curation_app && python api.py
   ```

5. **PostgreSQL** (port 4332)
   ```bash
   docker-compose up postgres
   ```

### **Service Health Check**

The test runner automatically checks service health:
```bash
✅ Batch API (port 4080)
✅ Label Studio (port 4115)
✅ Curation API (port 8001)
✅ Worker (heartbeat active)
```

---

## 📝 What Each Test Suite Covers

### **1. Label Studio Client Tests** (`test_label_studio_client.py`)

Tests the Label Studio API wrapper functionality:

- **Initialization**: API key handling, session setup
- **Project Management**: Create, get projects
- **Task Management**: Create, get, delete tasks with filters
- **Annotation Management**: Create, get, update annotations
- **Agreement Calculation**: Perfect match, partial match, no match scenarios
- **Gold-Star Tasks**: Filtering high-agreement tasks for training data
- **Export**: Task export with filters

**17 tests** covering all Label Studio client operations.

### 2. Conquest Schema Tests (`test_conquest_schemas.py`)

Tests the schema registry and validation system:

- **Schema Loading**: Single schema, multiple schemas, invalid schemas
- **Schema Retrieval**: Get by ID, list all schemas
- **Label Studio Config**: XML config generation
- **Task Validation**: Required fields, optional fields, data types
- **Annotation Validation**: Required fields, valid options, invalid options
- **ICL Export**: Message format, system/user/assistant roles
- **Fine-tuning Export**: Input/output field extraction

**17 tests** covering schema management and validation.

### 3. Curation API Tests (`test_curation_api.py`)

Tests the FastAPI backend endpoints:

- **Schema Endpoints**: List schemas, get schema by ID
- **Task Endpoints**: Create task, list tasks, get task
- **Annotation Endpoints**: Submit annotation, validation
- **Export Endpoints**: ICL format, fine-tuning format
- **Statistics Endpoint**: Task counts, agreement metrics

**16 tests** covering all API endpoints.

## Running Tests

### Quick Run

```bash
# Run all tests
./run_tests.sh

# Run specific test file
source venv/bin/activate
python -m pytest tests/test_label_studio_client.py -v

# Run specific test
python -m pytest tests/test_label_studio_client.py::TestLabelStudioClient::test_create_task -v
```

### With Coverage

```bash
source venv/bin/activate
python -m pytest tests/ \
    -v \
    --cov=curation_app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov
```

View coverage report: `htmlcov/index.html`

### Test Options

```bash
# Verbose output
python -m pytest tests/ -v

# Show print statements
python -m pytest tests/ -s

# Stop on first failure
python -m pytest tests/ -x

# Run only failed tests from last run
python -m pytest tests/ --lf

# Run tests matching pattern
python -m pytest tests/ -k "annotation"
```

## Test Structure

```
tests/
├── __init__.py
├── requirements-test.txt          # Test dependencies
├── test_label_studio_client.py    # Label Studio API wrapper tests
├── test_conquest_schemas.py       # Schema registry tests
└── test_curation_api.py           # FastAPI endpoint tests
```

## Test Dependencies

Install test dependencies:

```bash
pip install -r tests/requirements-test.txt
```

Dependencies:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `httpx` - FastAPI test client
- `responses` - HTTP mocking

## Writing New Tests

### Example Test

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_client():
    """Mock Label Studio client"""
    with patch('curation_app.api.label_studio') as mock:
        mock.create_task.return_value = {"id": 1}
        yield mock

def test_create_task(mock_client):
    """Test creating a task"""
    result = mock_client.create_task(
        project_id=1,
        data={"name": "John Doe"}
    )
    
    assert result["id"] == 1
    mock_client.create_task.assert_called_once()
```

### Best Practices

1. **Use fixtures** for common setup (mocks, test data)
2. **Mock external dependencies** (Label Studio API, database)
3. **Test edge cases** (missing data, invalid input, errors)
4. **Use descriptive names** (`test_create_task_with_invalid_data`)
5. **Keep tests isolated** (no shared state between tests)
6. **Test one thing** per test function

## Continuous Integration

Tests run automatically on:
- Every commit (pre-commit hook)
- Every pull request (GitHub Actions)
- Before deployment (CI/CD pipeline)

---

## 🔄 Workflows Tested

### **1. Batch Processing Workflow** ✅
```
Client → Upload File → Create Batch → Worker Processes → Download Results
```
**Tests**: File upload, batch creation, worker processing, result download

### **2. Label Studio Auto-Import Workflow** ✅
```
Batch Completes → Auto-Import Handler → Label Studio Tasks Created
```
**Tests**: Auto-import trigger, task creation, metadata extraction

### **3. Curation Workflow** ✅
```
Label Studio Tasks → Curation UI → View/Edit/Annotate → Save Changes
```
**Tests**: UI accessibility, data display, annotation capabilities

### **4. Gold Star Workflow** ✅
```
Mark Gold Star in Label Studio → Webhook → Update Aristotle Database
```
**Tests**: Gold star marking, webhook trigger, database sync

### **5. Victory Conquest Workflow** ✅
```
Mark VICTORY in Aristotle → Webhook → Create Gold Star in Label Studio
```
**Tests**: Victory marking, webhook receiver, Label Studio sync

### **6. Webhook Workflow** ✅
```
Batch Completes → Webhook Handler → HTTP POST to URL
```
**Tests**: Webhook configuration, payload format, retry logic

### **7. Conquest Data Parsing Workflow** ✅
```
Conquest Request → Parse Messages → Extract Candidate Data → Store in Label Studio
```
**Tests**: Message parsing, candidate extraction, metadata parsing

### **8. Bidirectional Sync Workflow** ✅
```
Label Studio ↔ Aristotle Database (Gold Stars ↔ Victory Conquests)
```
**Tests**: Sync infrastructure, required fields, webhook endpoints

### **9. Model Hot-Swapping Workflow** (Manual Tests)
```
Batch 1 (Model A) → Unload → Batch 2 (Model B) → Unload → Batch 3 (Model A)
```
**Tests**: Model loading, GPU memory management, sequential processing

---

## 📊 Test Results

### **Unit Tests**: ✅ **90/90 passing (100%)**
```bash
pytest core/tests/unit/ -v
```

### **Integration Tests**: ✅ **NEW - Comprehensive Coverage**
```bash
./core/tests/integration/run_all_workflows.sh
```

**Test Suites**:
- Core Workflows: 4 test classes, 4 workflows ✅
- Conquest Workflows: 5 test classes, 5 workflows ✅
- Full Pipeline: 1 test class, end-to-end ✅

### **Legacy Tests**: ✅ **50/50 passing (100%)**
- Label Studio Client: 17/17 ✅
- Conquest Schemas: 17/17 ✅
- Curation API: 16/16 ✅

---

## 🐛 Troubleshooting

### Import Errors

```bash
# Make sure you're in the venv
source venv/bin/activate

# Install the package in editable mode
pip install -e .
```

### Mock Issues

If mocks aren't working, check:
1. Patch path is correct (`curation_app.api.label_studio`, not `label_studio_client.LabelStudioClient`)
2. Mock is applied before function call
3. Mock return values match expected types

### Async Test Issues

For async tests, use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## Next Steps

1. **Add integration tests** - Test full workflow end-to-end
2. **Add performance tests** - Test with large datasets
3. **Add load tests** - Test concurrent requests
4. **Increase coverage** - Aim for 90%+ code coverage

