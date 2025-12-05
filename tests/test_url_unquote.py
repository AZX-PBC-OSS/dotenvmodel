"""Tests for url_unquote parameter on SecretStr fields."""

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr


class TestUrlUnquote:
    """Test url_unquote parameter functionality."""

    def test_secretstr_url_unquote_default_true(self) -> None:
        """Test that url_unquote defaults to True for SecretStr."""

        class Config(DotEnvConfig):
            password: SecretStr = Field()

        # Password with percent-encoded special chars: "my@pass:word"
        config = Config.load_from_dict({"PASSWORD": "my%40pass%3Aword"})

        assert config.password.get_secret_value() == "my@pass:word"

    def test_secretstr_url_unquote_explicit_true(self) -> None:
        """Test that url_unquote=True decodes percent-encoded values."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(url_unquote=True)

        # API key with special chars: "key@123:456/789"
        config = Config.load_from_dict({"API_KEY": "key%40123%3A456%2F789"})

        assert config.api_key.get_secret_value() == "key@123:456/789"

    def test_secretstr_url_unquote_false(self) -> None:
        """Test that url_unquote=False preserves percent-encoded values."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(url_unquote=False)

        # API key should remain encoded
        config = Config.load_from_dict({"API_KEY": "key%40123%3A456"})

        assert config.api_key.get_secret_value() == "key%40123%3A456"

    def test_secretstr_url_unquote_with_slash(self) -> None:
        """Test decoding slash character in SecretStr."""

        class Config(DotEnvConfig):
            token: SecretStr = Field()

        # Token with slash: "abc/def/ghi"
        config = Config.load_from_dict({"TOKEN": "abc%2Fdef%2Fghi"})

        assert config.token.get_secret_value() == "abc/def/ghi"

    def test_secretstr_url_unquote_with_plus(self) -> None:
        """Test that plus sign is preserved (unquote doesn't convert + to space)."""

        class Config(DotEnvConfig):
            password: SecretStr = Field()

        # Plus signs are not converted to spaces by unquote()
        config = Config.load_from_dict({"PASSWORD": "my+password"})

        # unquote() preserves + as-is (use unquote_plus() for space conversion)
        assert config.password.get_secret_value() == "my+password"

    def test_secretstr_url_unquote_with_equals(self) -> None:
        """Test decoding equals sign in SecretStr."""

        class Config(DotEnvConfig):
            token: SecretStr = Field()

        # Token with equals: "key=value"
        config = Config.load_from_dict({"TOKEN": "key%3Dvalue"})

        assert config.token.get_secret_value() == "key=value"

    def test_secretstr_url_unquote_already_decoded(self) -> None:
        """Test that already-decoded values work fine."""

        class Config(DotEnvConfig):
            password: SecretStr = Field()

        # Password without encoding
        config = Config.load_from_dict({"PASSWORD": "plain-password-123"})

        assert config.password.get_secret_value() == "plain-password-123"

    def test_secretstr_url_unquote_mixed_encoded_decoded(self) -> None:
        """Test mix of encoded and plain characters."""

        class Config(DotEnvConfig):
            token: SecretStr = Field()

        # Mix: "user@example.com"
        config = Config.load_from_dict({"TOKEN": "user%40example.com"})

        assert config.token.get_secret_value() == "user@example.com"

    def test_secretstr_url_unquote_false_preserves_literal(self) -> None:
        """Test that url_unquote=False preserves literal values unchanged."""

        class Config(DotEnvConfig):
            raw_value: SecretStr = Field(url_unquote=False)

        # Should be stored exactly as provided
        config = Config.load_from_dict({"RAW_VALUE": "literal@value"})

        assert config.raw_value.get_secret_value() == "literal@value"

    def test_secretstr_url_unquote_unicode(self) -> None:
        """Test decoding unicode characters."""

        class Config(DotEnvConfig):
            password: SecretStr = Field()

        # Password with unicode: "café"
        config = Config.load_from_dict({"PASSWORD": "caf%C3%A9"})

        assert config.password.get_secret_value() == "café"

    def test_secretstr_url_unquote_empty_string_optional(self) -> None:
        """Test that empty string returns None for optional SecretStr."""

        class Config(DotEnvConfig):
            token: SecretStr | None = Field()

        config = Config.load_from_dict({"TOKEN": ""})

        # Empty string for non-str types (including SecretStr) returns None
        assert config.token is None

    def test_secretstr_url_unquote_special_chars_combination(self) -> None:
        """Test combination of multiple special characters."""

        class Config(DotEnvConfig):
            password: SecretStr = Field()

        # Password: "p@ss:w/rd!#$"
        config = Config.load_from_dict({"PASSWORD": "p%40ss%3Aw%2Frd%21%23%24"})

        assert config.password.get_secret_value() == "p@ss:w/rd!#$"
