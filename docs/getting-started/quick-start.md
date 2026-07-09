# Quick Start

This guide walks you through defining, loading, and validating typed configuration with dotenvmodel in about 5 minutes. By the end you will have a working config class, a `.env` file, type-safe access to values, and an auto-generated `.env.example`.

## 1. Define a config class

Create a class that inherits from `DotEnvConfig` and declare your settings as typed fields. Use `Field(...)` for required values and `Field(default=...)` for optional ones. Add validation constraints to catch bad configuration early.

```python
from dotenvmodel import DotEnvConfig, Field


class AppConfig(DotEnvConfig):
    """Application configuration."""

    # Required fields (no default means the value must be provided)
    database_url: str = Field(description="PostgreSQL connection string")
    api_key: str = Field(description="API key for external service")

    # Optional fields with defaults
    debug: bool = Field(default=False, description="Enable debug mode")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    workers: int = Field(default=4, ge=1, le=16, description="Worker process count")

    # Validated choice
    environment: str = Field(
        default="dev",
        choices=["dev", "test", "staging", "prod"],
        description="Deployment environment",
    )

    # Collection type
    allowed_hosts: list[str] = Field(default_factory=list, description="CORS allowed hosts")
```

!!! tip "Field(...) marks a required field"
    `Field(...)` (with the ellipsis) is the recommended, Pydantic-style way to mark a field as required. `Field()` with no arguments also works, and `Required` is available as an alternative sentinel.

## 2. Create a `.env` file

dotenvmodel automatically cascades `.env` files in this order (later files override earlier ones):

1. `.env` &mdash; base configuration
2. `.env.local` &mdash; local base overrides (gitignored)
3. `.env.{env}` &mdash; environment-specific (committed to repo)
4. `.env.{env}.local` &mdash; local environment overrides (gitignored)

For this guide, create a `.env` file and a `.env.dev` file in your project root:

```bash title=".env"
DATABASE_URL=postgresql://user:pass@localhost:5432/myapp
API_KEY=super-secret-key-1234567890abcdef
DEBUG=true
PORT=3000
WORKERS=8
ENVIRONMENT=dev
ALLOWED_HOSTS=localhost,example.com,api.example.com
```

```bash title=".env.dev"
DEBUG=true
LOG_LEVEL=DEBUG
```

!!! tip "Keep secrets out of version control"
    Add `.env`, `.env.local`, and `.env.*.local` to your `.gitignore`. Commit only the environment-specific `.env.{env}` files (like `.env.dev`) that contain non-secret defaults.

## 3. Load the configuration

Call the `load()` class method, passing the environment name so dotenvmodel picks up the right `.env.{env}` files:

```python
config = AppConfig.load(env="dev")
```

This loads files in cascade order &mdash; `.env` → `.env.local` → `.env.dev` → `.env.dev.local` &mdash; applies any matching environment variables, coerces values to the declared types, and runs validation. If a required field is missing or a constraint fails, dotenvmodel raises a clear error describing exactly what went wrong and how to fix it.

## 4. Access typed values

Every field on the config object has the exact type you declared. No manual casting, no `os.getenv()` strings to parse:

```python
print(f"Database: {config.database_url}")   # config.database_url: str
print(f"Port:     {config.port}")           # config.port: int
print(f"Debug:    {config.debug}")          # config.debug: bool
print(f"Workers:  {config.workers}")        # config.workers: int
print(f"Hosts:    {config.allowed_hosts}")  # config.allowed_hosts: list[str]
```

Output:

```text
Database: postgresql://user:pass@localhost:5432/myapp
Port:     3000
Debug:    True
Workers:  8
Hosts:    ['localhost', 'example.com', 'api.example.com']
```

Notice that `config.port` is the integer `3000`, not the string `"3000"`, and `config.debug` is the boolean `True`, not the string `"true"`. dotenvmodel handles the coercion automatically based on your type hints.

## 5. Type safety in your IDE

Because dotenvmodel uses real type annotations, your IDE and type checkers (mypy, pyright) understand the field types and catch mismatches at development time:

```python
config = AppConfig.load(env="dev")

# ✅ These are correct — types match the declarations
db_url: str = config.database_url      # str = str
port_num: int = config.port            # int = int
is_debug: bool = config.debug          # bool = bool

# ❌ A type checker flags these as errors
wrong: int = config.database_url       # Error: str is not assignable to int
wrong: str = config.debug              # Error: bool is not assignable to str
```

Your IDE will give you:

- **Autocomplete** for every config field
- **Inline type hints** showing each field's type
- **Error highlighting** for type mismatches
- **Go-to-definition** support

!!! tip "No more stringly-typed config"
    With `os.getenv()` every value is a `str` and you must remember to cast. dotenvmodel eliminates that class of bugs entirely &mdash; the type system enforces correctness for you.

## 6. Generate a `.env.example`

dotenvmodel can generate a `.env.example` file directly from your config class, complete with type information, constraints, and example values. This is invaluable for onboarding new developers to your project.

```python
# Print to console
print(AppConfig.generate_env_example())

# Or save directly to a file
AppConfig.generate_env_example(output=".env.example")
```

The generated file includes comments documenting each variable's type, constraints, and default, so teammates know exactly what to fill in:

```bash
# Configuration for AppConfig

# PostgreSQL connection string
# Type: str
# Example: DATABASE_URL=your_value_here
DATABASE_URL=

# API key for external service
# Type: str
# Example: API_KEY=your_value_here
API_KEY=

# Enable debug mode
# Type: bool
# DEBUG=False

# Server port
# Type: int | Constraints: ge=1, le=65535
# PORT=8000

# Worker process count
# Type: int | Constraints: ge=1, le=16
# WORKERS=4

# Deployment environment
# Type: str | Choices: dev, test, staging, prod
# ENVIRONMENT=dev

# CORS allowed hosts
# Type: list[str]
# ALLOWED_HOSTS=[]
```

!!! tip "Automate generation in CI"
    Add `AppConfig.generate_env_example(output=".env.example")` to a build script or pre-commit hook so your `.env.example` never drifts out of sync with your config class.

## Next steps

You now have a fully typed, validated configuration. Dive deeper into specific features:

- :material-arrow-right: [Fields](../guides/fields.md) &mdash; required vs optional, defaults, aliases, descriptions
- :material-arrow-right: [Types](../guides/types.md) &mdash; UUID, Decimal, datetime, SecretStr, URLs, JSON, and more
- :material-arrow-right: [Validation](../guides/validation.md) &mdash; numeric ranges, string constraints, choices, collection sizes
