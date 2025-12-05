"""Tests for Json type, Optional types, and Literal types."""

from typing import Literal

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    TypeCoercionError,
)
from dotenvmodel.types import Json


class TestJsonType:
    """Test Json[T] type."""

    def test_json_dict(self) -> None:
        """Test Json[dict] parsing."""

        class Config(DotEnvConfig):
            feature_flags: Json[dict[str, bool]] = Field()

        config = Config.load_from_dict({"FEATURE_FLAGS": '{"new_ui": true, "beta_api": false}'})
        assert config.feature_flags == {"new_ui": True, "beta_api": False}
        assert isinstance(config.feature_flags, dict)

    def test_json_list(self) -> None:
        """Test Json[list] parsing."""

        class Config(DotEnvConfig):
            allowed_roles: Json[list[str]] = Field()

        config = Config.load_from_dict({"ALLOWED_ROLES": '["admin", "user", "guest"]'})
        assert config.allowed_roles == ["admin", "user", "guest"]
        assert isinstance(config.allowed_roles, list)

    def test_json_nested_structure(self) -> None:
        """Test Json with nested structure."""

        class Config(DotEnvConfig):
            service_config: Json[dict[str, dict[str, str]]] = Field()

        config = Config.load_from_dict(
            {"SERVICE_CONFIG": '{"db": {"host": "localhost", "port": "5432"}}'}
        )
        assert config.service_config == {"db": {"host": "localhost", "port": "5432"}}

    def test_json_invalid_format(self) -> None:
        """Test Json with invalid JSON."""

        class Config(DotEnvConfig):
            data: Json[dict] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATA": "not valid json"})

        assert "Invalid JSON format" in str(exc_info.value)

    def test_json_type_mismatch_dict(self) -> None:
        """Test Json type mismatch - expected dict, got list."""

        class Config(DotEnvConfig):
            config: Json[dict] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"CONFIG": "[1, 2, 3]"})

        assert "Expected JSON object (dict)" in str(exc_info.value)

    def test_json_type_mismatch_list(self) -> None:
        """Test Json type mismatch - expected list, got dict."""

        class Config(DotEnvConfig):
            items: Json[list] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"ITEMS": '{"key": "value"}'})

        assert "Expected JSON array (list)" in str(exc_info.value)


class TestOptionalTypes:
    """Test Optional type handling."""

    def test_optional_str_with_value(self) -> None:
        """Test optional string with value."""

        class Config(DotEnvConfig):
            name: str | None = Field()

        config = Config.load_from_dict({"NAME": "test"})
        assert config.name == "test"

    def test_optional_str_without_value(self) -> None:
        """Test optional string without value (auto None)."""

        class Config(DotEnvConfig):
            name: str | None = Field()

        config = Config.load_from_dict({})
        assert config.name is None

    def test_optional_int(self) -> None:
        """Test optional int."""

        class Config(DotEnvConfig):
            port: int | None = Field()

        # With value
        config = Config.load_from_dict({"PORT": "8000"})
        assert config.port == 8000

        # Without value
        config = Config.load_from_dict({})
        assert config.port is None

    def test_optional_using_typing_optional(self) -> None:
        """Test Optional using typing.Optional."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        config = Config.load_from_dict({})
        assert config.value is None

    def test_optional_with_explicit_default(self) -> None:
        """Test Optional with explicit default value."""

        class Config(DotEnvConfig):
            name: str | None = Field(default="default-name")

        config = Config.load_from_dict({})
        assert config.name == "default-name"

    def test_optional_empty_string(self) -> None:
        """Test optional field with empty string."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value is None

    def test_optional_list(self) -> None:
        """Test optional list."""

        class Config(DotEnvConfig):
            items: list[str] | None = Field()

        # With value
        config = Config.load_from_dict({"ITEMS": "a,b,c"})
        assert config.items == ["a", "b", "c"]

        # Without value
        config = Config.load_from_dict({})
        assert config.items is None

    def test_optional_with_validation(self) -> None:
        """Test Optional field with validation constraints."""

        class Config(DotEnvConfig):
            port: int | None = Field(ge=1, le=65535)

        # Valid value
        config = Config.load_from_dict({"PORT": "8000"})
        assert config.port == 8000

        # None is valid
        config = Config.load_from_dict({})
        assert config.port is None

        # Invalid value still raises
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORT": "99999"})


