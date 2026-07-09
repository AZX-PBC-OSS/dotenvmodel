# Complete Application Example

This page walks through a real-world application that uses multiple configuration
classes with different environment prefixes, rich field types, validation
constraints, aliases, runtime reload, and automatic `.env.example` generation.

---

## Configuration Classes

The application splits its configuration into three classes, each namespaced with
its own `env_prefix`:

| Class            | Prefix    | Reads variables like           |
| ---------------- | --------- | ------------------------------ |
| `DatabaseConfig` | `DB_`     | `DB_HOST`, `DB_PORT`, …        |
| `RedisConfig`    | `REDIS_`  | `REDIS_HOST`, `REDIS_PORT`, …  |
| `AppConfig`      | `APP_`    | `APP_NAME`, `APP_DEBUG`, …     |

!!! example "Full configuration module"

    Save this as `config.py` in your project:

    ```python
    from pathlib import Path

    from dotenvmodel import DotEnvConfig, Field
    from dotenvmodel.types import SecretStr


    class DatabaseConfig(DotEnvConfig):
        """PostgreSQL database configuration."""

        env_prefix = "DB_"  # Namespace all fields with DB_

        # str — required
        host: str = Field(description="Database host address")
        name: str = Field(description="Database name")

        # int with ge/le validation (closed range)
        port: int = Field(default=5432, ge=1, le=65535, description="Database port")
        pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")

        # float with gt validation (strictly positive)
        pool_timeout: float = Field(default=30.0, gt=0, description="Pool timeout in seconds")

        # bool with flexible parsing (true/1/yes/on …)
        echo: bool = Field(default=False, description="Echo SQL statements")

        # SecretStr — value is masked in repr and logs
        password: SecretStr = Field(description="Database password")

        # Alias overrides prefix: reads DATABASE_URL instead of DB_DATABASE_URL
        url: str = Field(alias="DATABASE_URL", description="Full connection URL (overrides prefix)")


    class RedisConfig(DotEnvConfig):
        """Redis cache configuration."""

        env_prefix = "REDIS_"  # Namespace all fields with REDIS_

        # str — required
        host: str = Field(description="Redis host address")

        # int with ge/le validation
        port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
        db: int = Field(default=0, ge=0, le=15, description="Redis database number")

        # Optional str (defaults to None when not set)
        password: str | None = Field(default=None, description="Redis password (optional)")

        # bool flag
        socket_keepalive: bool = Field(default=True, description="Enable TCP keepalive")


    class AppConfig(DotEnvConfig):
        """Application-level configuration."""

        env_prefix = "APP_"  # Namespace all fields with APP_

        # str with choices validation
        environment: str = Field(
            default="dev",
            choices=["dev", "test", "staging", "prod"],
            description="Deployment environment",
        )

        # bool flag
        debug: bool = Field(default=False, description="Enable debug mode")

        # SecretStr with min_length validation
        secret_key: SecretStr = Field(min_length=32, description="Session secret key")

        # int with ge/le (server port) and int with ge only (workers)
        host: str = Field(default="0.0.0.0", description="Server bind address")
        port: int = Field(default=8000, ge=1, le=65535, description="Server port")
        workers: int = Field(default=4, ge=1, description="Number of worker processes")

        # float with ge and le (bounded range)
        api_timeout: float = Field(default=30.0, ge=0.1, le=300.0, description="API timeout in seconds")

        # Alias overrides prefix: reads API_BASE_URL instead of APP_API_BASE_URL
        api_base_url: str = Field(alias="API_BASE_URL", description="External API base URL")

        # list[str] — comma-separated in the environment
        allowed_origins: list[str] = Field(default_factory=list, description="CORS allowed origins")

        # Path — automatically resolved (expanduser + resolve)
        upload_dir: Path = Field(default=Path("/tmp/uploads"), description="File upload directory")
    ```

---

## The `.env` File

With the configuration classes above, the corresponding `.env` file looks like
this:

!!! example "Corresponding `.env` file"

    ```bash
    # ── DatabaseConfig (prefix: DB_) ──────────────────────────────
    DB_HOST=localhost
    DB_NAME=myapp
    DB_PORT=5432
    DB_POOL_SIZE=10
    DB_POOL_TIMEOUT=30.0
    DB_ECHO=false
    DB_PASSWORD=super-secret-db-password
    # Alias — prefix is NOT applied:
    DATABASE_URL=postgresql://app:super-secret-db-password@localhost:5432/myapp

    # ── RedisConfig (prefix: REDIS_) ──────────────────────────────
    REDIS_HOST=localhost
    REDIS_PORT=6379
    REDIS_DB=0
    # REDIS_PASSWORD is optional (defaults to None)
    REDIS_SOCKET_KEEPALIVE=true

    # ── AppConfig (prefix: APP_) ──────────────────────────────────
    APP_ENVIRONMENT=dev
    APP_DEBUG=true
    APP_SECRET_KEY=change-me-this-must-be-at-least-32-chars
    APP_HOST=0.0.0.0
    APP_PORT=8000
    APP_WORKERS=4
    APP_API_TIMEOUT=30.0
    # Alias — prefix is NOT applied:
    API_BASE_URL=https://api.example.com/v1
    # list[str] — comma-separated:
    APP_ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
    APP_UPLOAD_DIR=/tmp/uploads
    ```

    !!! note "Alias behavior"
        Fields with an explicit `alias` read from the alias name **without** the
        class prefix applied. In the example above, `DatabaseConfig.url` reads
        `DATABASE_URL` (not `DB_DATABASE_URL`), and `AppConfig.api_base_url`
        reads `API_BASE_URL` (not `APP_API_BASE_URL`).

