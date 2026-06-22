# Install project
install:
    uv sync

# Install development dependencies
install-dev:
    uv sync --all-extras

# Run all tests
test:
    uv run pytest -v --no-cov

# Run all tests with coverage
test-cov:
    uv run pytest --cov=src --cov-report=html --cov-report=term

# Lint code
lint:
    uv run ruff check src tests

# Format code
format:
    uv run ruff format src tests

# Type check code
type:
    uv run ty check src tests

# Check code quality
check: lint format type

# Run all pre-commit hooks
pre:
    uv run prek run --all-files
