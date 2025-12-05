"""Tests for Field constraint parameter validation."""

import pytest

from dotenvmodel import Field


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
