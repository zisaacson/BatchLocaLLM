# Contributing to vLLM Batch Server

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 🎯 Ways to Contribute

- **Bug Reports**: Found a bug? Open an issue with reproduction steps
- **Feature Requests**: Have an idea? Propose it in GitHub Discussions
- **Code Contributions**: Submit pull requests for bug fixes or features
- **Documentation**: Improve docs, add examples, fix typos
- **Testing**: Add test coverage, report edge cases
- **Community**: Help others in discussions and issues

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/vllm-batch-server.git
cd vllm-batch-server
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Start PostgreSQL
docker compose -f docker-compose.postgres.yml up -d

# Initialize database
python -c "from core.batch_app.database import init_db; init_db()"
```

### 3. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 📝 Development Workflow

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_api_validation.py -v

# Run with coverage
pytest --cov=core --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Format code (required before commit)
black core/ tools/ integrations/

# Lint code
ruff check core/ tools/ integrations/

# Type check
mypy core/

# Run all quality checks
make lint
```

### Manual Testing

```bash
# Start services
./scripts/start_all.sh

# Test API
curl http://localhost:4080/health

# Submit test batch
python integrations/examples/simple_client.py

# Check logs
tail -f logs/worker.log
tail -f logs/api_server.log
```

## 🎨 Code Style

### Python Style Guide

- **Formatting**: Use `black` with default settings (88 char line length)
- **Imports**: Use `isort` for import sorting
- **Type Hints**: Add type hints to all functions
- **Docstrings**: Use Google-style docstrings

Example:

```python
def process_batch(
    batch_id: str,
    model_name: str,
    max_tokens: int = 500
) -> dict[str, Any]:
    """
    Process a batch job with the specified model.
    
    Args:
        batch_id: Unique identifier for the batch job
        model_name: HuggingFace model identifier
        max_tokens: Maximum tokens to generate per request
        
    Returns:
        Dictionary containing batch results and metadata
        
    Raises:
        ValueError: If batch_id is invalid
        ModelNotFoundError: If model is not in registry
    """
    # Implementation here
    pass
```

### Naming Conventions

- **Variables**: `snake_case`
- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: Prefix with `_` (e.g., `_internal_function`)

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/       # Integration tests (slower, with DB)
└── manual/            # Manual test scripts
```

### Writing Tests

```python
import pytest
from core.batch_app.database import BatchJob

def test_batch_job_creation():
    """Test that batch jobs are created with correct defaults."""
    job = BatchJob(
        batch_id="batch_test123",
        input_file_id="file_abc",
        endpoint="/v1/chat/completions"
    )
    
    assert job.status == "validating"
    assert job.request_counts == {"total": 0, "completed": 0, "failed": 0}
```

### Test Coverage

- Aim for **80%+ coverage** on new code
- All bug fixes should include a regression test
- Integration tests for API endpoints
- Unit tests for business logic

## 📚 Documentation

### Code Documentation

- Add docstrings to all public functions and classes
- Include type hints
- Document complex algorithms with inline comments
- Update API docs when changing endpoints

### User Documentation

- Update `README.md` for user-facing changes
- Add examples to `examples/` directory
- Update `docs/` for architectural changes
- Include screenshots for UI changes

## 🔄 Pull Request Process

### Before Submitting

1. **Run tests**: `pytest tests/ -v`
2. **Check coverage**: `pytest --cov=core`
3. **Format code**: `black core/ tools/ integrations/`
4. **Lint code**: `ruff check core/ tools/ integrations/`
5. **Type check**: `mypy core/`
6. **Update docs**: If you changed APIs or added features
7. **Add tests**: For new features or bug fixes

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Added unit tests
- [ ] Added integration tests
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] No new warnings
```

### Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: Maintainer reviews code
3. **Feedback**: Address review comments
4. **Approval**: Maintainer approves PR
5. **Merge**: Squash and merge to main

## 🐛 Bug Reports

### Before Reporting

1. **Search existing issues**: Your bug might already be reported
2. **Try latest version**: Bug might be fixed in main branch
3. **Minimal reproduction**: Create smallest example that reproduces bug

### Bug Report Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Start server with...
2. Submit batch with...
3. Observe error...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: Ubuntu 22.04
- Python: 3.10.12
- vLLM: 0.11.0
- GPU: RTX 4080 16GB
- CUDA: 12.1

## Logs
```
Paste relevant logs here
```

## Additional Context
Screenshots, error messages, etc.
```

## 💡 Feature Requests

### Proposing Features

1. **Check roadmap**: Feature might already be planned
2. **Open discussion**: Discuss in GitHub Discussions first
3. **Gather feedback**: Get community input
4. **Create issue**: If there's consensus, create feature request

### Feature Request Template

```markdown
## Feature Description
What feature do you want?

## Use Case
Why is this feature needed?

## Proposed Solution
How should it work?

## Alternatives Considered
What other approaches did you consider?

## Additional Context
Mockups, examples, etc.
```

## 🏗️ Architecture Guidelines

### Adding New Endpoints

1. Add route to `core/batch_app/api_server.py`
2. Add database models if needed
3. Add validation with Pydantic
4. Add tests
5. Update API documentation

### Adding New Models

1. Add model to registry via API or database
2. Test with small batch first
3. Document VRAM requirements
4. Add to supported models list

### Database Changes

1. Create migration script in `scripts/migrate_*.py`
2. Test migration on dev database
3. Document migration in PR
4. Update database schema docs

## 🤝 Community Guidelines

### Code of Conduct

- **Be respectful**: Treat everyone with respect
- **Be constructive**: Provide helpful feedback
- **Be patient**: Remember everyone is learning
- **Be inclusive**: Welcome diverse perspectives

### Communication

- **Issues**: For bugs and feature requests
- **Discussions**: For questions and ideas
- **Pull Requests**: For code contributions
- **Discord/Slack**: For real-time chat (if available)

## 📜 License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## 🙏 Recognition

Contributors will be:
- Listed in `CONTRIBUTORS.md`
- Mentioned in release notes
- Credited in documentation

## ❓ Questions?

- **General questions**: GitHub Discussions
- **Bug reports**: GitHub Issues
- **Security issues**: See `SECURITY.md`

---

Thank you for contributing to vLLM Batch Server! 🎉

