# Supported Types

dotenvmodel supports a wide range of Python types with automatic coercion from environment variable strings. This page covers every supported type with code examples and the expected environment variable format.

For the complete API reference, see [Types API](../api-reference/types.md).

---

## Basic Types

=== "String"

    ```python
    class Config(DotEnvConfig):
        name: str = Field()
    ```

    ```bash
    # .env
    NAME=myapp
    ```

    ```python
    config = Config.load()
    assert config.name == "myapp"
    ```

=== "Integer"

    ```python
    class Config(DotEnvConfig):
        port: int = Field(default=8000)
    ```

    ```bash
    # .env
    PORT=3000
    ```

    ```python
    config = Config.load()
    assert config.port == 3000  # int
    ```

=== "Float"

    ```python
    class Config(DotEnvConfig):
        timeout: float = Field(default=30.0)
    ```

    ```bash
    # .env
    TIMEOUT=60.5
    ```

    ```python
    config = Config.load()
    assert config.timeout == 60.5  # float
    ```

=== "Boolean"

    Booleans accept multiple string formats (case-insensitive):

    - **True:** `"true"`, `"1"`, `"yes"`, `"on"`, `"t"`, `"y"`
    - **False:** `"false"`, `"0"`, `"no"`, `"off"`, `"f"`, `"n"`, `""`

    ```python
    class Config(DotEnvConfig):
        debug: bool = Field(default=False)
    ```

    ```bash
    # .env
    DEBUG=true
    ```

    ```python
    config = Config.load()
    assert config.debug is True
    ```

=== "Path"

    `Path` fields are resolved by default (`expanduser` + `resolve`). Use `resolve_path=False` to keep raw paths.

    ```python
    from pathlib import Path

    class Config(DotEnvConfig):
        config_path: Path = Field(default=Path("/etc/app"))
        # Resolved: ~/logs -> /home/user/logs, ./output -> /cwd/output

        log_dir: Path = Field(resolve_path=False)  # raw, no resolution
    ```

    ```bash
    # .env
    CONFIG_PATH=/opt/myapp/config
    ```

    ```python
    config = Config.load()
    assert config.config_path == Path("/opt/myapp/config").resolve()
    ```

---

## Collection Types

Collection types are parsed from comma-separated strings by default. Use the `separator` parameter to change the delimiter.

=== "List"

    ```python
    class Config(DotEnvConfig):
        # List of strings
        hosts: list[str] = Field(default_factory=list)

        # List of integers
        ports: list[int] = Field(default_factory=list)

        # Custom separator
        tags: list[str] = Field(default_factory=list, separator=";")
    ```

    ```bash
    # .env
    HOSTS=localhost,example.com,*.example.com
    PORTS=8000,8001,8002
    TAGS=web;api;backend
    ```

    ```python
    config = Config.load()
    assert config.hosts == ["localhost", "example.com", "*.example.com"]
    assert config.ports == [8000, 8001, 8002]
    assert config.tags == ["web", "api", "backend"]
    ```

=== "Set"

    Sets automatically deduplicate values.

    ```python
    class Config(DotEnvConfig):
        roles: set[str] = Field(default_factory=set)
    ```

    ```bash
    # .env
    ROLES=admin,user,admin
    ```

    ```python
    config = Config.load()
    assert config.roles == {"admin", "user"}
    ```

=== "Tuple"

    ```python
    class Config(DotEnvConfig):
        coordinates: tuple[str, ...] = Field()
    ```

    ```bash
    # .env
    COORDINATES=x,y,z
    ```

    ```python
    config = Config.load()
    assert config.coordinates == ("x", "y", "z")
    ```

=== "Dictionary"

    Dicts use `key=value` pairs separated by the `separator` (default comma).

    ```python
    class Config(DotEnvConfig):
        headers: dict[str, str] = Field(default_factory=dict)
    ```

    ```bash
    # .env
    HEADERS=Content-Type=application/json,Accept=*/*
    ```

    ```python
    config = Config.load()
    assert config.headers == {"Content-Type": "application/json", "Accept": "*/*"}
    ```

!!! tip "Custom separators"
    If your values contain commas, use a different delimiter: `separator=";"`, `separator="|"`, etc. The separator applies to `list`, `set`, `tuple`, and `dict` types.

