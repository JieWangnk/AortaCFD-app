# AortaCFD build system
# Conventions: tabs for recipe indentation (Make requirement).
#               assumes ./venv exists; create with `make install`.

.PHONY: help install test test-all test-bench lint format build clean clean-all

help:
	@echo "AortaCFD — common tasks"
	@echo "  make install     Create ./venv and install package + dev deps"
	@echo "  make test        Fast test suite (~30s, deselects slow/e2e/benchmark)"
	@echo "  make test-all    Full suite minus benchmark fixtures"
	@echo "  make test-bench  Benchmark tests against a real qoi_summary.json"
	@echo "                   (requires BPM120_QOI or BPM120_TUTORIAL_QOI env var)"
	@echo "  make lint        flake8 F-codes + bandit HIGH (the actual gates)"
	@echo "  make format      black + isort"
	@echo "  make build       sdist + wheel into dist/"
	@echo "  make clean       Remove build artefacts and pycache"
	@echo "  make clean-all   Reset to a fresh-clone state (output/, caches, build/)."
	@echo "                   Preserves cases_input/, venv/, repo source. Dry-run by"
	@echo "                   default; pass CONFIRM=yes to actually delete."

install:
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip && pip install -e ".[dev]"
	@echo "✓ venv ready — run 'source venv/bin/activate' to use it"

test:
	. venv/bin/activate && PYTHONPATH=src pytest tests/ -q \
		-m "not slow and not e2e and not benchmark" --tb=line

test-all:
	. venv/bin/activate && PYTHONPATH=src pytest tests/ -v \
		-m "not benchmark" --tb=short

test-bench:
	@if [ -z "$$BPM120_QOI" ] && [ -z "$$BPM120_TUTORIAL_QOI" ]; then \
		echo "Set BPM120_QOI or BPM120_TUTORIAL_QOI to a qoi_summary.json path."; \
		exit 1; \
	fi
	. venv/bin/activate && PYTHONPATH=src pytest tests/benchmarks/ -v -m benchmark

lint:
	. venv/bin/activate && flake8 src/ --select F --max-line-length 120 --extend-ignore E203,W503
	. venv/bin/activate && bandit -r src/ -ll -ii --quiet

format:
	. venv/bin/activate && black src/ tests/ --line-length 120
	. venv/bin/activate && isort src/ tests/ --profile black

build:
	. venv/bin/activate && python -m build

clean:
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/ coverage.xml
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

clean-all:
	@. venv/bin/activate && python -m scripts.reset_app $(if $(filter yes,$(CONFIRM)),--yes,) $(if $(filter yes,$(INCLUDE_VENV)),--include-venv,)
