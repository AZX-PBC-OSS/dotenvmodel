"""Tests for configuration inheritance."""

import pytest

from dotenvmodel import DotEnvConfig, Field


class TestInheritance:
    """Test configuration class inheritance."""

    def test_basic_inheritance(self) -> None:
        """Test child config inherits parent fields."""

        class BaseConfig(DotEnvConfig):
            host: str = Field(default="localhost")
            port: int = Field(default=8000)

        class AppConfig(BaseConfig):
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict({})
        assert config.host == "localhost"
        assert config.port == 8000
        assert config.debug is False

    def test_inheritance_with_override(self) -> None:
        """Test child can override parent field values."""

        class BaseConfig(DotEnvConfig):
            host: str = Field(default="localhost")
            port: int = Field(default=8000)

        class AppConfig(BaseConfig):
            port: int = Field(default=3000)  # Override parent default
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict({})
        assert config.host == "localhost"
        assert config.port == 3000  # Child default takes precedence
        assert config.debug is False

    def test_inheritance_with_prefix(self) -> None:
        """Test inheritance respects env_prefix."""

        class BaseConfig(DotEnvConfig):
            env_prefix = "APP_"
            host: str = Field(default="localhost")
            port: int = Field(default=8000)

        class AppConfig(BaseConfig):
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict(
            {
                "APP_HOST": "example.com",
                "APP_PORT": "9000",
                "APP_DEBUG": "true",
            }
        )
        assert config.host == "example.com"
        assert config.port == 9000
        assert config.debug is True

    def test_multiple_inheritance_levels(self) -> None:
        """Test multiple levels of inheritance."""

        class BaseConfig(DotEnvConfig):
            host: str = Field(default="localhost")

        class MiddleConfig(BaseConfig):
            port: int = Field(default=8000)

        class AppConfig(MiddleConfig):
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict({})
        assert config.host == "localhost"
        assert config.port == 8000
        assert config.debug is False

    def test_inheritance_with_validation(self) -> None:
        """Test inherited fields maintain validation constraints."""
        from dotenvmodel import ConstraintViolationError

        class BaseConfig(DotEnvConfig):
            port: int = Field(ge=1, le=65535)

        class AppConfig(BaseConfig):
            debug: bool = Field(default=False)

        # Valid value
        config = AppConfig.load_from_dict({"PORT": "8000"})
        assert config.port == 8000

        # Invalid value - should fail validation
        with pytest.raises(ConstraintViolationError):
            AppConfig.load_from_dict({"PORT": "99999"})

    def test_inheritance_preserves_field_metadata(self) -> None:
        """Test that field metadata (aliases, constraints) are preserved."""

        class BaseConfig(DotEnvConfig):
            db_url: str = Field(alias="DATABASE_URL")

        class AppConfig(BaseConfig):
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict({"DATABASE_URL": "postgresql://localhost/db"})
        assert config.db_url == "postgresql://localhost/db"

    def test_child_can_change_prefix(self) -> None:
        """Test child config can override parent's env_prefix."""

        class BaseConfig(DotEnvConfig):
            env_prefix = "BASE_"
            value: str = Field(default="base")

        class AppConfig(BaseConfig):
            env_prefix = "APP_"  # Override parent prefix
            other: str = Field(default="app")

        config = AppConfig.load_from_dict(
            {
                "APP_VALUE": "custom_value",
                "APP_OTHER": "custom_other",
            }
        )
        assert config.value == "custom_value"
        assert config.other == "custom_other"
