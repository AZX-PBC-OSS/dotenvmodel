"""Tests for the Field(strip=...) string-processing option and strip_strings."""

import re
from typing import Literal, Optional

import pytest

from dotenvmodel import DotEnvConfig, Field, HttpUrl, SecretStr
from dotenvmodel.fields import FieldInfo


class TestStripBasicModes:
    """Test strip=True / strip=False / inherited default."""

    def test_no_strip_by_default(self) -> None:
        """Values are not stripped unless requested."""

        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "  hello  "

    def test_strip_true(self) -> None:
        """strip=True strips leading/trailing whitespace."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "hello"

    def test_strip_true_whitespace_variants(self) -> None:
        """strip=True handles tabs, carriage returns, and newlines."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)

        config = Config.load_from_dict({"NAME": "\t\r\n hello \r\n\t"})
        assert config.name == "hello"

    def test_strip_false_explicit(self) -> None:
        """strip=False preserves whitespace."""

        class Config(DotEnvConfig):
            name: str = Field(strip=False)

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "  hello  "

    def test_strip_only_strips_ends(self) -> None:
        """Interior whitespace is preserved by strip=True."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)

        config = Config.load_from_dict({"NAME": "  hello world  "})
        assert config.name == "hello world"


class TestStripClassLevelDefault:
    """Test the strip_strings class attribute and per-field overrides."""

    def test_class_level_default_on(self) -> None:
        """strip_strings=True strips fields that don't set strip."""

        class Config(DotEnvConfig):
            strip_strings: bool = True

            name: str = Field()

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "hello"

    def test_class_level_default_off(self) -> None:
        """strip_strings=False (the default) leaves values untouched."""

        class Config(DotEnvConfig):
            strip_strings: bool = False

            name: str = Field()

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "  hello  "

    def test_field_override_beats_class_true(self) -> None:
        """Field(strip=False) wins over strip_strings=True."""

        class Config(DotEnvConfig):
            strip_strings: bool = True

            name: str = Field(strip=False)
            other: str = Field()

        config = Config.load_from_dict({"NAME": "  keep  ", "OTHER": "  strip  "})
        assert config.name == "  keep  "
        assert config.other == "strip"

    def test_field_override_beats_class_false(self) -> None:
        """Field(strip=True) wins over the default strip_strings=False."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)
            other: str = Field()

        config = Config.load_from_dict({"NAME": "  strip  ", "OTHER": "  keep  "})
        assert config.name == "strip"
        assert config.other == "  keep  "

    def test_strip_strings_inherited_by_subclass(self) -> None:
        """strip_strings propagates through normal class inheritance."""

        class Base(DotEnvConfig):
            strip_strings: bool = True

        class Child(Base):
            name: str = Field()

        config = Child.load_from_dict({"NAME": "  hello  "})
        assert config.name == "hello"

    def test_strip_strings_not_discovered_as_field(self) -> None:
        """The metaclass must not treat strip_strings as a config field."""

        class Config(DotEnvConfig):
            strip_strings: bool = True

            name: str = Field()

        assert "strip_strings" not in Config.get_fields()
        assert "name" in Config.get_fields()
        # Class attribute remains readable
        assert Config.strip_strings is True

    def test_strip_strings_default_is_false(self) -> None:
        """DotEnvConfig itself defaults strip_strings to False."""
        assert DotEnvConfig.strip_strings is False


class TestStripCharSetForm:
    """Test strip=<str> char-set semantics."""

    def test_strip_char_set(self) -> None:
        """strip=<chars> uses str.strip(chars) semantics."""

        class Config(DotEnvConfig):
            tag: str = Field(strip=",'\"")

        config = Config.load_from_dict({"TAG": "\",'hello',\""})
        assert config.tag == "hello"

    def test_strip_char_set_preserves_interior(self) -> None:
        """Char-set stripping only affects the ends."""

        class Config(DotEnvConfig):
            tag: str = Field(strip=",")

        config = Config.load_from_dict({"TAG": ",a,b,"})
        assert config.tag == "a,b"

    def test_strip_char_set_not_whitespace(self) -> None:
        """Char-set form does not strip whitespace unless included."""

        class Config(DotEnvConfig):
            tag: str = Field(strip=",")

        config = Config.load_from_dict({"TAG": ", hello ,"})
        assert config.tag == " hello "


class TestStripPatternForm:
    """Test strip=<re.Pattern> semantics."""

    def test_strip_pattern_ends(self) -> None:
        """A compiled pattern removes every match."""

        class Config(DotEnvConfig):
            key: str = Field(strip=re.compile(r"^['\"]+|['\"]+$"))

        config = Config.load_from_dict({"KEY": "\"'hello'\""})
        assert config.key == "hello"

    def test_strip_pattern_anywhere(self) -> None:
        """Pattern matches anywhere in the string are removed, not just ends."""

        class Config(DotEnvConfig):
            key: str = Field(strip=re.compile(r"\s+"))

        config = Config.load_from_dict({"KEY": " a b c "})
        assert config.key == "abc"


class TestStripOnStringLikeTypes:
    """Test strip on SecretStr, Optional, and str-subclass fields."""

    def test_strip_secret_str(self) -> None:
        """strip applies to SecretStr fields before wrapping."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(strip=True)

        config = Config.load_from_dict({"API_KEY": "  s3cr3t  "})
        assert config.api_key.get_secret_value() == "s3cr3t"

    def test_strip_optional_secret_str(self) -> None:
        """strip applies to Optional[SecretStr] fields."""

        class Config(DotEnvConfig):
            api_key: SecretStr | None = Field(default=None, strip=True)

        config = Config.load_from_dict({"API_KEY": "  s3cr3t  "})
        assert config.api_key is not None
        assert config.api_key.get_secret_value() == "s3cr3t"

    def test_strip_optional_str_whitespace_only_becomes_none(self) -> None:
        """Optional[str] + whitespace-only value strips to '' which maps to None."""

        class Config(DotEnvConfig):
            name: str | None = Field(default=None, strip=True)

        config = Config.load_from_dict({"NAME": " \t\r\n "})
        assert config.name is None

    def test_strip_optional_secretstr_whitespace_only_becomes_none(self) -> None:
        """Optional[SecretStr] + whitespace-only strips to '' -> None, not SecretStr('')."""

        class Config(DotEnvConfig):
            api_key: SecretStr | None = Field(default=None, strip=True)

        config = Config.load_from_dict({"API_KEY": "   "})
        assert config.api_key is None

    def test_strip_plain_str_whitespace_only_preserved(self) -> None:
        """Plain str keeps the stripped empty string as a real value."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)

        config = Config.load_from_dict({"NAME": "   "})
        assert config.name == ""

    def test_strip_dsn_str_subclass(self) -> None:
        """strip applies to str subclasses like HttpUrl."""

        class Config(DotEnvConfig):
            url: HttpUrl = Field(strip=True)

        config = Config.load_from_dict({"URL": "  https://example.com/path  "})
        assert config.url == "https://example.com/path"

    def test_strip_not_applied_to_non_string_fields(self) -> None:
        """strip_strings=True does not break non-string fields."""

        class Config(DotEnvConfig):
            strip_strings: bool = True

            port: int = Field()
            hosts: list[str] = Field()

        config = Config.load_from_dict({"PORT": "8000", "HOSTS": "a, b"})
        assert config.port == 8000
        # Collection items self-strip as before
        assert config.hosts == ["a", "b"]


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(str | None, id="pipe-none"),
        # Deliberately uses typing.Optional to exercise the typing.Union code
        # path in unwrap_optional (UP045 would modernize this away and defeat
        # the mutation pin — see test class docstring).
        pytest.param(Optional[str], id="typing-optional"),  # noqa: UP045
    ],
)
class TestStripOnBothUnionSpellings:
    """Both ``Optional[str]`` (typing.Union) and ``str | None`` support strip.

    A mutation removing ``origin is Union`` from ``unwrap_optional`` would break
    the ``typing.Optional`` spelling while leaving ``str | None`` intact,
    escaping the rest of the suite (which only uses ``str | None``). This
    parametrized pin covers both Union spellings so either branch regresses.
    """

    def test_strip_applies(self, field_type: object) -> None:
        class Config(DotEnvConfig):
            name: field_type = Field(default=None, strip=True)  # type: ignore[valid-type]

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "hello"

    def test_whitespace_only_becomes_none(self, field_type: object) -> None:
        class Config(DotEnvConfig):
            name: field_type = Field(default=None, strip=True)  # type: ignore[valid-type]

        config = Config.load_from_dict({"NAME": "   "})
        assert config.name is None


class TestStripInteractionWithPipeline:
    """Test strip ordering relative to coercion and validation."""

    def test_strip_before_validation_min_length(self) -> None:
        """min_length sees the stripped length."""

        from dotenvmodel import ConstraintViolationError

        class Config(DotEnvConfig):
            code: str = Field(strip=True, min_length=3)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"CODE": "  ab  "})
        assert exc_info.value.constraint == "min_length=3"

    def test_strip_runs_with_validate_false(self) -> None:
        """Stripping is value processing, not validation: it runs even with validate=False."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True, min_length=100)

        config = Config.load_from_dict({"NAME": "  hi  "}, validate=False)
        assert config.name == "hi"


