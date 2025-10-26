# Contributing to vLLM Batch Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/YOUR_ORG/vllm-batch-server/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, GPU, vLLM version)
   - Logs if applicable

### Suggesting Features

1. Check existing [Issues](https://github.com/YOUR_ORG/vllm-batch-server/issues) and [Discussions](https://github.com/YOUR_ORG/vllm-batch-server/discussions)
2. Create a new discussion with:
   - Use case description
   - Proposed solution
   - Alternatives considered
   - Impact on existing functionality

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/vllm-batch-server.git
   cd vllm-batch-server
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the code style (Black, Ruff)
   - Add tests for new functionality
   - Update documentation

4. **Run tests**
   ```bash
   # Install dev dependencies
   pip install -e ".[dev]"
   
   # Run tests
   pytest
   
   # Run linters
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```
   
   Use conventional commits:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test changes
   - `refactor:` - Code refactoring
   - `perf:` - Performance improvements
   - `chore:` - Build/tooling changes

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   
   Then create a pull request on GitHub with:
   - Clear description of changes
   - Link to related issues
   - Screenshots/examples if applicable

## Development Setup

### Prerequisites

- Python 3.10+
- NVIDIA GPU with CUDA 12.1+
- Docker & Docker Compose

### Local Development

```bash
# Clone repository
git clone https://github.com/YOUR_ORG/vllm-batch-server.git
cd vllm-batch-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Run tests
pytest

# Run server locally (without Docker)
python -m uvicorn src.main:app --reload
```

### Code Style

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **mypy** for type checking

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/ --fix

# Type check
mypy src/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_batch_processor.py

# Run specific test
pytest tests/test_batch_processor.py::test_process_batch
```

## Project Structure

```
vllm-batch-server/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models
│   ├── storage.py           # Storage layer
│   ├── batch_processor.py   # Batch processing logic
│   └── logger.py            # Logging configuration
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_batch_processor.py
│   └── test_storage.py
├── docs/
│   ├── ARIS_INTEGRATION.md
│   ├── API.md
│   └── CONFIGURATION.md
├── docker/
│   └── Dockerfile
├── pyproject.toml
├── docker-compose.yml
└── README.md
```

## Documentation

- Update README.md for user-facing changes
- Update docs/ for detailed guides
- Add docstrings to all functions/classes
- Include type hints

## Release Process

1. Update version in `pyproject.toml` and `src/__init__.py`
2. Update CHANGELOG.md
3. Create release tag: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions will build and publish

## Questions?

- Open a [Discussion](https://github.com/YOUR_ORG/vllm-batch-server/discussions)
- Join our community chat (if available)
- Email maintainers (if listed)

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

