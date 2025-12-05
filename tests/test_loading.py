"""Tests for .env file loading and environment variable handling."""

from pathlib import Path

import pytest

from dotenvmodel import DotEnvConfig, Field


class TestEnvFileLoading:
    """Test .env file loading functionality."""

    def test_load_from_env_dir(self, tmp_path: Path) -> None:
        """Test loading from .env file."""
        # Create .env file
        env_dir = tmp_path / ".env"
        env_dir.write_text("DATABASE_URL=postgresql://localhost/test\nDEBUG=true\n")

        class Config(DotEnvConfig):
            database_url: str = Field()
            debug: bool = Field()

        config = Config.load(env_dir=tmp_path)
        assert config.database_url == "postgresql://localhost/test"
        assert config.debug is True

    def test_load_with_environment_cascade(self, tmp_path: Path) -> None:
        """Test cascading .env files (.env, .env.local, .env.dev, .env.dev.local)."""
        # Create base .env
        (tmp_path / ".env").write_text(
            "DATABASE_URL=postgresql://localhost/prod\nDEBUG=false\nPORT=8000\n"
        )

        # Create .env.local (local base overrides)
        (tmp_path / ".env.local").write_text("DATABASE_URL=postgresql://localhost/local_base\n")

        # Create .env.dev (environment-specific)
        (tmp_path / ".env.dev").write_text("DEBUG=true\nLOG_LEVEL=DEBUG\n")

        # Create .env.dev.local (local environment overrides)
        (tmp_path / ".env.dev.local").write_text("PORT=3000\n")

        class Config(DotEnvConfig):
            database_url: str = Field()
            debug: bool = Field()
            log_level: str = Field(default="INFO")
            port: int = Field()

        config = Config.load(env="dev", env_dir=tmp_path)
        # Should use .env.local value for DATABASE_URL (overrides .env)
        assert config.database_url == "postgresql://localhost/local_base"
        # Should use .env.dev value for DEBUG (overrides .env)
        assert config.debug is True
        # Should use .env.dev value for LOG_LEVEL
        assert config.log_level == "DEBUG"
        # Should use .env.dev.local value for PORT (overrides .env)
        assert config.port == 3000

    def test_load_with_explicit_env(self, tmp_path: Path) -> None:
        """Test loading with explicit environment."""
        (tmp_path / ".env").write_text("PORT=8000\n")
        (tmp_path / ".env.prod").write_text("PORT=80\n")

        class Config(DotEnvConfig):
            port: int = Field()

        config = Config.load(env="prod", env_dir=tmp_path)
        assert config.port == 80

    def test_load_env_from_environment_variable(self, tmp_path: Path, monkeypatch) -> None:
        """Test loading env from ENV environment variable."""
        (tmp_path / ".env").write_text("VALUE=base\n")
        (tmp_path / ".env.custom").write_text("VALUE=custom\n")

        # Set ENV environment variable
        monkeypatch.setenv("ENV", "custom")

        class Config(DotEnvConfig):
            value: str = Field()

        config = Config.load(env_dir=tmp_path)
        assert config.value == "custom"

    def test_load_override_true(self, tmp_path: Path, monkeypatch) -> None:
        """Test override=True (env file overrides existing env vars)."""
        # Set environment variable
        monkeypatch.setenv("PORT", "9000")

        # Create .env file with different value
        (tmp_path / ".env").write_text("PORT=8000\n")

        class Config(DotEnvConfig):
            port: int = Field()

        config = Config.load(env_dir=tmp_path, override=True)
        # .env file should override env var
        assert config.port == 8000

    def test_load_override_false(self, tmp_path: Path, monkeypatch) -> None:
        """Test override=False (existing env vars take precedence)."""
        # Set environment variable
        monkeypatch.setenv("PORT", "9000")

        # Create .env file with different value
        (tmp_path / ".env").write_text("PORT=8000\n")

        class Config(DotEnvConfig):
            port: int = Field()

        config = Config.load(env_dir=tmp_path, override=False)
        # Existing env var should take precedence
        assert config.port == 9000

    def test_load_missing_env_dir_directory(self) -> None:
        """Test loading with non-existent env file directory."""

        class Config(DotEnvConfig):
            value: str = Field(default="test")

        with pytest.raises(FileNotFoundError) as exc_info:
            Config.load(env_dir=Path("/nonexistent/directory"))

        assert "does not exist" in str(exc_info.value)

    def test_load_from_cwd(self, tmp_path: Path, monkeypatch) -> None:
        """Test loading from current working directory."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create .env in cwd
        (tmp_path / ".env").write_text("VALUE=from_cwd\n")

        class Config(DotEnvConfig):
            value: str = Field()

        config = Config.load()
        assert config.value == "from_cwd"

    def test_load_from_dotenv_dir_env_var(self, tmp_path: Path, monkeypatch) -> None:
        """Test loading from DOTENV_DIR environment variable."""
        # Set DOTENV_DIR
        monkeypatch.setenv("DOTENV_DIR", str(tmp_path))

        # Create .env in that directory
        (tmp_path / ".env").write_text("VALUE=from_dotenv_dir\n")

        class Config(DotEnvConfig):
            value: str = Field()

        config = Config.load()
        assert config.value == "from_dotenv_dir"

    def test_missing_env_dirs_are_ignored(self, tmp_path: Path, monkeypatch) -> None:
        """Test that missing .env files are silently ignored."""
        # Don't create any .env files
        # Clear any existing VALUE env var to avoid pollution
        monkeypatch.delenv("VALUE", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        # Should not raise error, just use defaults
        config = Config.load(env="dev", env_dir=tmp_path)
        assert config.value == "default"

    def test_env_parameter_validation_prevents_path_traversal(self, tmp_path: Path) -> None:
        """Test that env parameter is validated to prevent path traversal attacks."""

        class Config(DotEnvConfig):
            value: str = Field(default="test")

        # Test various malicious env values
        malicious_envs = [
            "../etc/passwd",
            "../../secrets",
            "..",
            ".",
            "dev/../prod",
            "dev/../../etc",
            "dev/local",
            "/etc/passwd",
        ]

        for malicious_env in malicious_envs:
            with pytest.raises(ValueError) as exc_info:
                Config.load(env=malicious_env, env_dir=tmp_path)

            assert "Invalid environment name" in str(exc_info.value)
            assert "alphanumeric" in str(exc_info.value)

    def test_env_parameter_allows_valid_names(self, tmp_path: Path, monkeypatch) -> None:
        """Test that valid environment names are accepted."""
        # Clear any existing VALUE env var to avoid pollution
        monkeypatch.delenv("VALUE", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="test")

        # Test valid env names
        valid_envs = ["dev", "prod", "test", "staging", "dev-local", "test_env", "prod123"]

        for valid_env in valid_envs:
            # Should not raise error
            config = Config.load(env=valid_env, env_dir=tmp_path)
            assert config.value == "test"


class TestEnvVarName:
    """Test environment variable name handling."""

    def test_field_name_to_upper(self, monkeypatch) -> None:
        """Test field name converts to UPPER_CASE for env var."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

        class Config(DotEnvConfig):
            database_url: str = Field()

        config = Config.load()
        assert config.database_url == "postgresql://localhost/db"

    def test_alias_used_instead_of_field_name(self, monkeypatch) -> None:
        """Test alias is used for env var name."""
        monkeypatch.setenv("DB_CONNECTION", "postgresql://localhost/db")

        class Config(DotEnvConfig):
            postgres_dsn: str = Field(alias="DB_CONNECTION")

        config = Config.load()
        assert config.postgres_dsn == "postgresql://localhost/db"

    def test_load_from_dict_supports_both_names(self) -> None:
        """Test load_from_dict supports both field name and env var name."""

        class Config(DotEnvConfig):
            database_url: str = Field()

        # Using field name
        config1 = Config.load_from_dict({"database_url": "test1"})
        assert config1.database_url == "test1"

        # Using env var name (UPPER_CASE)
        config2 = Config.load_from_dict({"DATABASE_URL": "test2"})
        assert config2.database_url == "test2"
