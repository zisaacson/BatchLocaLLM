# Test Organization

## Test Directory Structure

```
tests/
├── unit/                           # 59 tests - Mock external dependencies
│   ├── test_conquest_schemas.py    # Schema validation logic
│   ├── test_label_studio_client.py # Label Studio client methods
│   └── test_curation_api.py        # FastAPI endpoints (mocked LS + schemas)
│
├── integration/                    # 1 test - Real service integration
│   └── test_label_studio_integration.py  # Real Label Studio connectivity
│
├── e2e/                            # 5 tests - End-to-end workflows
│   └── test_batch_workflow.py      # Complete batch processing workflow
│
└── manual/                         # Manual validation scripts
    └── test_full_e2e.py            # Full system test (all services)
```

## Test Philosophy

### Unit Tests (59 tests)
**Purpose:** Test business logic in isolation
**Characteristics:**
- Mock all external dependencies (Label Studio, databases, file systems)
- Fast execution (< 1 second)
- No network calls
- No service dependencies

**Examples:**
- `test_curation_api.py` - Tests FastAPI endpoints with mocked Label Studio client
- `test_label_studio_client.py` - Tests HTTP client methods with mocked requests
- `test_conquest_schemas.py` - Tests schema validation logic

### Integration Tests (1 test)
**Purpose:** Test real integration between components
**Characteristics:**
- NO MOCKING of the integration being tested
- Tests real service connectivity
- Skips if services not available
- May be slower (network calls)

**Examples:**
- `test_label_studio_integration.py` - Tests real Label Studio connectivity (skips if LS not running)

**Anti-pattern:** Mocking Label Studio in an "integration" test - that's a unit test!

### E2E Tests (5 tests)
**Purpose:** Test complete user workflows
**Characteristics:**
- Tests full system behavior
- Uses real database (PostgreSQL)
- Uses TestClient for API calls
- Tests complete workflows (upload → batch → process → download)

**Examples:**
- `test_batch_workflow.py` - Complete batch processing workflow

### Manual Tests
**Purpose:** Full system validation before deployment
**Characteristics:**
- Requires all services running (Batch API, Curation API, Label Studio, Worker, PostgreSQL)
- Human-readable output
- Not part of automated CI/CD

**Examples:**
- `test_full_e2e.py` - Full system validation script

## Key Principles

1. **Unit tests mock external dependencies** - Fast, isolated, test logic
2. **Integration tests use real services** - Test actual integrations, skip if unavailable
3. **E2E tests use real workflows** - Test user journeys
4. **If you're mocking everything, it's a unit test** - Don't call it integration

## Test Counts

- **Unit tests:** 59 (97% of tests)
- **Integration tests:** 1 (2% of tests)
- **E2E tests:** 5 (8% of tests)
- **Total:** 61 tests (100% passing)

## Coverage

- **Overall:** 18% (low because batch_app/worker.py has no unit tests)
- **Curation app:** 27-67% (good coverage on user-facing code)
- **Unit tests:** High coverage on tested modules
- **Integration/E2E:** Cover critical paths

## Running Tests

```bash
# All tests
pytest -v

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (requires Label Studio)
pytest tests/integration/ -v

# E2E tests (requires PostgreSQL)
pytest tests/e2e/ -v

# Manual full system test
python tests/manual/test_full_e2e.py
```
