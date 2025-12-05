# dotenvmodel

> Type-safe environment configuration with automatic .env file loading

**dotenvmodel** is a Python library that provides type-safe environment configuration with automatic `.env` file loading. It combines the familiar developer experience of Pydantic-style field definitions with intelligent `.env` file cascading inspired by Node.js dotenv patterns.

## Features

- **Minimal Dependencies**: Only requires `python-dotenv`
- **Type Safety**: Full type hint support with automatic type coercion
- **Rich Type Support**: UUID, Decimal, datetime, timedelta, SecretStr, HttpUrl, PostgresDsn, RedisDsn, Json[T], and more
- **Developer Experience**: Intuitive Pydantic-style API
- **Smart .env Loading**: Automatic cascading of `.env`, `.env.{env}`, `.env.{env}.local` files
- **Configuration Reload**: Reload configuration at runtime without creating new instances
- **Configuration Documentation**: Generate docs in multiple formats (table, markdown, JSON, HTML, dotenv) with `describe()`
- **.env.example Generation**: Automatically generate `.env.example` files with type hints, constraints, and examples
- **File Export**: Save documentation directly to files for integration with build tools and wikis
- **Environment Prefixes**: Class-level `env_prefix` to namespace environment variables
- **Validation**: Numeric constraints (ge, le, gt, lt), string constraints (min_length, max_length, regex), choice validation, and collection size constraints (min_items, max_items)
- **Clear Error Messages**: Helpful validation errors that guide you to fixes
- **Optional Logging**: Built-in logging support to debug configuration loading
- **Zero Runtime Overhead**: All validation happens at startup/load time

## Installation

```bash
pip install dotenvmodel
```

Or with uv:

```bash
uv add dotenvmodel
```

## Quick Start

```python
from dotenvmodel import DotEnvConfig, Field

class AppConfig(DotEnvConfig):
    # Required fields (Pydantic-style)
    database_url: str = Field(...)
    api_key: str = Field(...)

    # Optional with defaults
    debug: bool = Field(default=False)
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=16)

    # Collection types
    allowed_hosts: list[str] = Field(default_factory=list)

# Load configuration from .env files
config = AppConfig.load(env="dev")

# Access configuration with full type safety and IntelliSense
print(f"Connecting to {config.database_url}")  # config.database_url: str
print(f"Running on port {config.port}")        # config.port: int
print(f"Debug mode: {config.debug}")           # config.debug: bool

# Generate documentation for your configuration
print(AppConfig.describe())
```

## Type Safety and IntelliSense

**dotenvmodel provides full type safety** - your IDE and type checkers (mypy, pyright) understand the types of your configuration fields:

```python
class AppConfig(DotEnvConfig):
    database_url: str = Field()
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

config = AppConfig.load()

# ✅ Type checkers know these types:
db_url: str = config.database_url      # ✅ Correct: str = str
port_num: int = config.port            # ✅ Correct: int = int
is_debug: bool = config.debug          # ✅ Correct: bool = bool

# ❌ Type checker errors:
wrong: int = config.database_url       # ❌ Error: str is not compatible with int
wrong: str = config.debug              # ❌ Error: bool is not compatible with str
```

Your IDE will provide:

- **Autocomplete** for all config fields
- **Type hints** showing field types
- **Error detection** for type mismatches
- **Go to definition** support

## Supported Types

### Basic Types

**String**
```python
class Config(DotEnvConfig):
    name: str = Field()
    # Environment: NAME=myapp
    # Result: config.name == "myapp"
```

**Integer**
```python
class Config(DotEnvConfig):
    port: int = Field(default=8000)
    # Environment: PORT=3000
    # Result: config.port == 3000 (int)
```

**Float**
```python
class Config(DotEnvConfig):
    timeout: float = Field(default=30.0)
    # Environment: TIMEOUT=60.5
    # Result: config.timeout == 60.5 (float)
```

**Boolean**

Supports multiple formats for true/false values:

```python
class Config(DotEnvConfig):
    debug: bool = Field(default=False)

# True values: "true", "1", "yes", "on", "t", "y" (case-insensitive)
# False values: "false", "0", "no", "off", "f", "n", "" (case-insensitive)
```

