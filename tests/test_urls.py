"""Tests for URL and DSN types (HttpUrl, PostgresDsn, RedisDsn)."""

import pytest

from dotenvmodel import DotEnvConfig, Field, TypeCoercionError
from dotenvmodel.types import HttpUrl, PostgresDsn, RedisDsn


class TestHttpUrl:
    """Test HttpUrl type."""

    def test_http_url(self) -> None:
        """Test HTTP URL."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "http://api.example.com/v1"})
        assert isinstance(config.api_url, HttpUrl)
        assert str(config.api_url) == "http://api.example.com/v1"

    def test_https_url(self) -> None:
        """Test HTTPS URL."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "https://api.example.com/v1"})
        assert config.api_url.scheme == "https"
        assert config.api_url.host == "api.example.com"
        assert config.api_url.path == "/v1"

    def test_http_url_with_port(self) -> None:
        """Test HTTP URL with custom port."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "http://localhost:8080/api"})
        assert config.api_url.host == "localhost"
        assert config.api_url.port == 8080
        assert config.api_url.path == "/api"

    def test_http_url_with_query(self) -> None:
        """Test HTTP URL with query parameters."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        config = Config.load_from_dict({"API_URL": "https://api.example.com/search?q=test"})
        assert config.api_url.query == "q=test"

    def test_http_url_invalid_scheme(self) -> None:
        """Test HTTP URL with invalid scheme."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"API_URL": "ftp://example.com"})

        assert "http or https" in str(exc_info.value).lower()

    def test_http_url_no_scheme(self) -> None:
        """Test HTTP URL without scheme."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"API_URL": "example.com"})

    def test_http_url_no_host(self) -> None:
        """Test HTTP URL without host."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"API_URL": "http://"})


class TestPostgresDsn:
    """Test PostgresDsn type."""

    def test_postgres_dsn(self) -> None:
        """Test PostgreSQL DSN."""

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
        """Test PostgreSQL DSN with 'postgres' scheme."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DATABASE_URL": "postgres://localhost/mydb"})
        assert config.database_url.scheme == "postgres"
        assert config.database_url.database == "mydb"

    def test_postgres_dsn_default_port(self) -> None:
        """Test PostgreSQL DSN default port."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost/mydb"})
        assert config.database_url.port == 5432  # Default PostgreSQL port

    def test_postgres_dsn_no_database(self) -> None:
        """Test PostgreSQL DSN without database."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost"})
        assert config.database_url.database == ""

    def test_postgres_dsn_with_query(self) -> None:
        """Test PostgreSQL DSN with query parameters."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        config = Config.load_from_dict(
            {"DATABASE_URL": "postgresql://localhost/mydb?sslmode=require"}
        )
        assert config.database_url.query == "sslmode=require"

    def test_postgres_dsn_invalid_scheme(self) -> None:
        """Test PostgreSQL DSN with invalid scheme."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": "mysql://localhost/mydb"})

        assert "postgresql or postgres" in str(exc_info.value).lower()


class TestRedisDsn:
    """Test RedisDsn type."""

    def test_redis_dsn(self) -> None:
        """Test Redis DSN."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost:6379/0"})
        assert isinstance(config.redis_url, RedisDsn)
        assert config.redis_url.scheme == "redis"
        assert config.redis_url.host == "localhost"
        assert config.redis_url.port == 6379
        assert config.redis_url.database == 0

    def test_redis_dsn_with_auth(self) -> None:
        """Test Redis DSN with authentication."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://:password@localhost:6379/0"})
        assert config.redis_url.password == "password"

    def test_redis_dsn_ssl(self) -> None:
        """Test Redis DSN with SSL (rediss://)."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "rediss://localhost:6380/0"})
        assert config.redis_url.scheme == "rediss"

    def test_redis_dsn_default_port(self) -> None:
        """Test Redis DSN default port."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost"})
        assert config.redis_url.port == 6379  # Default Redis port

    def test_redis_dsn_no_database(self) -> None:
        """Test Redis DSN without database number."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost:6379"})
        assert config.redis_url.database == 0  # Default to database 0

    def test_redis_dsn_database_number(self) -> None:
        """Test Redis DSN with different database numbers."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost:6379/5"})
        assert config.redis_url.database == 5

    def test_redis_dsn_invalid_scheme(self) -> None:
        """Test Redis DSN with invalid scheme."""

        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"REDIS_URL": "http://localhost:6379"})

        assert "redis or rediss" in str(exc_info.value).lower()


class TestUrlProperties:
    """Test URL/DSN property access."""

    def test_url_parsed_property(self) -> None:
        """Test that parsed property returns ParseResult."""

        class Config(DotEnvConfig):
            url: HttpUrl = Field()

        config = Config.load_from_dict({"URL": "https://example.com:8080/path?q=1"})
        parsed = config.url.parsed

        assert parsed.scheme == "https"
        assert parsed.netloc == "example.com:8080"
        assert parsed.path == "/path"
        assert parsed.query == "q=1"

    def test_url_username_password(self) -> None:
        """Test username and password extraction."""

        class Config(DotEnvConfig):
            db_url: PostgresDsn = Field()

        config = Config.load_from_dict({"DB_URL": "postgresql://myuser:mypass@localhost/db"})
        assert config.db_url.username == "myuser"
        assert config.db_url.password == "mypass"

    def test_url_no_username_password(self) -> None:
        """Test URL without username/password."""

        class Config(DotEnvConfig):
            url: HttpUrl = Field()

        config = Config.load_from_dict({"URL": "https://example.com"})
        assert config.url.username is None
        assert config.url.password is None
