"""Tests for type coercion logic."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest

from dotenvmodel import DotEnvConfig, Field, TypeCoercionError
from dotenvmodel.coercion import (
    _coerce_bool,
    _coerce_dict,
    _coerce_generic,
    _coerce_list,
    _coerce_literal,
    _coerce_set,
    _coerce_tuple,
    coerce_value,
)
from dotenvmodel.types import HttpUrl, Json, PostgresDsn, RedisDsn, SecretStr


class TestCoerceValue:
    """Tests for the main coerce_value function."""

    def test_coerce_none_value_returns_none(self) -> None:
        """Test that None value returns None for non-collection types."""
        result = coerce_value("test_field", None, str, "TEST_FIELD")
        assert result is None

    def test_coerce_empty_string_to_none_for_int(self) -> None:
        """Test that empty string becomes None for int type."""
        result = coerce_value("test_field", "", int, "TEST_FIELD")
        assert result is None

    def test_coerce_empty_string_to_none_for_float(self) -> None:
        """Test that empty string becomes None for float type."""
        result = coerce_value("test_field", "", float, "TEST_FIELD")
        assert result is None

    def test_coerce_string_type(self) -> None:
        """Test coercing to string type."""
        result = coerce_value("test_field", "hello", str, "TEST_FIELD")
        assert result == "hello"

    def test_coerce_int_type(self) -> None:
        """Test coercing to int type."""
        result = coerce_value("test_field", "123", int, "TEST_FIELD")
        assert result == 123
        assert isinstance(result, int)

    def test_coerce_int_type_invalid(self) -> None:
        """Test coercing invalid int raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            coerce_value("test_field", "not_a_number", int, "TEST_FIELD")
        assert "TEST_FIELD" in str(exc_info.value)

    def test_coerce_float_type(self) -> None:
        """Test coercing to float type."""
        result = coerce_value("test_field", "123.45", float, "TEST_FIELD")
        assert result == 123.45
        assert isinstance(result, float)

    def test_coerce_float_type_invalid(self) -> None:
        """Test coercing invalid float raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            coerce_value("test_field", "not_a_float", float, "TEST_FIELD")
        assert "TEST_FIELD" in str(exc_info.value)

    def test_coerce_bool_true(self) -> None:
        """Test coercing to bool True."""
        for value in ["true", "1", "yes", "on", "t", "y", "TRUE", "YES"]:
            result = coerce_value("test_field", value, bool, "TEST_FIELD")
            assert result is True

    def test_coerce_bool_false(self) -> None:
        """Test coercing to bool False."""
        for value in ["false", "0", "no", "off", "f", "n", "", "FALSE", "NO"]:
            result = coerce_value("test_field", value, bool, "TEST_FIELD")
            assert result is False

    def test_coerce_path_type(self) -> None:
        """Test coercing to Path type."""
        result = coerce_value("test_field", "/tmp/test", Path, "TEST_FIELD")
        assert result == Path("/tmp/test")
        assert isinstance(result, Path)

    def test_coerce_uuid_type(self) -> None:
        """Test coercing to UUID type."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = coerce_value("test_field", uuid_str, UUID, "TEST_FIELD")
        assert isinstance(result, UUID)
        assert str(result) == uuid_str

    def test_coerce_decimal_type(self) -> None:
        """Test coercing to Decimal type."""
        result = coerce_value("test_field", "123.45", Decimal, "TEST_FIELD")
        assert isinstance(result, Decimal)
        assert result == Decimal("123.45")

    def test_coerce_datetime_type(self) -> None:
        """Test coercing to datetime type."""
        result = coerce_value("test_field", "2024-01-15T10:30:00", datetime, "TEST_FIELD")
        assert isinstance(result, datetime)

    def test_coerce_timedelta_type(self) -> None:
        """Test coercing to timedelta type."""
        result = coerce_value("test_field", "3600", timedelta, "TEST_FIELD")
        assert isinstance(result, timedelta)
        assert result.total_seconds() == 3600

    def test_coerce_optional_with_value(self) -> None:
        """Test coercing Optional type with value."""
        result = coerce_value("test_field", "123", int | None, "TEST_FIELD")
        assert result == 123

    def test_coerce_optional_with_none(self) -> None:
        """Test coercing Optional type with None."""
        result = coerce_value("test_field", None, int | None, "TEST_FIELD")
        assert result is None

    def test_coerce_optional_with_empty_string(self) -> None:
        """Test coercing Optional type with empty string."""
        result = coerce_value("test_field", "", int | None, "TEST_FIELD")
        assert result is None

    def test_coerce_list_str(self) -> None:
        """Test coercing to list[str]."""
        result = coerce_value("test_field", "a,b,c", list[str], "TEST_FIELD")
        assert result == ["a", "b", "c"]

    def test_coerce_list_int(self) -> None:
        """Test coercing to list[int]."""
        result = coerce_value("test_field", "1,2,3", list[int], "TEST_FIELD")
        assert result == [1, 2, 3]

    def test_coerce_set_str(self) -> None:
        """Test coercing to set[str]."""
        result = coerce_value("test_field", "a,b,c", set[str], "TEST_FIELD")
        assert result == {"a", "b", "c"}

    def test_coerce_tuple_str(self) -> None:
        """Test coercing to tuple[str, ...]."""
        result = coerce_value("test_field", "a,b,c", tuple[str, ...], "TEST_FIELD")
        assert result == ("a", "b", "c")

    def test_coerce_dict_str_str(self) -> None:
        """Test coercing to dict[str, str]."""
        result = coerce_value("test_field", "key1=val1,key2=val2", dict[str, str], "TEST_FIELD")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_coerce_literal_type(self) -> None:
        """Test coercing to Literal type."""
        result = coerce_value("test_field", "dev", Literal["dev", "prod"], "TEST_FIELD")
        assert result == "dev"

    def test_coerce_unsupported_type(self) -> None:
        """Test coercing to unsupported type raises error."""

        class CustomType:
            pass

        with pytest.raises(TypeCoercionError) as exc_info:
            coerce_value("test_field", "value", CustomType, "TEST_FIELD")
        assert "Unsupported type" in str(exc_info.value)

    def test_coerce_secret_str_type(self) -> None:
        """Test coercing to SecretStr type."""
        result = coerce_value("test_field", "secret_password", SecretStr, "TEST_FIELD")
        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "secret_password"

    def test_coerce_http_url_type(self) -> None:
        """Test coercing to HttpUrl type."""
        result = coerce_value("test_field", "https://example.com", HttpUrl, "TEST_FIELD")
        assert isinstance(result, HttpUrl)

    def test_coerce_http_url_invalid(self) -> None:
        """Test coercing invalid HttpUrl raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            coerce_value("test_field", "not-a-url", HttpUrl, "TEST_FIELD")
        assert "TEST_FIELD" in str(exc_info.value)

    def test_coerce_postgres_dsn_type(self) -> None:
        """Test coercing to PostgresDsn type."""
        result = coerce_value(
            "test_field",
            "postgresql://user:pass@localhost/db",
            PostgresDsn,
            "TEST_FIELD",
        )
        assert isinstance(result, PostgresDsn)

    def test_coerce_postgres_dsn_invalid(self) -> None:
        """Test coercing invalid PostgresDsn raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            coerce_value("test_field", "not-a-dsn", PostgresDsn, "TEST_FIELD")
        assert "TEST_FIELD" in str(exc_info.value)

    def test_coerce_redis_dsn_type(self) -> None:
        """Test coercing to RedisDsn type."""
        result = coerce_value("test_field", "redis://localhost:6379/0", RedisDsn, "TEST_FIELD")
        assert isinstance(result, RedisDsn)

    def test_coerce_redis_dsn_invalid(self) -> None:
        """Test coercing invalid RedisDsn raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            coerce_value("test_field", "not-a-dsn", RedisDsn, "TEST_FIELD")
        assert "TEST_FIELD" in str(exc_info.value)

    def test_coerce_json_type(self) -> None:
        """Test coercing to Json type."""
        result = coerce_value("test_field", '{"key": "value"}', Json[dict], "TEST_FIELD")
        assert result == {"key": "value"}


class TestCoerceBool:
    """Tests for _coerce_bool function."""

    def test_coerce_bool_true_values(self) -> None:
        """Test all true boolean values."""
        true_values = ["true", "1", "yes", "on", "t", "y", "TRUE", "Yes", "ON"]
        for value in true_values:
            result = _coerce_bool("field", value, "ENV_VAR")
            assert result is True, f"Failed for value: {value}"

    def test_coerce_bool_false_values(self) -> None:
        """Test all false boolean values."""
        false_values = ["false", "0", "no", "off", "f", "n", "", "FALSE", "No", "OFF"]
        for value in false_values:
            result = _coerce_bool("field", value, "ENV_VAR")
            assert result is False, f"Failed for value: {value}"

    def test_coerce_bool_with_whitespace(self) -> None:
        """Test boolean coercion strips whitespace."""
        assert _coerce_bool("field", "  true  ", "ENV_VAR") is True
        assert _coerce_bool("field", "  false  ", "ENV_VAR") is False

    def test_coerce_bool_invalid_value(self) -> None:
        """Test invalid boolean value raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_bool("field", "invalid", "ENV_VAR")
        assert "Invalid boolean value" in str(exc_info.value)


