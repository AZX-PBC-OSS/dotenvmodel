"""Tests for .env file loading and environment variable handling."""

from pathlib import Path

import pytest

from dotenvmodel import DotEnvConfig, Field


class TestEnvFileLoading:
    """Test .env file loading functionality."""

    def test_load_from_env_file(self, tmp_path: Path) -> None:
        """Test loading from .env file."""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgresql://localhost/test\nDEBUG=true\n")

        class Config(DotEnvConfig):
            database_url: str = Field()
            debug: bool = Field()

        config = Config.load(env_file=tmp_path)
        assert config.database_url == "postgresql://localhost/test"
        assert config.debug is True

    def test_load_with_environment_cascade(self, tmp_path: Path) -> None:
        """Test cascading .env files (.env, .env.dev, .env.dev.local)."""
        # Create base .env
        (tmp_path / ".env").write_text("DATABASE_URL=postgresql://localhost/prod\nDEBUG=false\n")

        # Create .env.dev (overrides base)
        (tmp_path / ".env.dev").write_text("DEBUG=true\nLOG_LEVEL=DEBUG\n")

        # Create .env.dev.local (overrides everything)
        (tmp_path / ".env.dev.local").write_text("DATABASE_URL=postgresql://localhost/dev_local\n")

        class Config(DotEnvConfig):
            database_url: str = Field()
            debug: bool = Field()
            log_level: str = Field(default="INFO")

        config = Config.load(env="dev", env_file=tmp_path)
        # Should use .env.dev.local value for DATABASE_URL
        assert config.database_url == "postgresql://localhost/dev_local"
        # Should use .env.dev value for DEBUG
        assert config.debug is True
        # Should use .env.dev value for LOG_LEVEL
        assert config.log_level == "DEBUG"

    def test_load_with_explicit_env(self, tmp_path: Path) -> None:
        """Test loading with explicit environment."""
        (tmp_path / ".env").write_text("PORT=8000\n")
        (tmp_path / ".env.prod").write_text("PORT=80\n")

        class Config(DotEnvConfig):
            port: int = Field()

        config = Config.load(env="prod", env_file=tmp_path)
        assert config.port == 80

    def test_load_env_from_environment_variable(self, tmp_path: Path, monkeypatch) -> None:
        """Test loading env from ENV environment variable."""
        (tmp_path / ".env").write_text("VALUE=base\n")
        (tmp_path / ".env.custom").write_text("VALUE=custom\n")

        # Set ENV environment variable
        monkeypatch.setenv("ENV", "custom")

        class Config(DotEnvConfig):
            value: str = Field()

        config = Config.load(env_file=tmp_path)
        assert config.value == "custom"

    def test_load_override_true(self, tmp_path: Path, monkeypatch) -> None:
        """Test override=True (env file overrides existing env vars)."""
        # Set environment variable
        monkeypatch.setenv("PORT", "9000")

        # Create .env file with different value
        (tmp_path / ".env").write_text("PORT=8000\n")

        class Config(DotEnvConfig):
            port: int = Field()

        config = Config.load(env_file=tmp_path, override=True)
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

        config = Config.load(env_file=tmp_path, override=False)
        # Existing env var should take precedence
        assert config.port == 9000

    def test_load_missing_env_file_directory(self) -> None:
        """Test loading with non-existent env file directory."""

        class Config(DotEnvConfig):
            value: str = Field(default="test")

        with pytest.raises(FileNotFoundError) as exc_info:
            Config.load(env_file=Path("/nonexistent/directory"))

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

    def test_missing_env_files_are_ignored(self, tmp_path: Path, monkeypatch) -> None:
        """Test that missing .env files are silently ignored."""
        # Don't create any .env files
        # Clear any existing VALUE env var to avoid pollution
        monkeypatch.delenv("VALUE", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        # Should not raise error, just use defaults
        config = Config.load(env="dev", env_file=tmp_path)
        assert config.value == "default"


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
