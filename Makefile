# DXtrade Python SDK Makefile

.PHONY: help install install-dev test test-unit test-integration test-cov lint format type-check quality clean build docs serve-docs

# Default target
help:
	@echo "Available commands:"
	@echo "  install      Install the package"
	@echo "  install-dev  Install development dependencies"
	@echo "  test         Run all tests"
	@echo "  test-unit    Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-cov     Run tests with coverage report"
	@echo "  lint         Run code linting"
	@echo "  format       Format code with black and ruff"
	@echo "  type-check   Run mypy type checking"
	@echo "  quality      Run all quality checks"
	@echo "  clean        Clean build artifacts"
	@echo "  build        Build package"
	@echo "  docs         Build documentation"
	@echo "  serve-docs   Serve documentation locally"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev,docs]"

# Testing
test:
	pytest

test-unit:
	pytest -m "unit"

test-integration:
	pytest -m "integration"

test-cov:
	pytest --cov=dxtrade --cov-report=html --cov-report=term-missing --cov-fail-under=90

# Code quality
lint:
	ruff check src tests
	
format:
	black src tests examples
	ruff check --fix src tests examples

type-check:
	mypy src

quality: lint type-check
	@echo "All quality checks passed!"

# Development
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

# Documentation
docs:
	cd docs && mkdocs build

serve-docs:
	cd docs && mkdocs serve

# CI/CD helpers
ci-install:
	pip install -e ".[dev]"

ci-test:
	pytest --cov=dxtrade --cov-report=xml --cov-report=term

ci-quality:
	ruff check src tests
	black --check src tests
	mypy src

# Release helpers
version-patch:
	bump2version patch

version-minor:
	bump2version minor

version-major:
	bump2version major

publish-test:
	python -m twine upload --repository testpypi dist/*

publish:
	python -m twine upload dist/*