---

## Advanced Types

=== "UUID"

    ```python
    from uuid import UUID

    class Config(DotEnvConfig):
        tenant_id: UUID = Field()
    ```

    ```bash
    # .env
    TENANT_ID=550e8400-e29b-41d4-a716-446655440000
    ```

    ```python
    config = Config.load()
    assert config.tenant_id == UUID('550e8400-e29b-41d4-a716-446655440000')
    ```

    Use `uuid_version` to require a specific UUID version. See [Validation](validation.md#uuid-version).

=== "Decimal"

    Use `Decimal` for precise arithmetic (e.g., monetary values).

    ```python
    from decimal import Decimal

    class Config(DotEnvConfig):
        price: Decimal = Field()
        tax_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('1'))
    ```

    ```bash
    # .env
    PRICE=19.99
    TAX_RATE=0.0825
    ```

    ```python
    config = Config.load()
    assert config.price == Decimal('19.99')
    ```

=== "Datetime"

    `datetime` fields use ISO 8601 format.

    ```python
    from datetime import datetime

    class Config(DotEnvConfig):
        created_at: datetime = Field()
    ```

    ```bash
    # .env
    CREATED_AT=2025-01-15T10:30:00
    ```

    ```python
    config = Config.load()
    assert config.created_at == datetime(2025, 1, 15, 10, 30, 0)
    ```

=== "Timedelta"

    `timedelta` accepts human-readable duration strings.

    **Supported units (case-insensitive):** `ms`, `s`, `m`, `h`, `d`, `w`

    ```python
    from datetime import timedelta

    class Config(DotEnvConfig):
        cache_ttl: timedelta = Field()
    ```

    ```bash
    # .env — all of these produce timedelta(hours=1, minutes=30):
    CACHE_TTL=1h30m
    # or as plain seconds:
    CACHE_TTL=5400
    ```

    ```python
    config = Config.load()
    assert config.cache_ttl == timedelta(hours=1, minutes=30)
    ```

    !!! example "Duration formats"
        | Format | Meaning |
        |--------|---------|
        | `90` | 90 seconds |
        | `90s` | 90 seconds |
        | `1h30m` | 1 hour 30 minutes |
        | `2d` | 2 days |
        | `500ms` | 500 milliseconds |
        | `1w` | 1 week |
        | `1d2h30m` | 1 day 2 hours 30 minutes |

---

## Secret Types

### SecretStr

`SecretStr` hides sensitive values in logs and `repr` output. Use it for API keys, passwords, and tokens.

```python
from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr

class Config(DotEnvConfig):
    api_key: SecretStr = Field(min_length=32)
    password: SecretStr = Field()
```

```bash
# .env
API_KEY=super-secret-key-with-at-least-32-chars
PASSWORD=hunter2
```

```python
config = Config.load()
print(config.api_key)                       # SecretStr('**********')
print(repr(config.api_key))                 # "SecretStr('**********')"
print(config.api_key.get_secret_value())    # 'super-secret-key-with-at-least-32-chars'
```

!!! warning "SecretStr cannot be pickled"
    `SecretStr` prevents pickling for security reasons. Extract the value with `get_secret_value()` before serializing if needed.

---

## URL and DSN Types

URL/DSN types work like strings but validate the scheme and provide parsed components as properties. Import them from `dotenvmodel.types`.

=== "HttpUrl"

    Validates `http` and `https` URLs.

    ```python
    from dotenvmodel.types import HttpUrl

    class Config(DotEnvConfig):
        api_url: HttpUrl = Field()
    ```

    ```bash
    # .env
    API_URL=https://api.example.com/v1
    ```

    ```python
    config = Config.load()
    print(config.api_url)        # https://api.example.com/v1
    print(config.api_url.host)   # api.example.com
    print(config.api_url.port)   # None (no explicit port)
    print(config.api_url.path)   # /v1
    ```

=== "PostgresDsn"

    Validates PostgreSQL connection strings. Accepts `postgresql://` and `postgres://` schemes. Default port: `5432`.

    ```python
    from dotenvmodel.types import PostgresDsn

    class Config(DotEnvConfig):
        database_url: PostgresDsn = Field()
    ```

    ```bash
    # .env
    DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
    ```

    ```python
    config = Config.load()
    print(config.database_url.host)       # localhost
    print(config.database_url.port)       # 5432
    print(config.database_url.database)   # mydb
    print(config.database_url.username)   # user
    print(config.database_url.password)   # pass (URL-decoded)
    ```

=== "RedisDsn"

    Validates Redis connection strings. Accepts `redis://` and `rediss://` (SSL) schemes. Default port: `6379`.

    ```python
    from dotenvmodel.types import RedisDsn

    class Config(DotEnvConfig):
        redis_url: RedisDsn = Field()
    ```

    ```bash
    # .env
    REDIS_URL=redis://localhost:6379/0
    ```

    ```python
    config = Config.load()
    print(config.redis_url.host)        # localhost
    print(config.redis_url.port)        # 6379
    print(config.redis_url.database)    # 0
    ```

!!! info "Available properties"
    All DSN types inherit from `BaseDsn` and provide: `scheme`, `host`, `port`, `path`, `query`, `username`, `password`. `PostgresDsn` and `RedisDsn` add a `database` property.

---

## JSON Parsing

Use `Json[T]` to parse JSON strings into Python objects. The inner type parameter controls validation:

- `Json[dict]` — validates the parsed result is a dict
- `Json[list]` — validates the parsed result is a list
- Other inner types are accepted but not deeply validated

```python
from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import Json

class Config(DotEnvConfig):
    # JSON object
    feature_flags: Json[dict[str, bool]] = Field()

    # JSON array
    allowed_roles: Json[list[str]] = Field()

    # JSON without type validation
    raw_config: Json = Field()
```

```bash
# .env
FEATURE_FLAGS={"new_ui": true, "beta_api": false}
ALLOWED_ROLES=["admin", "user", "guest"]
RAW_CONFIG={"nested": {"value": 42}}
```

```python
config = Config.load()
assert config.feature_flags == {"new_ui": True, "beta_api": False}
assert config.allowed_roles == ["admin", "user", "guest"]
```

!!! tip "Json vs comma-separated lists"
    Use `Json[list[str]]` when values may contain commas or need complex structure. Use `list[str]` with `separator` for simple comma-separated values — it's lighter weight.

---

## Optional Types

Optional types automatically default to `None` if no explicit default is provided. Both modern union syntax (`str | None`) and `Optional[str]` from `typing` work.

```python
from typing import Optional

class Config(DotEnvConfig):
    # These automatically default to None — no need for default=None
    optional_value: str | None = Field()
    optional_port: int | None = Field()

    # Using Optional from typing also works
    optional_name: Optional[str] = Field()

    # You can still provide explicit defaults
    optional_with_default: str | None = Field(default="custom")
```

```python
config = Config.load()  # No env vars set
assert config.optional_value is None
assert config.optional_port is None
assert config.optional_name is None
assert config.optional_with_default == "custom"
```

!!! warning "Non-optional unions not supported"
    Types like `str | int` or `Union[str, int]` (without `None`) are **not** supported. Only optional unions work. Use a single type (typically `str`) and handle conversion in your application code.

---

## Enum Types

Enum fields are coerced by matching the environment variable string against enum member **values** (case-sensitive) or **names** (case-insensitive).

```python
from enum import Enum

class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class Config(DotEnvConfig):
    log_level: LogLevel = Field(default=LogLevel.INFO)
```

```bash
# .env — match by value (case-sensitive)
LOG_LEVEL=debug

# or match by name (case-insensitive)
LOG_LEVEL=DEBUG
```

```python
config = Config.load()
assert config.log_level == LogLevel.DEBUG
```

!!! tip "Enum in describe output"
    When you use `describe()` or `generate_env_example()`, enum types display their allowed values automatically (e.g., `LogLevel (debug, info, warning, error)`).

Optional enums also work:

```python
class Config(DotEnvConfig):
    log_level: LogLevel | None = Field(default=None)
```

---

## See Also

- [Field Definitions](fields.md) — how to define fields with `Field()`
- [Validation](validation.md) — constraints for all types
- [Types API](../api-reference/types.md) — auto-generated API reference
