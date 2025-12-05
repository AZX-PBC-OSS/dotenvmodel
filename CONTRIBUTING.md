# Contributing to dotenvmodel

Thank you for your interest in contributing to dotenvmodel! We appreciate your time and effort in making this library better for everyone.

## Development Setup

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer and resolver

### Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/azxio/dotenvmodel.git
   cd dotenvmodel
   ```

2. **Install dependencies:**

   This project uses `uv` for dependency management. Install development dependencies with:
   ```bash
   uv sync --dev
   ```

   This will create a virtual environment and install all necessary dependencies including pytest, mypy, ruff, and other development tools.

## Running Tests

**IMPORTANT: Always use `uv run` to execute pytest and other development commands.**

Using `uv run` ensures that:
- Commands run in the correct virtual environment
- All dependencies are properly resolved
- You're using the exact versions specified in the project
- No conflicts with globally installed packages

### Test Commands

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_describe.py

# Run specific test class
uv run pytest tests/test_describe.py::TestLineEndings

# Run specific test function
uv run pytest tests/test_core.py::TestDotEnvConfig::test_load_from_dict

# Run with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=dotenvmodel --cov-report=html

# Run tests matching a pattern
uv run pytest -k "test_validation"

# Run tests with output from print statements
uv run pytest -s
```

### Understanding Test Output

The project is configured with the following pytest settings (in `pyproject.toml`):
- Coverage is automatically collected for the `dotenvmodel` package
- HTML coverage reports are generated in `htmlcov/`
- Tests must maintain at least 95% code coverage
- Coverage reports exclude test files and implementation details

## Code Quality

### Type Checking

The project uses `ty` (a wrapper around pyright) for type checking:

```bash
# Run type checking
uv run ty check

# Type check specific file
uv run ty check dotenvmodel/core.py
```

### Linting and Formatting

The project uses `ruff` for both linting and formatting:

```bash
# Check for linting issues
uv run ruff check dotenvmodel

# Auto-fix linting issues
uv run ruff check --fix dotenvmodel

# Format code
uv run ruff format dotenvmodel

# Check formatting without making changes
uv run ruff format --check dotenvmodel
```

### Running All Quality Checks

Before submitting a PR, run all quality checks:

```bash
# Run tests with coverage
uv run pytest

# Run type checking
uv run ty check

# Run linting
uv run ruff check dotenvmodel

# Check formatting
uv run ruff format --check dotenvmodel
```

## Making Changes

### Workflow

1. **Create a feature branch:**
   ```bash
   git checkout -b feat/your-feature-name
   ```

   Or for bug fixes:
   ```bash
   git checkout -b fix/bug-description
   ```

2. **Make your changes:**
   - Write clear, readable code
   - Follow existing code patterns and conventions
   - Add type hints to all functions and methods
   - Keep functions focused and modular

3. **Write tests:**
   - Add tests for all new functionality
   - Update existing tests if modifying behavior
   - Ensure tests are clear and well-documented
   - Test edge cases and error conditions
   - Run tests with `uv run pytest`

4. **Update documentation:**
   - Update README.md if adding new features
   - Add docstrings to new functions and classes
   - Update type hints and examples

5. **Verify your changes:**
   ```bash
   # Run all tests
   uv run pytest

   # Check types
   uv run ty check

   # Check linting
   uv run ruff check dotenvmodel

   # Check formatting
   uv run ruff format --check dotenvmodel
   ```

## Pull Request Process

### Before Submitting

1. **Ensure all tests pass:**
   ```bash
   uv run pytest
   ```

2. **Ensure type checking passes:**
   ```bash
   uv run ty check
   ```

3. **Ensure code is properly formatted:**
   ```bash
   uv run ruff format dotenvmodel
   uv run ruff check --fix dotenvmodel
   ```

4. **Verify coverage hasn't decreased:**
   ```bash
   uv run pytest --cov=dotenvmodel --cov-report=term-missing
   ```

   Coverage should remain at or above 95%.

### Submitting Your PR

1. **Push your branch:**
   ```bash
   git push origin feat/your-feature-name
   ```

2. **Create a pull request on GitHub**

3. **In your PR description:**
   - Clearly describe what changes you made
   - Explain why the changes are needed
   - Reference any related issues
   - Include examples of new functionality (if applicable)
   - List any breaking changes

### PR Description Template

```markdown
## Summary
Brief description of what this PR does

## Changes
- Change 1
- Change 2
- Change 3

## Testing
Describe how you tested these changes

## Related Issues
Fixes #123
```

## Code Review

### What to Expect

- All changes must pass automated tests and type checking
- Code reviewers will check for:
  - Implementation correctness
  - Code clarity and maintainability
  - Adequate test coverage
  - Documentation completeness
  - Adherence to project conventions

- You may be asked to make revisions
- Reviews are constructive - they help improve code quality

### Addressing Feedback

When reviewers request changes:

1. Make the requested changes in your branch
2. Run tests again: `uv run pytest`
3. Push the updates: `git push origin feat/your-feature-name`
4. Respond to reviewer comments

## Development Tips

### Virtual Environment

The `uv run` command automatically manages the virtual environment. You don't need to manually activate it.

If you prefer to activate the environment manually:
```bash
# uv creates a .venv directory
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

However, we recommend using `uv run` for consistency.

### Interactive Testing

You can use `uv run python` to start a Python interpreter with the correct environment:

```bash
uv run python
```

Then test your changes interactively:
```python
from dotenvmodel import DotEnvConfig, Field

class TestConfig(DotEnvConfig):
    value: str = Field()

config = TestConfig.load_from_dict({"value": "test"})
print(config.value)
```

### Debugging Tests

To debug a specific test with pdb:

```bash
# Add breakpoint() in your test or code
# Then run with -s to see output
uv run pytest -s tests/test_describe.py::test_specific_function
```

### Coverage Reports

After running tests with coverage, view the HTML report:

```bash
uv run pytest --cov=dotenvmodel --cov-report=html
# Open htmlcov/index.html in your browser
```

## Code Style Guidelines

### General Principles

- Write clear, self-documenting code
- Use meaningful variable and function names
- Keep functions short and focused (ideally under 50 lines)
- Avoid deep nesting (max 3-4 levels)
- Comments should explain "why", not "what"

### Type Hints

Always use type hints:

```python
# Good
def process_value(value: str, default: int = 0) -> int:
    return int(value) if value else default

# Bad
def process_value(value, default=0):
    return int(value) if value else default
```

### Docstrings

Use clear docstrings for public APIs:

```python
def describe(cls, format: str = "table") -> str:
    """Generate documentation for the configuration class.

    Args:
        format: Output format - "table", "markdown", "json", "html", or "dotenv"

    Returns:
        Formatted documentation string

    Raises:
        ValueError: If format is not supported
    """
```

### Error Messages

Write helpful error messages:

```python
# Good
raise ValueError(
    f"Invalid format '{format}'. "
    f"Supported formats: table, markdown, json, html, dotenv"
)

# Bad
raise ValueError("Invalid format")
```

## Getting Help

- **Questions?** Open a [GitHub Discussion](https://github.com/azxio/dotenvmodel/discussions)
- **Bug Reports?** Open an [Issue](https://github.com/azxio/dotenvmodel/issues)
- **Feature Requests?** Open an [Issue](https://github.com/azxio/dotenvmodel/issues) with the `enhancement` label

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions help make dotenvmodel better for everyone. We appreciate your time and effort!
