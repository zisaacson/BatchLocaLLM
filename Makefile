.PHONY: help install install-dev test test-unit test-integration lint format clean run-api run-worker run-all docker-up docker-down pre-commit docs

help:
	@echo "vLLM Batch Server - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make lint             Run linters (ruff, mypy)"
	@echo "  make format           Format code (black, isort, ruff)"
	@echo "  make pre-commit       Run pre-commit hooks"
	@echo "  make clean            Clean temporary files"
	@echo ""
	@echo "Run Services:"
	@echo "  make run-api          Start batch API server (port 4080)"
	@echo "  make run-worker       Start batch worker"
	@echo "  make run-all          Start all services"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start PostgreSQL with docker-compose"
	@echo "  make docker-down      Stop all docker services"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs             Build documentation"

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

install-dev:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

test:
	pytest tests/ -v --cov=core --cov-report=html --cov-report=term --cov-report=xml

test-unit:
	pytest tests/unit/ -v --cov=core --cov-report=term

test-integration:
	pytest tests/integration/ -v --maxfail=3

lint:
	@echo "Running ruff..."
	ruff check core/ tools/ integrations/examples/
	@echo "Running mypy..."
	mypy core/ --ignore-missing-imports

format:
	@echo "Running black..."
	black core/ tools/ integrations/examples/
	@echo "Running isort..."
	isort core/ tools/ integrations/examples/
	@echo "Running ruff --fix..."
	ruff check --fix core/ tools/ integrations/examples/

pre-commit:
	pre-commit run --all-files

clean:
	@echo "Cleaning temporary files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage coverage.xml
	rm -rf build/ dist/ *.egg-info

run-api:
	@echo "Starting vLLM Batch API on http://localhost:4080"
	python -m core.batch_app.api_server

run-worker:
	@echo "Starting Batch Worker..."
	python -m core.batch_app.worker

run-all:
	@echo "Starting all services..."
	./scripts/start_all.sh

docker-up:
	@echo "Starting PostgreSQL..."
	docker compose -f docker-compose.postgres.yml up -d

docker-down:
	@echo "Stopping all docker services..."
	docker compose -f docker-compose.postgres.yml down
	docker compose -f docker-compose.monitoring.yml down 2>/dev/null || true

docs:
	@echo "Building documentation..."
	mkdocs build

