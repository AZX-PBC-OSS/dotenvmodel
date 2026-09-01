# Loading Configuration

dotenvmodel provides flexible configuration loading from environment variables and `.env` files with Node.js-style cascading. This guide covers all loading methods and their parameters.

## Resolution Order

`load()` resolves each field across three layers, without ever mutating `os.environ`:

1. **Process environment** — real environment variables
2. **Merged dotfile cascade** — the `.env` files, merged with later files winning
3. **Field default** — the `Field(default=...)` value

By default (`override=False`), the process environment wins: a real `DATABASE_URL` beats whatever the `.env` files say. With `override=True` (or `DOTENV_OVERRIDE=true`), the merged dotfile layer wins instead. The first layer can also be turned off entirely — `read_environ=False` (or `DOTENV_READ_ENVIRON=false`) removes the process environment from the lookup (see [The `read_environ` Parameter](#the-read_environ-parameter)).

| Mode | Lookup order |
|------|--------------|
| `override=False` (default) | process env → dotfiles → field default |
| `override=True` | dotfiles → process env → field default |
| `read_environ=False` | dotfiles → field default |

The `.env` cascade is merged once per load (later, more specific files win within the file layer), and the override policy is applied once against the whole merged layer — the same model Vite and Next.js use.

!!! info "`load()` never mutates `os.environ`"

    Loading is a pure read: dotfile values resolve inside the config instance only and are never injected into the process environment. If another part of your process needs the values in `os.environ` (a library that reads the environment directly, for example), inject them yourself.

    With python-dotenv, under your own precedence policy:

    ```python
    from dotenv import load_dotenv

    load_dotenv("/app/config/.env", override=True)
    ```

    Or with `read_env_files()`, the pure reader that returns the merged cascade as a `DotenvLayer`:

    ```python
    from dotenvmodel import read_env_files

    os.environ.update(read_env_files(env="dev").values)
    ```

    Caution: `os.environ.update()` **overwrites** existing keys — the file values clobber the real environment. To inject while letting the real environment keep precedence, call python-dotenv's `load_dotenv()` without `override=True` instead.

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

`${VAR}` references inside `.env` values — and inside string field defaults — resolve through one implementation and one reference syntax; the two paths differ in what a reference can see:

1. **File values resolve progressively, in merged-key order** — a reference in a file value sees the keys defined earlier in the merged cascade, with their already-resolved values, over the process environment; a forward or self reference — to a key defined later in the merged order, or after it in the same file — sees only the process environment (python-dotenv semantics). Merged-key order follows first definition across the cascade, so a later file can still build on an earlier file's value (`.env` defines `HOST`, `.env.local` uses `${HOST}`)
2. **String defaults resolve against the fully merged cascade** — every key in the merged dotfile layer is visible to every reference in a default, over the process environment as the fallback
3. Unresolved references become `""` (python-dotenv semantics: `${VAR}` and `${VAR:-default}` are supported; `$VAR` shorthand is not interpolated)

File values resolve once, after the whole cascade is merged:

```bash
# .env
HOST=db.internal

# .env.local
DATABASE_URL=postgres://${HOST}/app   # resolves to postgres://db.internal/app
```

Interpolation is independent of `override`: references resolve while the file layer is built, before the per-field precedence policy is applied — so `URL=http://${HOST}` from a file always interpolates against the file layer's `HOST`, even when the process environment wins the `HOST` field lookup itself.

#### String Defaults Are Templates

A literal string default — `Field(default="${BASE_URL}/api")` or a bare class attribute (`api_url: str = "${BASE_URL}/api"`) — is a template too. When no layer provides the field's value, the default's references resolve at load time against the fully merged dotfile cascade over the process environment — every merged key is visible to every reference, with no merged-key ordering restriction (unlike file values, which resolve progressively) — and against the process environment alone when no dotfiles are read (`read_dotfiles=False`, or a `load_from_dict()` call). References resolve against dotfile values and environment variables, never against other fields' values or defaults. A reference names an absolute environment variable: `env_prefix` and `alias` govern the field's own lookup, never a reference inside the default — `${HOST}` on a class with `env_prefix = "APP_"` resolves `HOST`, while `${APP_HOST}` resolves `APP_HOST`. A `default_factory` result is built programmatically and is never interpolated.

```python
class AppConfig(DotEnvConfig):
    api_url: str = Field(default="${BASE_URL}/api")


# With BASE_URL=https://api.example.com in .env or the environment:
config = AppConfig.load(env="dev")
config.api_url  # "https://api.example.com/api"
```

Resolution re-runs on every `load()` / `reload()`, so a default picks up a changed environment. The resolved value then flows through the normal default machinery unchanged — a `str` default for a non-`str` field type is still coerced and validated (e.g. `"a,${REGION}"` for a `list[str]` field interpolates, then splits), and a `SecretStr` default stays masked in `repr` and errors.

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

!!! tip "Selecting the environment from your `.env` files"

    `env=` can itself be computed from the base files — read `ENV` from `.env` then `.env.local` with python-dotenv's `dotenv_values()` and pass the result to `load()`:

    ```python
    from dotenv import dotenv_values


    def env_from_base_files() -> str | None:
        for name in (".env", ".env.local"):
            value = dotenv_values(name).get("ENV")
            if value:
                return value
        return None


    config = AppConfig.load(env=env_from_base_files())
    ```

    `None` falls through to the `ENV` environment-variable tier, so a missing key behaves exactly like not passing `env=` at all. Precedence is the caller's choice in code: as written, the file wins; `os.getenv("ENV") or env_from_base_files()` flips it to process-wins. The selector runs before the load — in the knob channel, not the value channel — so it composes with `read_environ=False`, which excludes `os.environ` as a *value* source only. For per-directory environment exports without any code, [direnv](https://direnv.net/) is the ecosystem-standard tool.

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

Set `read_dotfiles=False` to skip the `.env` cascade entirely: no files are probed, no "No .env files found" warning is logged, and an unusable `env_dir` does not raise — neither `FileNotFoundError` for a missing directory nor `NotADirectoryError` for a path that isn't one. Fields resolve from the process environment and field defaults only — and `override` has nothing to promote in this mode.

```python
# Resolve from real env vars and defaults only — no .env files touched
config = AppConfig.load(read_dotfiles=False)
```

This is the right mode for processes whose configuration is fully injected via environment variables (12-factor platforms, CI runners) and for avoiding surprises from a stray `.env` file in the working directory.

The `DOTENV_READ_DOTFILES=false` environment variable has the same effect; an explicit argument wins over the env var.

## The `read_environ` Parameter

Set `read_environ=False` to exclude the process environment as a *value* source: fields resolve from the `.env` cascade and field defaults only — in both override modes, since with no process-env layer `override` becomes moot (there is nothing for it to promote or demote). The exclusion covers `${VAR}` interpolation too: both the file-value base and the string-default base resolve against the merged dotfile values alone, so a variable defined only in `os.environ` resolves to `""` (or its `:-` default), and a string default with no dotfile behind it resolves against an empty base.

```python
# The .env cascade is the only external source — ambient env vars are ignored
config = AppConfig.load(read_environ=False)
```

This is the mirror of `read_dotfiles=False` for the same problem from the other side: a developer laptop or CI runner with stray exported variables that silently beat the `.env` files. Use it when the `.env` files are the intended source of truth and the ambient environment is untrusted.

!!! note "The knob channel is unaffected"

    `read_environ=False` excludes `os.environ` as a *value* source only. The knobs themselves — `ENV`, `DOTENV_DIR`, `DOTENV_OVERRIDE`, `DOTENV_READ_DOTFILES`, `DOTENV_READ_ENVIRON`, `DOTENV_LOAD_LOCAL` — still resolve from the process environment, so the env-var tier keeps steering a `read_environ=False` load.

Both knobs can be combined: `load(read_dotfiles=False, read_environ=False)` is allowed and is the hermetic defaults-only mode — fields resolve from `Field(default=...)` values, required fields still raise `MissingFieldError`, and a string default's `${VAR}` references resolve against an empty base. `load_from_dict()` deliberately does not offer this mode; its template defaults resolve against the process environment (see [Loading from a Dictionary](#loading-from-a-dictionary)).

The `DOTENV_READ_ENVIRON=false` environment variable has the same effect; an explicit argument wins over the env var.

## The `load_local` Parameter

Controls whether the gitignored `.local` files (`.env.local` and `.env.{env}.local`) are read:

- `load_local=False` excludes them in **every** environment.
- The default includes them — **except** when the resolved environment is `test` (matched case-insensitively), where they are skipped automatically. `.env.test` itself is still read. This extends the Next.js / dotenv-flow rule, which skips only `.env.local` in test and still loads `.env.{env}.local` — dotenvmodel skips both, because a gitignored `.env.test.local` must not decide test outcomes either: tests should produce the same results for everyone.

```python
# Tests: .env.local and .env.test.local are skipped by default
config = AppConfig.load(env="test")

# Opt back in (DOTENV_LOAD_LOCAL=true works too)
config = AppConfig.load(env="test", load_local=True)
```

!!! note "Non-test environments are unaffected"

    In `dev`, `prod`, `staging`, or any custom environment, `.local` files are read by default, exactly as before.

## Behavior Knobs: Argument > Environment Variable > Default

A fresh `load()` — and the first, cache-cold `cached()` call — resolves every behavior knob through the same three tiers: an explicit (non-`None`) argument wins, then a well-known environment variable, then the documented default:

| Behavior | Parameter | Env var | Default |
|---|---|---|---|
| Environment name | `env` | `ENV` | `"dev"` |
| Base directory | `env_dir` | `DOTENV_DIR` | current working directory |
| Read dotfiles at all | `read_dotfiles` | `DOTENV_READ_DOTFILES` | `True` |
| Read the process environment | `read_environ` | `DOTENV_READ_ENVIRON` | `True` |
| Dotfiles beat process env | `override` | `DOTENV_OVERRIDE` | `False` |
| Include `.local` files | `load_local` | `DOTENV_LOAD_LOCAL` | `True`, except `False` when env is `test` |

Boolean env vars parse case-insensitively (`true/1/yes/on` vs `false/0/no/off`). Any other value logs a warning naming the variable and falls back to the default — a stray env var never crashes a load.

The resolved values are recorded on the instance as a `LoadParams` (returned by `loaded_with()`), and they are exactly what a bare `reload()` repeats.

Two paths deliberately deviate from the full tier walk: `reload()` on an instance that has recorded parameters substitutes the recorded values for the env-var tier (see [Reusing Original Parameters](#reusing-original-parameters)), and a warm `cached()` ignores its arguments entirely — it only warns when they resolve differently from the recorded `LoadParams`.

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

!!! note "No hermetic-template mode here"

    `load_from_dict()` has no `read_dotfiles` / `read_environ` knobs: its values come from the dict, and a string default's `${VAR}` template resolves against the process environment — documented behavior, unchanged. Callers wanting a hermetic template load (no dotfiles, no process environment in the interpolation base) should use `load(read_dotfiles=False, read_environ=False)` instead.

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

By default, `reload()` reuses the same six resolved parameters (`env`, `override`, `env_dir`, `read_dotfiles`, `read_environ`, `load_local`) recorded by the original `load()` call. Recorded values win over the `DOTENV_*` env-var tier, so a bare `reload()` never silently changes behavior — only the field *values* are re-read from the live environment and files:

```python
config = AppConfig.load(env="dev", override=True)
config.reload()  # Uses env="dev", override=True (and every other recorded parameter)
```

An instance loaded via `load_from_dict()` has nothing recorded; its `reload()` resolves all six parameters from the tiers.

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

Arguments (`env`, `override`, `env_dir`, `read_dotfiles`, `read_environ`, `load_local`) are only used on the first call. Once the instance is cached, subsequent calls ignore any arguments and return the existing instance. A warning is logged when the caller's arguments *resolve* differently from the `LoadParams` the cached instance holds — so an accessor that consistently asks for what it already got (however it spells it) stays silent, while a caller asking for something the cache does not hold is told what it actually holds.

Calling `.reload()` on the cached instance mutates it in place; since `cached()` always returns the same object, subsequent `cached()` calls see the reloaded values. A reload also updates what the instance reports as its load arguments, so `reload(env="prod")` is reflected by both `loaded_with()` and the comparison above.

!!! tip "Refreshing a `cached()` singleton on `SIGHUP`"

    A signal-style refresh of a cached singleton is one line — `reload()` refreshes the cached instance in place, so every holder of the `cached()` instance sees the new values:

    ```python
    AppConfig.cached().reload()
    ```

    Use `reset_cached()` followed by `cached()` when a fresh instance is wanted instead of an in-place refresh. A plain `load()` never reads or writes the cache — every `load()` call is a full fresh read — so code that mixes `load()` with `cached()` holds separate instances.

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