**Path**
```python
from pathlib import Path

class Config(DotEnvConfig):
    config_path: Path = Field(default=Path("/etc/app"))
    # Environment: CONFIG_PATH=/opt/myapp/config
    # Result: config.config_path == Path("/opt/myapp/config")
```

### Collection Types

**List**
```python
class Config(DotEnvConfig):
    # List of strings
    hosts: list[str] = Field(default_factory=list)
    # Environment: HOSTS=localhost,example.com,*.example.com
    # Result: config.hosts == ["localhost", "example.com", "*.example.com"]

    # List of integers
    ports: list[int] = Field(default_factory=list)
    # Environment: PORTS=8000,8001,8002
    # Result: config.ports == [8000, 8001, 8002]

    # Custom separator
    tags: list[str] = Field(default_factory=list, separator=";")
    # Environment: TAGS=web;api;backend
    # Result: config.tags == ["web", "api", "backend"]
```

**Set**
```python
class Config(DotEnvConfig):
    roles: set[str] = Field(default_factory=set)
    # Environment: ROLES=admin,user,admin
    # Result: config.roles == {"admin", "user"}
```

**Tuple**
```python
class Config(DotEnvConfig):
    coordinates: tuple[str, ...] = Field()
    # Environment: COORDINATES=x,y,z
    # Result: config.coordinates == ("x", "y", "z")
```

**Dictionary**
```python
class Config(DotEnvConfig):
    headers: dict[str, str] = Field(default_factory=dict)
    # Environment: HEADERS=Content-Type=application/json,Accept=*/*
    # Result: config.headers == {"Content-Type": "application/json", "Accept": "*/*"}
```

### Advanced Types

**UUID**
```python
from uuid import UUID

class Config(DotEnvConfig):
    tenant_id: UUID = Field()
    # Environment: TENANT_ID=550e8400-e29b-41d4-a716-446655440000
    # Result: config.tenant_id == UUID('550e8400-e29b-41d4-a716-446655440000')
```

**Decimal (for precise arithmetic)**
```python
from decimal import Decimal

class Config(DotEnvConfig):
    price: Decimal = Field()
    tax_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('1'))
    # Environment: PRICE=19.99, TAX_RATE=0.0825
    # Result: config.price == Decimal('19.99')
```

**Datetime and Timedelta**
```python
from datetime import datetime, timedelta

class Config(DotEnvConfig):
    created_at: datetime = Field()
    # Environment: CREATED_AT=2025-01-15T10:30:00
    # Result: config.created_at == datetime(2025, 1, 15, 10, 30, 0)

    cache_ttl: timedelta = Field()
    # Environment: CACHE_TTL=1h30m  (or: 5400 for seconds)
    # Result: config.cache_ttl == timedelta(hours=1, minutes=30)
    # Supports: ms, s, m, h, d, w
```

**SecretStr (hide sensitive data)**
```python
from dotenvmodel.types import SecretStr

class Config(DotEnvConfig):
    api_key: SecretStr = Field(min_length=32)
    password: SecretStr = Field()
    # Hides value in logs and repr

config = Config.load()
print(config.api_key)  # SecretStr('**********')
print(config.api_key.get_secret_value())  # 'actual-secret-key'
```

**URL and DSN Types**
```python
from dotenvmodel.types import HttpUrl, PostgresDsn, RedisDsn

class Config(DotEnvConfig):
    api_url: HttpUrl = Field()
    # Environment: API_URL=https://api.example.com/v1
    # Validates scheme, provides parsed components

    database_url: PostgresDsn = Field()
    # Environment: DATABASE_URL=postgresql://user:pass@localhost:5432/db

    redis_url: RedisDsn = Field()
    # Environment: REDIS_URL=redis://localhost:6379/0

# URL types work like strings but provide properties:
config = Config.load()
print(config.api_url.host)      # 'api.example.com'
print(config.api_url.port)      # 443
print(config.database_url.database)  # 'db'
print(config.redis_url.database)     # 0
```

**JSON Parsing**
```python
from dotenvmodel.types import Json

class Config(DotEnvConfig):
    feature_flags: Json[dict[str, bool]] = Field()
    # Environment: FEATURE_FLAGS={"new_ui": true, "beta_api": false}

    allowed_roles: Json[list[str]] = Field()
    # Environment: ALLOWED_ROLES=["admin", "user", "guest"]

config = Config.load()
assert config.feature_flags == {"new_ui": True, "beta_api": False}
```

