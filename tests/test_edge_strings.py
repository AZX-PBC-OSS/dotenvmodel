"""Edge case tests for strings, unicode, and special values."""

from pathlib import Path

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import Json


class TestStringEdgeCases:
    """Test string coercion with special values."""

    def test_unicode_ascii_extended(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": "José"})
        assert config.name == "José"

    def test_unicode_cjk(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": "日本語"})
        assert config.name == "日本語"

    def test_unicode_emoji(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": "🎉"})
        assert config.name == "🎉"

    def test_string_with_spaces(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": "Hello World"})
        assert config.name == "Hello World"

    def test_string_with_equals(self) -> None:
        class Config(DotEnvConfig):
            conn: str = Field()

        config = Config.load_from_dict({"CONN": "user=foo;pass=bar"})
        assert config.conn == "user=foo;pass=bar"

    def test_string_with_quotes(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": '"hello"'})
        assert config.name == '"hello"'

    def test_empty_string_preserved(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(default="fallback")

        config = Config.load_from_dict({"NAME": ""})
        assert config.name == ""


class TestBooleanEdgeCases:
    """Test boolean coercion edge cases."""

    def test_whitespace_true(self) -> None:
        class Config(DotEnvConfig):
            debug: bool = Field(default=False)

        config = Config.load_from_dict({"DEBUG": "true "})
        assert config.debug is True

    def test_leading_whitespace_true(self) -> None:
        class Config(DotEnvConfig):
            debug: bool = Field(default=False)

        config = Config.load_from_dict({"DEBUG": " true"})
        assert config.debug is True

    def test_uppercase_true(self) -> None:
        class Config(DotEnvConfig):
            debug: bool = Field(default=False)

        config = Config.load_from_dict({"DEBUG": "TRUE"})
        assert config.debug is True

    def test_mixed_case_true(self) -> None:
        class Config(DotEnvConfig):
            debug: bool = Field(default=False)

        config = Config.load_from_dict({"DEBUG": "tRuE"})
        assert config.debug is True

    def test_empty_string_is_false(self) -> None:
        class Config(DotEnvConfig):
            debug: bool = Field(default=False)

        config = Config.load_from_dict({"DEBUG": ""})
        assert config.debug is False


class TestPathEdgeCases:
    """Test Path type edge cases."""

    def test_tilde_expanded_by_default(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field()

        config = Config.load_from_dict({"PATH": "~/config"})
        assert config.path == Path.home() / "config"

    def test_tilde_not_expanded_when_disabled(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field(resolve_path=False)

        config = Config.load_from_dict({"PATH": "~/config"})
        assert config.path == Path("~/config")

    def test_relative_path_resolved_by_default(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field()

        config = Config.load_from_dict({"PATH": "./relative/path"})
        assert config.path == Path("./relative/path").resolve()
        assert config.path.is_absolute()

    def test_relative_path_not_resolved_when_disabled(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field(resolve_path=False)

        config = Config.load_from_dict({"PATH": "./relative/path"})
        assert config.path == Path("./relative/path")

    def test_env_var_not_expanded(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field(resolve_path=False)

        config = Config.load_from_dict({"PATH": "$HOME/config"})
        assert config.path == Path("$HOME/config")

    def test_nonexistent_path_resolves(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field()

        config = Config.load_from_dict({"PATH": "/nonexistent/path/that/does/not/exist"})
        assert config.path == Path("/nonexistent/path/that/does/not/exist").resolve()


class TestJsonEdgeCases:
    """Test JSON type edge cases."""

    def test_nested_objects(self) -> None:
        class Config(DotEnvConfig):
            data: Json[dict] = Field(default_factory=dict)

        config = Config.load_from_dict({"DATA": '{"a": {"b": {"c": [1, 2, 3]}}}'})
        assert config.data == {"a": {"b": {"c": [1, 2, 3]}}}

    def test_unicode_in_json(self) -> None:
        class Config(DotEnvConfig):
            data: Json[dict] = Field(default_factory=dict)

        config = Config.load_from_dict({"DATA": '{"name": "José"}'})
        assert config.data == {"name": "José"}

    def test_deeply_nested_json(self) -> None:
        class Config(DotEnvConfig):
            data: Json[dict] = Field(default_factory=dict)

        config = Config.load_from_dict(
            {"DATA": '{"nested": {"deep": {"deeper": {"deepest": true}}}}'}
        )
        assert config.data["nested"]["deep"]["deeper"]["deepest"] is True
