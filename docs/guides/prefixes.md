# Environment Prefixes

Use class-level `env_prefix` to namespace environment variables and avoid collisions when multiple config classes read from the same environment.

## Basic Usage

Set `env_prefix` as a class attribute on your `DotEnvConfig` subclass. All field environment variables will be prefixed with this value.

```python
from dotenvmodel import DotEnvConfig, Field

class DatabaseConfig(DotEnvConfig):
    env_prefix = "DB_"  # All fields will be prefixed with DB_
    host: str = Field()
    port: int = Field(default=5432)
    name: str = Field()

# Reads DB_HOST, DB_PORT, DB_NAME from environment
config = DatabaseConfig.load_from_dict({
    "DB_HOST": "localhost",
    "DB_PORT": "5433",
    "DB_NAME": "myapp"
})
```

## Automatic Uppercasing

Field names are automatically uppercased and prefixed. You don't need to use uppercase in your Python field names:

| Field Name | `env_prefix` | Environment Variable |
|------------|-------------|---------------------|
| `host` | `"DB_"` | `DB_HOST` |
| `port` | `"DB_"` | `DB_PORT` |
| `database_url` | `"APP_"` | `APP_DATABASE_URL` |
| `host` | `""` (none) | `HOST` |

## Aliases Override Prefixes

When you use `alias`, the prefix is **not** applied. Aliases are absolute — they specify the exact environment variable name.

```python
class Config(DotEnvConfig):
    env_prefix = "APP_"

    # Uses alias exactly — reads DATABASE_URL (no prefix)
    db_url: str = Field(alias="DATABASE_URL")

    # No alias — reads APP_API_KEY (with prefix)
    api_key: str = Field()
```

| Field | Alias | `env_prefix` | Environment Variable |
|-------|-------|-------------|---------------------|
| `db_url` | `"DATABASE_URL"` | `"APP_"` | `DATABASE_URL` |
| `api_key` | None | `"APP_"` | `APP_API_KEY` |
| `host` | None | `"DB_"` | `DB_HOST` |
| `host` | None | `""` (none) | `HOST` |

!!! tip "When to use aliases with prefixes"

    Use aliases when a convention or external tool expects a specific environment variable name that doesn't fit your prefix scheme. For example, many tools expect `DATABASE_URL` — use `alias="DATABASE_URL"` even if your config uses `APP_` prefix.

## No Prefix by Default

If `env_prefix` is not set, no prefix is applied:

```python
class Config(DotEnvConfig):
    # No env_prefix defined
    host: str = Field()  # Reads HOST
    port: int = Field(default=8000)  # Reads PORT
```

## Multiple Config Classes

Prefixes shine when you have multiple config classes in the same application. Each class gets its own namespace:

```python
class DatabaseConfig(DotEnvConfig):
    env_prefix = "DB_"
    host: str = Field()
    port: int = Field(default=5432)

class RedisConfig(DotEnvConfig):
    env_prefix = "REDIS_"
    host: str = Field()
    port: int = Field(default=6379)

class AppConfig(DotEnvConfig):
    env_prefix = "APP_"
    name: str = Field()
    version: str = Field()

# Each config reads its own prefixed variables
db = DatabaseConfig.load()      # Reads DB_HOST, DB_PORT
redis = RedisConfig.load()      # Reads REDIS_HOST, REDIS_PORT
app = AppConfig.load()          # Reads APP_NAME, APP_VERSION
```

### Complete Multi-Config Example

```python
from pathlib import Path
from dotenvmodel import DotEnvConfig, Field

class DatabaseConfig(DotEnvConfig):
    env_prefix = "DB_"
    host: str = Field()
    port: int = Field(default=5432)
    name: str = Field()
    pool_size: int = Field(default=10, ge=1, le=100)

class RedisConfig(DotEnvConfig):
    env_prefix = "REDIS_"
    host: str = Field()
    port: int = Field(default=6379)
    password: str | None = Field(default=None)
    db: int = Field(default=0, ge=0, le=15)

class AppConfig(DotEnvConfig):
    env_prefix = "APP_"
    environment: str = Field(
        default="dev",
        choices=["dev", "test", "staging", "prod"]
    )
    debug: bool = Field(default=False)
    secret_key: str = Field(min_length=32)

    # External service using alias to override prefix
    api_base_url: str = Field(alias="API_BASE_URL")

    # Regular prefixed field
    port: int = Field(default=8000, ge=1, le=65535)

# Load all configs
# DatabaseConfig reads: DB_HOST, DB_PORT, DB_NAME, DB_POOL_SIZE
# RedisConfig reads: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB
# AppConfig reads: APP_ENVIRONMENT, APP_DEBUG, APP_SECRET_KEY, API_BASE_URL (alias), APP_PORT
db_config = DatabaseConfig.load(env="prod")
redis_config = RedisConfig.load(env="prod")
app_config = AppConfig.load(env="prod")
```

!!! note "Prefix and describe()"

    When you use `describe()` or `generate_env_example()`, the output shows the prefixed environment variable names, making it easy for developers to know exactly what to set.

## See Also

- [DotEnvConfig API Reference](../api-reference/config.md) — `env_prefix` attribute, `load()`, `load_from_dict()`
- [Field Definitions](fields.md) — `Field()` and `alias` parameter
- [Configuration Documentation](configuration-docs.md) — `describe()` shows prefixed env var names
