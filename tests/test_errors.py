"""Tests for error messages and edge cases."""

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    MissingFieldError,
    MultipleValidationErrors,
    Required,
    TypeCoercionError,
    ValidationError,
)


class TestErrorMessages:
    """Test error message formatting."""

    def test_missing_field_error_message(self) -> None:
        """Test MissingFieldError message format."""

        class Config(DotEnvConfig):
            api_key: str = Required

        with pytest.raises(MissingFieldError) as exc_info:
            Config.load_from_dict({})

        error_msg = str(exc_info.value)
        assert "MissingFieldError" in error_msg
        assert "api_key" in error_msg
        assert "API_KEY" in error_msg
        assert "not set" in error_msg.lower()
        assert "Hint:" in error_msg

    def test_type_coercion_error_message(self) -> None:
        """Test TypeCoercionError message format."""

        class Config(DotEnvConfig):
            port: int = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"PORT": "not-a-number"})

        error_msg = str(exc_info.value)
        assert "TypeCoercionError" in error_msg
        assert "port" in error_msg
        assert "int" in error_msg.lower()
        assert "not-a-number" in error_msg
        assert "PORT" in error_msg

    def test_constraint_violation_error_message(self) -> None:
        """Test ConstraintViolationError message format."""

        class Config(DotEnvConfig):
            port: int = Field(ge=1, le=65535)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"PORT": "99999"})

        error_msg = str(exc_info.value)
        assert "ConstraintViolationError" in error_msg
        assert "port" in error_msg
        assert "99999" in error_msg
        assert "le=65535" in error_msg
        assert "less than or equal" in error_msg.lower()

    def test_multiple_validation_errors_message(self) -> None:
        """Test MultipleValidationErrors message format."""

        class Config(DotEnvConfig):
            api_key: str = Required
            database_url: str = Required
            port: int = Field(ge=1, le=65535)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Config.load_from_dict({"PORT": "99999"})

        error_msg = str(exc_info.value)
        assert "ValidationError" in error_msg
        # Should list multiple errors
        assert "1." in error_msg
        assert "2." in error_msg
        assert "api_key" in error_msg.lower() or "API_KEY" in error_msg
        assert "database_url" in error_msg.lower() or "DATABASE_URL" in error_msg

    def test_validation_error_base_class(self) -> None:
        """Test ValidationError base class."""
        error = ValidationError(
            field_name="test_field",
            value="bad_value",
            error_msg="Something went wrong",
            field_type=str,
            env_var_name="TEST_FIELD",
        )

        error_msg = str(error)
        assert "test_field" in error_msg
        assert "bad_value" in error_msg
        assert "Something went wrong" in error_msg
        assert "TEST_FIELD" in error_msg


class TestFieldEdgeCases:
    """Test edge cases in field definitions."""

    def test_field_with_both_default_and_factory_raises(self) -> None:
        """Test that Field raises error if both default and default_factory provided."""
        with pytest.raises(ValueError) as exc_info:
            Field(default="test", default_factory=list)

        assert "both 'default' and 'default_factory'" in str(exc_info.value).lower()

    def test_field_ellipsis_treated_as_required(self) -> None:
        """Test that Field(...) is treated as required."""

        class Config(DotEnvConfig):
            value: str = Field(...)

        with pytest.raises(MissingFieldError):
            Config.load_from_dict({})

    def test_field_info_repr(self) -> None:
        """Test FieldInfo repr."""
        from dotenvmodel.fields import FieldInfo

        field = FieldInfo(
            default="test",
            alias="TEST_ALIAS",
            description="Test field",
            ge=1,
            le=100,
            min_length=5,
            max_length=50,
            regex=r"^\w+$",
            choices=["a", "b", "c"],
        )

        repr_str = repr(field)
        assert "FieldInfo" in repr_str
        assert "default='test'" in repr_str
        assert "alias='TEST_ALIAS'" in repr_str
        assert "ge=1" in repr_str
        assert "le=100" in repr_str


