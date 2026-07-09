"""Secret-redaction regression tests (GitHub issue #27).

Contract after review (PR #29):
- ``repr(dsn)`` / ``repr(config)`` mask the password (safe display).
- ``str(dsn)`` / f-strings stay RAW so the DSN is usable as a connection
  string (drivers read the object's buffer). Masking ``str`` broke that idiom.
- Exception messages and ``describe()`` / ``generate_env_example()`` mask,
  including ``Optional[DSN]`` fields.
- A ``SecretStr`` constraint error carries no plaintext anywhere in its
  exception chain (``__cause__`` / ``__context__``).
- ``redact_url_password`` masks userinfo AND sensitive query-string keys.

Known, documented limitation: because DSN types subclass ``str``, raw buffer
operations (``.encode()``, ``json.dumps``, concatenation) still expose the
value. Use ``SecretStr`` for values that must never appear in serialized output.
"""

import logging
import traceback

import pytest

from dotenvmodel import DotEnvConfig, Field, TypeCoercionError
from dotenvmodel._redaction import redact_url_password
from dotenvmodel.types import PostgresDsn, RedisDsn, SecretStr

SECRET = "s3cr3t-pw"
DSN = f"postgresql://dbuser:{SECRET}@db.example.com:5432/appdb"


def _config() -> DotEnvConfig:
    class Config(DotEnvConfig):
        database_url: PostgresDsn = Field()

    return Config.load_from_dict({"DATABASE_URL": DSN})


class TestDsnDisplayRedaction:
    """repr()-family paths mask the password; str() stays usable."""

    def test_repr_of_dsn_masks_password(self) -> None:
        assert SECRET not in repr(_config().database_url)

    def test_repr_of_config_masks_dsn_password(self) -> None:
        assert SECRET not in repr(_config())

    def test_repr_style_logging_masks_password(self, caplog) -> None:
        config = _config()
        with caplog.at_level(logging.INFO):
            logging.getLogger("test").info("connecting to %r", config.database_url)
        assert SECRET not in caplog.text

    def test_masked_repr_keeps_useful_structure(self) -> None:
        shown = repr(_config().database_url)
        assert "db.example.com" in shown
        assert "postgresql" in shown
        assert "dbuser" in shown


class TestDsnStillUsable:
    """The DSN must remain usable as a real connection string."""

    def test_str_returns_the_raw_connection_string(self) -> None:
        # Reverted the __str__ override: str(dsn) is the real value so the
        # create_engine(str(url)) / redis.from_url(str(url)) idiom keeps working.
        assert str(_config().database_url) == DSN

    def test_fstring_returns_raw_value(self) -> None:
        assert str(SECRET) in f"{_config().database_url}"

    def test_equality_and_accessors_intact(self) -> None:
        d = _config().database_url
        assert d == DSN
        assert d.password == SECRET
        assert d.host == "db.example.com"
        assert d.port == 5432

    def test_passwordless_dsn_roundtrips(self) -> None:
        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()

        config = Config.load_from_dict({"REDIS_URL": "redis://localhost:6379/0"})
        assert str(config.redis_url) == "redis://localhost:6379/0"
        assert repr(config.redis_url) == repr("redis://localhost:6379/0")


class TestDsnCoercionErrorRedaction:
    """A DSN that fails coercion must not echo its password in the error."""

    def test_type_coercion_error_masks_password(self) -> None:
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        bad = f"ftp://dbuser:{SECRET}@db.example.com/appdb"
        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": bad})
        assert SECRET not in str(exc_info.value)


