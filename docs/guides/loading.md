# Loading Configuration

dotenvmodel provides flexible configuration loading from environment variables and `.env` files with Node.js-style cascading. This guide covers all loading methods and their parameters.

## .env File Cascading

When you call `load()`, dotenvmodel automatically reads `.env` files in a cascading order. Later files override earlier ones, giving you layered configuration from shared base values to local overrides.

!!! info "Cascade Order"

    Files are loaded in the following order (later files override earlier ones):

    1. **`.env`** — Base configuration (usually gitignored)
    2. **`.env.local`** — Local base overrides (gitignored, never committed)
    3. **`.env.{env}`** — Environment-specific (committed to repo)
    4. **`.env.{env}.local`** — Local environment overrides (gitignored, never committed)

### Practical Example

```bash
# .env (base - usually gitignored)
DATABASE_URL=postgresql://localhost/myapp
REDIS_URL=redis://localhost:6379
DEBUG=false

# .env.local (local base overrides - gitignored)
DATABASE_URL=postgresql://localhost/myapp_local

# .env.dev (development - committed to repo)
DEBUG=true
LOG_LEVEL=DEBUG

# .env.dev.local (local dev overrides - gitignored)
ENABLE_PROFILING=true
API_KEY=dev-key-local-override
```

When you load with `env="dev"`:

```python
config = AppConfig.load(env="dev")
# Loads in order: .env -> .env.local -> .env.dev -> .env.dev.local
# Final DATABASE_URL: postgresql://localhost/myapp_local (from .env.local)
# Final DEBUG: true (from .env.dev)
# Final ENABLE_PROFILING: true (from .env.dev.local)
```

!!! tip "Committing .env files"

    - **Commit**: `.env.{env}` files (e.g., `.env.dev`, `.env.prod`) — shared defaults
    - **Gitignore**: `.env`, `.env.local`, `.env.{env}.local` — contain secrets and local overrides

## The `env` Parameter

The `env` parameter selects which environment-specific files to load. If not provided, it reads from the `ENV` environment variable, defaulting to `"dev"`.

```python
# Auto-detect from ENV environment variable, default "dev"
config = AppConfig.load()

# Explicit environment
config = AppConfig.load(env="prod")

# Test environment
config = AppConfig.load(env="test")
```

!!! warning "Valid environment names"

    Environment names must only contain alphanumeric characters, hyphens, and underscores. This prevents path traversal attacks. Invalid names raise `ValueError`.

## The `override` Parameter

Controls whether `.env` file values override existing environment variables.

```python
# .env files override env vars (default)
config = AppConfig.load(override=True)

# Env vars take precedence over .env files
config = AppConfig.load(override=False)
```

| `override` | Behavior |
|------------|----------|
| `True` (default) | `.env` file values override existing environment variables |
| `False` | Existing environment variables take precedence over `.env` files |

!!! tip "When to use `override=False`"

    Use `override=False` in containerized environments where you inject config via environment variables and want them to take precedence over any `.env` files that might exist in the image.

## The `env_dir` Parameter

By default, dotenvmodel looks for `.env` files in the current working directory. You can specify a custom directory.

```python
from pathlib import Path

# Custom .env file directory
config = AppConfig.load(env_dir=Path("/app/config"))
```

### `DOTENV_DIR` Environment Variable

If `env_dir` is not provided, dotenvmodel checks the `DOTENV_DIR` environment variable:

```bash
# Set via environment variable
export DOTENV_DIR=/app/config
python your_app.py
```

```python
# No env_dir needed — reads from DOTENV_DIR
config = AppConfig.load()
```

!!! note "Precedence"

    The `env_dir` parameter takes precedence over the `DOTENV_DIR` environment variable, which takes precedence over the current working directory.

## Loading from a Dictionary

Use `load_from_dict()` for testing or when you have config values from a non-environment source. This bypasses `.env` file loading entirely.

```python
# Load from dictionary for testing
config = AppConfig.load_from_dict({
    "DATABASE_URL": "postgresql://localhost/test",
    "API_KEY": "test-key",
    "DEBUG": "true",
    "PORT": "8000",
})

# Skip validation if needed
config = AppConfig.load_from_dict(data, validate=False)
```

!!! tip "Keys can be field names or env var names"

    Dictionary keys can be either the env var name (e.g., `"DATABASE_URL"`) or the field name (e.g., `"database_url"`). Env var names take precedence.

!!! warning "Use `load()` in production"

    `load_from_dict()` is designed for testing. In production, always use `load()` to read from environment variables and `.env` files.

## Reloading Configuration

The `reload()` method lets you refresh configuration at runtime without creating a new instance. This is useful for picking up environment changes or switching environments.

```python
import os

# Load initial configuration
config = AppConfig.load(env="dev")
print(config.port)  # 8000

# Later, when environment variables change...
os.environ["PORT"] = "9000"

# Reload the configuration
config.reload()
print(config.port)  # 9000
```

### Reusing Original Parameters

By default, `reload()` reuses the same `env`, `override`, and `env_dir` from the original `load()` call:

```python
config = AppConfig.load(env="dev", override=True)
config.reload()  # Uses env="dev", override=True
```

### Overriding Parameters During Reload

You can override any parameter by passing new values:

```python
# Switch to production environment
config.reload(env="prod")

# Change override behavior
config.reload(override=False)
```

!!! warning "A failed reload can leave the instance partially reloaded"

    Fields are reloaded onto the same instance one at a time, so if validation (or the `post_load` hook) fails mid-reload, fields already reloaded keep their new values while the rest keep the old. If you catch reload errors, treat the instance as suspect — or build a fresh one with `load()` instead.

!!! info "reload() returns the same instance"

    `reload()` returns `self`, making it useful for method chaining:

    ```python
    config.reload(env="prod").port
    ```

!!! warning "Thread safety"

    `DotEnvConfig` instances are **not thread-safe** during `reload()`. In multi-threaded environments, use a lock or create a new instance via `load()` instead of calling `reload()` on a shared instance.

## See Also

- [Loading API Reference](../api-reference/loading.md) — `load_env_files()`, `get_env_var()`, `get_env_var_name()`
- [DotEnvConfig API Reference](../api-reference/config.md) — `load()`, `reload()`, `load_from_dict()`
- [Field Definitions](fields.md) — Defining config fields with `Field()`
- [Validation](validation.md) — Constraint validation
