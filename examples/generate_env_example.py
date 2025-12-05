"""Example demonstrating .env.example file generation.

This shows how to automatically generate .env.example files with:
- Type information and parsing hints
- Constraint documentation
- Helpful comments and examples
- Proper formatting for required vs optional fields
"""

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr


class AppConfig(DotEnvConfig):
    """Application configuration."""

    env_prefix = "APP_"

    # Required field with constraints
    api_key: str = Field(min_length=32, max_length=64, description="API key for external service")

    # Numeric field with validation
    port: int = Field(default=8000, ge=1, le=65535, description="Server port number")

    # Secret field
    database_password: SecretStr = Field(
        default=SecretStr("change_me_in_production"),
        min_length=8,
        description="Database connection password",
    )

    # Collection with custom separator
    allowed_hosts: list[str] = Field(
        default_factory=list,
        separator=";",
        min_items=1,
        max_items=10,
        description="Allowed hostnames for CORS",
    )

    # Boolean flag
    debug: bool = Field(default=False, description="Enable debug mode (never use in production!)")


if __name__ == "__main__":
    print("=" * 80)
    print(".env.example GENERATION")
    print("=" * 80)
    print()

    # Method 1: Print to console
    print("Method 1: Print to console")
    print("-" * 80)
    env_example = AppConfig.generate_env_example()
    print(env_example)
    print()

    # Method 2: Save to file
    print("Method 2: Save to file")
    print("-" * 80)
    output_file = "/tmp/.env.example"
    AppConfig.generate_env_example(output=output_file)
    print(f"✓ Saved to {output_file}")
    print()

    # Method 3: Using describe() with dotenv format
    print("Method 3: Using describe() with dotenv format (equivalent)")
    print("-" * 80)
    dotenv_docs = AppConfig.describe(output_format="dotenv")
    print(dotenv_docs)
    print()

    print("=" * 80)
    print("TIP: Add this to your build process to keep .env.example up to date!")
    print("=" * 80)