class TestStripOrderingPins:
    """Pin that strip runs before other constraints/lookups on the raw value."""

    def test_strip_runs_before_starts_with(self) -> None:
        """strip=True then starts_with: '  sk-abc  ' passes starts_with='sk-'."""

        class Config(DotEnvConfig):
            key: str = Field(strip=True, starts_with="sk-")

        config = Config.load_from_dict({"KEY": "  sk-abc  "})
        assert config.key == "sk-abc"

    def test_strip_runs_before_choices(self) -> None:
        """strip=True then choices: '  dev  ' passes choices=['dev','prod']."""

        class Config(DotEnvConfig):
            env: str = Field(strip=True, choices=["dev", "prod"])

        config = Config.load_from_dict({"ENV": "  dev  "})
        assert config.env == "dev"

    def test_strip_applies_on_alias_field(self) -> None:
        """strip applies to the raw value read via an alias."""

        class Config(DotEnvConfig):
            name: str = Field(alias="MY_ALIAS", strip=True)

        config = Config.load_from_dict({"MY_ALIAS": "  x  "})
        assert config.name == "x"


class TestStripCheapPins:
    """One-assertion pins for strip edge behaviors."""

    def test_two_level_inheritance_with_mid_chain_override(self) -> None:
        """Base True -> Mid False -> Leaf preserves padding; sibling Leaf2(Base) strips."""

        class Base(DotEnvConfig):
            strip_strings: bool = True

        class Mid(Base):
            strip_strings: bool = False

        class Leaf(Mid):
            name: str = Field()

        class Leaf2(Base):
            name: str = Field()

        assert Leaf.load_from_dict({"NAME": "  x  "}).name == "  x  "
        assert Leaf2.load_from_dict({"NAME": "  x  "}).name == "x"

    def test_default_not_stripped(self) -> None:
        """Defaults aren't raw env strings; strip is a raw-string-before-coercion op."""

        class Config(DotEnvConfig):
            name: str = Field(default="  padded  ", strip=True)

        assert Config.load_from_dict({}).name == "  padded  "

    def test_parent_strip_strings_not_applied_to_nested_fields(self) -> None:
        """A parent strip_strings=True does not reach a nested config's str fields."""

        class Inner(DotEnvConfig):
            name: str = Field(default="  keep  ")

        class Outer(DotEnvConfig):
            strip_strings: bool = True
            inner: Inner = Field(default_factory=Inner)

        assert Outer.load_from_dict({}).inner.name == "  keep  "


