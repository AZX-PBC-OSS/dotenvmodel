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

    def test_malformed_url_does_not_leak_password_in_exception(self) -> None:
        # urlparse() raises on this (bad IPv6) — the fallback must still mask.
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        bad = f"postgresql://user:{SECRET}@[::1:5432/db"
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
        assert not _is_sensitive_key("_")  # all-separator key -> no tokens
        assert not _is_sensitive_key("--")

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
        # Only exact-token lookalikes are benign; qualified `*_key`/`*_token`
        # compounds mask by design (no carve-outs — see module docstring).
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
            "secretary",
            "monkey",
        ):
            assert not _is_sensitive_key(key), key

    def test_qualified_key_and_token_compounds_mask_by_design(self) -> None:
        # Formerly carved out as benign; the carve-out lists were themselves
        # a leak surface (each entry a potential false negative), so any
        # `*_key`/`*_token` now masks. Over-masking here is the cheap failure.
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "sort_key",
            "public_key",
            "partition_key",
            "foreign_key",
            "token_endpoint",
            "token_type",
        ):
            assert _is_sensitive_key(key), key

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

    def test_lookalike_token_key_not_masked_but_compounds_are(self) -> None:
        # `tokenizer` is a lookalike (exact-token match keeps it benign);
        # `token_endpoint`/`sort_key` mask under the no-carve-out contract.
        out = redact_url_password(
            "https://h/v1?tokenizer=cl100k&token_endpoint=/oauth&sort_key=name"
        )
        assert "tokenizer=cl100k" in out
        assert "token_endpoint=***" in out
        assert "sort_key=***" in out

    def test_semicolon_is_data_not_a_separator(self) -> None:
        # Per the WHATWG URL standard (and Python 3.10+ parse_qsl), only '&'
        # separates params; a ';' stays inside its value. A secret value that
        # contains ';' is masked whole (no tail leak).
        out = redact_url_password("https://h/p?password=secret;db=0")
        assert "secret" not in out
        assert out == "https://h/p?password=***"

    def test_base64_value_with_equals_masked_whole(self) -> None:
        out = redact_url_password("https://h/cb?signature=Zm9vYmFy==")
        assert "Zm9vYmFy" not in out
        assert "***" in out

    def test_unparseable_url_still_masks_userinfo(self) -> None:
        # Even when urlparse raises, a userinfo password must be masked.
        out = redact_url_password("postgresql://user:s3cret@[::1:5432/db")
        assert "s3cret" not in out
        assert "***" in out

    def test_unparseable_url_still_masks_query_secret(self) -> None:
        # Malformed URL (bad IPv6) that also carries a query secret must not
        # leak it (this reintroduced the issue-#27 leak via a one-char typo).
        out = redact_url_password("redis://[::1:6379?password=s3cret")
        assert "s3cret" not in out
        out2 = redact_url_password("postgresql://user:pw@[::1:5432/db?sslpassword=SECRET")
        assert "SECRET" not in out2 and "pw" not in out2.split("@")[0].split(":")[-1]
        # Fragment secret on a malformed URL must also be masked.
        out3 = redact_url_password("redis://[::1:6379#access_token=abc123")
        assert "abc123" not in out3

    def test_separated_session_id_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in ("sessionid", "session_id", "sessionId", "SESSION_ID"):
            assert _is_sensitive_key(key), key

    def test_glued_compound_secrets_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "secretkey",
            "accesskey",
            "privatekey",
            "accesstoken",
            "clientsecret",
            "refreshtoken",
        ):
            assert _is_sensitive_key(key), key
        assert "AKIA" not in redact_url_password("https://h/p?secretkey=AKIAEXAMPLE")

    def test_identifier_key_compounds_mask_by_design(self) -> None:
        # Storage/pagination identifiers mask too — the benign-qualifier
        # lists were removed (each entry was a potential leak).
        from dotenvmodel._redaction import _is_sensitive_key

        for key in ("object_key", "index_key", "row_key", "continue_token", "start_token"):
            assert _is_sensitive_key(key), key

    def test_versioned_secret_keys_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in ("auth_token_v2", "access_key_v1", "refresh_token_v3", "api_key_2"):
            assert _is_sensitive_key(key), key
        # Versioned `*_key`/`*_token` compounds mask too (any-token rule);
        # a version suffix can no longer hide the secret word.
        for key in ("page_token_v2", "sort_key_v1", "api_key_v2beta"):
            assert _is_sensitive_key(key), key

    def test_ssl_key_masks_by_design(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        # ssl_key/sslkey usually holds a key-file *path*, but hiding a path in
        # an error message is cheap and a carve-out for it is a leak surface —
        # so it masks under the no-carve-out contract.
        assert _is_sensitive_key("ssl_key")
        assert _is_sensitive_key("sslkey")

    def test_at_sign_in_password_fully_masked_on_fallback(self) -> None:
        # Malformed URL whose password contains a literal '@' must not leak a tail.
        out = redact_url_password("postgresql://u:p@ss@[::1:5432/db")
        assert "p@ss" not in out
        assert "ss@" not in out

    def test_leading_userinfo_masked_even_with_later_scheme(self) -> None:
        # A scheme-less leading user:pw@host must mask even when '://' appears
        # later (e.g. in a redirect param) — the classic issue-#27 leak.
        out = redact_url_password(
            "dbuser:s3cret@db.example.com/db?redirect=https://app.example.com"
        )
        assert "s3cret" not in out
        assert "dbuser" in out  # username preserved

    def test_email_shaped_value_not_masked(self) -> None:
        # word:word@host with no path/port is an email-ish value, not a DSN.
        for v in ("cc:john@example.com", "from:alice@example.com"):
            assert redact_url_password(v) == v

    def test_fallback_masks_semicolon_params(self) -> None:
        out = redact_url_password("https://[::1/path;password=s3cret?q=1")
        assert "s3cret" not in out
        assert "q=1" in out

    def test_saml_pkce_session_and_plural_keys_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "SAMLResponse",
            "SAMLRequest",
            "code_verifier",
            "code_challenge",
            "jsessionid",
            "phpsessid",
            "sid",
            "session",
            "passwords",
            "secrets",
            "tokens",
            "keys",
            "secretaccesskey",
            "sharedaccesskey",
        ):
            assert _is_sensitive_key(key), key

    def test_password_value_with_semicolon_masked_whole(self) -> None:
        # A ';' inside a secret value must not leak the tail.
        out = redact_url_password("https://h/p?password=se;cret&db=0")
        assert "cret" not in out
        assert "db=0" in out

    def test_semicolon_in_benign_value_preserved(self) -> None:
        # ';' is data, not a separator: a benign value keeps it verbatim.
        out = redact_url_password("https://h/p?filter=a;b&password=x")
        assert "filter=a;b" in out
        assert "password=***" in out

    def test_more_secret_keys_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "totp",
            "client_assertion",
            "HMACKey",
            "storage_account_key",
            "Ocp-Apim-Subscription-Key",
            "pass",
            "access_token",
        ):
            assert _is_sensitive_key(key), key

    def test_lookalike_words_stay_benign_but_compounds_mask(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        # Exact-token matching keeps single-word lookalikes benign...
        assert not _is_sensitive_key("passwordless")
        # ...while qualified secret-word compounds all mask by design.
        for key in (
            "page_token",
            "next_token",
            "continuation_token",
            "signature_method",
            "auth_type",
            "token_endpoint",
            "authorization_endpoint",
        ):
            assert _is_sensitive_key(key), key


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


class TestReviewLeakRegressions:
    """Leak paths confirmed by execution during the multi-model review.

    Philosophy shift pinned here: the classifier now masks on ANY secret-word
    token (not just the last), with no benign carve-out lists. Over-masking a
    ``sort_key`` in an error message costs nothing; under-masking a credential
    is a leak.
    """

    def test_schemeless_userinfo_password_masked(self) -> None:
        # The forgot-the-scheme typo: urlparse sees scheme="dbuser", no netloc.
        out = redact_url_password(f"dbuser:{SECRET}@db.example.com:5432/appdb")
        assert SECRET not in out
        assert "dbuser" in out
        assert "db.example.com:5432/appdb" in out

    def test_schemeless_dsn_not_leaked_in_coercion_error(self) -> None:
        # The same typo triggers the very error message that used to echo it.
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

        bad = f"dbuser:{SECRET}@db.example.com:5432/appdb"
        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": bad})
        assert SECRET not in str(exc_info.value)

    def test_additional_credential_words_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in ("pin", "cvv", "cvc", "pat", "license", "dsn", "connection_string", "conn_str"):
            assert _is_sensitive_key(key), key

    def test_bare_oauth_code_masked_but_qualified_codes_preserved(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        assert _is_sensitive_key("code")  # OAuth authorization code
        for key in ("status_code", "country_code", "error_code", "zip_code"):
            assert not _is_sensitive_key(key), key

    def test_bare_key_param_masked(self) -> None:
        # ?key= is the standard Google-style API-key parameter.
        out = redact_url_password("https://maps.example.com/api?key=AIzaSyFAKE&region=us")
        assert "AIzaSyFAKE" not in out
        assert "region=us" in out

    def test_version_and_qualifier_suffixed_keys_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in (
            "api_key_v2beta",
            "access_key_v3_preview",
            "auth_token_v2",
            "api_secret_v2beta",
        ):
            assert _is_sensitive_key(key), key

    def test_path_params_component_masked(self) -> None:
        # urlparse splits ;-params off the last path segment — must be redacted too.
        out = redact_url_password("https://h/path;password=secret?q=1")
        assert "secret" not in out
        assert "q=1" in out

    def test_semicolon_subpair_inside_benign_value_masked(self) -> None:
        # Legacy ;-separated pair glued into a benign key's value.
        out = redact_url_password("https://h/p?db=0;password=s3cret&x=1")
        assert "s3cret" not in out
        assert "db=0" in out
        assert "x=1" in out

    def test_pass_and_auth_compounds_masked(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in ("db_pass", "user_pass", "app-pass", "db_auth", "user_auth"):
            assert _is_sensitive_key(key), key

    def test_secret_word_lookalikes_still_benign(self) -> None:
        from dotenvmodel._redaction import _is_sensitive_key

        for key in ("bypass", "passenger", "compass", "authors", "oauth", "pinned", "keyword"):
            assert not _is_sensitive_key(key), key