class TestCoerceLiteral:
    """Tests for _coerce_literal function."""

    def test_coerce_literal_valid_value(self) -> None:
        """Test coercing valid literal value."""
        result = _coerce_literal("field", "dev", Literal["dev", "staging", "prod"], "ENV_VAR")
        assert result == "dev"

    def test_coerce_literal_invalid_value(self) -> None:
        """Test coercing invalid literal value raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_literal("field", "invalid", Literal["dev", "prod"], "ENV_VAR")
        assert "must be one of" in str(exc_info.value)

    def test_coerce_literal_none_value(self) -> None:
        """Test coercing None to literal raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_literal("field", None, Literal["dev", "prod"], "ENV_VAR")
        assert "cannot be None" in str(exc_info.value)


class TestCoerceGeneric:
    """Tests for _coerce_generic function."""

    def test_coerce_generic_empty_list(self) -> None:
        """Test coercing empty string to list."""
        result = _coerce_generic("field", "", list[str], list, "ENV_VAR")
        assert result == []

    def test_coerce_generic_none_list(self) -> None:
        """Test coercing None to list."""
        result = _coerce_generic("field", None, list[str], list, "ENV_VAR")
        assert result == []

    def test_coerce_generic_empty_set(self) -> None:
        """Test coercing empty string to set."""
        result = _coerce_generic("field", "", set[str], set, "ENV_VAR")
        assert result == set()

    def test_coerce_generic_empty_tuple(self) -> None:
        """Test coercing empty string to tuple."""
        result = _coerce_generic("field", "", tuple[str, ...], tuple, "ENV_VAR")
        assert result == ()

    def test_coerce_generic_empty_dict(self) -> None:
        """Test coercing empty string to dict."""
        result = _coerce_generic("field", "", dict[str, str], dict, "ENV_VAR")
        assert result == {}

    def test_coerce_generic_unsupported_type(self) -> None:
        """Test coercing to unsupported generic type raises error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_generic("field", "value", frozenset[str], frozenset, "ENV_VAR")
        assert "Unsupported generic type" in str(exc_info.value)

    def test_coerce_generic_unsupported_type_with_none(self) -> None:
        """Test coercing None to unsupported generic type returns None."""
        result = _coerce_generic("field", None, frozenset[str], frozenset, "ENV_VAR")
        assert result is None


class TestCoerceList:
    """Tests for _coerce_list function."""

    def test_coerce_list_empty_string(self) -> None:
        """Test coercing empty string returns empty list."""
        result = _coerce_list("field", "", (str,), "ENV_VAR")
        assert result == []

    def test_coerce_list_no_type_args(self) -> None:
        """Test coercing list without type arguments."""
        result = _coerce_list("field", "a,b,c", (), "ENV_VAR")
        assert result == ["a", "b", "c"]

    def test_coerce_list_with_custom_separator(self) -> None:
        """Test coercing list with custom separator."""
        result = _coerce_list("field", "a|b|c", (str,), "ENV_VAR", separator="|")
        assert result == ["a", "b", "c"]

    def test_coerce_list_with_whitespace(self) -> None:
        """Test coercing list strips whitespace."""
        result = _coerce_list("field", " a , b , c ", (str,), "ENV_VAR")
        assert result == ["a", "b", "c"]

    def test_coerce_list_element_coercion_error(self) -> None:
        """Test list element coercion error."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_list("field", "1,2,invalid", (int,), "ENV_VAR")
        assert "Failed to coerce list element" in str(exc_info.value)


