"""Example demonstrating dotenvmodel logging capabilities."""

from dotenvmodel import DotEnvConfig, Field, configure_logging

# Enable logging to see what's happening
# Try different levels: "DEBUG", "INFO", "WARNING", "ERROR"
configure_logging("INFO")

# For more verbose output during debugging:
# configure_logging("DEBUG")


class AppConfig(DotEnvConfig):
    """Application configuration with logging enabled."""

    # Required fields
    database_url: str = Field()
    api_key: str = Field()

    # Optional with defaults
    debug: bool = Field(default=False)
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4)

    # Collection types
    allowed_hosts: list[str] = Field(default_factory=list)


if __name__ == "__main__":
    print("=" * 60)
    print("Loading configuration with logging enabled...")
    print("=" * 60)
    print()

    # Load configuration - you'll see log messages showing:
    # - Which environment is being used
    # - Which .env files are being searched for
    # - Which files are found and loaded
    # - Configuration loading progress
    try:
        config = AppConfig.load_from_dict(
            {
                "DATABASE_URL": "postgresql://localhost/myapp",
                "API_KEY": "test-key-123",
                "DEBUG": "true",
                "PORT": "3000",
                "ALLOWED_HOSTS": "localhost,example.com",
            }
        )

        print()
        print("=" * 60)
        print("Configuration loaded successfully!")
        print("=" * 60)
        print(f"Database: {config.database_url}")
        print(f"Debug: {config.debug}")
        print(f"Port: {config.port}")
        print(f"Workers: {config.workers}")
        print(f"Allowed hosts: {config.allowed_hosts}")

    except Exception as e:
        print()
        print("=" * 60)
        print("Configuration loading failed!")
        print("=" * 60)
        print(f"Error: {e}")
        raise


# Example showing what logs look like at different levels:
print("\n" + "=" * 60)
print("Example log levels:")
print("=" * 60)
print("""
DEBUG level shows:
  - Environment detection
  - Base directory
  - File search paths
  - Each file loaded/skipped
  - Number of fields being processed
  - Loaded field names

INFO level shows:
  - Environment being used
  - Files being loaded
  - Load summary (how many files loaded)
  - Configuration class name
  - Success/failure status

WARNING level shows:
  - Only warnings (e.g., no .env files found)
  - Errors

ERROR level shows:
  - Only errors

To control logging:
  1. Via environment variable:
     export DOTENVMODEL_LOG_LEVEL=DEBUG

  2. Programmatically:
     from dotenvmodel import configure_logging
     configure_logging("DEBUG")

  3. Using standard logging:
     import logging
     logging.getLogger("dotenvmodel").setLevel(logging.DEBUG)

  4. Disable logging:
     from dotenvmodel import disable_logging
     disable_logging()
""")
