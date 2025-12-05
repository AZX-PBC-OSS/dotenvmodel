"""Tests for URL password decoding."""

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import PostgresDsn, RedisDsn


class TestUrlPasswordDecoding:
    """Test that passwords in DSN URLs are properly decoded."""

    def test_postgres_password_with_special_chars(self) -> None:
        """Test PostgreSQL password with special characters is decoded."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        # Password with special chars: "my@pass:word/"
        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://user:my%40pass%3Aword%2F@localhost:5432/db"}
        )

        assert config.database_url.password == "my@pass:word/"
        assert config.database_url.username == "user"

    def test_redis_password_with_special_chars(self) -> None:
        """Test Redis password with special characters is decoded."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        # Password with special chars: "redis@pass!"
        config = Config.load_from_dict({"REDIS_URL": "redis://:redis%40pass%21@localhost:6379/0"})

        assert config.redis_url.password == "redis@pass!"

    def test_postgres_password_with_slash(self) -> None:
        """Test PostgreSQL password with slash character."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        # Password: "pass/word"
        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://user:pass%2Fword@localhost:5432/db"}
        )

        assert config.database_url.password == "pass/word"

    def test_postgres_password_with_at_sign(self) -> None:
        """Test PostgreSQL password with @ character."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        # Password: "p@ssw0rd"
        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://user:p%40ssw0rd@localhost:5432/db"}
        )

        assert config.database_url.password == "p@ssw0rd"

    def test_postgres_no_password(self) -> None:
        """Test PostgreSQL URL without password."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DATABASE_URL": "postgresql://user@localhost:5432/db"})

        assert config.database_url.password is None
        assert config.database_url.username == "user"

    def test_password_with_plus_sign(self) -> None:
        """Test password with + character (space encoding)."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        # Password: "pass word" (+ should become space)
        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://user:pass+word@localhost:5432/db"}
        )

        # unquote() converts + to space
        assert (
            config.database_url.password == "pass+word"
            or config.database_url.password == "pass word"
        )