### Optional Types

Optional types automatically default to `None` if no explicit default is provided:

```python
from typing import Optional

class Config(DotEnvConfig):
    # These automatically default to None (no need for explicit default=None)
    optional_value: str | None = Field()
    optional_port: int | None = Field()

    # Using Optional from typing also works
    optional_name: Optional[str] = Field()

    # You can still provide explicit defaults if needed
    optional_with_default: str | None = Field(default="custom")
```

## Field Definitions

### Defining Required Fields

```python
from dotenvmodel import DotEnvConfig, Field, Required

class Config(DotEnvConfig):
    # Method 1: Pydantic-style Field(...) - Recommended
    api_key: str = Field(...)

    # Method 2: Field() with no default - Also works
    database_url: str = Field()

    # Method 3: Required sentinel - Alternative
    secret: str = Required
```

All three methods work identically at runtime and have no type checker issues. We recommend **`Field(...)`** as it's consistent with Pydantic's API and makes it explicit that you're defining a field.

### Optional Fields with Defaults

```python
class Config(DotEnvConfig):
    # Simple default
    port: int = Field(default=8000)

    # Default factory for mutable defaults
    hosts: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
```

### Field Aliases

Use a different environment variable name than the field name:

```python
class Config(DotEnvConfig):
    # Field name: postgres_dsn
    # Environment variable: DATABASE_URL
    postgres_dsn: str = Field(alias="DATABASE_URL")

    # Field name: api_token
    # Environment variable: SECRET_TOKEN
    api_token: str = Field(alias="SECRET_TOKEN")
```

### Field Descriptions

Document your fields for better maintainability:

```python
class Config(DotEnvConfig):
    timeout: float = Field(
        default=30.0,
        description="Request timeout in seconds"
    )
```

## Validation

### Numeric Validation

```python
class Config(DotEnvConfig):
    # Greater than or equal (>=)
    min_connections: int = Field(ge=1)

    # Less than or equal (<=)
    max_connections: int = Field(le=100)

    # Greater than (>)
    timeout: float = Field(gt=0)

    # Less than (<)
    percentage: float = Field(lt=100.0)

    # Combined constraints
    port: int = Field(default=8000, ge=1, le=65535)
    pool_size: int = Field(default=10, ge=1, le=100)
```

### String Validation

```python
class Config(DotEnvConfig):
    # Minimum length
    api_key: str = Field(min_length=32)

    # Maximum length
    username: str = Field(max_length=20)

    # Regex pattern
    email: str = Field(regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')

    # Combined constraints
    password: str = Field(
        min_length=8,
        max_length=128,
        regex=r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).+$'
    )
```

### Choice Validation

```python
class Config(DotEnvConfig):
    # Must be one of the specified values
    environment: str = Field(
        default="dev",
        choices=["dev", "test", "staging", "prod"]
    )

    log_level: str = Field(
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
```

## Loading Configuration

### From Environment Variables

```python
# Load from environment and .env files
config = AppConfig.load()

# Specify environment explicitly
config = AppConfig.load(env="prod")

# Override behavior
config = AppConfig.load(override=True)   # .env files override env vars (default)
config = AppConfig.load(override=False)  # Env vars take precedence

# Custom .env file directory
from pathlib import Path
config = AppConfig.load(env_dir=Path("/app/config"))
```

### .env File Cascading

Files are loaded in order (later files override earlier ones):

1. `.env` - Base configuration (usually gitignored)
2. `.env.local` - Local base overrides (gitignored, never committed)
3. `.env.{env}` - Environment-specific (committed to repo)
4. `.env.{env}.local` - Local environment overrides (gitignored, never committed)

**Example:**

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
# Loads in order: .env → .env.local → .env.dev → .env.dev.local
# Final DATABASE_URL: postgresql://localhost/myapp_local (from .env.local)
# Final DEBUG: true (from .env.dev)
# Final ENABLE_PROFILING: true (from .env.dev.local)
```

### From Dictionary (Testing)

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

## Logging

dotenvmodel includes optional logging to help debug configuration issues. Logging is disabled by default but can be easily enabled.

### Enable Logging

```python
from dotenvmodel import configure_logging, DotEnvConfig, Field

# Enable INFO level logging
configure_logging("INFO")

class Config(DotEnvConfig):
    database_url: str = Field()

