"""Regression tests: str defaults are coerced for non-str field types.

GROUP A of the 2026-07-17 code-review findings. Previously the missing-value
branch of ``DotEnvConfig._process_field`` used ``field_info.get_default()``
verbatim, so a ``str`` default for a non-``str`` field bypassed coercion and
validation: a ``SecretStr`` field with ``default='sekret'`` loaded a plaintext
``str`` (repr leaked it, pickle block bypassed, ``get_secret_value`` raised),
an ``int`` str default skipped ``le``, a ``bool`` str default stayed truthy,
and DSN/UUID/Decimal/Path/Json/list str defaults were type-confused.

These tests pin the corrected behavior: a ``str`` default whose
Optional-unwrapped field type is not ``str`` is routed through
``coerce_value`` so it flows through the same typing/validation as env values.
A ``str`` default for a ``str``-ish type (``str``/``Optional[str]``) is NOT
re-coerced (the unwrap gate), preserving the Optional empty-string -> ``None``
semantics.
"""

import pickle
from pathlib import Path
from uuid import UUID

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    Json,
    PostgresDsn,
    SecretStr,
    TypeCoercionError,
)


class TestDefaultCoercionSecretStr:
    """SecretStr str-defaults must be wrapped, masked, and pickle-protected."""

    def test_str_default_wrapped_to_secretstr(self) -> None:
        """A str default for a SecretStr field becomes a real SecretStr."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default="sekret")

        config = Config.load_from_dict({})
        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "sekret"
        assert repr(config.api_key) == "SecretStr('**********')"

    def test_str_default_pickle_blocked(self) -> None:
        """A SecretStr str-default keeps the pickle guard."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default="sekret")

        config = Config.load_from_dict({})
        with pytest.raises(TypeError):
            pickle.dumps(config.api_key)

    def test_str_default_constraint_failure_masked(self) -> None:
        """A constraint failure on a SecretStr str-default masks the plaintext."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default="leaked-secret-value", min_length=32)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({})

        msg = str(exc_info.value)
        assert "leaked-secret-value" not in msg
        assert "**********" in msg
        assert exc_info.value.constraint == "min_length=32"
        # No plaintext anywhere in the exception chain
        exc: BaseException | None = exc_info.value
        while exc is not None:
            assert "leaked-secret-value" not in str(exc)
            assert "leaked-secret-value" not in str(getattr(exc, "value", ""))
            exc = exc.__cause__ or exc.__context__


class TestDefaultCoercionDsn:
    """DSN str-defaults must be validated, redacted, and parseable."""

    def test_dsn_str_default_validated_and_usable(self) -> None:
        """A str default for a PostgresDsn field is constructed and parseable."""

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(default="postgresql://user:hunter2@host:5432/db")

        config = Config.load_from_dict({})
        assert isinstance(config.db, PostgresDsn)
        assert config.db.host == "host"
        assert config.db.database == "db"
        # functional access to the password still works
        assert config.db.password == "hunter2"

    def test_dsn_str_default_repr_redacted(self) -> None:
        """The repr of a DSN str-default masks the password."""

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(default="postgresql://user:hunter2@host:5432/db")

        config = Config.load_from_dict({})
        assert "hunter2" not in repr(config.db)
        assert "hunter2" not in repr(config)

    def test_dsn_str_default_bad_scheme_raises(self) -> None:
        """An invalid DSN str-default is rejected at coercion time."""

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(default="ftp://host/db")

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({})


class TestDefaultCoercionScalars:
    """int/bool/UUID/Json/list/Path str-defaults are coerced to their types."""

    def test_int_str_default_le_enforced(self) -> None:
        """An int str-default is coerced and then constraint-checked."""

        class Config(DotEnvConfig):
            port: int = Field(default="99999", le=65535)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({})
        assert exc_info.value.constraint == "le=65535"

    def test_int_str_default_valid_coerced(self) -> None:
        """A valid int str-default becomes a real int."""

        class Config(DotEnvConfig):
            port: int = Field(default="8080", le=65535)

        config = Config.load_from_dict({})
        assert config.port == 8080
        assert isinstance(config.port, int)

    def test_bool_str_default_false_coerced(self) -> None:
        """A 'false' str default for a bool field becomes False, not truthy."""

        class Config(DotEnvConfig):
            debug: bool = Field(default="false")

        config = Config.load_from_dict({})
        assert config.debug is False

    def test_bool_str_default_true_coerced(self) -> None:
        """A 'true' str default for a bool field becomes True."""

        class Config(DotEnvConfig):
            debug: bool = Field(default="true")

        config = Config.load_from_dict({})
        assert config.debug is True

    def test_uuid_str_default_coerced(self) -> None:
        """A UUID str default becomes a UUID instance."""

        class Config(DotEnvConfig):
            tenant: UUID = Field(default="12345678-1234-5678-1234-567812345678")

        config = Config.load_from_dict({})
        assert isinstance(config.tenant, UUID)
        assert str(config.tenant) == "12345678-1234-5678-1234-567812345678"

    def test_json_str_default_coerced(self) -> None:
        """A JSON str default for a Json field is parsed."""

        class Config(DotEnvConfig):
            flags: Json[dict[str, bool]] = Field(default='{"a": true}')

        config = Config.load_from_dict({})
        assert config.flags == {"a": True}

    def test_list_str_default_coerced(self) -> None:
        """A separated str default for a list field is split into a list."""

        class Config(DotEnvConfig):
            hosts: list[str] = Field(default="a,b,c")

        config = Config.load_from_dict({})
        assert config.hosts == ["a", "b", "c"]

    def test_path_str_default_resolved(self) -> None:
        """A Path str default is resolved like an env value."""

        class Config(DotEnvConfig):
            location: Path = Field(default="/tmp/dotenvmodel_default")

        config = Config.load_from_dict({})
        assert isinstance(config.location, Path)
        assert config.location.name == "dotenvmodel_default"


class TestDefaultCoercionFactory:
    """default_factory results that are str are coerced too."""

    def test_factory_returning_str_coerced(self) -> None:
        """A default_factory returning a str is coerced for non-str fields."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default_factory=lambda: "factory-secret")

        config = Config.load_from_dict({})
        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "factory-secret"


class TestDefaultCoercionUnwrapGate:
    """str defaults for str-ish types are NOT re-coerced (the unwrap gate)."""

    def test_optional_str_empty_default_stays_empty(self) -> None:
        """Optional[str] default='' stays '' (not re-coerced to None)."""

        class Config(DotEnvConfig):
            name: str | None = Field(default="")

        config = Config.load_from_dict({})
        assert config.name == ""

    def test_str_default_untouched(self) -> None:
        """A str default for a plain str field is returned as-is."""

        class Config(DotEnvConfig):
            name: str = Field(default="localhost")

        config = Config.load_from_dict({})
        assert config.name == "localhost"
        assert isinstance(config.name, str)

    def test_non_str_default_untouched(self) -> None:
        """Non-str defaults (int, bool, factory=list) bypass coercion entirely."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)
            debug: bool = Field(default=False)
            hosts: list[str] = Field(default_factory=list)

        config = Config.load_from_dict({})
        assert config.port == 8000
        assert isinstance(config.port, int)
        assert config.debug is False
        assert config.hosts == []
