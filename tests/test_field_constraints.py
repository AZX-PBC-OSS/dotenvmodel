"""Tests for Field constraint parameter validation."""

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.fields import _MISSING, FieldInfo


class TestFieldConstraintValidation:
    """Test that Field() validates constraint parameters."""

    def test_ge_greater_than_le(self) -> None:
        """Test that ge > le raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(ge=10, le=5)

        assert "ge" in str(exc_info.value)
        assert "le" in str(exc_info.value)
        assert "cannot be greater than" in str(exc_info.value).lower()

    def test_gt_greater_than_or_equal_lt(self) -> None:
        """Test that gt >= lt raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(gt=10, lt=10)

        assert "gt" in str(exc_info.value)
        assert "lt" in str(exc_info.value)
        assert "must be less than" in str(exc_info.value).lower()

    def test_min_length_greater_than_max_length(self) -> None:
        """Test that min_length > max_length raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(min_length=10, max_length=5)

        assert "min_length" in str(exc_info.value)
        assert "max_length" in str(exc_info.value)
        assert "cannot be greater than" in str(exc_info.value).lower()

    def test_min_items_greater_than_max_items(self) -> None:
        """Test that min_items > max_items raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(min_items=10, max_items=5)

        assert "min_items" in str(exc_info.value)
        assert "max_items" in str(exc_info.value)
        assert "cannot be greater than" in str(exc_info.value).lower()

    def test_invalid_numeric_constraint_type(self) -> None:
        """Test that non-numeric ge/le/gt/lt values raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            Field(ge="10")

        assert "ge" in str(exc_info.value)
        assert "int, float, or Decimal" in str(exc_info.value)

    def test_negative_min_length(self) -> None:
        """Test that negative min_length raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(min_length=-1)

        assert "min_length" in str(exc_info.value)
        assert "non-negative" in str(exc_info.value).lower()

    def test_negative_min_items(self) -> None:
        """Test that negative min_items raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(min_items=-1)

        assert "min_items" in str(exc_info.value)
        assert "non-negative" in str(exc_info.value).lower()

    def test_invalid_uuid_version(self) -> None:
        """Test that invalid UUID version raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(uuid_version=6)

        assert "uuid_version" in str(exc_info.value)
        assert "1, 3, 4, or 5" in str(exc_info.value)

    def test_invalid_regex_pattern(self) -> None:
        """Test that invalid regex pattern raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(regex="[invalid(regex")

        assert "regex" in str(exc_info.value).lower()
        assert "invalid" in str(exc_info.value).lower()

    def test_both_default_and_default_factory(self) -> None:
        """Test that specifying both default and default_factory raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Field(default="value", default_factory=lambda: "value")

        assert "default" in str(exc_info.value).lower()
        assert "default_factory" in str(exc_info.value).lower()

    def test_valid_constraints(self) -> None:
        """Test that valid constraints are accepted."""
        # These should all succeed
        Field(ge=5, le=10)
        Field(gt=5, lt=10)
        Field(min_length=5, max_length=10)
        Field(min_items=1, max_items=5)
        Field(uuid_version=4)
        Field(regex=r"^\d+$")
        Field(default="test")
        Field(default_factory=list)

    def test_equal_ge_le(self) -> None:
        """Test that ge == le is valid."""
        # Should succeed - allows only one value
        Field(ge=5, le=5)

    def test_decimal_constraints(self) -> None:
        """Test that Decimal values work for numeric constraints."""
        from decimal import Decimal

        # Should succeed
        Field(ge=Decimal("0"), le=Decimal("1"))
        Field(gt=Decimal("0"), lt=Decimal("1"))


class TestFieldInfoMethods:
    """Test FieldInfo methods."""

    def test_get_default_when_default_is_missing(self) -> None:
        """Test FieldInfo.get_default() when default is _MISSING."""
        field_info = FieldInfo()  # No default provided
        assert field_info.default is _MISSING
        assert field_info.get_default() is _MISSING

    def test_has_default_property(self) -> None:
        """Test FieldInfo.has_default property."""
        # Field with default
        field_with_default = FieldInfo(default="value")
        assert field_with_default.has_default is True

        # Field with default_factory
        field_with_factory = FieldInfo(default_factory=list)
        assert field_with_factory.has_default is True

        # Required field (no default)
        required_field = FieldInfo()
        assert required_field.has_default is False

    def test_field_info_get_default_with_factory(self) -> None:
        """Test FieldInfo.get_default() with default_factory."""
        field_info = FieldInfo(default_factory=list)
        result = field_info.get_default()
        assert result == []
        assert isinstance(result, list)

    def test_optional_field_in_metaclass_with_field_info(self) -> None:
        """Test optional field gets auto None when using FieldInfo with no default."""

        class Config(DotEnvConfig):
            # Optional type with Field() but no default
            value: str | None = Field()

        config = Config.load_from_dict({})
        assert config.value is None
