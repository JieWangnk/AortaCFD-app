# AortaCFD Development Makefile

.PHONY: help install test test-unit test-integration test-coverage lint format clean docs

# Default target
help:
	@echo "AortaCFD Development Commands:"
	@echo "  install          Install dependencies"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  test-watch       Run tests in watch mode"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black"
	@echo "  type-check       Run type checking"
	@echo "  security-check   Run security checks"
	@echo "  clean            Clean build artifacts"
	@echo "  docs             Build documentation"
	@echo "  docs-serve       Serve documentation locally"

# Installation
install:
	pip install -r requirement.txt

install-dev:
	pip install -r requirement.txt
	pip install pytest-watch

# Testing
test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-coverage:
	pytest --cov=aortacfd_lib --cov=config --cov=workflow \
		--cov-report=html --cov-report=term-missing \
		--cov-report=xml

test-watch:
	ptw -- --testmon

test-parallel:
	pytest -n auto

test-verbose:
	pytest -vv --tb=short

# Code Quality
lint:
	@echo "Running Python syntax checks..."
	python3 -m py_compile app.py
	python3 -m py_compile config/builder.py config/base.py
	python3 -m py_compile workflow/manager.py workflow/base_task.py
	python3 -m py_compile aortacfd_lib/utils/logger.py aortacfd_lib/utils/runner.py aortacfd_lib/utils/format_points.py
	@echo "✓ All Python files compile successfully"
	@echo "Note: Install flake8, black, mypy for full linting"

lint-full:
	flake8 aortacfd_lib/ config/ workflow/ app.py
	flake8 tests/ --ignore=E501

format:
	black aortacfd_lib/ config/ workflow/ app.py tests/

format-check:
	black --check aortacfd_lib/ config/ workflow/ app.py tests/

type-check:
	mypy aortacfd_lib/ config/ workflow/ --ignore-missing-imports

security-check:
	bandit -r aortacfd_lib/ config/ workflow/
	safety check

# Documentation
docs:
	cd aortacfd-site && mkdocs build

docs-serve:
	cd aortacfd-site && mkdocs serve

# Web Interface
web-dev:
	cd aortacfd-site && python app.py

# Cleanup
clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf tests/reports/
	rm -rf coverage.xml
	rm -rf bandit-report.json
	rm -rf safety-report.json
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	find . -name ".DS_Store" -delete

# CI/CD simulation
ci-test:
	make lint
	make type-check
	make test-coverage
	make security-check

# Development workflow
dev-setup:
	make install-dev
	make test
	@echo "Development environment ready!"

# OpenFOAM environment check
check-openfoam:
	@echo "Checking OpenFOAM environment..."
	@if [ -z "$$WM_PROJECT_VERSION" ]; then \
		echo "Warning: OpenFOAM not sourced. Run 'source /opt/openfoam8/etc/bashrc'"; \
	else \
		echo "OpenFOAM version: $$WM_PROJECT_VERSION"; \
	fi

# Case management
clean-cases:
	rm -rf OPENFOAM/
	@echo "Cleaned all OpenFOAM cases"

# Quick development test
quick-test:
	pytest tests/unit/test_config/ -v

# Generate test reports
test-reports:
	mkdir -p tests/reports
	pytest --junit-xml=tests/reports/junit.xml \
		--html=tests/reports/report.html \
		--self-contained-html \
		--cov=aortacfd_lib --cov=config --cov=workflow \
		--cov-report=html:tests/reports/coverage

# Release preparation
pre-release:
	make clean
	make lint
	make type-check
	make test-coverage
	make security-check
	make docs
	@echo "Pre-release checks complete!"

# Docker support
docker-test:
	docker build -t aortacfd-test -f Dockerfile.test .
	docker run --rm aortacfd-test

# Benchmark tests
benchmark:
	pytest tests/ -v --benchmark-only