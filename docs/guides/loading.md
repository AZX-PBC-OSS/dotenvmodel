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

## Caching a Singleton Instance

Application code often needs a single shared config instance that is loaded once and reused everywhere. `cached()` provides this as a built-in: it loads on first call and returns the same instance on every subsequent call, with no re-reading of the environment.

```python
class AppConfig(DotEnvConfig):
    database_url: str = Field()
    port: int = Field(default=8000)

# First call loads from the environment.
config = AppConfig.cached()

# Subsequent calls return the same instance — no re-read.
same_config = AppConfig.cached()
assert config is same_config
```

### Lazy and Thread-Safe

`cached()` is lazy — the environment is only read on the very first call. It is also thread-safe: if multiple threads call `cached()` simultaneously before the first load completes, they race on a lock and only one thread calls `load()`; the rest block and receive the same instance. Once the cache is warm, all calls return immediately without acquiring the lock.

Arguments (`env`, `override`, `env_dir`) are only used on the first call. Once the instance is cached, subsequent calls ignore any arguments and return the existing instance. A warning is logged when the arguments passed disagree with the ones the cached instance was loaded with — so an accessor that consistently passes the same non-default arguments (`override=False`, say) stays silent, while a caller asking for something the cache does not hold is told what it actually holds.

Calling `.reload()` on the cached instance mutates it in place; since `cached()` always returns the same object, subsequent `cached()` calls see the reloaded values. A reload also updates what the instance reports as its load arguments, so `reload(env="prod")` is reflected by both `loaded_with()` and the comparison above.

!!! warning "Reentrant `cached()` calls raise `RuntimeError`"

    Calling `cached()` reentrantly for the same class from within that class's own `load()` / `post_load()` / field `validator` hooks raises `RuntimeError`. The internal lock is reentrant, so the nested call would not deadlock — it would see a cold cache and recurse into `load()` without bound, which is why it is rejected. If a hook needs the config instance mid-load, use `self`, or call `cls.load()` directly with re-entry guarding (an unconditional `cls.load()` inside `post_load()` re-runs the hooks and recurses until `RecursionError`).

    Calling `cached()`, `reset_cached()`, or `cached_override()` for **other** classes from those hooks is supported — for example, one class's `post_load()` may call `cached()` on another config class. However, calling `reset_cached()` or entering `cached_override()` for the **same** class whose first load is still in flight raises `RuntimeError` (the load installs its instance when it completes, which would silently undo the reset or discard the override). A circular cross-class hook chain (A's hook loads B, B's hook loads A) collapses back onto the first class and likewise raises `RuntimeError`.

    Hooks must not block on another thread (e.g. `thread.join()`) that touches the cache: the internal lock is held for the duration of a load, so the joining thread would hold the lock while the joined thread waits for it — a deadlock the reentrant lock cannot prevent.

### Scoped Overrides for Tests

`cached_override()` is a context manager that temporarily replaces the cached instance for the duration of a `with` block and automatically restores the previous state on exit — even if the block raises an exception. This is the **primary recommended tool** for test isolation when a single test needs a different config: it is structurally the same shape as Django's `override_settings` — scoped, self-restoring, and failure-safe.

```python
def test_with_custom_config():
    test_config = AppConfig.load_from_dict({"DATABASE_URL": "postgresql://localhost/test"})
    with AppConfig.cached_override(test_config):
        assert AppConfig.cached() is test_config
    # Previous cached() state (or absence of one) is restored here.
```

Because restoration is automatic and unconditional, `cached_override()` cannot forget to clean up — unlike a bare `reset_cached()` call that a test author might omit, silently leaking state into the next test. Reach for `cached_override()` first when a single test needs a different config; use `reset_cached()` (below) for the coarser case of a blanket fixture teardown between test modules.

!!! warning "Not for concurrent use"

    `cached_override()` is not designed for use while other threads may concurrently call `cached()` on the same class. The override window is not synchronized against concurrent readers beyond the lock-protected set/restore operations, so overlapping a `cached_override()` block with genuinely concurrent cross-thread `cached()` calls is racy in terms of which threads observe the override vs. the restored value. No data corruption occurs, but the observed value is unspecified during the transition.

### Resetting the Cache for Tests

`reset_cached()` is the coarser fallback: it unconditionally clears this class's cached instance so the next `cached()` call will call `load()` again. It is useful as a blanket fixture teardown — for example, clearing everything between test modules — but `cached_override()` (above) should be reached for first when a single test needs a different config, because `reset_cached()` cannot auto-restore and a forgotten call leaks state.

```python
import pytest


@pytest.fixture(autouse=True)
def reset_config_cache():
    yield
    AppConfig.reset_cached()


def test_dev_config(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/dev")
    config = AppConfig.cached()
    assert "dev" in config.database_url


def test_prod_config(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/prod")
    config = AppConfig.cached()
    assert "prod" in config.database_url
```

`reset_cached()` only affects the exact class it is called on — other `DotEnvConfig` subclasses keep their own cached instances.

!!! note "Per-class isolation"

    The cache is keyed by the exact class object. `SubA.cached()` and `SubB.cached()` cache independently, and a subclass of a subclass does not inherit its parent's cached instance.

### Not a Substitute for Dependency Injection

`cached()` is a single-config-per-process convenience for the common case where there is no DI framework already in place — scripts, simple services, cases where threading a config parameter through every call is impractical. It is **not** a substitute for dependency injection in applications that already have one.

- **pydantic-settings** deliberately does not ship a singleton/caching accessor itself; the maintainers' position (see [pydantic/pydantic-settings#410](https://github.com/pydantic/pydantic-settings/issues/410)) is that singleton lifecycle is an application concern, not the settings library's.
- **FastAPI**'s own documented settings pattern uses `functools.lru_cache` to avoid re-loading, but the load-bearing mechanism for *testability* is `app.dependency_overrides` — FastAPI's docs steer people toward DI-based overriding for tests, with the cache being an optimization, not the override mechanism.

**Conclusion:** if your application already has an app/request object and a DI mechanism (FastAPI, Flask with a DI extension, `svcs`-style service locators, etc.), prefer injecting the loaded config instance through that mechanism rather than calling `cached()` from deep in the call stack. `cached()` and `cached_override()` exist for the case where there is no DI framework to thread the config through — not to encourage a global-singleton-everywhere style in apps that already have DI.

## See Also

- [Loading API Reference](../api-reference/loading.md) — `load_env_files()`, `get_env_var()`, `get_env_var_name()`
- [DotEnvConfig API Reference](../api-reference/config.md) — `load()`, `reload()`, `load_from_dict()`, `cached()`, `reset_cached()`, `cached_override()`
- [Field Definitions](fields.md) — Defining config fields with `Field()`
- [Validation](validation.md) — Constraint validation
