"""Tests for URL and DSN types (HttpUrl, PostgresDsn, RedisDsn)."""

import pytest

from dotenvmodel import DotEnvConfig, Field, TypeCoercionError
from dotenvmodel.types import HttpUrl, PostgresDsn, RedisDsn


class TestHttpUrl:
    """Test HttpUrl type."""

    def test_http_url_valid(self) -> None:
        """Test valid HTTP URL."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "http://api.example.com/v1"})
        assert isinstance(config.api_url, HttpUrl)
        assert str(config.api_url) == "http://api.example.com/v1"

    def test_https_url_valid(self) -> None:
        """Test valid HTTPS URL."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "https://api.example.com:8443/v1"})
        assert config.api_url.scheme == "https"
        assert config.api_url.host == "api.example.com"
        assert config.api_url.port == 8443
        assert config.api_url.path == "/v1"

    def test_http_url_with_query(self) -> None:
        """Test HTTP URL with query string."""

        class Config(DotEnvConfig):
            webhook_url: HttpUrl = Field()

        config = Config.load_from_dict({"WEBHOOK_URL": "https://example.com/webhook?token=abc123"})
        assert config.webhook_url.query == "token=abc123"

    def test_http_url_invalid_scheme(self) -> None:
        """Test HTTP URL with invalid scheme."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"API_URL": "ftp://example.com"})

        assert "URL scheme must be http or https" in str(exc_info.value)

    def test_http_url_no_scheme(self) -> None:
        """Test HTTP URL without scheme."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"API_URL": "example.com"})

        assert "URL must have a scheme" in str(exc_info.value)

    def test_http_url_no_host(self) -> None:
        """Test HTTP URL without host."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"API_URL": "http://"})

        assert "URL must have a host" in str(exc_info.value)


class TestPostgresDsn:
    """Test PostgresDsn type."""

    def test_postgres_dsn_valid(self) -> None:
        """Test valid PostgreSQL DSN."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb"}
        )
        assert isinstance(config.database_url, PostgresDsn)
        assert config.database_url.scheme == "postgresql"
        assert config.database_url.host == "localhost"
        assert config.database_url.port == 5432
        assert config.database_url.database == "mydb"
        assert config.database_url.username == "user"
        assert config.database_url.password == "pass"

    def test_postgres_dsn_short_scheme(self) -> None:
        """Test PostgreSQL DSN with short scheme (postgres://)."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DATABASE_URL": "postgres://user:pass@localhost/mydb"})
        assert config.database_url.scheme == "postgres"
        assert config.database_url.port == 5432  # Default port
        assert config.database_url.database == "mydb"

    def test_postgres_dsn_without_credentials(self) -> None:
        """Test PostgreSQL DSN without username/password."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost/mydb"})
        assert config.database_url.username is None
        assert config.database_url.password is None
        assert config.database_url.database == "mydb"

    def test_postgres_dsn_with_special_chars_password(self) -> None:
        """Test PostgreSQL DSN with special characters in password."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://user:p@ssw0rd!@localhost/mydb"}
        )
        assert config.database_url.password == "p@ssw0rd!"

    def test_postgres_dsn_invalid_scheme(self) -> None:
        """Test PostgreSQL DSN with invalid scheme."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": "mysql://localhost/mydb"})

        assert "URL scheme must be postgresql or postgres" in str(exc_info.value)

    def test_postgres_dsn_no_host(self) -> None:
        """Test PostgreSQL DSN without host."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": "postgresql:///mydb"})

        assert "URL must have a host" in str(exc_info.value)


class TestRedisDsn:
    """Test RedisDsn type."""

    def test_redis_dsn_valid(self) -> None:
        """Test valid Redis DSN."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost:6379/0"})
        assert isinstance(config.redis_url, RedisDsn)
        assert config.redis_url.scheme == "redis"
        assert config.redis_url.host == "localhost"
        assert config.redis_url.port == 6379
        assert config.redis_url.database == 0

    def test_redis_dsn_with_password(self) -> None:
        """Test Redis DSN with password."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://:mypassword@localhost/1"})
        assert config.redis_url.password == "mypassword"
        assert config.redis_url.database == 1
        assert config.redis_url.port == 6379  # Default port

    def test_redis_dsn_ssl(self) -> None:
        """Test Redis DSN with SSL (rediss://)."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "rediss://localhost:6380/0"})
        assert config.redis_url.scheme == "rediss"
        assert config.redis_url.port == 6380

    def test_redis_dsn_no_database(self) -> None:
        """Test Redis DSN without database number."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost"})
        assert config.redis_url.database == 0  # Default database

    def test_redis_dsn_invalid_scheme(self) -> None:
        """Test Redis DSN with invalid scheme."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"REDIS_URL": "http://localhost"})

        assert "URL scheme must be redis or rediss" in str(exc_info.value)

    def test_redis_dsn_invalid_database_number(self) -> None:
        """Test Redis DSN with invalid database number."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        # Should default to 0 for invalid database number
        config = Config.load_from_dict({"REDIS_URL": "redis://localhost/abc"})
        assert config.redis_url.database == 0


class TestUrlDsnProperties:
    """Test URL/DSN property access."""

    def test_url_properties_immutable(self) -> None:
        """Test that URL properties are read-only."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "https://api.example.com:8080/v1"})

        # These should all work without errors
        assert config.api_url.scheme == "https"
        assert config.api_url.host == "api.example.com"
        assert config.api_url.port == 8080
        assert config.api_url.path == "/v1"

    def test_postgres_database_extraction(self) -> None:
        """Test database name extraction from path."""

        class Config(DotEnvConfig):
            db1: PostgresDsn = Field()
            db2: PostgresDsn = Field()

        config = Config.load_from_dict(
            {
                "DB1": "postgresql://localhost/mydb",
                "DB2": "postgresql://localhost/",
            }
        )

        assert config.db1.database == "mydb"
        assert config.db2.database == ""

    def test_redis_database_extraction(self) -> None:
        """Test database number extraction from path."""

        class Config(DotEnvConfig):
            redis1: RedisDsn = Field()
            redis2: RedisDsn = Field()
            redis3: RedisDsn = Field()

        config = Config.load_from_dict(
            {
                "REDIS1": "redis://localhost/5",
                "REDIS2": "redis://localhost/",
                "REDIS3": "redis://localhost",
            }
        )

        assert config.redis1.database == 5
        assert config.redis2.database == 0
        assert config.redis3.database == 0
