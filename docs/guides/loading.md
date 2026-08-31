# Loading Configuration

dotenvmodel provides flexible configuration loading from environment variables and `.env` files with Node.js-style cascading. This guide covers all loading methods and their parameters.

## Resolution Order

`load()` resolves each field across three layers, without ever mutating `os.environ`:

1. **Process environment** — real environment variables
2. **Merged dotfile cascade** — the `.env` files, merged with later files winning
3. **Field default** — the `Field(default=...)` value

By default (`override=False`), the process environment wins: a real `DATABASE_URL` beats whatever the `.env` files say. With `override=True` (or `DOTENV_OVERRIDE=true`), the merged dotfile layer wins instead — the pre-0.7 precedence, now explicit and opt-in.

| Mode | Lookup order |
|------|--------------|
| `override=False` (default) | process env → dotfiles → field default |
| `override=True` | dotfiles → process env → field default |

The `.env` cascade is merged once per load (later, more specific files win within the file layer), and the override policy is applied once against the whole merged layer — the same model Vite and Next.js use.

!!! warning "Breaking change: `load()` no longer mutates `os.environ`"

    Through 0.6.3, `load()` injected every dotfile value into the process environment via python-dotenv's `load_dotenv()` — so dotfiles beat real env vars by default, `monkeypatch.setenv` was defeated in tests, and injected values leaked into everything else the process did. As of 0.7.0, loading is a pure read. If you relied on the side effect (for example, other libraries reading `os.environ` after your config load), call python-dotenv yourself:

    ```python
    from dotenv import load_dotenv

    load_dotenv("/app/config/.env", override=True)  # explicit injection, your policy
    ```

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

### Variable Interpolation

`${VAR}` references inside `.env` values are resolved once, after the whole cascade is merged. The lookup base is:

1. **Merged dotfile cascade** — a reference sees values from every file in the cascade, so a later file can build on an earlier file's value (`.env` defines `HOST`, `.env.local` uses `${HOST}`)
2. **Process environment** — the fallback for names no file defines
3. Unresolved references become `""` (python-dotenv semantics: `${VAR}` and `${VAR:-default}` are supported; `$VAR` shorthand is not interpolated)

```bash
# .env
HOST=db.internal

# .env.local
DATABASE_URL=postgres://${HOST}/app   # resolves to postgres://db.internal/app
```

Interpolation is independent of `override`: references resolve while the file layer is built, before the per-field precedence policy is applied — so `URL=http://${HOST}` from a file always interpolates against the file layer's `HOST`, even when the process environment wins the `HOST` field lookup itself.

Bare keys (a line with just `KEY`, no `=`) are left unset — python-dotenv's `load_dotenv()` skips them too, so a bare key never satisfies a field with an empty string.

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

Controls whether `.env` file values beat existing environment variables. The default is `False`: real environment variables take precedence over `.env` files — the convention used by pydantic-settings, dynaconf, django-environ, and the other settings libraries dotenvmodel surveyed.

```python
# Env vars take precedence over .env files (default)
config = AppConfig.load(override=False)

# Opt in: .env files override env vars
config = AppConfig.load(override=True)
```

| `override` | Behavior |
|------------|----------|
| `False` (default) | Existing environment variables take precedence over `.env` files |
| `True` | `.env` file values override existing environment variables |

!!! tip "When to use `override=True`"

    Use `override=True` when the `.env` files are the intended source of truth and the ambient environment is untrusted — for example, a developer laptop with stray exported variables. Containerized deployments that inject config via environment variables (12-factor) should keep the default.

### `DOTENV_OVERRIDE` Environment Variable

Flip precedence without code changes — useful as a migration escape hatch for code that depended on the old default:

```bash
export DOTENV_OVERRIDE=true
python your_app.py
```

An explicit `override=` argument always wins over `DOTENV_OVERRIDE`.

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

## The `read_dotfiles` Parameter

Set `read_dotfiles=False` to skip the `.env` cascade entirely: no files are probed, no "No .env files found" warning is logged, and a missing `env_dir` does not raise `FileNotFoundError`. Fields resolve from the process environment and field defaults only — and `override` has nothing to promote in this mode.

```python
# Resolve from real env vars and defaults only — no .env files touched
config = AppConfig.load(read_dotfiles=False)
```

