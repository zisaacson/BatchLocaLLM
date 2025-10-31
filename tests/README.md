# Test Suite for vLLM Batch Server + Curation System

Comprehensive test suite for the Label Studio integration and curation system.

## Test Coverage

### 1. Label Studio Client Tests (`test_label_studio_client.py`)

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

## Test Results

**Current Status**: ✅ **50/50 tests passing (100%)**

- Label Studio Client: 17/17 ✅
- Conquest Schemas: 17/17 ✅
- Curation API: 16/16 ✅

## Troubleshooting

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

