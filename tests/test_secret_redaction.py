"""Secret-redaction regression tests (GitHub issue #27).

These lock in that credentials never surface in plaintext through the four
paths the security review found: DSN ``repr``/``str``, config ``repr``,
coercion error messages, generated documentation/.env.example, and the
``SecretStr`` exception chain.
"""

import logging
import traceback

import pytest

from dotenvmodel import DotEnvConfig, Field, TypeCoercionError
from dotenvmodel.types import PostgresDsn, RedisDsn, SecretStr

SECRET = "s3cr3t-pw"
DSN = f"postgresql://dbuser:{SECRET}@db.example.com:5432/appdb"


class TestDsnDisplayRedaction:
    """A credential-bearing DSN must not reveal its password when displayed."""

    def _config(self) -> DotEnvConfig:
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        return Config.load_from_dict({"DATABASE_URL": DSN})

    def test_repr_of_dsn_masks_password(self) -> None:
        config = self._config()
        assert SECRET not in repr(config.database_url)

    def test_str_of_dsn_masks_password(self) -> None:
        config = self._config()
        assert SECRET not in str(config.database_url)

    def test_fstring_of_dsn_masks_password(self) -> None:
        config = self._config()
        assert SECRET not in f"{config.database_url}"

    def test_repr_of_config_masks_dsn_password(self) -> None:
        config = self._config()
        assert SECRET not in repr(config)

    def test_percent_style_logging_masks_password(self, caplog) -> None:
        config = self._config()
        with caplog.at_level(logging.INFO):
            logging.getLogger("test").info("connecting to %s", config.database_url)
        assert SECRET not in caplog.text

    def test_masked_form_keeps_useful_structure(self) -> None:
        config = self._config()
        shown = str(config.database_url)
        # host / scheme / user stay visible; only the password is hidden.
        assert "db.example.com" in shown
        assert "postgresql" in shown
        assert "dbuser" in shown

    def test_dsn_still_usable_as_connection_string(self) -> None:
        config = self._config()
        # The object still carries the real value for drivers, and explicit
        # component accessors still return the true credential.
        assert config.database_url == DSN
        assert config.database_url.password == SECRET
        assert config.database_url.host == "db.example.com"
        assert config.database_url.port == 5432

    def test_passwordless_dsn_is_unchanged(self) -> None:
        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost:6379/0"})
        assert str(config.redis_url) == "redis://localhost:6379/0"
        assert repr(config.redis_url) == repr("redis://localhost:6379/0") or (
            "redis://localhost:6379/0" in repr(config.redis_url)
        )


class TestDsnCoercionErrorRedaction:
    """A DSN that fails coercion must not echo its password in the error."""

    def test_type_coercion_error_masks_password(self) -> None:
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        # Wrong scheme -> ValueError -> TypeCoercionError, value still has creds.
        bad = f"ftp://dbuser:{SECRET}@db.example.com/appdb"
        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": bad})
        assert SECRET not in str(exc_info.value)


class TestDsnDefaultRedactionInDocs:
    """describe()/generate_env_example() must not print DSN default creds."""

    def _config_cls(self) -> type[DotEnvConfig]:
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field(default=DSN)

        return Config

    def test_describe_table_masks_default_password(self) -> None:
        assert SECRET not in self._config_cls().describe(output_format="table")

    def test_describe_markdown_masks_default_password(self) -> None:
        assert SECRET not in self._config_cls().describe(output_format="markdown")

    def test_describe_html_masks_default_password(self) -> None:
        assert SECRET not in self._config_cls().describe(output_format="html")

    def test_env_example_masks_default_password(self) -> None:
        assert SECRET not in self._config_cls().generate_env_example()


class TestRedactionHelper:
    """The standalone helper is defensive and safe on arbitrary input."""

    def test_unparseable_url_returned_unchanged(self) -> None:
        from dotenvmodel._redaction import redact_url_password

        # Invalid IPv6 makes urlparse raise when the password is read.
        assert redact_url_password("http://[::1") == "http://[::1"

    def test_non_url_string_returned_unchanged(self) -> None:
        from dotenvmodel._redaction import redact_url_password

        assert redact_url_password("just-a-plain-value") == "just-a-plain-value"


class TestSecretStrExceptionChain:
    """SecretStr plaintext must not leak through a chained/contextual traceback."""

    def test_full_traceback_has_no_plaintext(self) -> None:
        secret_value = "super-secret-value-that-is-long"

        class Config(DotEnvConfig):
            token: SecretStr = Field(min_length=999)

        try:
            Config.load_from_dict({"TOKEN": secret_value})
        except Exception as exc:
            rendered = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            assert secret_value not in rendered
        else:
            pytest.fail("expected a validation error for the too-short SecretStr")
