# Contributing to dotenvmodel

Thank you for your interest in contributing to dotenvmodel! We appreciate your time and effort in making this library better for everyone.

## Development Setup

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer and resolver

### Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AZX-PBC-OSS/dotenvmodel.git
   cd dotenvmodel
   ```

2. **Install dependencies:**

   This project uses `uv` for dependency management (the required uv version is pinned in `pyproject.toml`). Install development dependencies with:
   ```bash
   uv sync --group dev
   ```

   This creates a virtual environment and installs everything CI uses: pytest, pyright, ruff, pip-audit, and the MkDocs toolchain.

   The `Makefile` wraps the same commands CI runs: `make install`, `make test`, `make lint`, `make format`, `make type-check`, `make docs`.

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
uv run pytest tests/test_basic.py::TestBasicTypes::test_string_field

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

The project uses `pyright` for type checking (the same invocation CI and `make type-check` use):

```bash
# Run type checking (package and tests)
uv run pyright dotenvmodel tests

# Type check specific file
uv run pyright dotenvmodel/config.py
```

### Linting and Formatting

The project uses `ruff` for both linting and formatting (over the whole repository, matching CI):

```bash
# Check for linting issues
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check formatting without making changes
uv run ruff format --check .
```

### Running All Quality Checks

Before submitting a PR, run all quality checks (or their `make` equivalents: `make test`, `make lint`, `make type-check`):

```bash
# Run tests with coverage
uv run pytest

# Run type checking
uv run pyright dotenvmodel tests

# Run linting
uv run ruff check .

# Check formatting
uv run ruff format --check .
```

## Documentation

Build the docs site locally before submitting documentation changes:

```bash
make docs
```

The build runs with `--strict`: broken links and anchors fail the build instead of shipping quietly, exactly like the CI docs job. Use `make docs-serve` for a live preview while editing.

The site's changelog page (`docs/changelog.md`) is generated from `CHANGELOG.md` on every build — it is gitignored and must never be edited or committed. `CHANGELOG.md` itself is maintained by release-please; see the next section.

## Commits, Changelog, and Releases

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Commit messages drive the changelog and version bumps via [release-please](https://github.com/googleapis/release-please):

- `feat:` → minor version bump, "Features" changelog section
- `fix:` → patch bump, "Bug Fixes"
- `feat!:` / `fix!:` or a `BREAKING CHANGE:` footer → major bump, "⚠ BREAKING CHANGES" section
- `perf:`, `docs:`, `refactor:`, `build:`, `ci:` → their own changelog sections
- `style:`, `chore:`, `test:` → hidden from the changelog

Merging the release PR that release-please opens updates `CHANGELOG.md`, `pyproject.toml`, `dotenvmodel/__init__.py`, and `.release-please-manifest.json`, then tags the release and publishes it. Never bump versions or edit the changelog manually; write good conventional commit messages instead, and let the tooling do the rest.

Full history lives in [CHANGELOG.md](CHANGELOG.md).

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
   - Update README.md and the matching `docs/` guide for user-facing changes (the published guides live in `docs/`)
   - Add docstrings to new functions and classes (the API reference pages render them)
   - Update type hints and examples
   - Do not edit `CHANGELOG.md` by hand — see [Commits, Changelog, and Releases](#commits-changelog-and-releases)

5. **Verify your changes:**
   ```bash
   # Run all tests
   uv run pytest

   # Check types
   uv run pyright dotenvmodel tests

   # Check linting
   uv run ruff check .

   # Check formatting
   uv run ruff format --check .
   ```

## Pull Request Process

### Before Submitting

1. **Ensure all tests pass:**
   ```bash
   uv run pytest
   ```

2. **Ensure type checking passes:**
   ```bash
   uv run pyright dotenvmodel tests
   ```

3. **Ensure code is properly formatted:**
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
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
    f"Invalid format '{format}'. Supported formats: table, markdown, json, html, dotenv"
)

# Bad
raise ValueError("Invalid format")
```

## Getting Help

- **Questions?** Open a [GitHub Discussion](https://github.com/AZX-PBC-OSS/dotenvmodel/discussions)
- **Bug Reports?** Open an [Issue](https://github.com/AZX-PBC-OSS/dotenvmodel/issues)
- **Feature Requests?** Open an [Issue](https://github.com/AZX-PBC-OSS/dotenvmodel/issues) with the `enhancement` label

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions help make dotenvmodel better for everyone. We appreciate your time and effort!