config = Config.load()
```

### Logging Output Example

```
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading Config configuration
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading configuration for environment: dev
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading environment variables from .env
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading environment variables from .env.dev
2025-12-05 00:33:40 - dotenvmodel - INFO - Successfully loaded 2 file(s): .env, .env.dev
2025-12-05 00:33:40 - dotenvmodel - INFO - Config configuration loaded successfully
```

### Log Levels

```python
# DEBUG - Most verbose, shows all operations
configure_logging("DEBUG")

# INFO - Shows file loading and configuration status
configure_logging("INFO")

# WARNING - Only shows warnings (e.g., missing files)
configure_logging("WARNING")

# ERROR - Only shows errors
configure_logging("ERROR")
```

### Using Environment Variable

```bash
# Set via environment variable
export DOTENVMODEL_LOG_LEVEL=DEBUG
python your_app.py
```

### Disable Logging

```python
from dotenvmodel import disable_logging

disable_logging()
```

### Custom Logging Configuration

```python
import logging
from dotenvmodel import configure_logging

# Use custom format
configure_logging(
    "INFO",
    format_string="[%(levelname)s] %(message)s"
)

# Or configure directly with standard logging
logger = logging.getLogger("dotenvmodel")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
```

## Configuration Methods

### Access as Dictionary

```python
config = AppConfig.load()
config_dict = config.dict()
# {'database_url': 'postgresql://...', 'debug': True, 'port': 8000}
```

### Get Method with Default

```python
config = AppConfig.load()
timeout = config.get('timeout', 30)  # Returns 30 if timeout not set
```

### String Representation

```python
config = AppConfig.load()
print(repr(config))
# AppConfig(database_url='postgresql://...', debug=True, port=8000)
```

### Reload Configuration

Reload configuration from environment variables without creating a new instance:

```python
# Load initial configuration
config = AppConfig.load(env="dev")
print(config.port)  # 8000

# Later, when environment variables change...
os.environ["PORT"] = "9000"

# Reload the configuration
config.reload()
print(config.port)  # 9000

# Reload reuses the original parameters by default
config = AppConfig.load(env="dev", override=True)
config.reload()  # Uses env="dev", override=True

# Override any parameter during reload
config.reload(env="prod")  # Switch to production environment
```

The `reload()` method:

- Reloads all fields from environment variables and .env files
- By default, reuses the same `env`, `override`, and `env_dir` parameters from the original `load()` call
- Allows overriding any parameter by passing new values
- Validates all fields and raises errors if validation fails
- Returns the same instance (useful for method chaining)

## Configuration Documentation

Generate human-readable documentation for your configuration classes using the `describe()` method. This is useful for:

- **Creating documentation** for your team
- **Generating `.env.example` files** automatically
- **Validating configuration** in CI pipelines
- **Onboarding new developers** quickly

### Generate Documentation for a Single Config

```python
from dotenvmodel import DotEnvConfig, Field

class AppConfig(DotEnvConfig):
    database_url: str = Field(description="PostgreSQL connection string")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    workers: int = Field(default=4, ge=1, le=16, description="Number of worker processes")

# Generate ASCII table (default)
print(AppConfig.describe())
```

Output:

```
AppConfig
=========
+--------------+------+----------+---------+---------------------------+----------------+
| ENV Variable | Type | Required | Default | Description               | Constraints    |
+--------------+------+----------+---------+---------------------------+----------------+
| DATABASE_URL | str  | Yes      | -       | PostgreSQL connection ... | -              |
| PORT         | int  | No       | 8000    | Server port               | ge=1, le=65535 |
| DEBUG        | bool | No       | False   | Enable debug mode         | -              |
| WORKERS      | int  | No       | 4       | Number of worker proces...| ge=1, le=16    |
+--------------+------+----------+---------+---------------------------+----------------+
```

### Output Formats

**ASCII Table (default)** - Best for terminal output and logging:

```python
print(AppConfig.describe(output_format="table"))
```

**Markdown** - Perfect for README files and documentation:

```python
# Generate markdown documentation
docs = AppConfig.describe(output_format="markdown")

# Save to file
with open("CONFIG.md", "w") as f:
    f.write(docs)
```

**JSON** - Ideal for CI validation and programmatic processing:

```python
import json

