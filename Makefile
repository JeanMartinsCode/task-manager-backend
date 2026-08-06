.PHONY: help install test run migrate lint type-check format clean

help:
	@echo "Task Manager Backend - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run              Run development server (localhost:8000)"
	@echo "  make test             Run all tests"
	@echo "  make test-cov         Run tests with coverage report"
	@echo ""
	@echo "Database:"
	@echo "  make migrate          Run database migrations"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linting checks (ruff)"
	@echo "  make type-check       Run type checking (mypy)"
	@echo "  make format           Auto-format code"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove cache and build artifacts"

install:
	uv sync --all-extras

run:
	uvicorn task_manager.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

migrate:
	alembic upgrade head

lint:
	ruff check src/ tests/

type-check:
	mypy src/

format:
	ruff format src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage
