# AortaCFD Build System
# Professional build automation for CFD application

.PHONY: help dev-setup test lint build docker-build deploy-local clean

# Default target
help:
	@echo "🚀 AortaCFD Build System"
	@echo "========================="
	@echo "Development Commands:"
	@echo "  dev-setup     - Set up development environment"
	@echo "  test          - Run all tests"
	@echo "  test-watch    - Run tests in watch mode"
	@echo "  lint          - Run code linting"
	@echo "  lint-fix      - Auto-fix linting issues"
	@echo ""
	@echo "Build Commands:"
	@echo "  build         - Build application package"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run application in Docker"
	@echo ""
	@echo "Deployment Commands:"
	@echo "  deploy-local  - Deploy locally for testing"
	@echo "  deploy-k8s    - Deploy to Kubernetes"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean         - Clean build artifacts"
	@echo "  validate      - Validate codebase integrity"

# Development Environment Setup
dev-setup:
	@echo "🔧 Setting up development environment..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	. venv/bin/activate && pip install -r requirements-dev.txt
	@echo "✅ Development environment ready! Run: source venv/bin/activate"

# Testing
test:
	@echo "🧪 Running test suite..."
	. venv/bin/activate && pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-watch:
	@echo "👀 Running tests in watch mode..."
	. venv/bin/activate && pytest-watch tests/ -- -v

test-integration:
	@echo "🔧 Running integration tests..."
	. venv/bin/activate && pytest tests/integration/ -v --tb=short

# Code Quality
lint:
	@echo "🔍 Running code analysis..."
	. venv/bin/activate && flake8 src/ tests/ app.py
	. venv/bin/activate && mypy src/ --ignore-missing-imports
	. venv/bin/activate && black --check src/ tests/ app.py

lint-fix:
	@echo "🔧 Auto-fixing code issues..."
	. venv/bin/activate && black src/ tests/ app.py
	. venv/bin/activate && isort src/ tests/ app.py

# Security scanning
security-scan:
	@echo "🔒 Running security analysis..."
	. venv/bin/activate && bandit -r src/ -f json -o security-report.json
	. venv/bin/activate && safety check --json --output safety-report.json

# Build
build:
	@echo "📦 Building application package..."
	. venv/bin/activate && python -m build
	@echo "✅ Build complete! Check dist/ directory"

# Docker operations
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t aortacfd:latest .
	docker build -t aortacfd:dev -f Dockerfile.dev .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/output:/app/output \
		aortacfd:latest

docker-compose-up:
	@echo "🐳 Starting Docker Compose services..."
	docker-compose up -d

# Deployment
deploy-local:
	@echo "🚀 Deploying locally..."
	. venv/bin/activate && python app.py --help
	@echo "✅ Local deployment ready!"

deploy-k8s:
	@echo "☸️ Deploying to Kubernetes..."
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml

# Validation
validate:
	@echo "✅ Validating codebase..."
	python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('src/**/*.py', recursive=True)]"
	@echo "✅ All Python files have valid syntax"

# Performance profiling
profile:
	@echo "📊 Running performance analysis..."
	. venv/bin/activate && python -m cProfile -o profile.stats app.py --help
	. venv/bin/activate && python -c "import pstats; p=pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Documentation
docs:
	@echo "📚 Generating documentation..."
	. venv/bin/activate && sphinx-build -b html docs/ docs/_build/html

# Clean up
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/
	rm -rf __pycache__/ src/**/__pycache__/ tests/**/__pycache__/
	rm -f profile.stats security-report.json safety-report.json
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete

# Development database setup (for future features)
db-setup:
	@echo "🗄️ Setting up development database..."
	. venv/bin/activate && python scripts/setup_db.py

# Benchmark testing
benchmark:
	@echo "⚡ Running benchmark tests..."
	. venv/bin/activate && pytest tests/benchmark/ -v --benchmark-only

# Version management
version-patch:
	@echo "🏷️ Bumping patch version..."
	. venv/bin/activate && bumpversion patch

version-minor:
	@echo "🏷️ Bumping minor version..."
	. venv/bin/activate && bumpversion minor

# Release preparation
prepare-release:
	@echo "🚀 Preparing release..."
	make clean
	make test
	make lint
	make security-scan
	make build
	@echo "✅ Release preparation complete!"