"""Tests for the @field_validator decorator (before/after custom field hooks)."""

import functools
import logging
from typing import Any
from uuid import UUID

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    MultipleValidationErrors,
    PostgresDsn,
    SecretStr,
    TypeCoercionError,
    ValidatorContext,
    field_validator,
)


@field_validator("tag", mode="before")
def _module_normalize_tag(value: str, ctx: ValidatorContext) -> str:
    """Module-level before-hook, assigned inside a class body in the tests."""
    return value.strip().lower()


class TestFieldValidatorMotivatingCases:
    """The motivating pipelines: normalize before, validate/transform after."""

    def test_log_level_uppercased_before_then_mapped_after(self) -> None:
        """A raw 'info' becomes uppercased, stripped, then mapped to a logging int."""

        class Config(DotEnvConfig):
            log_level: str = Field(default="ERROR", strip=True)

            @field_validator("log_level", mode="before")
            def uppercase_log_level(self, value: str, ctx: ValidatorContext) -> str:
                return value.upper() if value else value

            @field_validator("log_level")
            def convert_to_logging_int(self, value: str, ctx: ValidatorContext) -> int:
                return logging.getLevelNamesMapping().get(value, logging.ERROR)

        # dict() indexing: the after-hook legitimately changes the value's
        # type away from the declared annotation, so static narrowing is not
        # meaningful here.
        assert Config.load_from_dict({"LOG_LEVEL": " info"}).dict()["log_level"] == 20

    def test_after_hook_maps_default_value_too(self) -> None:
        """After hooks run on defaults (inline validator semantics)."""

        class Config(DotEnvConfig):
            log_level: str = Field(default="ERROR")

            @field_validator("log_level")
            def convert_to_logging_int(self, value: str, ctx: ValidatorContext) -> int:
                return logging.getLevelNamesMapping().get(value, logging.ERROR)

        assert Config.load_from_dict({}).dict()["log_level"] == 40

    def test_normalize_email_before(self) -> None:
        """A before-hook normalizes the raw external string."""

        class Config(DotEnvConfig):
            email: str = Field()

            @field_validator("email", mode="before")
            def normalize(self, value: str, ctx: ValidatorContext) -> str:
                return value.strip().lower()

        assert Config.load_from_dict({"EMAIL": "  Ada@EXAMPLE.com "}).email == "ada@example.com"

    def test_custom_validation_raising_after(self) -> None:
        """An after-hook rejecting the value raises ConstraintViolationError."""

        class Config(DotEnvConfig):
            webhook_url: str = Field()

            @field_validator("webhook_url")
            def https_only(self, value: str, ctx: ValidatorContext) -> str:
                if not value.startswith("https://"):
                    raise ValueError("webhook_url must use HTTPS")
                return value

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"WEBHOOK_URL": "http://example.com"})

        err = exc_info.value
        assert err.constraint == "validator=https_only"
        assert "webhook_url must use HTTPS" in err.error_msg
        assert err.field_name == "webhook_url"
        assert err.env_var_name == "WEBHOOK_URL"
        assert isinstance(err.__cause__, ValueError)


