"""Tests for automatic prefix derivation from class names."""

import pytest

from dotenvmodel import DotEnvConfig, Field, MissingFieldError


class TestCamelToScreamingSnake:
    """Test CamelCase to SCREAMING_SNAKE_CASE conversion."""

    @pytest.mark.parametrize(
        ("input_name", "expected"),
        [
            # Simple cases
            ("Database", "DATABASE"),
            ("Config", "CONFIG"),
            ("Settings", "SETTINGS"),
            # Two words
            ("DatabaseConfig", "DATABASE_CONFIG"),
            ("RedisSettings", "REDIS_SETTINGS"),
            # Multiple words
            ("MyAppConfig", "MY_APP_CONFIG"),
            ("MyDatabaseSettings", "MY_DATABASE_SETTINGS"),
            ("VeryLongClassNameConfig", "VERY_LONG_CLASS_NAME_CONFIG"),
            # Acronyms (2 chars - stay together)
            ("DB", "DB"),
            ("DBConfig", "DB_CONFIG"),
            ("MyDBConfig", "MY_DB_CONFIG"),
            # Acronyms (3+ chars - stay together)
            ("HTTP", "HTTP"),
            ("HTTPConfig", "HTTP_CONFIG"),
            ("HTTPServerConfig", "HTTP_SERVER_CONFIG"),
            ("MyHTTPServerConfig", "MY_HTTP_SERVER_CONFIG"),
            ("API", "API"),
            ("APIConfig", "API_CONFIG"),
            ("AWSConfig", "AWS_CONFIG"),
            ("AWSLambdaConfig", "AWS_LAMBDA_CONFIG"),
            # Numbers
            ("OAuth2Config", "OAUTH2_CONFIG"),
            ("V2Config", "V2_CONFIG"),
            ("Config2", "CONFIG2"),
            ("My2ndConfig", "MY2ND_CONFIG"),
            ("S3Config", "S3_CONFIG"),
            ("EC2Config", "EC2_CONFIG"),
            # Edge cases
            ("", ""),
            ("A", "A"),
            ("Ab", "AB"),
            ("AB", "AB"),
            ("ABc", "ABC"),  # Short sequences don't split (need 2+ uppercase before split)
            ("ABCd", "AB_CD"),  # 3 uppercase before uppercase+lowercase -> split
            ("XMLParser", "XML_PARSER"),
            ("parseXML", "PARSE_XML"),
            ("getHTTPResponse", "GET_HTTP_RESPONSE"),
        ],
    )
    def test_camel_to_screaming_snake(self, input_name: str, expected: str) -> None:
        """Test CamelCase to SCREAMING_SNAKE_CASE conversion."""
        from dotenvmodel.prefix import camel_to_screaming_snake

        assert camel_to_screaming_snake(input_name) == expected