# Get configuration schema as JSON
config_spec = AppConfig.describe(output_format="json")
data = json.loads(config_spec)

# Use for validation, code generation, etc.
print(data["class_name"])  # "AppConfig"
print(data["fields"][0]["env_var"])  # "DATABASE_URL"
```

**HTML** - Styled output for web documentation:

```python
# Generate HTML with styled tables
html_docs = AppConfig.describe(output_format="html")

# Save to file
with open("config.html", "w") as f:
    f.write(html_docs)
```

**Dotenv Format** - For generating `.env.example` files:

```python
# Generate .env.example format
dotenv_docs = AppConfig.describe(output_format="dotenv")
print(dotenv_docs)
```

### File Export

Save documentation directly to files using the `output` parameter:

```python
# Save as markdown
AppConfig.describe(output_format="markdown", output="docs/config.md")

# Save as HTML
AppConfig.describe(output_format="html", output="docs/config.html")

# Save as JSON
AppConfig.describe(output_format="json", output="config-schema.json")
```

### Generate `.env.example` Files

Automatically generate `.env.example` files for onboarding new developers:

```python
from dotenvmodel import DotEnvConfig, Field, SecretStr

class AppConfig(DotEnvConfig):
    env_prefix = "APP_"

    api_key: str = Field(
        min_length=32,
        max_length=64,
        description="API key for external service"
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port number"
    )
    database_password: SecretStr = Field(
        default=SecretStr("change_me_in_production"),
        min_length=8,
        description="Database connection password"
    )
    allowed_hosts: list[str] = Field(
        default_factory=list,
        separator=";",
        min_items=1,
        max_items=10,
        description="Allowed hostnames for CORS"
    )

# Generate and print .env.example
print(AppConfig.generate_env_example())

# Or save directly to file
AppConfig.generate_env_example(output=".env.example")
```

Output in `.env.example`:

```bash
# Configuration for AppConfig
# All variables prefixed with: APP_

# API key for external service
# Type: str | Constraints: min_length=32, max_length=64
# Example: APP_API_KEY=your_value_here
APP_API_KEY=

# Server port number
# Type: int | Constraints: ge=1, le=65535
# Example: APP_PORT=8000
# APP_PORT=8000

# Database connection password
# Type: SecretStr | Constraints: min_length=8
# APP_DATABASE_PASSWORD=your_secret_here

# Allowed hostnames for CORS
# Type: list[str] | Constraints: min_items=1, max_items=10, separator=';'
# Example: APP_ALLOWED_HOSTS=[]
# APP_ALLOWED_HOSTS=[]
```

The `.env.example` file includes:

- **Type information** - Shows the expected Python type
- **Parsing hints** - Explains how to format complex types (e.g., "comma-separated values" for lists)
- **Constraints** - Documents validation rules (min/max length, numeric ranges, etc.)
- **Examples** - Shows example values for required fields
- **Commented defaults** - Optional fields are commented out with their default values
- **Secret handling** - SecretStr fields are masked appropriately

### Document Multiple Configurations

Use `describe_configs()` to document multiple related configuration classes:

```python
from dotenvmodel import DotEnvConfig, Field, describe_configs

class DatabaseConfig(DotEnvConfig):
    env_prefix = "DB_"
    host: str = Field(description="Database host")
    port: int = Field(default=5432, description="Database port")

class RedisConfig(DotEnvConfig):
    env_prefix = "REDIS_"
    host: str = Field(description="Redis host")
    port: int = Field(default=6379, description="Redis port")

# Generate documentation for all configs
all_docs = describe_configs([DatabaseConfig, RedisConfig], output_format="markdown")
print(all_docs)
```

### Practical Use Cases

**1. Generate `.env.example` files for onboarding:**

```python
# Generate .env.example with helpful comments and type information
AppConfig.generate_env_example(output=".env.example")

# Or combine multiple configs
from dotenvmodel import describe_configs

with open(".env.example", "w") as f:
    f.write("# Application Configuration\n\n")
    f.write("# Copy this file to .env and fill in the values\n\n")
    for config_cls in [AppConfig, DatabaseConfig, RedisConfig]:
        f.write(config_cls.generate_env_example())
        f.write("\n\n")
```

**2. CI Configuration Validation:**

```python
import json
import os