class TestLiteralType:
    """Test Literal type handling."""

    def test_literal_string(self) -> None:
        """Test Literal with string values."""

        class Config(DotEnvConfig):
            environment: Literal["dev", "test", "staging", "prod"] = Field()

        config = Config.load_from_dict({"ENVIRONMENT": "prod"})
        assert config.environment == "prod"

    def test_literal_invalid_value(self) -> None:
        """Test Literal with invalid value."""

        class Config(DotEnvConfig):
            env: Literal["dev", "test", "prod"] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"ENV": "staging"})

        assert "must be one of" in str(exc_info.value).lower()

    def test_literal_with_default(self) -> None:
        """Test Literal with default value."""

        class Config(DotEnvConfig):
            log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

        config = Config.load_from_dict({})
        assert config.log_level == "INFO"

    def test_literal_required_field_missing(self) -> None:
        """Test Literal field that is required and missing."""
        from dotenvmodel import MissingFieldError

        class Config(DotEnvConfig):
            mode: Literal["fast", "slow"] = Field()

        with pytest.raises(MissingFieldError):
            Config.load_from_dict({})


class TestEmptyStringHandling:
    """Test empty string handling for various types."""

    def test_empty_string_to_none_for_int(self) -> None:
        """Test empty string converts to None for int."""

        class Config(DotEnvConfig):
            value: int | None = Field()

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value is None

    def test_empty_string_for_bool_is_false(self) -> None:
        """Test empty string is False for bool."""

        class Config(DotEnvConfig):
            flag: bool = Field()

        config = Config.load_from_dict({"FLAG": ""})
        assert config.flag is False

    def test_empty_string_for_required_int_fails(self) -> None:
        """Test empty string for required int field fails."""

        class Config(DotEnvConfig):
            count: int = Field()

        # Empty string should result in None, which fails validation for required field
        from dotenvmodel import MissingFieldError

        with pytest.raises(MissingFieldError):
            Config.load_from_dict({"COUNT": ""})

    def test_empty_string_for_list(self) -> None:
        """Test empty string returns empty list."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        config = Config.load_from_dict({"ITEMS": ""})
        assert config.items == []

    def test_empty_string_for_dict(self) -> None:
        """Test empty string returns empty dict."""

        class Config(DotEnvConfig):
            headers: dict[str, str] = Field()

        config = Config.load_from_dict({"HEADERS": ""})
        assert config.headers == {}

    def test_empty_string_for_set(self) -> None:
        """Test empty string returns empty set."""

        class Config(DotEnvConfig):
            tags: set[str] = Field()

        config = Config.load_from_dict({"TAGS": ""})
        assert config.tags == set()


class TestCollectionValidation:
    """Test collection size validation (min_items, max_items)."""

    def test_list_min_items(self) -> None:
        """Test list min_items validation."""

        class Config(DotEnvConfig):
            allowed_ips: list[str] = Field(min_items=1)

        # Valid - has items
        config = Config.load_from_dict({"ALLOWED_IPS": "192.168.1.1,10.0.0.1"})
        assert len(config.allowed_ips) == 2

        # Invalid - empty
        # Note: min_items/max_items not yet implemented in validation.py
        # This test documents expected behavior

    def test_list_max_items(self) -> None:
        """Test list max_items validation."""

        class Config(DotEnvConfig):
            backup_servers: list[str] = Field(max_items=10)

        # Valid - within limit
        config = Config.load_from_dict({"BACKUP_SERVERS": "server1,server2,server3"})
        assert len(config.backup_servers) == 3

        # Note: max_items validation not yet implemented
