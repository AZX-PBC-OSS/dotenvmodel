"""Tests for automatic prefix derivation from class names."""

import pytest

from dotenvmodel import DotEnvConfig, Field


class TestCamelToScreamingSnake:
    """Test CamelCase to SCREAMING_SNAKE_CASE conversion."""

    def test_simple_camel_case(self) -> None:
        """Test simple CamelCase conversion."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("Database") == "DATABASE"
        assert camel_to_screaming_snake("DatabaseConfig") == "DATABASE_CONFIG"
        assert camel_to_screaming_snake("MyAppConfig") == "MY_APP_CONFIG"

    def test_acronyms_stay_together(self) -> None:
        """Test that acronyms like DB, HTTP stay together."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("DB") == "DB"
        assert camel_to_screaming_snake("DBConfig") == "DB_CONFIG"
        assert camel_to_screaming_snake("HTTP") == "HTTP"
        assert camel_to_screaming_snake("HTTPConfig") == "HTTP_CONFIG"
        assert camel_to_screaming_snake("HTTPServerConfig") == "HTTP_SERVER_CONFIG"

    def test_acronym_in_middle(self) -> None:
        """Test acronyms in the middle of the name."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("MyDBConfig") == "MY_DB_CONFIG"
        assert camel_to_screaming_snake("MyHTTPServerConfig") == "MY_HTTP_SERVER_CONFIG"

    def test_numbers(self) -> None:
        """Test names with numbers."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("OAuth2Config") == "OAUTH2_CONFIG"
        assert camel_to_screaming_snake("V2Config") == "V2_CONFIG"
        assert camel_to_screaming_snake("Config2") == "CONFIG2"

    def test_single_word(self) -> None:
        """Test single word names."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("Config") == "CONFIG"
        assert camel_to_screaming_snake("Database") == "DATABASE"
        assert camel_to_screaming_snake("Settings") == "SETTINGS"

    def test_empty_string(self) -> None:
        """Test empty string."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("") == ""

    def test_already_uppercase(self) -> None:
        """Test already uppercase strings."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake("DB") == "DB"
        assert camel_to_screaming_snake("HTTP") == "HTTP"
        assert camel_to_screaming_snake("API") == "API"


class TestDerivePrefixFromClassName:
    """Test prefix derivation from class names."""

    def test_single_word_no_prefix(self) -> None:
        """Test single-word class names have no prefix."""
        from dotenvmodel.prefix import derive_prefix_from_class_name

        assert derive_prefix_from_class_name("Config") == ""
        assert derive_prefix_from_class_name("Database") == ""
        assert derive_prefix_from_class_name("Settings") == ""

    def test_two_word_class_name(self) -> None:
        """Test two-word class names use first word as prefix."""
        from dotenvmodel.prefix import derive_prefix_from_class_name

        assert derive_prefix_from_class_name("DatabaseConfig") == "DATABASE"
        assert derive_prefix_from_class_name("RedisSettings") == "REDIS"
        assert derive_prefix_from_class_name("AppConfiguration") == "APP"

    def test_multi_word_class_name(self) -> None:
        """Test multi-word class names use all but last word as prefix."""
        from dotenvmodel.prefix import derive_prefix_from_class_name

        assert derive_prefix_from_class_name("MyAppConfig") == "MY_APP"
        assert derive_prefix_from_class_name("HTTPServerConfig") == "HTTP_SERVER"
        assert derive_prefix_from_class_name("MyDatabaseSettings") == "MY_DATABASE"

    def test_acronym_prefix(self) -> None:
        """Test acronym class names."""
        from dotenvmodel.prefix import derive_prefix_from_class_name

        assert derive_prefix_from_class_name("DBConfig") == "DB"
        assert derive_prefix_from_class_name("HTTPConfig") == "HTTP"
        assert derive_prefix_from_class_name("AWSConfig") == "AWS"

    def test_numbers_in_name(self) -> None:
        """Test class names with numbers."""
        from dotenvmodel.prefix import derive_prefix_from_class_name

        assert derive_prefix_from_class_name("OAuth2Config") == "OAUTH2"
        assert derive_prefix_from_class_name("V2Settings") == "V2"


class TestAutoPrefixIntegration:
    """Test auto-prefix derivation integrated with DotEnvConfig."""

    def test_single_word_class_no_prefix(self) -> None:
        """Test single-word class gets no prefix."""

        class Config(DotEnvConfig):
            host: str = Field()

        config = Config.load_from_dict({"HOST": "localhost"})
        assert config.host == "localhost"

    def test_database_config_gets_prefix(self) -> None:
        """Test DatabaseConfig gets DATABASE_ prefix."""

        class DatabaseConfig(DotEnvConfig):
            host: str = Field()
            port: int = Field(default=5432)

        config = DatabaseConfig.load_from_dict({
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5433",
        })
        assert config.host == "localhost"
        assert config.port == 5433

    def test_db_config_gets_db_prefix(self) -> None:
        """Test DBConfig gets DB_ prefix."""

        class DBConfig(DotEnvConfig):
            host: str = Field()
            port: int = Field(default=5432)

        config = DBConfig.load_from_dict({
            "DB_HOST": "localhost",
            "DB_PORT": "5433",
        })
        assert config.host == "localhost"
        assert config.port == 5433

    def test_http_server_config(self) -> None:
        """Test HTTPServerConfig gets HTTP_SERVER_ prefix."""

        class HTTPServerConfig(DotEnvConfig):
            host: str = Field()
            port: int = Field(default=8080)

        config = HTTPServerConfig.load_from_dict({
            "HTTP_SERVER_HOST": "0.0.0.0",
            "HTTP_SERVER_PORT": "9000",
        })
        assert config.host == "0.0.0.0"
        assert config.port == 9000

    def test_explicit_prefix_overrides_auto(self) -> None:
        """Test explicit env_prefix overrides auto-derivation."""

        class DatabaseConfig(DotEnvConfig):
            env_prefix = "DB"  # Override auto-derived DATABASE
            host: str = Field()

        config = DatabaseConfig.load_from_dict({"DB_HOST": "localhost"})
        assert config.host == "localhost"

    def test_explicit_empty_prefix_disables_auto(self) -> None:
        """Test explicit empty string disables auto-derivation."""

        class DatabaseConfig(DotEnvConfig):
            env_prefix = ""  # Explicitly no prefix
            host: str = Field()

        config = DatabaseConfig.load_from_dict({"HOST": "localhost"})
        assert config.host == "localhost"

    def test_alias_not_affected_by_auto_prefix(self) -> None:
        """Test that aliases are not affected by auto-prefix."""

        class DatabaseConfig(DotEnvConfig):
            # Auto-prefix would be DATABASE_
            db_url: str = Field(alias="DATABASE_URL")  # Alias is absolute
            host: str = Field()  # Gets DATABASE_HOST

        config = DatabaseConfig.load_from_dict({
            "DATABASE_URL": "postgresql://localhost/db",
            "DATABASE_HOST": "localhost",
        })
        assert config.db_url == "postgresql://localhost/db"
        assert config.host == "localhost"

    def test_my_app_config(self) -> None:
        """Test MyAppConfig gets MY_APP_ prefix."""

        class MyAppConfig(DotEnvConfig):
            debug: bool = Field(default=False)
            name: str = Field()

        config = MyAppConfig.load_from_dict({
            "MY_APP_DEBUG": "true",
            "MY_APP_NAME": "test-app",
        })
        assert config.debug is True
        assert config.name == "test-app"

    def test_oauth2_config(self) -> None:
        """Test OAuth2Config gets OAUTH2_ prefix."""

        class OAuth2Config(DotEnvConfig):
            client_id: str = Field()
            client_secret: str = Field()

        config = OAuth2Config.load_from_dict({
            "OAUTH2_CLIENT_ID": "my-client",
            "OAUTH2_CLIENT_SECRET": "secret123",
        })
        assert config.client_id == "my-client"
        assert config.client_secret == "secret123"


class TestAutoPrefixWithUnderscore:
    """Test that underscore is auto-inserted between prefix and field."""

    def test_prefix_without_trailing_underscore(self) -> None:
        """Test prefix without trailing underscore still works."""

        class Config(DotEnvConfig):
            env_prefix = "APP"  # No trailing underscore
            host: str = Field()

        config = Config.load_from_dict({"APP_HOST": "localhost"})
        assert config.host == "localhost"

    def test_prefix_with_trailing_underscore(self) -> None:
        """Test prefix with trailing underscore doesn't double up."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"  # With trailing underscore
            host: str = Field()

        config = Config.load_from_dict({"APP_HOST": "localhost"})
        assert config.host == "localhost"


class TestAutoPrefixInheritance:
    """Test auto-prefix behavior with inheritance."""

    def test_child_inherits_parent_explicit_prefix(self) -> None:
        """Test child class inherits parent's explicit prefix."""

        class BaseConfig(DotEnvConfig):
            env_prefix = "APP"
            host: str = Field(default="localhost")

        class AppConfig(BaseConfig):
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict({
            "APP_HOST": "example.com",
            "APP_DEBUG": "true",
        })
        assert config.host == "example.com"
        assert config.debug is True

    def test_child_can_override_auto_prefix(self) -> None:
        """Test child can override with explicit prefix."""

        class BaseConfig(DotEnvConfig):
            # Would auto-derive BASE
            value: str = Field(default="base")

        class AppConfig(BaseConfig):
            env_prefix = "CUSTOM"  # Override auto-derived APP
            other: str = Field(default="app")

        config = AppConfig.load_from_dict({
            "CUSTOM_VALUE": "custom_value",
            "CUSTOM_OTHER": "custom_other",
        })
        assert config.value == "custom_value"
        assert config.other == "custom_other"
