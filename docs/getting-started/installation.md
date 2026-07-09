# Installation

dotenvmodel is a pure-Python library with minimal dependencies. It runs on Python 3.12+ and works with any modern project setup.

## Requirements

!!! warning "Python 3.12+ required"
    dotenvmodel requires **Python 3.12 or newer**. It uses modern type syntax such as `str | None` and `list[str]` that is only fully supported on 3.12+. If you need to support older Python versions, pin to a compatible library instead.

dotenvmodel has only two runtime dependencies, so it stays lightweight:

| Dependency | Purpose |
| :-- | :-- |
| [python-dotenv](https://github.com/theskumar/python-dotenv) `>=0.19.0` | Reads and parses `.env` files |
| [typing-extensions](https://github.com/python/typing_extensions) `>=4.15.0` | Backports for advanced typing features |

## Installing with pip

Install from [PyPI](https://pypi.org/project/dotenvmodel/) using pip:

```bash
pip install dotenvmodel
```

## Installing with uv

If you use [uv](https://github.com/astral-sh/uv) for dependency management (recommended):

```bash
uv add dotenvmodel
```

## Verifying the installation

Confirm the package is installed and check the version:

```bash
python -c "import dotenvmodel; print(dotenvmodel.__version__)"
```

You should see the installed version printed, for example:

```text
0.2.0
```

!!! tip "Troubleshooting"
    If you see `ModuleNotFoundError: No module named 'dotenvmodel'`, make sure the virtual environment where you installed the package is the same one you are running Python from. Activate the environment (or use `uv run`) and try again.

## Next steps

Now that dotenvmodel is installed, learn how to define and load typed configuration in 5 minutes:

:material-arrow-right: [Quick Start](quick-start.md)
