# Field Definitions

Every configuration field in a `DotEnvConfig` subclass is declared with a type annotation and a `Field()` descriptor (or the `Required` sentinel). This page covers all the ways to define fields, set defaults, use aliases, and document your configuration.

For the complete API reference, see [Fields API](../api-reference/fields.md).

---

## The `Field()` Function

`Field()` returns a `FieldInfo` instance that the metaclass uses to discover and process your fields. It accepts a positional `default` argument plus keyword-only constraints and options.

```python
from dotenvmodel import DotEnvConfig, Field

class Config(DotEnvConfig):
    # Required field (no default)
    database_url: str = Field()

    # Optional with default
    debug: bool = Field(default=False)

    # With validation constraints
    port: int = Field(default=8000, ge=1, le=65535)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `default` | `Any` | Default value if the env var is not set. Use `...` (ellipsis) or omit for required fields. |
| `default_factory` | `Callable[[], Any] \| None` | Callable that returns a default value. Use for mutable defaults (`list`, `dict`, `set`). |
| `alias` | `str \| None` | Alternative environment variable name. Overrides `env_prefix`. |
| `description` | `str \| None` | Human-readable description shown in `describe()` output and `.env.example` files. |
| `ge` | `int \| float \| Decimal \| None` | Greater-than-or-equal (`>=`) constraint. |
| `le` | `int \| float \| Decimal \| None` | Less-than-or-equal (`<=`) constraint. |
| `gt` | `int \| float \| Decimal \| None` | Greater-than (`>`) constraint. |
| `lt` | `int \| float \| Decimal \| None` | Less-than (`<`) constraint. |
| `min_length` | `int \| None` | Minimum string length (inclusive). For `str` and `SecretStr`. |
| `max_length` | `int \| None` | Maximum string length (inclusive). For `str` and `SecretStr`. |
| `regex` | `str \| None` | Regular expression pattern the string must match. |
| `choices` | `list[Any] \| None` | List of allowed values (validated after type coercion). |
| `min_items` | `int \| None` | Minimum items in a collection (`list`, `set`, `tuple`, `dict`). |
| `max_items` | `int \| None` | Maximum items in a collection (`list`, `set`, `tuple`, `dict`). |
| `uuid_version` | `int \| None` | Required UUID version (`1`, `3`, `4`, or `5`). |
| `separator` | `str` | Delimiter for parsing `list`/`set`/`tuple`/`dict` from a string. Default: `","`. |
| `url_unquote` | `bool` | Whether to URL-unquote `SecretStr` values. Default: `True`. |
| `resolve_path` | `bool` | Whether to resolve `Path` values (`expanduser` + `resolve`). Default: `True`. |
| `require_exists` | `bool` | Whether a `Path` field must point to an existing path. Default: `False`. |

!!! info "Validation parameters"
    The validation parameters (`ge`, `le`, `gt`, `lt`, `min_length`, `max_length`, `regex`, `choices`, `min_items`, `max_items`, `uuid_version`) are documented in detail in the [Validation guide](validation.md).

---

## Required Fields

There are three equivalent ways to mark a field as required. All produce identical runtime behavior and have no type checker issues.

=== "`Field(...)` — Recommended"

    Pydantic-style ellipsis syntax. This is the recommended approach because it's consistent with Pydantic's API and makes it explicit that you're defining a field.

    ```python
    from dotenvmodel import DotEnvConfig, Field

    class Config(DotEnvConfig):
        api_key: str = Field(...)
        database_url: str = Field(...)
    ```

=== "`Field()` — No default"

    `Field()` with no arguments also marks a field as required.

    ```python
    from dotenvmodel import DotEnvConfig, Field

    class Config(DotEnvConfig):
        database_url: str = Field()
        api_key: str = Field()
    ```

=== "`Required` sentinel"

    The `Required` sentinel is an explicit alternative when a field has no constraints or defaults.

    ```python
    from dotenvmodel import DotEnvConfig, Required

    class Config(DotEnvConfig):
        database_url: str = Required
        api_key: str = Required
    ```

!!! tip "Which should I use?"
    We recommend **`Field(...)`** — it's consistent with Pydantic's API and makes it visually obvious that you're defining a field with no default. Use `Required` if you prefer the more declarative syntax for fields without constraints.

---

## Defaults

=== "`default` — Immutable values"

    Use `default` for immutable values like `str`, `int`, `float`, `bool`, and `None`.

    ```python
    class Config(DotEnvConfig):
        port: int = Field(default=8000)
        debug: bool = Field(default=False)
        host: str = Field(default="0.0.0.0")
        timeout: float | None = Field(default=None)
    ```

=== "`default_factory` — Mutable values"

    Use `default_factory` for mutable defaults like `list`, `dict`, and `set`. This avoids shared mutable state between config instances.

    ```python
    class Config(DotEnvConfig):
        # Correct — uses a factory to create a fresh list each time
        hosts: list[str] = Field(default_factory=list)
        tags: dict[str, str] = Field(default_factory=dict)
        roles: set[str] = Field(default_factory=set)

        # Wrong — mutable default, do NOT do this
        # bad_hosts: list[str] = Field(default=[])
    ```

!!! warning "Never use mutable defaults"
    Using `default=[]` or `default={}` shares the same object across all instances. Always use `default_factory=list` or `default_factory=dict` instead. `Field()` raises a `ValueError` if you specify both `default` and `default_factory`.

---

## Aliases

Use `alias` to read from a different environment variable name than the field name. When `alias` is set, `env_prefix` is **not** applied — the alias is absolute.

```python
class Config(DotEnvConfig):
    env_prefix = "APP_"

    # Field name: postgres_dsn
    # Reads from: DATABASE_URL (alias is absolute, no prefix applied)
    postgres_dsn: str = Field(alias="DATABASE_URL")

    # Field name: api_token
    # Reads from: SECRET_TOKEN (alias is absolute)
    api_token: str = Field(alias="SECRET_TOKEN")

    # Field name: name
    # Reads from: APP_NAME (prefix applied, no alias)
    name: str = Field()
```

!!! note "Aliases override prefixes"
    When you set an `alias`, the `env_prefix` on the class is **not** applied to that field. See the [Environment Prefixes guide](prefixes.md) for full details on prefix and alias interaction.

---

## Descriptions

Add a `description` to document your fields. Descriptions appear in `describe()` output and generated `.env.example` files, making them valuable for team documentation and onboarding.

```python
class Config(DotEnvConfig):
    timeout: float = Field(
        default=30.0,
        ge=0.1,
        description="API request timeout in seconds",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port number",
    )
    database_password: SecretStr = Field(
        default=SecretStr("change_me_in_production"),
        min_length=8,
        description="Database connection password",
    )
```

See the [Configuration Documentation guide](configuration-docs.md) for examples of how descriptions appear in generated output.

---

## Path Options

Two parameters control `Path` field behavior:

```python
from pathlib import Path

class Config(DotEnvConfig):
    # Resolved by default (expanduser + resolve)
    # ~/logs becomes /home/user/logs
    # ./output becomes /cwd/output
    log_dir: Path = Field(default=Path("/var/log/app"))

    # Keep paths raw (no resolution)
    raw_path: Path = Field(resolve_path=False)

    # Require the path to exist
    config_file: Path = Field(require_exists=True)
```

---

## See Also

- [Supported Types](types.md) — all types you can use with `Field()`
- [Validation](validation.md) — detailed constraint reference
- [Environment Prefixes](prefixes.md) — how `env_prefix` interacts with `alias`
- [Fields API](../api-reference/fields.md) — auto-generated API reference