# Get required environment variables from config schema
spec = json.loads(AppConfig.describe(output_format="json"))
required_vars = [f["env_var"] for f in spec["fields"] if f["required"]]

# Validate all required vars are set
missing = [var for var in required_vars if var not in os.environ]
if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
    exit(1)
```

**3. Developer Onboarding:**

```python
import os

# Display configuration reference in development mode
if os.getenv("ENV") == "dev":
    print("\n" + "=" * 80)
    print("CONFIGURATION REFERENCE")
    print("=" * 80)
    print(AppConfig.describe())
    print("=" * 80 + "\n")
```

**4. Generate Documentation Website:**

```python
from dotenvmodel import describe_configs

# Generate markdown docs for all config classes
configs = [AppConfig, DatabaseConfig, RedisConfig, CacheConfig]

# Save as markdown
describe_configs(configs, output_format="markdown", output="docs/configuration.md")

# Or generate HTML version with styling
describe_configs(configs, output_format="html", output="docs/configuration.html")
```

**5. Build Tool Integration:**

```python
# build_docs.py - Run during build process
from your_app.config import AppConfig, DatabaseConfig

# Generate .env.example for repository
AppConfig.generate_env_example(output=".env.example")

# Generate markdown docs
AppConfig.describe(output_format="markdown", output="docs/CONFIG.md")

# Generate HTML for internal wiki
AppConfig.describe(output_format="html", output="docs/config.html")

print("✓ Configuration documentation generated")
```

## Environment Variable Prefixes

Use class-level prefixes to namespace environment variables:

```python
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

### Prefix Behavior

- **Automatic Uppercasing**: Field names are automatically uppercased and prefixed
  - `host` → `DB_HOST`
  - `port` → `DB_PORT`

- **Aliases Override Prefix**: When using `alias`, the prefix is NOT applied (aliases are absolute)

  ```python
  class Config(DotEnvConfig):
      env_prefix = "APP_"
      db_url: str = Field(alias="DATABASE_URL")  # Reads DATABASE_URL (no prefix)
      api_key: str = Field()  # Reads APP_API_KEY (with prefix)
  ```

- **No Prefix by Default**: If `env_prefix` is not set, no prefix is applied

  ```python
  class Config(DotEnvConfig):
      # No env_prefix defined
      host: str = Field()  # Reads HOST
  ```

### Multiple Config Classes with Different Prefixes

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

## Error Handling

### Missing Required Field

```python
try:
    config = AppConfig.load()
except MissingFieldError as e:
    print(e)
    # MissingFieldError: Required field 'api_key' is not set.
    #
    # Environment variable name: API_KEY
    # Field type: str
    # Hint: Set API_KEY in your environment or .env file
```

### Type Coercion Error

```python
try:
    config = AppConfig.load_from_dict({"PORT": "abc"})
except TypeCoercionError as e:
    print(e)
    # TypeCoercionError: Failed to coerce field 'port' to type int.
    #
    # Value: "abc"
    # Environment variable: PORT
    # Error: invalid literal for int() with base 10: 'abc'
    # Hint: Ensure PORT contains a valid int
```

### Validation Constraint Error

```python
try:
    config = AppConfig.load_from_dict({"PORT": "99999"})
except ConstraintViolationError as e:
    print(e)
    # ConstraintViolationError: Field 'port' violates constraint.
    #
    # Value: 99999
    # Constraint: le=65535
    # Error: Value must be less than or equal to 65535
    # Hint: Set PORT to a value that satisfies the constraint
```

## Advanced Examples

### Complete Application Configuration