This is the right mode for processes whose configuration is fully injected via environment variables (12-factor platforms, CI runners) and for avoiding surprises from a stray `.env` file in the working directory.

The `DOTENV_READ_DOTFILES=false` environment variable has the same effect; an explicit argument wins over the env var.

## The `load_local` Parameter

Controls whether the gitignored `.local` files (`.env.local` and `.env.{env}.local`) are read:

- `load_local=False` excludes them in **every** environment.
- The default includes them — **except** when the resolved environment is `test`, where they are skipped automatically. `.env.test` itself is still read. This matches the Next.js / dotenv-flow convention: tests should produce the same results for everyone, so a developer's gitignored `.env.test.local` must not decide test outcomes.

```python
# Tests: .env.local and .env.test.local are skipped by default
config = AppConfig.load(env="test")

# Opt back in (DOTENV_LOAD_LOCAL=true works too)
config = AppConfig.load(env="test", load_local=True)
```

!!! note "Non-test environments are unaffected"

    In `dev`, `prod`, `staging`, or any custom environment, `.local` files are read by default, exactly as before.

## Behavior Knobs: Argument > Environment Variable > Default

Every `load()` / `reload()` / `cached()` behavior knob resolves through the same three tiers — an explicit (non-`None`) argument wins, then a well-known environment variable, then the documented default:

| Behavior | Parameter | Env var | Default |
|---|---|---|---|
| Environment name | `env` | `ENV` | `"dev"` |
| Base directory | `env_dir` | `DOTENV_DIR` | current working directory |
| Read dotfiles at all | `read_dotfiles` | `DOTENV_READ_DOTFILES` | `True` |
| Dotfiles beat process env | `override` | `DOTENV_OVERRIDE` | `False` |
| Include `.local` files | `load_local` | `DOTENV_LOAD_LOCAL` | `True`, except `False` when env is `test` |

Boolean env vars parse case-insensitively (`true/1/yes/on` vs `false/0/no/off`). Any other value logs a warning naming the variable and falls back to the default — a stray env var never crashes a load.

The resolved values are recorded on the instance as a `LoadParams` (returned by `loaded_with()`), and they are exactly what a bare `reload()` repeats.

## Loading from a Dictionary

Use `load_from_dict()` for testing or when you have config values from a non-environment source. This bypasses `.env` file loading entirely.

```python
# Load from dictionary for testing
config = AppConfig.load_from_dict(
    {
        "DATABASE_URL": "postgresql://localhost/test",
        "API_KEY": "test-key",
        "DEBUG": "true",
        "PORT": "8000",
    }
)

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

By default, `reload()` reuses the same five resolved parameters (`env`, `override`, `env_dir`, `read_dotfiles`, `load_local`) recorded by the original `load()` call. Recorded values win over the `DOTENV_*` env-var tier, so a bare `reload()` never silently changes behavior — only the field *values* are re-read from the live environment and files:

```python
config = AppConfig.load(env="dev", override=True)
config.reload()  # Uses env="dev", override=True (and every other recorded parameter)
```

An instance loaded via `load_from_dict()` has nothing recorded; its `reload()` resolves all five parameters from the tiers.

### Overriding Parameters During Reload

You can override any parameter by passing new values:

```python
# Switch to production environment
config.reload(env="prod")

# Change override behavior
config.reload(override=False)

# Stop reading .env files from here on
config.reload(read_dotfiles=False)
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

Arguments (`env`, `override`, `env_dir`, `read_dotfiles`, `load_local`) are only used on the first call. Once the instance is cached, subsequent calls ignore any arguments and return the existing instance. A warning is logged when the caller's arguments *resolve* differently from the `LoadParams` the cached instance holds — so an accessor that consistently asks for what it already got (however it spells it) stays silent, while a caller asking for something the cache does not hold is told what it actually holds.

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

- [Loading API Reference](../api-reference/loading.md) — `read_env_files()`, `LoadParams`, `resolve_load_params()`, `get_env_var()`, `get_env_var_name()`
- [DotEnvConfig API Reference](../api-reference/config.md) — `load()`, `reload()`, `load_from_dict()`, `cached()`, `loaded_with()`, `reset_cached()`, `cached_override()`
- [Field Definitions](fields.md) — Defining config fields with `Field()`
- [Validation](validation.md) — Constraint validation
