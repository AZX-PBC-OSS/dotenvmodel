"""Tests for config reload functionality."""

import pytest

from dotenvmodel import DotEnvConfig, Field, MissingFieldError


class TestReload:
    """Test configuration reload functionality."""

    def test_reload_basic(self, monkeypatch) -> None:
        """Test basic reload functionality."""

        class Config(DotEnvConfig):
            host: str = Field()
            port: int = Field(default=8000)

        # Initial load
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "3000")

        config = Config.load()
        assert config.host == "localhost"
        assert config.port == 3000

        # Change environment variables
        monkeypatch.setenv("HOST", "example.com")
        monkeypatch.setenv("PORT", "9000")

        # Reload
        config.reload()
        assert config.host == "example.com"
        assert config.port == 9000

    def test_reload_returns_self(self, monkeypatch) -> None:
        """Test that reload returns the same instance."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "initial")
        config = Config.load()

        monkeypatch.setenv("VALUE", "updated")
        result = config.reload()

        assert result is config
        assert config.value == "updated"

    def test_reload_with_prefix(self, monkeypatch) -> None:
        """Test reload with env_prefix."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            host: str = Field()
            port: int = Field()

        monkeypatch.setenv("APP_HOST", "localhost")
        monkeypatch.setenv("APP_PORT", "8000")

        config = Config.load()
        assert config.host == "localhost"
        assert config.port == 8000

        monkeypatch.setenv("APP_HOST", "example.com")
        monkeypatch.setenv("APP_PORT", "9000")

        config.reload()
        assert config.host == "example.com"
        assert config.port == 9000

    def test_reload_with_defaults(self, monkeypatch) -> None:
        """Test reload with default values."""

        class Config(DotEnvConfig):
            host: str = Field()
            port: int = Field(default=8000)
            debug: bool = Field(default=False)

        # Clean up any existing PORT and DEBUG env vars from other tests
        monkeypatch.delenv("PORT", raising=False)
        monkeypatch.delenv("DEBUG", raising=False)

        monkeypatch.setenv("HOST", "localhost")
        config = Config.load()
        assert config.host == "localhost"
        assert config.port == 8000
        assert config.debug is False

        # Set a value that was using default
        monkeypatch.setenv("PORT", "3000")
        monkeypatch.setenv("DEBUG", "true")

        config.reload()
        assert config.host == "localhost"
        assert config.port == 3000
        assert config.debug is True

    def test_reload_back_to_defaults(self, monkeypatch) -> None:
        """Test reload falls back to defaults when env var is removed."""

        class Config(DotEnvConfig):
            host: str = Field()
            port: int = Field(default=8000)

        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "3000")

        config = Config.load()
        assert config.port == 3000

        # Remove PORT env var
        monkeypatch.delenv("PORT")

        config.reload()
        assert config.port == 8000  # Back to default

    def test_reload_required_field_missing_fails(self, monkeypatch) -> None:
        """Test reload fails when required field becomes missing."""

        class Config(DotEnvConfig):
            host: str = Field()
            port: int = Field()

        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8000")

        config = Config.load()
        assert config.host == "localhost"
        assert config.port == 8000

        # Remove required field
        monkeypatch.delenv("PORT")

        with pytest.raises(MissingFieldError) as exc_info:
            config.reload()

        assert "port" in str(exc_info.value).lower()

    def test_reload_with_validation(self, monkeypatch) -> None:
        """Test reload with field validation."""
        from dotenvmodel import ConstraintViolationError

        class Config(DotEnvConfig):
            port: int = Field(ge=1, le=65535)

        monkeypatch.setenv("PORT", "8000")
        config = Config.load()
        assert config.port == 8000

        # Set valid value
        monkeypatch.setenv("PORT", "9000")
        config.reload()
        assert config.port == 9000

        # Set invalid value
        monkeypatch.setenv("PORT", "99999")
        with pytest.raises(ConstraintViolationError):
            config.reload()

    def test_reload_with_type_coercion(self, monkeypatch) -> None:
        """Test reload with type coercion."""

        class Config(DotEnvConfig):
            port: int = Field()
            debug: bool = Field()
            hosts: list[str] = Field()

        monkeypatch.setenv("PORT", "8000")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("HOSTS", "localhost,example.com")

        config = Config.load()
        assert config.port == 8000
        assert config.debug is False
        assert config.hosts == ["localhost", "example.com"]

        monkeypatch.setenv("PORT", "3000")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("HOSTS", "api.example.com")

        config.reload()
        assert config.port == 3000
        assert config.debug is True
        assert config.hosts == ["api.example.com"]

    def test_reload_preserves_instance(self, monkeypatch) -> None:
        """Test that reload preserves instance identity."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "original")
        config = Config.load()
        original_id = id(config)

        monkeypatch.setenv("VALUE", "updated")
        config.reload()

        # Same instance
        assert id(config) == original_id
        assert config.value == "updated"

    def test_reload_with_alias(self, monkeypatch) -> None:
        """Test reload with field aliases."""

        class Config(DotEnvConfig):
            db_url: str = Field(alias="DATABASE_URL")

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db1")
        config = Config.load()
        assert config.db_url == "postgresql://localhost/db1"

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db2")
        config.reload()
        assert config.db_url == "postgresql://localhost/db2"

    def test_reload_multiple_times(self, monkeypatch) -> None:
        """Test reloading multiple times."""

        class Config(DotEnvConfig):
            counter: int = Field()

        monkeypatch.setenv("COUNTER", "1")
        config = Config.load()
        assert config.counter == 1

        monkeypatch.setenv("COUNTER", "2")
        config.reload()
        assert config.counter == 2

        monkeypatch.setenv("COUNTER", "3")
        config.reload()
        assert config.counter == 3

        monkeypatch.setenv("COUNTER", "4")
        config.reload()
        assert config.counter == 4

    def test_reload_with_complex_types(self, monkeypatch) -> None:
        """Test reload with complex types."""
        from uuid import UUID

        class Config(DotEnvConfig):
            tenant_id: UUID = Field()

        monkeypatch.setenv("TENANT_ID", "550e8400-e29b-41d4-a716-446655440000")
        config = Config.load()
        assert str(config.tenant_id) == "550e8400-e29b-41d4-a716-446655440000"

        monkeypatch.setenv("TENANT_ID", "6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        config.reload()
        assert str(config.tenant_id) == "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

    def test_reload_different_env(self, tmp_path, monkeypatch) -> None:
        """Test reload with different environment."""

        # Create .env files
        env_dir = tmp_path / "envs"
        env_dir.mkdir()

        (env_dir / ".env.dev").write_text("HOST=dev.example.com\nPORT=8000")
        (env_dir / ".env.prod").write_text("HOST=prod.example.com\nPORT=443")

        class Config(DotEnvConfig):
            host: str = Field()
            port: int = Field()

        config = Config.load(env="dev", env_dir=env_dir)
        assert config.host == "dev.example.com"
        assert config.port == 8000

        # Reload with different environment
        config.reload(env="prod", env_dir=env_dir)
        assert config.host == "prod.example.com"
        assert config.port == 443

    def test_reload_reuses_original_env(self, tmp_path) -> None:
        """Test that reload reuses original env parameter by default."""

        # Create .env files
        env_dir = tmp_path / "envs"
        env_dir.mkdir()

        (env_dir / ".env.dev").write_text("VALUE=dev_value")
        (env_dir / ".env.prod").write_text("VALUE=prod_value")

        class Config(DotEnvConfig):
            value: str = Field()

        # Load with env="dev"
        config = Config.load(env="dev", env_dir=env_dir)
        assert config.value == "dev_value"

        # Modify the .env.dev file
        (env_dir / ".env.dev").write_text("VALUE=dev_value_updated")

        # Reload without specifying env - should reuse "dev"
        config.reload()
        assert config.value == "dev_value_updated"

    def test_reload_reuses_original_override(self, monkeypatch) -> None:
        """Test that reload reuses original override parameter by default."""

        class Config(DotEnvConfig):
            value: str = Field()

        # Set env var before load
        monkeypatch.setenv("VALUE", "env_value")

        # Load with override=False (env vars take precedence)
        config = Config.load(override=False)
        assert config.value == "env_value"

        # Change env var
        monkeypatch.setenv("VALUE", "new_env_value")

        # Reload should still use override=False
        config.reload()
        assert config.value == "new_env_value"

    def test_reload_stores_parameters(self, monkeypatch) -> None:
        """Test that load parameters are stored correctly."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "test")
        config = Config.load(env="prod", override=False)

        # Check stored parameters
        assert config._load_env == "prod"
        assert config._load_override is False
        assert config._load_env_dir is None