class TestCoerceSet:
    """Tests for _coerce_set function."""

    def test_coerce_set_deduplication(self) -> None:
        """Test set deduplicates values."""
        result = _coerce_set("field", "a,b,a,c,b", (str,), "ENV_VAR")
        assert result == {"a", "b", "c"}

    def test_coerce_set_empty(self) -> None:
        """Test coercing empty string to set."""
        result = _coerce_set("field", "", (str,), "ENV_VAR")
        assert result == set()


class TestCoerceTuple:
    """Tests for _coerce_tuple function."""

    def test_coerce_tuple_basic(self) -> None:
        """Test coercing to tuple."""
        result = _coerce_tuple("field", "a,b,c", (str,), "ENV_VAR")
        assert result == ("a", "b", "c")
        assert isinstance(result, tuple)

    def test_coerce_tuple_empty(self) -> None:
        """Test coercing empty string to tuple."""
        result = _coerce_tuple("field", "", (str,), "ENV_VAR")
        assert result == ()


class TestCoerceDict:
    """Tests for _coerce_dict function."""

    def test_coerce_dict_empty_string(self) -> None:
        """Test coercing empty string returns empty dict."""
        result = _coerce_dict("field", "", (str, str), "ENV_VAR")
        assert result == {}

    def test_coerce_dict_basic(self) -> None:
        """Test coercing basic dict."""
        result = _coerce_dict("field", "key1=val1,key2=val2", (str, str), "ENV_VAR")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_coerce_dict_with_whitespace(self) -> None:
        """Test dict coercion strips whitespace."""
        result = _coerce_dict("field", " key1 = val1 , key2 = val2 ", (str, str), "ENV_VAR")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_coerce_dict_with_equals_in_value(self) -> None:
        """Test dict coercion handles equals sign in value."""
        result = _coerce_dict("field", "key=val=with=equals", (str, str), "ENV_VAR")
        assert result == {"key": "val=with=equals"}

    def test_coerce_dict_typed_keys_values(self) -> None:
        """Test dict coercion with typed keys and values."""
        result = _coerce_dict("field", "1=10,2=20,3=30", (int, int), "ENV_VAR")
        assert result == {1: 10, 2: 20, 3: 30}

    def test_coerce_dict_missing_equals(self) -> None:
        """Test dict coercion error when equals sign missing."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_dict("field", "key1=val1,invalid", (str, str), "ENV_VAR")
        assert "Invalid dict format" in str(exc_info.value)
        assert "Expected 'key=value'" in str(exc_info.value)

    def test_coerce_dict_coercion_error(self) -> None:
        """Test dict coercion error in key or value."""
        with pytest.raises(TypeCoercionError) as exc_info:
            _coerce_dict("field", "1=10,invalid=20", (int, int), "ENV_VAR")
        assert "Failed to coerce dict pair" in str(exc_info.value)

    def test_coerce_dict_no_type_args(self) -> None:
        """Test dict coercion without type arguments defaults to str."""
        result = _coerce_dict("field", "key=val", (), "ENV_VAR")
        assert result == {"key": "val"}

    def test_coerce_dict_partial_type_args(self) -> None:
        """Test dict coercion with only key type specified."""
        result = _coerce_dict("field", "key=val", (str,), "ENV_VAR")
        assert result == {"key": "val"}


class TestCoercionIntegration:
    """Integration tests for coercion with DotEnvConfig."""

    def test_coerce_in_config_context(self) -> None:
        """Test coercion works correctly in config context."""

        class Config(DotEnvConfig):
            name: str = Field()
            count: int = Field()
            enabled: bool = Field()
            tags: list[str] = Field()

        config = Config.load_from_dict(
            {
                "NAME": "test",
                "COUNT": "42",
                "ENABLED": "true",
                "TAGS": "tag1,tag2,tag3",
            }
        )

        assert config.name == "test"
        assert config.count == 42
        assert config.enabled is True
        assert config.tags == ["tag1", "tag2", "tag3"]

    def test_coerce_optional_fields(self) -> None:
        """Test coercion of optional fields."""

        class Config(DotEnvConfig):
            required: str = Field()
            optional_str: str | None = Field(default=None)
            optional_int: int | None = Field(default=None)

        config = Config.load_from_dict(
            {"REQUIRED": "value", "OPTIONAL_STR": "", "OPTIONAL_INT": ""}
        )

        assert config.required == "value"
        assert config.optional_str is None
        assert config.optional_int is None

    def test_coerce_with_custom_separator(self) -> None:
        """Test coercion with custom separator."""

        class Config(DotEnvConfig):
            items: list[str] = Field(separator="|")

        config = Config.load_from_dict({"ITEMS": "item1|item2|item3"})
        assert config.items == ["item1", "item2", "item3"]

    def test_coerce_complex_nested_types(self) -> None:
        """Test coercion of complex nested types."""

        class Config(DotEnvConfig):
            ports: list[int] = Field()
            settings: dict[str, int] = Field()

        config = Config.load_from_dict(
            {"PORTS": "8000,8001,8002", "SETTINGS": "timeout=30,retries=3"}
        )

        assert config.ports == [8000, 8001, 8002]
        assert config.settings == {"timeout": 30, "retries": 3}