class TestDerivePrefixFromClassName:
    """Test prefix derivation from class names."""

    @pytest.mark.parametrize(
        ("class_name", "expected_prefix"),
        [
            # Single word - no prefix
            ("Config", ""),
            ("Settings", ""),
            ("Database", ""),
            ("Options", ""),
            # Two words - first word as prefix
            ("DatabaseConfig", "DATABASE"),
            ("RedisSettings", "REDIS"),
            ("AppConfiguration", "APP"),
            ("ServerOptions", "SERVER"),
            # Multiple words - all but last
            ("MyAppConfig", "MY_APP"),
            ("HTTPServerConfig", "HTTP_SERVER"),
            ("MyDatabaseSettings", "MY_DATABASE"),
            ("AWSLambdaConfiguration", "AWS_LAMBDA"),
            # Acronyms
            ("DBConfig", "DB"),
            ("HTTPConfig", "HTTP"),
            ("AWSConfig", "AWS"),
            ("APISettings", "API"),
            ("S3Config", "S3"),
            # Numbers
            ("OAuth2Config", "OAUTH2"),
            ("V2Settings", "V2"),
            ("EC2Config", "EC2"),
            # Edge cases
            ("", ""),
            ("A", ""),  # Single char = single word
            ("AB", ""),  # Acronym = single word
        ],
    )
    def test_derive_prefix(self, class_name: str, expected_prefix: str) -> None:
        """Test prefix derivation from class names."""
        from dotenvmodel.prefix import derive_prefix_from_class_name

        assert derive_prefix_from_class_name(class_name) == expected_prefix


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

    @pytest.mark.parametrize(
        ("prefix", "expected_env_var"),
        [
            ("APP", "APP_HOST"),
            ("APP_", "APP_HOST"),
            ("MY_APP", "MY_APP_HOST"),
            ("MY_APP_", "MY_APP_HOST"),
            ("DB", "DB_HOST"),
            ("DB_", "DB_HOST"),
        ],
    )
    def test_underscore_handling(self, prefix: str, expected_env_var: str) -> None:
        """Test underscore is auto-inserted correctly."""

        class Config(DotEnvConfig):
            host: str = Field()

        Config.env_prefix = prefix
        config = Config.load_from_dict({expected_env_var: "localhost"})
        assert config.host == "localhost"

    def test_empty_prefix_no_underscore(self) -> None:
        """Test empty prefix doesn't add leading underscore."""

        class Config(DotEnvConfig):
            env_prefix = ""
            host: str = Field()

        config = Config.load_from_dict({"HOST": "localhost"})
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

    def test_child_can_override_with_explicit_prefix(self) -> None:
        """Test child can override with explicit prefix."""

        class BaseConfig(DotEnvConfig):
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

    def test_child_auto_derives_own_prefix_not_parent(self) -> None:
        """Test child with no explicit prefix uses its own name, not parent's."""

        class BaseConfig(DotEnvConfig):
            # Would auto-derive BASE
            value: str = Field(default="base")

        class MyAppConfig(BaseConfig):
            # Should auto-derive MY_APP, not BASE
            other: str = Field(default="app")

        config = MyAppConfig.load_from_dict({
            "MY_APP_VALUE": "my_value",
            "MY_APP_OTHER": "my_other",
        })
        assert config.value == "my_value"
        assert config.other == "my_other"

    def test_child_inherits_empty_prefix(self) -> None:
        """Test child inherits parent's explicit empty prefix."""

        class BaseConfig(DotEnvConfig):
            env_prefix = ""  # No prefix
            host: str = Field(default="localhost")

        class AppConfig(BaseConfig):
            # Should inherit empty prefix, not auto-derive APP
            debug: bool = Field(default=False)

        config = AppConfig.load_from_dict({
            "HOST": "example.com",
            "DEBUG": "true",
        })
        assert config.host == "example.com"
        assert config.debug is True


class TestAutoPrefixErrorMessages:
    """Test that error messages show correct prefixed env var names."""

    def test_missing_field_error_shows_prefixed_name(self) -> None:
        """Test MissingFieldError shows the prefixed env var name."""

        class DatabaseConfig(DotEnvConfig):
            # Auto-prefix: DATABASE_
            host: str = Field()

        with pytest.raises(MissingFieldError) as exc_info:
            DatabaseConfig.load_from_dict({})

        error_message = str(exc_info.value)
        assert "DATABASE_HOST" in error_message
        assert "host" in error_message

    def test_missing_field_error_with_explicit_prefix(self) -> None:
        """Test MissingFieldError shows explicit prefix in env var name."""

        class Config(DotEnvConfig):
            env_prefix = "MY_APP"
            api_key: str = Field()

        with pytest.raises(MissingFieldError) as exc_info:
            Config.load_from_dict({})

        error_message = str(exc_info.value)
        assert "MY_APP_API_KEY" in error_message

    def test_missing_field_error_no_prefix(self) -> None:
        """Test MissingFieldError with no prefix shows just field name."""

        class Config(DotEnvConfig):
            # Single word = no prefix
            host: str = Field()

        with pytest.raises(MissingFieldError) as exc_info:
            Config.load_from_dict({})

        error_message = str(exc_info.value)
        assert "HOST" in error_message
        # Should not have a prefix
        assert "_HOST" not in error_message or error_message.split()[-1] == "HOST"


