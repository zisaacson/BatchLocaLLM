.PHONY: help install test lint format clean run-api run-worker run-curation docker-up docker-down

help:
	@echo "vLLM Batch Server - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test           Run test suite"
	@echo "  make lint           Run linters (ruff, mypy)"
	@echo "  make format         Format code (black, ruff)"
	@echo "  make clean          Clean temporary files"
	@echo ""
	@echo "Run Services:"
	@echo "  make run-api        Start batch API server (port 4080)"
	@echo "  make run-worker     Start batch worker"
	@echo "  make run-curation   Start curation UI (port 8001)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      Start all services with docker-compose"
	@echo "  make docker-down    Stop all services"

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=batch_app --cov=curation_app --cov-report=html --cov-report=term

lint:
	ruff check batch_app curation_app tests
	mypy batch_app curation_app

format:
	black batch_app curation_app tests tools
	ruff check --fix batch_app curation_app tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage coverage.xml

run-api:
	@echo "Starting vLLM Batch API on http://localhost:4080"
	uvicorn batch_app.api_server:app --host 0.0.0.0 --port 4080 --reload

run-worker:
	@echo "Starting Batch Worker..."
	python -m batch_app.worker

run-curation:
	@echo "Starting Curation UI on http://localhost:8001"
	uvicorn curation_app.api:app --host 0.0.0.0 --port 8001 --reload

docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

