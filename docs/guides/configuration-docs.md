# Configuration Documentation

dotenvmodel can generate documentation for your configuration classes in multiple formats. This is useful for onboarding, CI validation, and build tool integration.

## The `describe()` Method

The `describe()` class method generates human-readable documentation showing all environment variables, their types, required status, defaults, descriptions, and validation constraints.

```python
from dotenvmodel import DotEnvConfig, Field

class AppConfig(DotEnvConfig):
    database_url: str = Field(description="PostgreSQL connection string")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    workers: int = Field(default=4, ge=1, le=16, description="Number of worker processes")

# Generate documentation
print(AppConfig.describe())
```

## Output Formats

`describe()` supports five output formats via the `output_format` parameter.

=== "Table"

    ASCII table — best for terminal output and logging. This is the default.

    ```python
    print(AppConfig.describe(output_format="table"))
    ```

    ```text
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

=== "Markdown"

    Markdown table — perfect for README files and documentation sites.

    ```python
    docs = AppConfig.describe(output_format="markdown")

    # Save to file
    with open("CONFIG.md", "w") as f:
        f.write(docs)
    ```

    The output is a standard Markdown table that renders in GitHub, GitLab, and any Markdown viewer.

=== "JSON"

    JSON schema — ideal for CI validation and programmatic processing.

    ```python
    import json

    config_spec = AppConfig.describe(output_format="json")
    data = json.loads(config_spec)

    # Use for validation, code generation, etc.
    print(data["class_name"])        # "AppConfig"
    print(data["fields"][0]["env_var"])  # "DATABASE_URL"

    # Get required environment variables
    required_vars = [f["env_var"] for f in data["fields"] if f["required"]]
    ```

    Example JSON structure:

    ```json
    {
      "class_name": "AppConfig",
      "fields": [
        {
          "env_var": "DATABASE_URL",
          "field_name": "database_url",
          "type": "str",
          "required": true,
          "default": "-",
          "description": "PostgreSQL connection string",
          "constraints": "-"
        }
      ]
    }
    ```

=== "HTML"

    Styled HTML table — for web documentation and internal wikis.

    ```python
    html_docs = AppConfig.describe(output_format="html")

    # Save to file
    with open("config.html", "w") as f:
        f.write(html_docs)
    ```

=== "Dotenv"

    `.env.example` format — for generating template files for onboarding.

    ```python
    dotenv_docs = AppConfig.describe(output_format="dotenv")
    print(dotenv_docs)
    ```

## File Export

Save documentation directly to files using the `output` parameter. The result is both written to the file and returned.

```python
# Save as markdown
AppConfig.describe(output_format="markdown", output="docs/config.md")

# Save as HTML
AppConfig.describe(output_format="html", output="docs/config.html")

# Save as JSON
AppConfig.describe(output_format="json", output="config-schema.json")

# Save .env.example
AppConfig.describe(output_format="dotenv", output=".env.example")
```

## Line Endings

Control line endings with the `line_ending` parameter. This is useful for cross-platform compatibility or when generating files for a specific OS.

```python
# Unix line endings
AppConfig.describe(output_format="markdown", line_ending="\n")

# Windows line endings
AppConfig.describe(output_format="markdown", line_ending="\r\n")

# Classic Mac line endings
AppConfig.describe(output_format="markdown", line_ending="\r")
```

If `line_ending` is `None` (default), the platform default (`os.linesep`) is used.

## Generating `.env.example` Files

The `generate_env_example()` method is a convenience wrapper that calls `describe()` with `output_format="dotenv"`. It produces a template file with type information, constraints, examples, and helpful comments.

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

Example output:

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

- **Type information** — Shows the expected Python type
- **Parsing hints** — Explains how to format complex types (e.g., comma-separated values for lists)
- **Constraints** — Documents validation rules (min/max length, numeric ranges, etc.)
- **Examples** — Shows example values for required fields
- **Commented defaults** — Optional fields are commented out with their default values
- **Secret handling** — `SecretStr` fields are masked appropriately

## Documenting Multiple Configurations

Use `describe_configs()` to document multiple config classes in a single output. Each class is shown as a separate section.

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

# Save to file
describe_configs(
    [DatabaseConfig, RedisConfig, AppConfig],
    output_format="markdown",
    output="docs/configuration.md"
)
```

## Practical Use Cases

### Developer Onboarding

Generate `.env.example` files automatically so new developers know exactly what to configure:

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

### CI Configuration Validation

Use the JSON output to validate that all required environment variables are set before deployment:

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

### Build Tool Integration

Generate documentation as part of your build process:

```python
# build_docs.py - Run during build process
from your_app.config import AppConfig, DatabaseConfig

# Generate .env.example for repository
AppConfig.generate_env_example(output=".env.example")

# Generate markdown docs
AppConfig.describe(output_format="markdown", output="docs/CONFIG.md")

# Generate HTML for internal wiki
AppConfig.describe(output_format="html", output="docs/config.html")

print("Configuration documentation generated")
```

### Display Configuration Reference in Development

Show configuration details when running in development mode:

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

## See Also

- [Describe API Reference](../api-reference/describe.md) — `describe_single()`, `describe_configs()`, `generate_env_example()`
- [DotEnvConfig API Reference](../api-reference/config.md) — `describe()` and `generate_env_example()` class methods
- [Field Definitions](fields.md) — `description` parameter for documenting fields
- [Environment Prefixes](prefixes.md) — Prefixes are reflected in documentation output