```python
from pathlib import Path
from dotenvmodel import DotEnvConfig, Field, Required

class DatabaseConfig(DotEnvConfig):
    env_prefix = "DB_"  # Namespace with DB_ prefix
    host: str = Field()
    port: int = Field(default=5432)
    name: str = Field()
    pool_size: int = Field(default=10, ge=1, le=100)
    pool_timeout: float = Field(default=30.0, gt=0)
    echo: bool = Field(default=False)

class RedisConfig(DotEnvConfig):
    env_prefix = "REDIS_"  # Namespace with REDIS_ prefix
    host: str = Field()
    port: int = Field(default=6379)
    password: str | None = Field(default=None)
    db: int = Field(default=0, ge=0, le=15)
    socket_keepalive: bool = Field(default=True)

class AppConfig(DotEnvConfig):
    env_prefix = "APP_"  # Namespace with APP_ prefix

    # App settings
    environment: str = Field(
        default="dev",
        choices=["dev", "test", "staging", "prod"]
    )
    debug: bool = Field(default=False)
    secret_key: str = Field(min_length=32)

    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1)

    # External services (using alias to override prefix)
    api_base_url: str = Field(alias="API_BASE_URL")
    api_timeout: float = Field(default=30.0, ge=0.1, le=300.0)

    # Feature flags
    enable_caching: bool = Field(default=True)
    enable_metrics: bool = Field(default=False)

    # Lists and paths
    allowed_origins: list[str] = Field(default_factory=list)
    upload_dir: Path = Field(default=Path("/tmp/uploads"))

# Load all configs with prefixes
# DatabaseConfig reads: DB_HOST, DB_PORT, DB_NAME, etc.
# RedisConfig reads: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, etc.
# AppConfig reads: APP_ENVIRONMENT, APP_DEBUG, APP_HOST, API_BASE_URL (alias), etc.
db_config = DatabaseConfig.load(env="prod")
redis_config = RedisConfig.load(env="prod")
app_config = AppConfig.load(env="prod")

# Reload configuration when environment changes
# (e.g., after receiving SIGHUP signal or config update)
db_config.reload()  # Reloads with same env="prod"
redis_config.reload()
app_config.reload()
```

### Testing Configuration

```python
import pytest
from dotenvmodel import DotEnvConfig, Field, Required, MissingFieldError

class TestConfig(DotEnvConfig):
    database_url: str = Required
    api_key: str = Required
    debug: bool = Field(default=False)

def test_load_from_dict():
    config = TestConfig.load_from_dict({
        "database_url": "sqlite:///:memory:",
        "api_key": "test-key-123",
        "debug": "true",
    })

    assert config.database_url == "sqlite:///:memory:"
    assert config.api_key == "test-key-123"
    assert config.debug is True

def test_missing_required_field():
    with pytest.raises(MissingFieldError) as exc_info:
        TestConfig.load_from_dict({"api_key": "test"})

    assert "database_url" in str(exc_info.value)

@pytest.fixture
def test_config():
    """Fixture providing test configuration."""
    return TestConfig.load_from_dict({
        "database_url": "sqlite:///:memory:",
        "api_key": "test-key",
    })

def test_with_fixture(test_config):
    assert test_config.database_url == "sqlite:///:memory:"
```

## Best Practices

1. **Use Type Hints**: Always specify type hints for proper validation
   ```python
   port: int = Field(default=8000)  # ✓ Good
   port = Field(default=8000)        # ✗ Bad - no type hint
   ```

2. **Use Validation**: Add constraints to catch configuration errors early
   ```python
   port: int = Field(default=8000, ge=1, le=65535)
   ```

3. **Use Aliases**: Keep environment variable names consistent with conventions
   ```python
   postgres_dsn: str = Field(alias="DATABASE_URL")
   ```

4. **Use Default Factories**: For mutable defaults like lists and dicts
   ```python
   hosts: list[str] = Field(default_factory=list)  # ✓ Good
   hosts: list[str] = Field(default=[])             # ✗ Bad - mutable default
   ```

5. **Document Fields**: Use descriptions for complex configurations
   ```python
   timeout: float = Field(
       default=30.0,
       ge=0.1,
       description="API request timeout in seconds"
   )
   ```

## Requirements

- Python 3.12+
- python-dotenv

## Known Limitations

### Union Types (Non-Optional)

Non-optional Union types like `str | int` or `Union[str, int]` are not currently supported. Only Optional unions (types with `None`) work:

```python
# ✅ Supported - Optional unions
class Config(DotEnvConfig):
    value: str | None = Field()  # Works
    other: int | None = Field()  # Works

# ❌ Not supported - Non-optional unions
class Config(DotEnvConfig):
    value: str | int = Field()  # Not supported
```

**Workaround**: Use a single type (typically `str`) and handle conversion in your application code:

```python
class Config(DotEnvConfig):
    value: str = Field()

config = Config.load()
# Convert to int if needed in your code
value_as_int = int(config.value) if config.value.isdigit() else config.value
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Links

- [GitHub Repository](https://github.com/azxio/dotenvmodel)
- [Full Specification](libraryspec.md)
