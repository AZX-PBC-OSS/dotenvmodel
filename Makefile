.PHONY: help install test lint format type-check docs docs-serve clean build publish

help:
	@echo "Available commands:"
	@echo "  make install      - Install package and dev dependencies"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Run ruff linter and formatting check (matches CI)"
	@echo "  make format       - Format code with ruff"
	@echo "  make type-check   - Run pyright type checker (dotenvmodel + tests)"
	@echo "  make docs         - Build docs site (changelog page generated from CHANGELOG.md)"
	@echo "  make docs-serve   - Live-preview docs site (changelog page generated from CHANGELOG.md)"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make build        - Build package"
	@echo "  make publish      - Publish to PyPI"

install:
	uv sync --group dev

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

type-check:
	uv run pyright dotenvmodel tests

# The changelog page is generated from CHANGELOG.md before every build
# so the published site can never drift from the root changelog.
docs:
	cp CHANGELOG.md docs/changelog.md
	uv run mkdocs build --strict

docs-serve:
	cp CHANGELOG.md docs/changelog.md
	uv run mkdocs serve

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	uv build

publish: build
	uv publish
