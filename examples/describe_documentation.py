"""Example demonstrating configuration documentation with describe()."""

import json

from dotenvmodel import DotEnvConfig, Field, describe_configs
from dotenvmodel.types import SecretStr


class DatabaseConfig(DotEnvConfig):
    """Database configuration."""

    env_prefix = "DB_"

    host: str = Field(description="Database host address")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    name: str = Field(description="Database name")
    user: str = Field(description="Database user")
    password: SecretStr = Field(description="Database password (stored securely)")
    pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")


class RedisConfig(DotEnvConfig):
    """Redis cache configuration."""

    env_prefix = "REDIS_"

    host: str = Field(description="Redis host address")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    password: SecretStr | None = Field(default=None, description="Redis password (optional)")


class AppConfig(DotEnvConfig):
    """Application configuration."""

    env_prefix = "APP_"

    name: str = Field(default="myapp", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(
        default="dev",
        choices=["dev", "test", "staging", "prod"],
        description="Application environment",
    )
    secret_key: SecretStr = Field(min_length=32, description="Secret key for sessions")
    workers: int = Field(default=4, ge=1, le=32, description="Number of worker processes")


if __name__ == "__main__":
    print("=" * 80)
    print("CONFIGURATION DOCUMENTATION EXAMPLES")
    print("=" * 80)
    print()

    # Example 1: ASCII Table Format (default)
    print("1. ASCII Table Format (default)")
    print("-" * 80)
    print(DatabaseConfig.describe())
    print()

    # Example 2: Markdown Format
    print("2. Markdown Format")
    print("-" * 80)
    print(AppConfig.describe(output_format="markdown"))
    print()

    # Example 3: JSON Format
    print("3. JSON Format")
    print("-" * 80)
    json_output = AppConfig.describe(output_format="json")
    print(json.dumps(json.loads(json_output), indent=2))
    print()

    # Example 4: HTML Format
    print("4. HTML Format")
    print("-" * 80)
    html_output = AppConfig.describe(output_format="html")
    print(html_output[:500] + "...")
    print("(Output truncated - full HTML includes styled tables)")
    print()

    # Example 5: Dotenv Format
    print("5. Dotenv Format - for .env.example files")
    print("-" * 80)
    dotenv_output = AppConfig.describe(output_format="dotenv")
    print(dotenv_output)
    print()

    # Example 6: Generate .env.example with generate_env_example()
    print("6. Generate .env.example with generate_env_example()")
    print("-" * 80)
    env_example = AppConfig.generate_env_example()
    print(env_example)
    print("Note: This includes type hints, constraints, and helpful comments!")
    print()

    # Example 7: File Export
    print("7. File Export - Save documentation to disk")
    print("-" * 80)
    print("You can now save directly to files:")
    print("  AppConfig.describe(output_format='markdown', output='docs/config.md')")
    print("  AppConfig.describe(output_format='html', output='docs/config.html')")
    print("  AppConfig.generate_env_example(output='.env.example')")
    print()

    # Example 8: Multiple Configurations
    print("8. Documenting Multiple Configurations")
    print("-" * 80)
    all_configs = describe_configs([AppConfig, DatabaseConfig, RedisConfig], output_format="table")
    print(all_configs)
    print()

    # Example 9: CI Validation Use Case
    print("9. CI Configuration Validation")
    print("-" * 80)

    # Check all config classes for required vars
    all_required_vars = []
    for config_cls in [AppConfig, DatabaseConfig, RedisConfig]:
        spec = json.loads(config_cls.describe(output_format="json"))
        required_vars = [f["env_var"] for f in spec["fields"] if f["required"]]
        all_required_vars.extend(required_vars)

    print(f"Required environment variables ({len(all_required_vars)}):")
    for var in all_required_vars:
        print(f"  ✓ {var}")
    print()

    # Example of how you'd check in CI
    print("Example CI validation script:")
    print(
        """
import json
import os
import sys

# Get all required variables
spec = json.loads(AppConfig.describe(output_format="json"))
required_vars = [f["env_var"] for f in spec["fields"] if f["required"]]

# Check which ones are missing
missing = [var for var in required_vars if var not in os.environ]

if missing:
    print(f"ERROR: Missing required environment variables:")
    for var in missing:
        print(f"  - {var}")
    sys.exit(1)

print("✓ All required environment variables are set")
"""
    )

    # Example 10: Programmatic Access to Schema
    print("10. Programmatic Access to Configuration Schema")
    print("-" * 80)
    spec = json.loads(DatabaseConfig.describe(output_format="json"))

    print(f"Configuration class: {spec['class_name']}")
    print(f"Environment prefix: {spec['env_prefix']}")
    print(f"Number of fields: {len(spec['fields'])}")
    print()
    print("Fields breakdown:")

    for field in spec["fields"]:
        print(f"  • {field['env_var']} ({field['type_name']})")
        print(f"    Required: {field['required']}")
        print(f"    Default: {field['default']}")
        if field["constraints"] != "-":
            print(f"    Constraints: {field['constraints']}")
        print()

    print()
    print("=" * 80)
    print("All examples completed!")
    print("=" * 80)
