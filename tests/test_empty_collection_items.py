"""Tests for empty items in collections."""

from dotenvmodel import DotEnvConfig, Field


class TestEmptyItemsInCollections:
    """Test empty item handling in collections."""

    def test_list_str_preserves_empty_items(self) -> None:
        """Test that list[str] preserves empty items as empty strings."""

        class Config(DotEnvConfig):
            names: list[str] = Field()

        config = Config.load_from_dict({"NAMES": "alice,,bob"})
        assert config.names == ["alice", "", "bob"]

    def test_list_int_skips_empty_items(self) -> None:
        """Test that list[int] skips empty items."""

        class Config(DotEnvConfig):
            numbers: list[int] = Field()

        config = Config.load_from_dict({"NUMBERS": "1,,3"})
        assert config.numbers == [1, 3]

    def test_list_str_with_only_empty_items(self) -> None:
        """Test list[str] with only empty items."""

        class Config(DotEnvConfig):
            values: list[str] = Field()

        config = Config.load_from_dict({"VALUES": ",,"})
        assert config.values == ["", "", ""]

    def test_set_str_preserves_empty_string(self) -> None:
        """Test that set[str] includes empty string."""

        class Config(DotEnvConfig):
            tags: set[str] = Field()

        config = Config.load_from_dict({"TAGS": "foo,,bar"})
        assert config.tags == {"foo", "", "bar"}

    def test_set_int_skips_empty_items(self) -> None:
        """Test that set[int] skips empty items."""

        class Config(DotEnvConfig):
            numbers: set[int] = Field()

        config = Config.load_from_dict({"NUMBERS": "1,,2,,3"})
        assert config.numbers == {1, 2, 3}

    def test_tuple_str_preserves_empty_items(self) -> None:
        """Test that tuple[str, ...] preserves empty items."""

        class Config(DotEnvConfig):
            values: tuple[str, ...] = Field()

        config = Config.load_from_dict({"VALUES": "a,,b,,c"})
        assert config.values == ("a", "", "b", "", "c")

    def test_tuple_int_skips_empty_items(self) -> None:
        """Test that tuple[int, ...] skips empty items."""

        class Config(DotEnvConfig):
            scores: tuple[int, ...] = Field()

        config = Config.load_from_dict({"SCORES": "10,,20,,30"})
        assert config.scores == (10, 20, 30)

    def test_list_optional_int_keeps_none_for_empty(self) -> None:
        """Test that list[int | None] keeps None for empty items."""

        class Config(DotEnvConfig):
            numbers: list[int | None] = Field()

        config = Config.load_from_dict({"NUMBERS": "1,,3"})
        assert config.numbers == [1, None, 3]

    def test_dict_with_empty_string_values(self) -> None:
        """Test dict with empty string values."""

        class Config(DotEnvConfig):
            mapping: dict[str, str] = Field()

        config = Config.load_from_dict({"MAPPING": "key1=,key2=value"})
        assert config.mapping == {"key1": "", "key2": "value"}

    def test_dict_skips_empty_int_keys(self) -> None:
        """Test that dict[int, str] skips pairs with empty keys."""

        class Config(DotEnvConfig):
            mapping: dict[int, str] = Field()

        config = Config.load_from_dict({"MAPPING": "1=one,=empty,2=two"})
        assert config.mapping == {1: "one", 2: "two"}

    def test_trailing_separator_creates_empty_item(self) -> None:
        """Test that trailing separator creates empty item for str types."""

        class Config(DotEnvConfig):
            values: list[str] = Field()

        config = Config.load_from_dict({"VALUES": "a,b,"})
        assert config.values == ["a", "b", ""]

    def test_leading_separator_creates_empty_item(self) -> None:
        """Test that leading separator creates empty item for str types."""

        class Config(DotEnvConfig):
            values: list[str] = Field()

        config = Config.load_from_dict({"VALUES": ",a,b"})
        assert config.values == ["", "a", "b"]

    def test_multiple_consecutive_separators(self) -> None:
        """Test multiple consecutive separators."""

        class Config(DotEnvConfig):
            values: list[str] = Field()

        config = Config.load_from_dict({"VALUES": "a,,,b"})
        assert config.values == ["a", "", "", "b"]