---

## Loading All Configurations

Each config class is loaded independently with its own `env` (which controls
`.env` file cascading):

```python
from config import AppConfig, DatabaseConfig, RedisConfig

# Load all configs for the "prod" environment.
# File cascade: .env → .env.local → .env.prod → .env.prod.local
db_config = DatabaseConfig.load(env="prod")
redis_config = RedisConfig.load(env="prod")
app_config = AppConfig.load(env="prod")

# Access typed values with full IntelliSense
print(app_config.host)              # '0.0.0.0'  (str)
print(app_config.port)              # 8000       (int)
print(app_config.debug)             # True       (bool)
print(db_config.password)           # SecretStr('**********')
print(db_config.password.get_secret_value())  # actual password
print(app_config.allowed_origins)   # ['http://localhost:3000', ...]
print(app_config.upload_dir)        # PosixPath('/tmp/uploads')
```

!!! tip "Loading order"
    The classes are independent — load them in any order. They read different
    environment variables thanks to their distinct `env_prefix` values, so there
    are no collisions even when all three are loaded in the same process.

---

## Hot-Reload with `reload()`

When environment variables change at runtime (for example after receiving a
`SIGHUP` signal), call `reload()` to refresh values **without** creating new
instances:

```python
import os
import signal

from config import AppConfig, DatabaseConfig, RedisConfig

# Initial load
app_config = AppConfig.load(env="dev")
print(app_config.port)  # 8000


def hot_reload(signum: int, frame: object) -> None:
    """Reload all configurations on SIGHUP."""
    db_config.reload()     # Reuses original env="dev"
    redis_config.reload()
    app_config.reload()
    print("Configuration reloaded")


signal.signal(signal.SIGHUP, hot_reload)


# You can also override parameters during reload:
# Switch to production environment on the fly
app_config.reload(env="prod")  # Now reads .env.prod files
print(app_config.port)  # value from .env.prod
```

!!! note "Thread safety"
    `reload()` is **not** thread-safe. In multi-threaded servers (FastAPI,
    gunicorn), call `load()` once at startup and share the immutable instance.
    If you must reload, use a lock or create a new instance via `load()`.

---

## Generating `.env.example` Files

Automatically generate a `.env.example` template that includes type
information, constraints, and helpful comments — ideal for onboarding new
developers:

```python
from config import AppConfig, DatabaseConfig, RedisConfig

# Generate a combined .env.example for all config classes
with open(".env.example", "w") as f:
    f.write("# Application Configuration\n")
    f.write("# Copy this file to .env and fill in the values\n\n")
    for config_cls in [DatabaseConfig, RedisConfig, AppConfig]:
        f.write(config_cls.generate_env_example())
        f.write("\n")

print("✓ .env.example generated")
```

!!! example "Generated `.env.example` output"

    ```bash
    # Configuration for DatabaseConfig
    # All variables prefixed with: DB_

    # Database host address
    # Type: str
    # Example: DB_HOST=your_value_here
    DB_HOST=

    # Database name
    # Type: str
    # Example: DB_NAME=your_value_here
    DB_NAME=

    # Database port
    # Type: int | Constraints: ge=1, le=65535
    # Example: DB_PORT=5432
    # DB_PORT=5432

    # Database password
    # Type: SecretStr
    # DB_PASSWORD=your_secret_here

    # Full connection URL (overrides prefix)
    # Type: str
    # Example: DATABASE_URL=your_value_here
    DATABASE_URL=

    # ... remaining fields omitted for brevity ...


    # Configuration for AppConfig
    # All variables prefixed with: APP_

    # Session secret key
    # Type: SecretStr | Constraints: min_length=32
    # APP_SECRET_KEY=your_secret_here

    # External API base URL
    # Type: str
    # Example: API_BASE_URL=your_value_here
    API_BASE_URL=

    # ... remaining fields omitted for brevity ...
    ```

---

## Documenting Multiple Configs

Use `describe_configs()` to generate a single document covering every
configuration class — perfect for wikis and README files:

```python
from dotenvmodel import describe_configs

from config import AppConfig, DatabaseConfig, RedisConfig

# Generate markdown documentation for all config classes
describe_configs(
    [DatabaseConfig, RedisConfig, AppConfig],
    output_format="markdown",
    output="docs/configuration.md",
)

# Or generate an HTML version for an internal wiki
describe_configs(
    [DatabaseConfig, RedisConfig, AppConfig],
    output_format="html",
    output="docs/configuration.html",
)
```

!!! tip "CI configuration validation"
    Use the JSON output format to check that every required variable is set
    before deployment:

    ```python
    import json
    import os
    import sys

    from config import AppConfig, DatabaseConfig, RedisConfig

    all_required: list[str] = []
    for cls in [DatabaseConfig, RedisConfig, AppConfig]:
        spec = json.loads(cls.describe(output_format="json"))
        all_required.extend(
            f["env_var"] for f in spec["fields"] if f["required"]
        )

    missing = [var for var in all_required if var not in os.environ]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    print("✓ All required environment variables are set")
    ```