class TestDsnDefaultRedactionInDocs:
    """describe()/generate_env_example() must not print DSN default creds."""

    def _cls(self, annotation: str = "plain") -> type[DotEnvConfig]:
        if annotation == "optional":

            class Config(DotEnvConfig):
                database_url: PostgresDsn | None = Field(default=DSN)

        else:

            class Config(DotEnvConfig):
                database_url: PostgresDsn = Field(default=DSN)

        return Config

    def test_describe_table_masks_default(self) -> None:
        assert SECRET not in self._cls().describe(output_format="table")

    def test_describe_markdown_masks_default(self) -> None:
        assert SECRET not in self._cls().describe(output_format="markdown")

    def test_describe_html_masks_default(self) -> None:
        assert SECRET not in self._cls().describe(output_format="html")

    def test_env_example_masks_default(self) -> None:
        assert SECRET not in self._cls().generate_env_example()

    def test_optional_dsn_default_masked_in_env_example(self) -> None:
        # Union/Optional field_type is not a BaseDsn subclass; must still mask.
        assert SECRET not in self._cls("optional").generate_env_example()

    def test_optional_dsn_default_masked_in_describe(self) -> None:
        assert SECRET not in self._cls("optional").describe(output_format="markdown")

    def test_multi_member_union_dsn_default_masked(self) -> None:
        # A DSN default in a multi-member union must still be masked.
        class Config(DotEnvConfig):
            database_url: PostgresDsn | RedisDsn | None = Field(default=DSN)

        assert SECRET not in Config.generate_env_example()
        assert SECRET not in Config.describe(output_format="markdown")


class TestRedactionHelper:
    """The standalone helper masks userinfo and sensitive query keys."""

    def test_userinfo_password_masked(self) -> None:
        assert redact_url_password(DSN) == "postgresql://dbuser:***@db.example.com:5432/appdb"

    def test_query_string_password_masked(self) -> None:
        out = redact_url_password("redis://localhost:6379/0?password=s3cr3t&db=0")
        assert "s3cr3t" not in out
        assert "***" in out
        assert "db=0" in out

    def test_query_string_token_masked(self) -> None:
        out = redact_url_password("https://api.example.com/v1?api_key=abc123")
        assert "abc123" not in out
        assert "***" in out

    def test_sslpassword_query_masked(self) -> None:
        # libpq's sslpassword must be caught (substring match, not exact set).
        out = redact_url_password("postgresql://h/db?sslmode=require&sslpassword=secret")
        assert "secret" not in out
        assert "sslmode=require" in out

    def test_hyphenated_and_prefixed_secret_keys_masked(self) -> None:
        assert "abc" not in redact_url_password("https://h/p?x-api-key=abc")
        assert "abc" not in redact_url_password("https://h/p?db_password=abc")

    def test_benign_query_params_preserved_verbatim(self) -> None:
        # Masking a sensitive key must not re-encode unrelated params.
        out = redact_url_password("https://h/p?note=a%20b&password=x&tag=1&tag=2")
        assert "note=a%20b" in out  # not normalized to a+b
        assert "tag=1" in out and "tag=2" in out
        assert "password=***" in out  # value masked, key preserved

    def test_lookalike_key_not_masked(self) -> None:
        # 'author' contains 'auth' but is not a secret; must survive.
        out = redact_url_password("https://h/p?author=jane&mode=ssl")
        assert out == "https://h/p?author=jane&mode=ssl"

    def test_fragment_secret_masked(self) -> None:
        # OAuth implicit-flow style secret in the fragment.
        out = redact_url_password("https://api.example.com/cb#access_token=abc123&state=xyz")
        assert "abc123" not in out
        assert "***" in out
        assert "state=xyz" in out

    def test_ipv6_host_and_port_preserved(self) -> None:
        out = redact_url_password("postgresql://u:pw@[2001:db8::1]:5432/db")
        assert "pw" not in out.split("@")[0].split(":")[-1]
        assert "[2001:db8::1]:5432" in out

    def test_unparseable_url_returned_unchanged(self) -> None:
        assert redact_url_password("http://[::1") == "http://[::1"

    def test_non_url_string_returned_unchanged(self) -> None:
        assert redact_url_password("just-a-plain-value") == "just-a-plain-value"


