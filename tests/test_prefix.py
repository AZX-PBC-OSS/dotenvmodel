"""Tests for env_prefix functionality."""

import pytest

from dotenvmodel import DotEnvConfig, Field


class TestEnvPrefix:
    """Test environment variable prefix support."""

    def test_class_level_prefix(self) -> None:
        """Test class-level env_prefix."""

        class AppConfig(DotEnvConfig):
            env_prefix = "APP_"
            database_url: str = Field()
            api_key: str = Field()

        config = AppConfig.load_from_dict(
            {
                "APP_DATABASE_URL": "postgresql://localhost/db",
                "APP_API_KEY": "secret123",
            }
        )

        assert config.database_url == "postgresql://localhost/db"
        assert config.api_key == "secret123"

    def test_prefix_with_default_values(self) -> None:
        """Test prefix with default values."""

        class Config(DotEnvConfig):
            env_prefix = "MY_"
            debug: bool = Field(default=False)
            port: int = Field(default=8000)

        # Use defaults (no env vars provided)
        config = Config.load_from_dict({})
        assert config.debug is False
        assert config.port == 8000

        # Override with prefixed env vars
        config = Config.load_from_dict(
            {
                "MY_DEBUG": "true",
                "MY_PORT": "3000",
            }
        )
        assert config.debug is True
        assert config.port == 3000

    def test_prefix_not_applied_to_alias(self) -> None:
        """Test that prefix is not applied when alias is used."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            # Alias should be used as-is, without prefix
            db_url: str = Field(alias="DATABASE_URL")
            # Regular field should get prefix
            api_key: str = Field()

        config = Config.load_from_dict(
            {
                "DATABASE_URL": "postgresql://localhost/db",  # No prefix!
                "APP_API_KEY": "secret123",  # With prefix
            }
        )

        assert config.db_url == "postgresql://localhost/db"
        assert config.api_key == "secret123"

    def test_no_prefix_by_default(self) -> None:
        """Test that no prefix is applied by default."""

        class Config(DotEnvConfig):
            # No env_prefix defined
            database_url: str = Field()
            api_key: str = Field()

        config = Config.load_from_dict(
            {
                "DATABASE_URL": "postgresql://localhost/db",
                "API_KEY": "secret123",
            }
        )

        assert config.database_url == "postgresql://localhost/db"
        assert config.api_key == "secret123"

    def test_empty_prefix(self) -> None:
        """Test explicit empty prefix."""

        class Config(DotEnvConfig):
            env_prefix = ""  # Explicit empty prefix
            database_url: str = Field()

        config = Config.load_from_dict(
            {
                "DATABASE_URL": "postgresql://localhost/db",
            }
        )

        assert config.database_url == "postgresql://localhost/db"

    def test_prefix_with_underscore(self) -> None:
        """Test prefix with trailing underscore."""

        class Config(DotEnvConfig):
            env_prefix = "MYAPP_"
            host: str = Field()
            port: int = Field()

        config = Config.load_from_dict(
            {
                "MYAPP_HOST": "localhost",
                "MYAPP_PORT": "8080",
            }
        )

        assert config.host == "localhost"
        assert config.port == 8080

    def test_prefix_without_underscore(self) -> None:
        """Test prefix without trailing underscore."""

        class Config(DotEnvConfig):
            env_prefix = "APP"  # No trailing underscore
            host: str = Field()

        config = Config.load_from_dict(
            {
                "APPHOST": "localhost",
            }
        )

        assert config.host == "localhost"

    def test_different_prefixes_for_different_configs(self) -> None:
        """Test different prefixes for different config classes."""

        class DatabaseConfig(DotEnvConfig):
            env_prefix = "DB_"
            host: str = Field()
            port: int = Field(default=5432)

        class RedisConfig(DotEnvConfig):
            env_prefix = "REDIS_"
            host: str = Field()
            port: int = Field(default=6379)

        db_config = DatabaseConfig.load_from_dict(
            {
                "DB_HOST": "db.example.com",
                "DB_PORT": "5433",
            }
        )

        redis_config = RedisConfig.load_from_dict(
            {
                "REDIS_HOST": "redis.example.com",
                "REDIS_PORT": "6380",
            }
        )

        assert db_config.host == "db.example.com"
        assert db_config.port == 5433
        assert redis_config.host == "redis.example.com"
        assert redis_config.port == 6380

    def test_prefix_with_validation(self) -> None:
        """Test prefix with field validation."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            port: int = Field(ge=1, le=65535)

        config = Config.load_from_dict(
            {
                "APP_PORT": "8080",
            }
        )

        assert config.port == 8080

        # Validation should still work
        from dotenvmodel import ConstraintViolationError

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict(
                {
                    "APP_PORT": "99999",
                }
            )

    def test_prefix_with_collections(self) -> None:
        """Test prefix with collection types."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            allowed_hosts: list[str] = Field()
            tags: set[str] = Field()

        config = Config.load_from_dict(
            {
                "APP_ALLOWED_HOSTS": "localhost,example.com,*.example.com",
                "APP_TAGS": "web,api,backend",
            }
        )

        assert config.allowed_hosts == ["localhost", "example.com", "*.example.com"]
        assert config.tags == {"web", "api", "backend"}

    def test_prefix_with_complex_types(self) -> None:
        """Test prefix with complex types like UUID and DSN."""
        from uuid import UUID

        from dotenvmodel.types import PostgresDsn

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            tenant_id: UUID = Field()
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict(
            {
                "APP_TENANT_ID": "550e8400-e29b-41d4-a716-446655440000",
                "APP_DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
            }
        )

        assert isinstance(config.tenant_id, UUID)
        assert str(config.tenant_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert isinstance(config.database_url, PostgresDsn)
        assert config.database_url.database == "db"