class TestStripFieldInfoValidation:
    """Test FieldInfo constructor validation of the strip mode."""

    def test_strip_empty_string_raises(self) -> None:
        """strip='' is rejected (use True for whitespace stripping)."""
        with pytest.raises(ValueError) as exc_info:
            Field(strip="")

        assert "strip" in str(exc_info.value)
        assert "non-empty" in str(exc_info.value)

    def test_strip_invalid_type_raises(self) -> None:
        """strip must be bool, str, re.Pattern, or None."""
        with pytest.raises(TypeError) as exc_info:
            Field(strip=123)  # type: ignore[arg-type]

        assert "strip" in str(exc_info.value)

    def test_strip_list_form_raises(self) -> None:
        """The list form is deliberately unsupported."""
        with pytest.raises(TypeError) as exc_info:
            Field(strip=[","])  # type: ignore[arg-type]

        assert "strip" in str(exc_info.value)

    def test_strip_valid_modes_accepted(self) -> None:
        """All documented strip modes are accepted."""
        Field(strip=True)
        Field(strip=False)
        Field(strip=None)
        Field(strip=",")
        Field(strip=re.compile(r"\s+"))

    def test_strip_mode_stored_on_field_info(self) -> None:
        """FieldInfo stores the raw strip mode."""
        pattern = re.compile(r"\s+")
        assert FieldInfo(strip=True).strip is True
        assert FieldInfo(strip=False).strip is False
        assert FieldInfo(strip=None).strip is None
        assert FieldInfo(strip=",").strip == ","
        assert FieldInfo(strip=pattern).strip is pattern

    def test_strip_bytes_pattern_raises_type_error(self) -> None:
        """A re.Pattern with a bytes pattern is rejected at construction.

        A bytes pattern would fail cryptically at load with "cannot use a bytes
        pattern on a string-like object"; reject it early at Field construction.
        """
        with pytest.raises(TypeError) as exc_info:
            Field(strip=re.compile(rb"\s+"))  # type: ignore[arg-type]

        assert "strip" in str(exc_info.value)
        assert "bytes" in str(exc_info.value).lower()

    def test_strip_str_pattern_accepted(self) -> None:
        """A re.Pattern with a str pattern is accepted (regression guard)."""
        Field(strip=re.compile(r"\s+"))


