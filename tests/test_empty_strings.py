"""Tests for empty string handling."""

import pytest

from dotenvmodel import DotEnvConfig, Field


class TestEmptyStringHandling:
    """Test that empty strings are handled correctly."""

    def test_empty_string_for_str_field(self) -> None:
        """Test that empty string is preserved for str fields."""

        class Config(DotEnvConfig):
            value: str = Field()

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value == ""
        assert isinstance(config.value, str)

    def test_empty_string_in_list(self) -> None:
        """Test that empty strings are preserved in lists."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        config = Config.load_from_dict({"ITEMS": "foo,,bar"})
        assert config.items == ["foo", "", "bar"]

    def test_multiple_empty_strings_in_list(self) -> None:
        """Test multiple consecutive empty strings in list."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        config = Config.load_from_dict({"ITEMS": "a,,,b"})
        assert config.items == ["a", "", "", "b"]

    def test_empty_string_at_start_of_list(self) -> None:
        """Test empty string at the start of a list."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        config = Config.load_from_dict({"ITEMS": ",a,b"})
        assert config.items == ["", "a", "b"]

    def test_empty_string_at_end_of_list(self) -> None:
        """Test empty string at the end of a list."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        config = Config.load_from_dict({"ITEMS": "a,b,"})
        assert config.items == ["a", "b", ""]

    def test_empty_string_in_set(self) -> None:
        """Test that empty strings are preserved in sets."""

        class Config(DotEnvConfig):
            items: set[str] = Field()

        config = Config.load_from_dict({"ITEMS": "foo,,bar"})
        assert config.items == {"foo", "", "bar"}

    def test_empty_string_in_tuple(self) -> None:
        """Test that empty strings are preserved in tuples."""

        class Config(DotEnvConfig):
            items: tuple[str, ...] = Field()

        config = Config.load_from_dict({"ITEMS": "foo,,bar"})
        assert config.items == ("foo", "", "bar")

    def test_empty_string_with_default(self) -> None:
        """Test empty string overrides default value."""

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value == ""

    def test_empty_string_optional_field(self) -> None:
        """Test empty string for optional str field."""

        class Config(DotEnvConfig):
            value: str | None = Field()

        # Empty string should become None for Optional fields
        config = Config.load_from_dict({"VALUE": ""})
        assert config.value is None

    def test_empty_string_not_same_as_missing(self) -> None:
        """Test that empty string is different from missing value."""

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        # Empty string provided
        config1 = Config.load_from_dict({"VALUE": ""})
        assert config1.value == ""

        # No value provided - uses default
        config2 = Config.load_from_dict({})
        assert config2.value == "default"

    def test_only_empty_strings_list(self) -> None:
        """Test list containing only empty strings."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        config = Config.load_from_dict({"ITEMS": ",,"})
        assert config.items == ["", "", ""]

    def test_empty_string_with_validation(self) -> None:
        """Test that empty string can pass min_length validation."""

        class Config(DotEnvConfig):
            value: str = Field(min_length=0)

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value == ""

    def test_empty_string_fails_min_length(self) -> None:
        """Test that empty string fails min_length > 0."""
        from dotenvmodel import ConstraintViolationError

        class Config(DotEnvConfig):
            value: str = Field(min_length=1)

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"VALUE": ""})

    def test_whitespace_only_not_empty(self) -> None:
        """Test that whitespace-only strings are preserved (after strip)."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

        # Spaces around items are stripped, but empty items remain
        config = Config.load_from_dict({"ITEMS": " a , , b "})
        assert config.items == ["a", "", "b"]