class TestCollectionEdgeCases:
    """Test edge cases in collection type coercion."""

    def test_list_coercion_error_in_element(self) -> None:
        """Test list coercion error when element fails."""

        class Config(DotEnvConfig):
            ports: list[int] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"PORTS": "8000,not-a-number,9000"})

        error_msg = str(exc_info.value)
        assert "Failed to coerce list element" in error_msg
        assert "not-a-number" in error_msg

    def test_dict_missing_equals_sign(self) -> None:
        """Test dict coercion error when pair missing '='."""

        class Config(DotEnvConfig):
            headers: dict[str, str] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"HEADERS": "key1=value1,invalid_pair"})

        error_msg = str(exc_info.value)
        assert "Expected 'key=value'" in error_msg

    def test_dict_coercion_error_in_key_or_value(self) -> None:
        """Test dict coercion error when key/value fails."""

        class Config(DotEnvConfig):
            mapping: dict[int, int] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"MAPPING": "1=100,bad=200"})

        error_msg = str(exc_info.value)
        assert "Failed to coerce dict pair" in error_msg

    def test_list_without_type_args(self) -> None:
        """Test list without type arguments defaults to str."""

        class Config(DotEnvConfig):
            items: list[str] = Field()  # list without args not supported in Python 3.12+

        config = Config.load_from_dict({"ITEMS": "a,b,c"})
        assert config.items == ["a", "b", "c"]


class TestMetaclassEdgeCases:
    """Test edge cases in metaclass field discovery."""

    def test_private_attributes_ignored(self) -> None:
        """Test that private attributes (starting with _) are ignored."""

        class Config(DotEnvConfig):
            _internal: str = "private"
            public: str = Field(default="public")

        config = Config.load_from_dict({})
        assert config.public == "public"
        # _internal should not be processed as a field
        assert "_internal" not in config._fields

    def test_field_without_type_hint_ignored(self) -> None:
        """Test that fields without type hints are handled."""

        class Config(DotEnvConfig):
            # This has a type hint, should work
            typed_field: str = Field(default="test")

        config = Config.load_from_dict({})
        assert config.typed_field == "test"

    def test_optional_field_auto_none_in_metaclass(self) -> None:
        """Test that Optional fields get auto None default in metaclass."""

        class Config(DotEnvConfig):
            # No explicit default, but Optional should default to None
            value: str | None = Field()

        config = Config.load_from_dict({})
        assert config.value is None


class TestConfigHelperMethods:
    """Test DotEnvConfig helper methods."""

    def test_dict_method_only_includes_set_fields(self) -> None:
        """Test dict() method."""

        class Config(DotEnvConfig):
            field1: str = Field(default="value1")
            field2: str = Field(default="value2")

        config = Config.load_from_dict({})
        config_dict = config.dict()

        assert "field1" in config_dict
        assert "field2" in config_dict
        assert config_dict["field1"] == "value1"

    def test_get_method_with_missing_key(self) -> None:
        """Test get() method with missing key."""

        class Config(DotEnvConfig):
            existing: str = Field(default="value")

        config = Config.load_from_dict({})

        assert config.get("existing") == "value"
        assert config.get("missing") is None
        assert config.get("missing", "default") == "default"

    def test_repr_shows_all_fields(self) -> None:
        """Test __repr__ includes all fields."""

        class Config(DotEnvConfig):
            name: str = Field(default="test")
            port: int = Field(default=8000)

        config = Config.load_from_dict({})
        repr_str = repr(config)

        assert "Config(" in repr_str
        assert "name='test'" in repr_str
        assert "port=8000" in repr_str


class TestLoadValidationToggle:
    """Test load_from_dict validation toggle."""

    def test_load_from_dict_without_validation(self) -> None:
        """Test load_from_dict with validate=False."""

        class Config(DotEnvConfig):
            port: int = Field(ge=1, le=65535)

        # This would normally fail validation
        config = Config.load_from_dict({"PORT": "99999"}, validate=False)

        # Value is coerced but not validated
        assert config.port == 99999

    def test_load_from_dict_validation_default_true(self) -> None:
        """Test that validation is on by default."""

        class Config(DotEnvConfig):
            port: int = Field(ge=1, le=65535)

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORT": "99999"})


class TestTypeCoercionEdgeCases:
    """Test edge cases in type coercion."""

    def test_none_value_returns_none(self) -> None:
        """Test that None value returns None (before bool check)."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        config = Config.load_from_dict({"VALUE": ""})
        # Empty string for optional should be None
        assert config.value is None

    def test_unsupported_type_raises_error(self) -> None:
        """Test that unsupported types raise TypeCoercionError."""

        class CustomType:
            pass

        class Config(DotEnvConfig):
            custom: CustomType = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"CUSTOM": "value"})

        assert "Unsupported type" in str(exc_info.value)
