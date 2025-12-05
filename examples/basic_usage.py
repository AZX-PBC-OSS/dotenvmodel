"""Basic usage example for dotenvmodel."""

from dotenvmodel import DotEnvConfig, Field, Required


class AppConfig(DotEnvConfig):
    """Application configuration."""

    # Required fields
    database_url: str = Required
    api_key: str = Field()

    # Optional with defaults
    debug: bool = Field(default=False)
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=16)

    # Collection types
    allowed_hosts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, separator=";")

    # With validation constraints
    pool_size: int = Field(default=10, ge=1, le=100)
    timeout: float = Field(default=30.0, gt=0, lt=3600)

    # With alias
    postgres_dsn: str = Field(alias="DB_URL", default="postgresql://localhost/db")

    # String validation
    env: str = Field(default="dev", choices=["dev", "test", "staging", "prod"])


if __name__ == "__main__":
    # Load configuration from environment
    try:
        config = AppConfig.load_from_dict(
            {
                "DATABASE_URL": "postgresql://localhost/myapp",
                "API_KEY": "secret-key-123",
                "DEBUG": "true",
                "PORT": "3000",
                "WORKERS": "8",
                "ALLOWED_HOSTS": "localhost,example.com,*.example.com",
                "TAGS": "web;api;backend",
                "POOL_SIZE": "25",
                "TIMEOUT": "60.5",
                "ENV": "dev",
            }
        )

        print("Configuration loaded successfully!")
        print(f"Database URL: {config.database_url}")
        print(f"API Key: {config.api_key}")
        print(f"Debug mode: {config.debug}")
        print(f"Port: {config.port}")
        print(f"Workers: {config.workers}")
        print(f"Allowed hosts: {config.allowed_hosts}")
        print(f"Tags: {config.tags}")
        print(f"Pool size: {config.pool_size}")
        print(f"Timeout: {config.timeout}s")
        print(f"Postgres DSN: {config.postgres_dsn}")
        print(f"Environment: {config.env}")
        print(f"\nFull config dict: {config.dict()}")

    except Exception as e:
        print(f"Error loading configuration: {e}")
        raise