class TestStripStringsClassLevelValidation:
    """Test that non-bool strip_strings values are rejected at class definition time."""

    def test_strip_strings_string_rejected(self) -> None:
        """strip_strings='true' is rejected at class definition, not load time."""

        with pytest.raises(TypeError) as exc_info:

            class Config(DotEnvConfig):
                strip_strings: str = "true"  # type: ignore[assignment]
                name: str = Field()

        assert "strip_strings" in str(exc_info.value)
        assert "bool" in str(exc_info.value).lower()

    def test_strip_strings_int_rejected(self) -> None:
        """strip_strings=1 is rejected at class definition, not load time."""

        with pytest.raises(TypeError) as exc_info:

            class Config(DotEnvConfig):
                strip_strings: int = 1  # type: ignore[assignment]
                name: str = Field()

        assert "strip_strings" in str(exc_info.value)
        assert "bool" in str(exc_info.value).lower()

    def test_strip_strings_non_bool_with_only_int_field_rejected(self) -> None:
        """Non-bool strip_strings is rejected even with no string-like fields.

        The eager metaclass check catches the bad value at class-definition
        time regardless of field types — the previous lazy check only fired
        when a string-like field was processed, so a class with only an int
        field silently accepted the bad value.
        """

        with pytest.raises(TypeError) as exc_info:

            class Config(DotEnvConfig):
                strip_strings: str = "true"  # type: ignore[assignment]
                port: int = Field()

        assert "strip_strings" in str(exc_info.value)
        assert "bool" in str(exc_info.value).lower()

    def test_strip_strings_bool_true_accepted(self) -> None:
        """A proper bool True is accepted (regression guard)."""

        class Config(DotEnvConfig):
            strip_strings: bool = True
            name: str = Field()

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "hello"

    def test_strip_strings_bool_false_accepted(self) -> None:
        """A proper bool False is accepted (regression guard)."""

        class Config(DotEnvConfig):
            strip_strings: bool = False
            name: str = Field()

        config = Config.load_from_dict({"NAME": "  hello  "})
        assert config.name == "  hello  "


class TestStripOnLiteralAllStr:
    """Test strip on Literal[...] fields where all args are str."""

    def test_literal_all_str_strips_before_coercion(self) -> None:
        """Literal['dev','prod'] with strip_strings=True strips '  dev  ' -> 'dev'."""

        class Config(DotEnvConfig):
            strip_strings: bool = True
            env: Literal["dev", "prod"] = Field(default="dev")

        config = Config.load_from_dict({"ENV": "  dev  "})
        assert config.env == "dev"

    def test_literal_all_str_without_strip_fails(self) -> None:
        """Without stripping, '  dev  ' fails Literal['dev','prod'] coercion."""

        from dotenvmodel import TypeCoercionError

        class Config(DotEnvConfig):
            env: Literal["dev", "prod"] = Field(default="dev")

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"ENV": "  dev  "})

    def test_literal_with_non_str_arg_not_string_like(self) -> None:
        """Literal['dev', 1] is not string-like (not all args are str)."""

        class Config(DotEnvConfig):
            strip_strings: bool = True
            env: Literal["dev", 1] = Field(default="dev")  # type: ignore[valid-type]

        # Strip should NOT be applied; '  dev  ' fails Literal coercion
        from dotenvmodel import TypeCoercionError

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"ENV": "  dev  "})