class TestAutoPrefixReload:
    """Test reload() works correctly with auto-prefix."""

    def test_reload_uses_auto_prefix(self) -> None:
        """Test reload() respects auto-derived prefix."""
        import os

        class DatabaseConfig(DotEnvConfig):
            host: str = Field(default="default")

        # Set up environment
        os.environ["DATABASE_HOST"] = "initial"

        config = DatabaseConfig.load()
        assert config.host == "initial"

        # Change environment
        os.environ["DATABASE_HOST"] = "reloaded"

        config.reload()
        assert config.host == "reloaded"

        # Cleanup
        del os.environ["DATABASE_HOST"]

    def test_reload_with_explicit_prefix(self) -> None:
        """Test reload() respects explicit prefix."""
        import os

        class DatabaseConfig(DotEnvConfig):
            env_prefix = "DB"
            host: str = Field(default="default")

        # Set up environment
        os.environ["DB_HOST"] = "initial"

        config = DatabaseConfig.load()
        assert config.host == "initial"

        # Change environment
        os.environ["DB_HOST"] = "reloaded"

        config.reload()
        assert config.host == "reloaded"

        # Cleanup
        del os.environ["DB_HOST"]


class TestGetPrefixMethod:
    """Test the _get_prefix() class method."""

    def test_get_prefix_auto_derived(self) -> None:
        """Test _get_prefix() returns auto-derived prefix."""

        class DatabaseConfig(DotEnvConfig):
            host: str = Field()

        assert DatabaseConfig._get_prefix() == "DATABASE"

    def test_get_prefix_explicit(self) -> None:
        """Test _get_prefix() returns explicit prefix."""

        class DatabaseConfig(DotEnvConfig):
            env_prefix = "DB"
            host: str = Field()

        assert DatabaseConfig._get_prefix() == "DB"

    def test_get_prefix_empty(self) -> None:
        """Test _get_prefix() returns empty for explicit empty prefix."""

        class DatabaseConfig(DotEnvConfig):
            env_prefix = ""
            host: str = Field()

        assert DatabaseConfig._get_prefix() == ""

    def test_get_prefix_single_word_class(self) -> None:
        """Test _get_prefix() returns empty for single-word class."""

        class Config(DotEnvConfig):
            host: str = Field()

        assert Config._get_prefix() == ""


class TestAutoPrefixEdgeCases:
    """Test edge cases for auto-prefix behavior."""

    def test_all_caps_class_name(self) -> None:
        """Test class name that is all caps."""

        class HTTPSConfig(DotEnvConfig):
            port: int = Field(default=443)

        # HTTPS is treated as single word -> HTTPS prefix
        config = HTTPSConfig.load_from_dict({"HTTPS_PORT": "8443"})
        assert config.port == 8443

    def test_class_name_with_numbers_only_suffix(self) -> None:
        """Test class name ending with numbers."""

        class Config2(DotEnvConfig):
            # Single word (Config2) -> no prefix
            value: str = Field()

        config = Config2.load_from_dict({"VALUE": "test"})
        assert config.value == "test"

    def test_field_name_with_underscores(self) -> None:
        """Test field names that already have underscores."""

        class AppConfig(DotEnvConfig):
            database_connection_string: str = Field()

        config = AppConfig.load_from_dict({
            "APP_DATABASE_CONNECTION_STRING": "postgres://localhost"
        })
        assert config.database_connection_string == "postgres://localhost"

    def test_multiple_configs_different_auto_prefixes(self) -> None:
        """Test multiple config classes get their own auto-prefixes."""

        class DatabaseConfig(DotEnvConfig):
            host: str = Field()

        class RedisConfig(DotEnvConfig):
            host: str = Field()

        class AppConfig(DotEnvConfig):
            debug: bool = Field(default=False)

        db = DatabaseConfig.load_from_dict({"DATABASE_HOST": "db.local"})
        redis = RedisConfig.load_from_dict({"REDIS_HOST": "redis.local"})
        app = AppConfig.load_from_dict({"APP_DEBUG": "true"})

        assert db.host == "db.local"
        assert redis.host == "redis.local"
        assert app.debug is True

    def test_load_from_dict_fallback_to_field_name(self) -> None:
        """Test load_from_dict falls back to field name if prefixed not found."""

        class AppConfig(DotEnvConfig):
            # Auto-prefix: APP_
            host: str = Field()

        # Using field name directly (fallback behavior)
        config = AppConfig.load_from_dict({"host": "localhost"})
        assert config.host == "localhost"

    def test_load_from_dict_prefers_prefixed_over_field_name(self) -> None:
        """Test load_from_dict prefers prefixed env var over field name."""

        class AppConfig(DotEnvConfig):
            host: str = Field()

        # Both provided - prefixed should win
        config = AppConfig.load_from_dict({
            "APP_HOST": "prefixed",
            "host": "field_name",
        })
        assert config.host == "prefixed"
