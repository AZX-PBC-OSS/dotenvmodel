"""Tests for Union type support and limitations."""

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.exceptions import TypeCoercionError


class TestUnionTypes:
    """Test Union type support."""

    def test_optional_union_with_value(self) -> None:
        """Test Optional union (T | None) with value."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        config = Config.load_from_dict({"VALUE": "hello"})
        assert config.value == "hello"

    def test_optional_union_with_none(self) -> None:
        """Test Optional union (T | None) with None."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        config = Config.load_from_dict({})
        assert config.value is None

    def test_optional_union_with_empty_string(self) -> None:
        """Test Optional union (T | None) with empty string."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value is None

    def test_optional_int_union(self) -> None:
        """Test Optional[int] union."""

        class Config(DotEnvConfig):
            port: int | None = Field()

        config = Config.load_from_dict({"PORT": "8000"})
        assert config.port == 8000

        config2 = Config.load_from_dict({})
        assert config2.port is None

    def test_non_optional_union_not_supported(self) -> None:
        """Test that non-optional Union types are not supported."""

        class Config(DotEnvConfig):
            value: str | int = Field()

        # Non-optional unions raise TypeCoercionError with clear message
        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"VALUE": "hello"})

        # Check for error message about Union types not being supported
        error_msg = str(exc_info.value)
        assert "Union types with multiple non-None types are not supported" in error_msg
        assert "Use Optional[T] or T | None" in error_msg

    def test_multiple_optional_fields(self) -> None:
        """Test multiple Optional fields in same config."""

        class Config(DotEnvConfig):
            name: str | None = Field()
            age: int | None = Field()
            active: bool | None = Field()

        config = Config.load_from_dict(
            {
                "NAME": "Alice",
                "AGE": "30",
            }
        )

        assert config.name == "Alice"
        assert config.age == 30
        assert config.active is None