class TestRedactionInternals:
    """Direct unit tests pinning the redaction helpers' contracts."""

    def test_is_sensitive_key_secret_words(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "password",
            "pwd",
            "passphrase",
            "passcode",
            "secret",
            "token",
            "auth",
            "authorization",
            "api_key",
            "apikey",
            "credential",
            "signature",
            "sig",
            "jwt",
            "bearer",
            "sessionid",
            "hmac",
        ):
            assert _is_sensitive_key(key), key

    def test_is_sensitive_key_empty(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        assert not _is_sensitive_key("")
        assert not _is_sensitive_key("   ")

    def test_is_sensitive_key_secret_compounds(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "sslpassword",
            "sslpassphrase",
            "db_password",
            "x-api-key",
            "clientSecret",
            "access-token",
            "access_token",
            "refresh_token",
            "client_secret",
            "private_key",
            "access_key",
            "X-Amz-Signature",
        ):
            assert _is_sensitive_key(key), key

    def test_is_sensitive_key_benign(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "author",
            "keyboard",
            "mode",
            "host",
            "note",
            "tag",
            "username",
            "tokenizer",
            "tokens",
            "token_endpoint",
            "token_type",
            "secretary",
            "sort_key",
            "public_key",
            "partition_key",
            "cache_key",
            "routing_key",
            "foreign_key",
            "monkey",
        ):
            assert not _is_sensitive_key(key), key

    def test_bare_query_key_without_value_preserved(self) -> None:
        # A flag-style key with no "=" must be left untouched.
        assert redact_url_password("https://h/p?flag&password=x") == "https://h/p?flag&password=***"

    def test_blank_sensitive_value_not_corrupted(self) -> None:
        # Nothing to mask (empty value); the URL must round-trip unchanged.
        assert redact_url_password("https://h/p?password=&db=1") == "https://h/p?password=&db=1"

    def test_no_sensitive_key_returns_input_unchanged(self) -> None:
        url = "https://h/p?mode=ssl&region=us-east-1"
        assert redact_url_password(url) == url

    def test_presigned_url_signature_masked(self) -> None:
        # The signature IS the credential in an AWS/Azure presigned URL.
        out = redact_url_password(
            "https://s3.example.com/o?X-Amz-Credential=AKIA&X-Amz-Signature=abcdef"
        )
        assert "abcdef" not in out
        assert "***" in out

    def test_benign_key_containing_token_not_masked(self) -> None:
        url = "https://h/v1?tokenizer=cl100k&token_endpoint=/oauth&sort_key=name"
        assert redact_url_password(url) == url

    def test_semicolon_separated_sensitive_pair_masked(self) -> None:
        # ';' must not let a password ride inside another key's value (leak)...
        leak = redact_url_password("https://h/p?a=1;password=x")
        assert "password=x" not in leak
        assert "***" in leak
        # ...and must not drop the non-sensitive neighbour (data loss).
        drop = redact_url_password("https://h/p?password=secret;db=0")
        assert "secret" not in drop
        assert "db=0" in drop

    def test_base64_value_with_equals_masked_whole(self) -> None:
        out = redact_url_password("https://h/cb?signature=Zm9vYmFy==")
        assert "Zm9vYmFy" not in out
        assert "***" in out


class TestUnionHelpers:
    """Direct unit tests for the describe() union-unwrapping helpers."""

    def test_union_members_plain_type(self) -> None:
        from dotenvmodel.describe.formatters import _union_members

        assert _union_members(int) == [int]

    def test_union_members_strips_none(self) -> None:
        from dotenvmodel.describe.formatters import _union_members

        assert _union_members(PostgresDsn | None) == [PostgresDsn]

    def test_is_type_in_union_multi_member(self) -> None:
        from dotenvmodel.describe.formatters import _is_type_in_union
        from dotenvmodel.types import BaseDsn

        assert _is_type_in_union(PostgresDsn | RedisDsn | None, BaseDsn)

    def test_is_type_in_union_absent(self) -> None:
        from dotenvmodel.describe.formatters import _is_type_in_union
        from dotenvmodel.types import BaseDsn

        assert not _is_type_in_union(int | str, BaseDsn)


class TestSecretStrExceptionChain:
    """SecretStr plaintext must not leak anywhere in the exception chain."""

    def _raise(self) -> Exception:
        secret_value = "super-secret-value-that-is-long"

        class Config(DotEnvConfig):
            token: SecretStr = Field(min_length=999)

        try:
            Config.load_from_dict({"TOKEN": secret_value})
        except Exception as exc:
            return exc
        pytest.fail("expected a validation error for the too-short SecretStr")

    def test_full_traceback_has_no_plaintext(self) -> None:
        exc = self._raise()
        rendered = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        assert "super-secret-value-that-is-long" not in rendered

    def test_no_plaintext_anywhere_in_chain(self) -> None:
        exc: BaseException | None = self._raise()
        secret_value = "super-secret-value-that-is-long"
        while exc is not None:
            assert secret_value not in str(exc)
            assert secret_value not in str(getattr(exc, "value", ""))
            exc = exc.__cause__ or exc.__context__