class TestFieldValidatorOrdering:
    """Pin hook ordering: before hooks, strip, coercion, inline, after hooks."""

    def test_multiple_before_hooks_run_in_definition_order(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name", mode="before")
            def first(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-b1"

            @field_validator("name", mode="before")
            def second(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-b2"

        assert Config.load_from_dict({"NAME": "raw"}).name == "raw-b1-b2"

    def test_multiple_after_hooks_run_in_definition_order(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name")
            def first(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-a1"

            @field_validator("name")
            def second(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-a2"

        assert Config.load_from_dict({"NAME": "raw"}).name == "raw-a1-a2"

    def test_inline_validator_runs_before_decorator_after_hooks(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(validator=lambda v, ctx: v + "-inline")

            @field_validator("name")
            def hook(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-decorator"

        assert Config.load_from_dict({"NAME": "raw"}).name == "raw-inline-decorator"

    def test_before_hook_runs_before_strip(self) -> None:
        class Config(DotEnvConfig):
            code: str = Field(strip="_")

            @field_validator("code", mode="before")
            def append_marker(self, value: str, ctx: ValidatorContext) -> str:
                return value + "__"

        # before: "ab" -> "ab__"; strip then removes the marker. Had strip
        # run first, the marker would survive into the final value.
        assert Config.load_from_dict({"CODE": "ab"}).code == "ab"

    def test_coercion_sees_before_hook_result(self) -> None:
        class Config(DotEnvConfig):
            port: int = Field()

            @field_validator("port", mode="before")
            def words_to_digits(self, value: str, ctx: ValidatorContext) -> str:
                return value.replace("eight", "8")

        assert Config.load_from_dict({"PORT": "eight000"}).port == 8000

    def test_before_hook_runs_on_empty_raw_value(self) -> None:
        class Config(DotEnvConfig):
            fallback: str | None = Field(default=None)

            @field_validator("fallback", mode="before")
            def replace_empty(self, value: str, ctx: ValidatorContext) -> str:
                return "unset" if value == "" else value

        assert Config.load_from_dict({"FALLBACK": ""}).fallback == "unset"

    def test_inline_returning_none_stops_after_hooks(self) -> None:
        """A hook returning None ends the chain: later after hooks never run."""
        calls: list[Any] = []

        class Config(DotEnvConfig):
            value: str | None = Field(default="x", validator=lambda v, ctx: None)

            @field_validator("value")
            def after_spy(self, value: Any, ctx: ValidatorContext) -> Any:
                calls.append(value)
                return value

        config = Config.load_from_dict({"VALUE": "set"})
        assert config.value is None
        assert calls == []


class TestFieldValidatorTypedBeforeResults:
    """Non-str before-hook results: declared-type instances are used as-is."""

    def test_int_result_skips_coercion(self) -> None:
        """An int-subclass return survives with its type, proving the skip."""

        class Port(int):
            """Marker subclass: coercion to int would flatten it."""

        class Config(DotEnvConfig):
            port: int = Field()

            @field_validator("port", mode="before")
            def parse(self, value: str, ctx: ValidatorContext) -> int:
                return Port(int(value))

        config = Config.load_from_dict({"PORT": "8000"})
        assert config.port == 8000
        assert type(config.port) is Port

    def test_bool_result_loads(self) -> None:
        class Config(DotEnvConfig):
            flag: bool = Field()

            @field_validator("flag", mode="before")
            def parse(self, value: str, ctx: ValidatorContext) -> bool:
                return value == "on"

        assert Config.load_from_dict({"FLAG": "on"}).flag is True
        assert Config.load_from_dict({"FLAG": "off"}).flag is False

    def test_list_result_loads_with_elements_untouched(self) -> None:
        class Config(DotEnvConfig):
            items: list[str] = Field()

            @field_validator("items", mode="before")
            def parse(self, value: str, ctx: ValidatorContext) -> list[str]:
                return value.split("::")

        # String coercion would strip each element; the typed list passes
        # through with its whitespace intact.
        assert Config.load_from_dict({"ITEMS": " a ::b"}).items == [" a ", "b"]

    def test_uuid_result_loads_unchanged(self) -> None:
        tenant = UUID("550e8400-e29b-41d4-a716-446655440000")

        class Config(DotEnvConfig):
            tenant_id: UUID = Field()

            @field_validator("tenant_id", mode="before")
            def parse(self, value: str, ctx: ValidatorContext) -> UUID:
                return tenant

        assert Config.load_from_dict({"TENANT_ID": "ignored"}).tenant_id is tenant

    def test_secretstr_result_used_as_is(self) -> None:
        """A SecretStr return skips both strip and wrapping — no nesting."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(strip=True)

            @field_validator("api_key", mode="before")
            def wrap(self, value: str, ctx: ValidatorContext) -> SecretStr:
                return SecretStr(value)

        key = Config.load_from_dict({"API_KEY": " k "}).api_key
        # The padded value survives untouched and get_secret_value() stays
        # a str, with no SecretStr(SecretStr(...)) nesting.
        assert isinstance(key.get_secret_value(), str)
        assert key.get_secret_value() == " k "

    def test_optional_declared_type_result_loads(self) -> None:
        """The instance check runs against the Optional-unwrapped type."""

        class Config(DotEnvConfig):
            port: int | None = Field(default=None)

            @field_validator("port", mode="before")
            def parse(self, value: str, ctx: ValidatorContext) -> int:
                return int(value) * 2

        assert Config.load_from_dict({"PORT": "21"}).port == 42

    def test_before_hook_returning_none_for_optional_field_loads(self) -> None:
        """A None return on an Optional field adopts None; nothing re-coerces it."""

        class Config(DotEnvConfig):
            port: int | None = Field(default=None)

            @field_validator("port", mode="before")
            def parse(self, value: str, ctx: ValidatorContext) -> int | None:
                return None

        assert Config.load_from_dict({"PORT": "8000"}).port is None

    def test_wrong_typed_result_raises_clean_type_coercion_error(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name", mode="before")
            def to_int(self, value: str, ctx: ValidatorContext) -> int:
                return 5

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"NAME": "x"})

        err = exc_info.value
        assert err.field_name == "name"
        assert err.env_var_name == "NAME"
        assert "int" in err.error_msg
        assert "str" in err.error_msg

    def test_wrong_typed_result_aggregates_with_other_field_errors(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()
            other: str = Field(min_length=10)

            @field_validator("name", mode="before")
            def to_int(self, value: str, ctx: ValidatorContext) -> int:
                return 5

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Config.load_from_dict({"NAME": "x", "OTHER": "short"})

        assert [type(e) for e in exc_info.value.errors] == [
            TypeCoercionError,
            ConstraintViolationError,
        ]

    def test_sensitive_declared_type_masks_wrong_typed_result(self) -> None:
        """The error for a sensitive-typed field cannot embed the hook's value."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

            @field_validator("api_key", mode="before")
            def to_bytes(self, value: str, ctx: ValidatorContext) -> bytes:
                return value.encode()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-super-secret"})

        err = exc_info.value
        assert "bytes" in err.error_msg
        assert "pk-super-secret" not in str(err)
        assert "**********" in str(err)

    def test_any_typed_field_non_str_result_raises_clean_type_coercion_error(self) -> None:
        """Any passes inspect.isclass yet rejects isinstance; the failure must
        still surface as the library's field error, aggregated like every other
        one — never a bare internal TypeError."""

        class Config(DotEnvConfig):
            blob: Any = Field()

            @field_validator("blob", mode="before")
            def to_int(self, value: str, ctx: ValidatorContext) -> int:
                return 5

        with pytest.raises(TypeCoercionError) as single_info:
            Config.load_from_dict({"BLOB": "x"})

        err = single_info.value
        assert err.field_name == "blob"
        assert err.env_var_name == "BLOB"
        assert "int" in err.error_msg

        class WithOtherError(DotEnvConfig):
            blob: Any = Field()
            other: str = Field(min_length=10)

            @field_validator("blob", mode="before")
            def to_int(self, value: str, ctx: ValidatorContext) -> int:
                return 5

        with pytest.raises(MultipleValidationErrors) as agg_info:
            WithOtherError.load_from_dict({"BLOB": "x", "OTHER": "short"})

        assert [type(e) for e in agg_info.value.errors] == [
            TypeCoercionError,
            ConstraintViolationError,
        ]

    def test_isinstance_rejecting_declared_type_fails_cleanly(self) -> None:
        """A declared type that defeats isinstance (Any does; a hostile
        metaclass can too) lands in the library's coercion error, never the
        bare TypeError raised by the check itself."""

        class InstanceCheckRejects(type):
            def __instancecheck__(cls, obj: object) -> bool:
                raise TypeError("no instance checks")

        class Opaque(metaclass=InstanceCheckRejects):
            pass

        class Sub(Opaque):
            # isinstance() fast-paths exact-type matches past the metaclass;
            # a subclass instance is what actually consults it.
            pass

        class Config(DotEnvConfig):
            blob: Opaque = Field()

            @field_validator("blob", mode="before")
            def build(self, value: str, ctx: ValidatorContext) -> Opaque:
                return Sub()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"BLOB": "x"})

        err = exc_info.value
        assert err.field_name == "blob"
        assert "Opaque" in err.error_msg

    def test_generic_declared_type_named_in_error(self) -> None:
        """The error names list[str]; GenericAlias.__name__ would degrade it
        to the bare origin list."""

        class Config(DotEnvConfig):
            items: list[str] = Field()

            @field_validator("items", mode="before")
            def as_tuple(self, value: str, ctx: ValidatorContext) -> tuple[str, ...]:
                return (value,)

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"ITEMS": "x"})

        assert "list[str]" in exc_info.value.error_msg

    def test_choices_see_before_hook_transformed_value(self) -> None:
        """Constraints validate the transformed value, not the raw string."""

        class Config(DotEnvConfig):
            port: int = Field(choices=[80, 443])

            @field_validator("port", mode="before")
            def map_scheme(self, value: str, ctx: ValidatorContext) -> int:
                return 80 if value == "http" else 443

        assert Config.load_from_dict({"PORT": "http"}).port == 80

    def test_choices_reject_before_hook_transformed_value(self) -> None:
        class Config(DotEnvConfig):
            port: int = Field(choices=[80, 443])

            @field_validator("port", mode="before")
            def to_8080(self, value: str, ctx: ValidatorContext) -> int:
                return 8080

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"PORT": "http"})

        assert exc_info.value.constraint == "choices=[80, 443]"


class TestFieldValidatorCallableForms:
    """Plain methods, classmethods, staticmethods, and module functions all work."""

    def test_plain_method_receives_instance(self) -> None:
        receivers: list[Any] = []

        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name")
            def record_and_upper(self, value: str, ctx: ValidatorContext) -> str:
                receivers.append(self)
                return value.upper()

        config = Config.load_from_dict({"NAME": "ada"})
        assert config.name == "ADA"
        assert receivers == [config]

    def test_classmethod_receives_class(self) -> None:
        receivers: list[Any] = []

        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name")
            @classmethod
            def record_and_upper(cls, value: str, ctx: ValidatorContext) -> str:
                receivers.append(cls)
                return value.upper()

        assert Config.load_from_dict({"NAME": "ada"}).name == "ADA"
        assert receivers == [Config]

    def test_staticmethod_form(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name")
            @staticmethod
            def upper(value: str, ctx: ValidatorContext) -> str:
                return value.upper()

        assert Config.load_from_dict({"NAME": "ada"}).name == "ADA"

    def test_module_level_function_form(self) -> None:
        class Config(DotEnvConfig):
            tag: str = Field()
            normalize_tag = _module_normalize_tag

        assert Config.load_from_dict({"TAG": "  Web  "}).tag == "web"

    def test_decorator_below_classmethod_and_staticmethod(self) -> None:
        """The marker is found whichever order the two decorators are applied in."""

        class Config(DotEnvConfig):
            first: str = Field()
            second: str = Field()

            @classmethod
            @field_validator("first")
            def upper_first(cls, value: str, ctx: ValidatorContext) -> str:
                return value.upper()

            @staticmethod
            @field_validator("second")
            def upper_second(value: str, ctx: ValidatorContext) -> str:
                return value.upper()

        config = Config.load_from_dict({"FIRST": "a", "SECOND": "b"})
        assert config.first == "A"
        assert config.second == "B"

    def test_stacked_decorators_apply_to_multiple_fields(self) -> None:
        class Config(DotEnvConfig):
            first: str = Field()
            second: str = Field()

            @field_validator("second")
            @field_validator("first")
            def append_marker(self, value: str, ctx: ValidatorContext) -> str:
                return value + "!"

        config = Config.load_from_dict({"FIRST": "a", "SECOND": "b"})
        assert config.first == "a!"
        assert config.second == "b!"

    def test_unsignaturable_callable_called_directly(self) -> None:
        """A callable whose signature cannot be inspected binds no receiver."""

        class Opaque:
            def __call__(self, value: str, ctx: ValidatorContext) -> str:
                return value.strip()

        # A non-Signature __signature__ makes inspect.signature raise, so the
        # bind detection falls back to the no-receiver form.
        Opaque.__signature__ = "not-a-signature"  # type: ignore[assignment]

        class Config(DotEnvConfig):
            name: str = Field()
            normalize = field_validator("name", mode="before")(Opaque())

        assert Config.load_from_dict({"NAME": " bob "}).name == "bob"

    def test_keyword_only_hook_fails_through_the_wrapped_channel(self) -> None:
        """A hook with no positional parameters wires, then fails wrapped.

        Bind detection falls back to the no-receiver form, so the positional
        (value, ctx) call raises TypeError inside the hook — surfaced as a
        ConstraintViolationError like any wrong-arity hook.
        """

        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name")
            @staticmethod
            def kwargs_only(*, value: str, ctx: ValidatorContext) -> str:
                return value

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"NAME": "x"})


class TestFieldValidatorDefaults:
    """Before hooks never run on defaults; dict values are external input."""

    def test_before_hooks_skipped_on_default(self) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            name: str = Field(default=" Ada Lovelace ")

            @field_validator("name", mode="before")
            def upper(self, value: str, ctx: ValidatorContext) -> str:
                calls.append(value)
                return value.upper()

        config = Config.load_from_dict({})
        assert calls == []
        assert config.name == " Ada Lovelace "

    def test_before_hooks_run_on_load_from_dict_values(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name", mode="before")
            def upper(self, value: str, ctx: ValidatorContext) -> str:
                return value.upper()

        assert Config.load_from_dict({"NAME": "ada"}).name == "ADA"


class TestFieldValidatorErrorWrapping:
    """Hook errors are wrapped exactly like the inline validator's."""

    def test_value_error_wrapped_for_before_hook(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name", mode="before")
            def reject(self, value: str, ctx: ValidatorContext) -> str:
                raise ValueError("raw value not acceptable")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"NAME": "x"})

        err = exc_info.value
        assert err.constraint == "validator=reject"
        assert "raw value not acceptable" in err.error_msg
        assert err.field_name == "name"
        assert err.env_var_name == "NAME"
        assert isinstance(err.__cause__, ValueError)

    def test_type_error_wrapped_for_after_hook(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name")
            def reject(self, value: str, ctx: ValidatorContext) -> str:
                raise TypeError("value must be a str")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"NAME": "x"})

        err = exc_info.value
        assert err.constraint == "validator=reject"
        assert "value must be a str" in err.error_msg
        assert isinstance(err.__cause__, TypeError)

    def test_before_hook_returning_none_for_required_field_raises(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field()

            @field_validator("name", mode="before")
            def to_none(self, value: str, ctx: ValidatorContext) -> None:
                return None

        with pytest.raises(TypeCoercionError, match="non-optional"):
            Config.load_from_dict({"NAME": "x"})


class TestFieldValidatorSensitive:
    """Decorator hooks on sensitive fields never leak the secret."""

    def test_secretstr_after_hook_error_never_leaks(self) -> None:
        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

            @field_validator("api_key")
            def leaky(self, value: SecretStr, ctx: ValidatorContext) -> SecretStr:
                raise ValueError(f"bad key: {value.get_secret_value()}")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-super-secret"})

        err = exc_info.value
        assert err.constraint == "validator=leaky"
        assert "pk-super-secret" not in str(err)
        assert "pk-super-secret" not in repr(err)
        assert "bad key" not in str(err)
        assert "**********" in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_secretstr_before_hook_error_never_leaks(self) -> None:
        """Before hooks see the raw plaintext string — their errors are masked too."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

            @field_validator("api_key", mode="before")
            def leaky(self, value: str, ctx: ValidatorContext) -> str:
                raise ValueError(f"bad key: {value}")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-super-secret"})

        err = exc_info.value
        assert err.constraint == "validator=leaky"
        assert "pk-super-secret" not in str(err)
        assert "bad key" not in str(err)
        assert "**********" in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_secretstr_before_hook_transform_flows_into_coercion(self) -> None:
        """A passing before-hook's result stays raw — coercion wraps the secret."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

            @field_validator("api_key", mode="before")
            def trim(self, value: str, ctx: ValidatorContext) -> str:
                return value.strip()

        config = Config.load_from_dict({"API_KEY": " sk-abc "})
        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "sk-abc"

    def test_dsn_before_hook_error_masked_with_empty_chain(self) -> None:
        """Before-hook failures on a DSN field mask the URL password entirely."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

            @field_validator("database_url", mode="before")
            def leaky(self, value: str, ctx: ValidatorContext) -> str:
                raise ValueError(f"bad dsn: {value}")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"DATABASE_URL": "postgresql://user:hunter2@localhost/db"})

        err = exc_info.value
        assert err.constraint == "validator=leaky"
        assert "hunter2" not in str(err)
        assert "bad dsn" not in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_dsn_after_hook_bare_str_return_is_rewrapped(self) -> None:
        """An after hook returning a bare str keeps the value a masked DSN."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

            @field_validator("database_url")
            def to_str(self, value: PostgresDsn, ctx: ValidatorContext) -> str:
                return str(value)

        dsn = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost/db"}).database_url
        assert isinstance(dsn, PostgresDsn)
        assert str(dsn) == "postgresql://localhost/db"

    def test_dsn_before_and_after_hooks_pipeline(self) -> None:
        """Both modes on one DSN field: trim before, re-wrap on return after."""

        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()

            @field_validator("database_url", mode="before")
            def trim(self, value: str, ctx: ValidatorContext) -> str:
                return value.strip()

            @field_validator("database_url")
            def to_str(self, value: PostgresDsn, ctx: ValidatorContext) -> str:
                return str(value)

        dsn = Config.load_from_dict({"DATABASE_URL": " postgresql://localhost/db "}).database_url
        assert isinstance(dsn, PostgresDsn)
        assert str(dsn) == "postgresql://localhost/db"


class TestFieldValidatorContext:
    """Decorator hooks receive the same ValidatorContext as the inline form."""

    def test_context_contents_with_prefix_and_alias(self) -> None:
        before_contexts: list[ValidatorContext] = []
        after_contexts: list[ValidatorContext] = []

        class Config(DotEnvConfig):
            env_prefix = "APP_"

            name: str = Field()
            token: str = Field(alias="SECRET_TOKEN")

            @field_validator("name", mode="before")
            def before_spy(self, value: str, ctx: ValidatorContext) -> str:
                before_contexts.append(ctx)
                return value

            @field_validator("token")
            def after_spy(self, value: str, ctx: ValidatorContext) -> str:
                after_contexts.append(ctx)
                return value

        Config.load_from_dict({"APP_NAME": "x", "SECRET_TOKEN": "y"})

        assert len(before_contexts) == 1
        assert before_contexts[0].field_name == "name"
        assert before_contexts[0].env_var_name == "APP_NAME"
        assert len(after_contexts) == 1
        assert after_contexts[0].field_name == "token"
        assert after_contexts[0].env_var_name == "SECRET_TOKEN"


class TestFieldValidatorWiring:
    """Metaclass attachment and class-definition-time errors."""

    def test_attaches_to_bare_annotated_field(self) -> None:
        class Config(DotEnvConfig):
            name: str

            @field_validator("name")
            def upper(self, value: str, ctx: ValidatorContext) -> str:
                return value.upper()

        assert Config.load_from_dict({"NAME": "ada"}).name == "ADA"

    def test_unknown_field_name_raises_at_class_definition(self) -> None:
        with pytest.raises(ValueError) as exc_info:

            class Bad(DotEnvConfig):
                name: str = Field()

                @field_validator("no_such_field")
                def hook(self, value: str, ctx: ValidatorContext) -> str:
                    return value

        message = str(exc_info.value)
        assert "no_such_field" in message
        assert "Bad" in message
        assert "hook" in message

    def test_property_wrapped_hook_raises_at_class_definition(self) -> None:
        """A @property-wrapped hook fails loudly instead of wiring nothing."""

        with pytest.raises(TypeError) as exc_info:

            class Bad(DotEnvConfig):
                name: str = Field()

                @property
                @field_validator("name")
                def hook(self) -> str:
                    return "never runs"

        message = str(exc_info.value)
        assert "Bad.hook" in message
        assert "property" in message
        assert "staticmethod" in message

    def test_cached_property_wrapped_hook_raises_at_class_definition(self) -> None:
        """Any wrapper hiding the marker fails, not just @property."""

        with pytest.raises(TypeError, match="cached_property"):

            class Bad(DotEnvConfig):
                name: str = Field()

                @functools.cached_property
                @field_validator("name")
                def hook(self) -> str:
                    return "never runs"

    def test_hook_can_target_inherited_field(self) -> None:
        class Child(InheritanceBase):
            @field_validator("name")
            def extra(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-child"

        # Inherited hook first, then the subclass's own hook; the parent's
        # wiring is untouched.
        assert Child.load_from_dict({"NAME": "mixed"}).name == "MIXED-child"
        assert InheritanceBase.load_from_dict({"NAME": "mixed"}).name == "MIXED"


class InheritanceBase(DotEnvConfig):
    """Shared base with one after-mode decorator hook on ``name``."""

    name: str = Field()

    @field_validator("name")
    def normalize(self, value: str, ctx: ValidatorContext) -> str:
        return value.upper()


class TestFieldValidatorInheritance:
    """Hooks inherit; same-named overrides replace; parents stay unaffected."""

    def test_inherited_hook_runs_in_subclass(self) -> None:
        class Sub(InheritanceBase):
            pass

        assert Sub.load_from_dict({"NAME": "mixed"}).name == "MIXED"

    def test_same_named_override_replaces_hook(self) -> None:
        class Child(InheritanceBase):
            @field_validator("name")
            def normalize(self, value: str, ctx: ValidatorContext) -> str:
                return value.lower()

        assert Child.load_from_dict({"NAME": "MiXeD"}).name == "mixed"
        # The parent's hook is untouched by the subclass's wiring.
        assert InheritanceBase.load_from_dict({"NAME": "MiXeD"}).name == "MIXED"

    def test_undecorated_override_removes_hook(self) -> None:
        class Plain(InheritanceBase):
            def normalize(self, value: str, ctx: ValidatorContext) -> str:
                return "never called as a hook"

        assert Plain.load_from_dict({"NAME": "MiXeD"}).name == "MiXeD"

    def test_redeclared_field_keeps_inherited_decorator_hooks(self) -> None:
        class Child(InheritanceBase):
            name: str = Field(min_length=2)

        # The inherited hook survives the fresh Field(...); its own new
        # constraints still apply.
        assert Child.load_from_dict({"NAME": "mixed"}).name == "MIXED"
        with pytest.raises(ConstraintViolationError):
            Child.load_from_dict({"NAME": "x"})

    def test_reregistration_for_different_field_removes_parent_hook(self) -> None:
        """The method name is the registration identity across three levels."""

        class Grand(DotEnvConfig):
            first: str = Field()
            second: str = Field()

            @field_validator("first")
            def check(self, value: str, ctx: ValidatorContext) -> str:
                return value.upper()

        class Mid(Grand):
            pass

        class Leaf(Mid):
            @field_validator("second")
            def check(self, value: str, ctx: ValidatorContext) -> str:
                return value.lower()

        leaf = Leaf.load_from_dict({"FIRST": "x", "SECOND": "Y"})
        # Leaf's `check` replaced the registration wholesale: `first` lost
        # its hook, `second` gained the new one.
        assert leaf.first == "x"
        assert leaf.second == "y"
        # Ancestors keep their own wiring.
        assert Mid.load_from_dict({"FIRST": "x", "SECOND": "Y"}).first == "X"
        assert Grand.load_from_dict({"FIRST": "x", "SECOND": "Y"}).first == "X"


class TestFieldValidatorValidateFalse:
    """Hooks run with validate=False — transformation is part of loading."""

    def test_before_and_after_hooks_run_with_validate_false(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(min_length=50)

            @field_validator("name", mode="before")
            def before(self, value: str, ctx: ValidatorContext) -> str:
                return value.upper()

            @field_validator("name")
            def after(self, value: str, ctx: ValidatorContext) -> str:
                return value + "-after"

        # "abc" violates min_length=50, but validation is skipped and the
        # hooks still transform the value.
        assert Config.load_from_dict({"NAME": "abc"}, validate=False).name == "ABC-after"


class TestFieldValidatorNested:
    """Nested config classes run their own decorator hooks."""

    def test_nested_config_hooks_run(self) -> None:
        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            email: str = Field()

            @field_validator("email", mode="before")
            def lower(self, value: str, ctx: ValidatorContext) -> str:
                return value.lower()

        class Outer(DotEnvConfig):
            inner: Inner

        config = Outer.load_from_dict({"INNER_EMAIL": "USER@Example.COM"})
        assert config.inner.email == "user@example.com"


class TestFieldValidatorDecoratorContract:
    """The decorator validates its own arguments and targets."""

    def test_non_str_field_name_rejected(self) -> None:
        with pytest.raises(TypeError, match="field_name"):
            field_validator(123)  # type: ignore[arg-type]

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            field_validator("name", mode="sometimes")  # type: ignore[arg-type]

    def test_non_callable_target_rejected(self) -> None:
        with pytest.raises(TypeError, match="callable"):
            field_validator("name")("not-a-callable")  # type: ignore[call-overload]

    def test_target_without_attribute_space_rejected(self) -> None:
        """Builtins cannot carry the marker; the decorator says so clearly."""
        with pytest.raises(TypeError, match="attribute"):
            field_validator("name")(print)
