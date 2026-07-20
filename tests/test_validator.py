"""Tests for the Field(validator=...) custom validation/transformation hook."""

from typing import Any

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    MultipleValidationErrors,
    PostgresDsn,
    SecretStr,
    TypeCoercionError,
)
from dotenvmodel.fields import FieldInfo, ValidatorContext


def check_starts_sk(value: Any, ctx: ValidatorContext) -> Any:
    """Module-level check-only validator used by several tests."""
    if not str(value).startswith("sk-"):
        raise ValueError("API key must start with 'sk-'")
    return value


class TestValidatorTransform:
    """Test that validator return values replace the field value."""

    def test_transform_lowercase(self) -> None:
        """The hook's return value becomes the final value."""

        class Config(DotEnvConfig):
            region: str = Field(default="US-EAST-1", validator=lambda v, ctx: v.lower())

        config = Config.load_from_dict({})
        assert config.region == "us-east-1"

    def test_transform_applied_to_env_value(self) -> None:
        """Transforms apply to coerced env values too."""

        class Config(DotEnvConfig):
            region: str = Field(validator=lambda v, ctx: v.strip().upper())

        config = Config.load_from_dict({"REGION": "eu-west-1"})
        assert config.region == "EU-WEST-1"

    def test_transform_receives_coerced_value(self) -> None:
        """The hook receives the coerced value, not the raw string."""
        received: list[Any] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            received.append(value)
            return value

        class Config(DotEnvConfig):
            port: int = Field(validator=spy)

        config = Config.load_from_dict({"PORT": "8000"})
        assert config.port == 8000
        assert received == [8000]
        assert isinstance(received[0], int)


class TestValidatorContext:
    """Test the ValidatorContext contents passed to the hook."""

    def test_context_contents(self) -> None:
        """Context carries the field name and resolved env var name."""
        contexts: list[ValidatorContext] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            contexts.append(ctx)
            return value

        class Config(DotEnvConfig):
            api_key: str = Field(validator=spy)

        config = Config.load_from_dict({"API_KEY": "sk-abc"})
        assert config.api_key == "sk-abc"
        assert len(contexts) == 1
        assert contexts[0].field_name == "api_key"
        assert contexts[0].env_var_name == "API_KEY"

    def test_context_with_prefix_and_alias(self) -> None:
        """env_var_name reflects env_prefix and alias resolution."""
        contexts: list[ValidatorContext] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            contexts.append(ctx)
            return value

        class Config(DotEnvConfig):
            env_prefix = "APP_"

            name: str = Field(validator=spy)
            token: str = Field(alias="SECRET_TOKEN", validator=spy)

        Config.load_from_dict({"APP_NAME": "x", "SECRET_TOKEN": "y"})
        assert contexts[0].env_var_name == "APP_NAME"
        assert contexts[1].env_var_name == "SECRET_TOKEN"

    def test_context_is_frozen(self) -> None:
        """ValidatorContext is immutable."""
        ctx = ValidatorContext(field_name="a", env_var_name="A")
        with pytest.raises(AttributeError):
            ctx.field_name = "b"  # type: ignore[misc]


class TestValidatorErrorWrapping:
    """Test ValueError/TypeError from hooks become ConstraintViolationError."""

    def test_value_error_wrapped(self) -> None:
        """A hook ValueError is wrapped with constraint=validator=<fn name>."""

        class Config(DotEnvConfig):
            api_key: str = Field(validator=check_starts_sk)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-abc"})

        assert exc_info.value.constraint == "validator=check_starts_sk"
        assert "API key must start with 'sk-'" in exc_info.value.error_msg
        assert exc_info.value.field_name == "api_key"
        assert exc_info.value.env_var_name == "API_KEY"

    def test_type_error_wrapped(self) -> None:
        """A hook TypeError is also wrapped."""

        def bad(value: Any, ctx: ValidatorContext) -> Any:
            raise TypeError("expected something else")

        class Config(DotEnvConfig):
            value: str = Field(validator=bad)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        assert exc_info.value.constraint == "validator=bad"
        assert "expected something else" in exc_info.value.error_msg

    def test_lambda_uses_lambda_name(self) -> None:
        """Lambdas report '<lambda>' as the validator name."""

        def raise_err(v: Any, ctx: ValidatorContext) -> Any:
            raise ValueError("nope")

        class Config(DotEnvConfig):
            value: str = Field(validator=lambda v, ctx: raise_err(v, ctx))

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        assert exc_info.value.constraint == "validator=<lambda>"

    def test_aggregation_into_multiple_validation_errors(self) -> None:
        """Validator failures aggregate like any other constraint failure."""

        def no_a(value: Any, ctx: ValidatorContext) -> Any:
            if "a" in value:
                raise ValueError("no 'a' allowed")
            return value

        class Config(DotEnvConfig):
            first: str = Field(validator=no_a)
            second: str = Field(validator=no_a)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Config.load_from_dict({"FIRST": "aaa", "SECOND": "bab"})

        assert len(exc_info.value.errors) == 2
        assert all(isinstance(e, ConstraintViolationError) for e in exc_info.value.errors)
        assert {e.field_name for e in exc_info.value.errors} == {"first", "second"}
        assert all(e.constraint == "validator=no_a" for e in exc_info.value.errors)  # type: ignore[attr-defined]

    def test_constraint_violation_error_passes_through(self) -> None:
        """A hook raising ConstraintViolationError directly is not re-wrapped."""

        def custom(value: Any, ctx: ValidatorContext) -> Any:
            raise ConstraintViolationError(
                field_name=ctx.field_name,
                value=value,
                constraint="custom-rule",
                error_msg="My custom message",
                env_var_name=ctx.env_var_name,
            )

        class Config(DotEnvConfig):
            value: str = Field(validator=custom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        assert exc_info.value.constraint == "custom-rule"
        assert exc_info.value.error_msg == "My custom message"

    def test_other_exceptions_bubble_up(self) -> None:
        """Non-validation exceptions (programming errors) are not wrapped."""

        def broken(value: Any, ctx: ValidatorContext) -> Any:
            raise RuntimeError("bug in the hook")

        class Config(DotEnvConfig):
            value: str = Field(validator=broken)

        with pytest.raises(RuntimeError, match="bug in the hook"):
            Config.load_from_dict({"VALUE": "x"})


class TestValidatorPipelineSemantics:
    """Test where the hook sits in the load pipeline."""

    def test_runs_after_builtin_constraints(self) -> None:
        """Built-in constraints run first; a failing built-in means no hook call."""
        calls: list[Any] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            calls.append(value)
            return value

        class Config(DotEnvConfig):
            key: str = Field(min_length=5, validator=spy)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"KEY": "abc"})

        assert exc_info.value.constraint == "min_length=5"
        assert calls == []

    def test_builtins_not_rerun_after_transform(self) -> None:
        """A transform result is not re-checked against built-in constraints."""

        class Config(DotEnvConfig):
            key: str = Field(min_length=5, validator=lambda v, ctx: v[:2])

        # "abcdef" passes min_length=5, then the hook shortens to "ab" —
        # min_length is NOT re-run on the transformed value.
        config = Config.load_from_dict({"KEY": "abcdef"})
        assert config.key == "ab"

    def test_skipped_on_none(self) -> None:
        """The hook never runs for None values."""
        calls: list[Any] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            calls.append(value)
            return value

        class Config(DotEnvConfig):
            value: str | None = Field(default=None, validator=spy)

        config = Config.load_from_dict({})
        assert config.value is None
        assert calls == []

    def test_skipped_on_empty_optional(self) -> None:
        """Empty env values for Optional fields coerce to None — hook skipped."""
        calls: list[Any] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            calls.append(value)
            return value

        class Config(DotEnvConfig):
            value: str | None = Field(default=None, validator=spy)

        config = Config.load_from_dict({"VALUE": ""})
        assert config.value is None
        assert calls == []

    def test_runs_with_validate_false(self) -> None:
        """The hook is part of loading: it runs even with validate=False."""

        class Config(DotEnvConfig):
            region: str = Field(validator=lambda v, ctx: v.lower())

        config = Config.load_from_dict({"REGION": "US-EAST-1"}, validate=False)
        assert config.region == "us-east-1"

    def test_failing_validator_raises_with_validate_false(self) -> None:
        """A failing validator still raises through validate=False.

        The validator is part of loading, not validation: a ValueError from
        the hook is wrapped in ConstraintViolationError even when the built-in
        validation pass is skipped.
        """

        def fail(value: Any, ctx: ValidatorContext) -> Any:
            raise ValueError("always fails")

        class Config(DotEnvConfig):
            value: str = Field(validator=fail)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"}, validate=False)

        assert "always fails" in exc_info.value.error_msg

    def test_runs_on_default_value(self) -> None:
        """The hook applies to defaults, not just env-provided values."""

        class Config(DotEnvConfig):
            region: str = Field(default="US-EAST-1", validator=lambda v, ctx: v.lower())

        config = Config.load_from_dict({})
        assert config.region == "us-east-1"

    def test_runs_on_coerced_default_value(self) -> None:
        """The hook receives the coerced default for non-str field types.

        A str default for a non-str field is routed through coerce_value before
        the hook runs (GROUP A fix), so the hook sees the typed value, not the
        raw string.
        """
        received: list[Any] = []

        def spy(value: Any, ctx: ValidatorContext) -> Any:
            received.append(value)
            return value

        class Config(DotEnvConfig):
            port: int = Field(default="8000", validator=spy)

        config = Config.load_from_dict({})
        assert config.port == 8000
        assert received == [8000]
        assert isinstance(received[0], int)


class TestValidatorSecretStr:
    """Test SecretStr handling: masked reporting and no plaintext leaks."""

    def test_secret_pass(self) -> None:
        """A passing SecretStr value flows through the hook."""

        def check(value: Any, ctx: ValidatorContext) -> Any:
            if not value.get_secret_value().startswith("sk-"):
                raise ValueError("bad prefix")
            return value

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=check)

        config = Config.load_from_dict({"API_KEY": "sk-secret"})
        assert config.api_key.get_secret_value() == "sk-secret"

    def test_secret_error_reports_masked_value(self) -> None:
        """The wrapped error carries the masked SecretStr, not plaintext."""

        def leaky_check(value: Any, ctx: ValidatorContext) -> Any:
            # A badly-behaved hook that embeds the plaintext in its message
            raise ValueError(f"invalid key: {value.get_secret_value()}")

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=leaky_check)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-super-secret"})

        err = exc_info.value
        assert err.constraint == "validator=leaky_check"
        msg = str(err)
        assert "pk-super-secret" not in msg
        assert "**********" in msg
        # The hook's exception text must NOT be embedded for secrets
        assert "invalid key" not in msg

    def test_secret_no_plaintext_anywhere_in_chain(self) -> None:
        """No plaintext in the exception or anywhere in __cause__/__context__."""

        def leaky_check(value: Any, ctx: ValidatorContext) -> Any:
            raise ValueError(f"invalid key: {value.get_secret_value()}")

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=leaky_check)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-super-secret"})

        exc: BaseException | None = exc_info.value
        while exc is not None:
            assert "pk-super-secret" not in str(exc)
            assert "pk-super-secret" not in str(getattr(exc, "value", ""))
            exc = exc.__cause__ or exc.__context__

    def test_non_secret_includes_hook_message_and_cause(self) -> None:
        """Non-secret fields embed str(e) and chain to the original error."""

        def check(value: Any, ctx: ValidatorContext) -> Any:
            raise ValueError("must be fancy")

        class Config(DotEnvConfig):
            value: str = Field(validator=check)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "plain"})

        err = exc_info.value
        assert "must be fancy" in err.error_msg
        assert isinstance(err.__cause__, ValueError)


class TestValidatorFieldInfo:
    """Test FieldInfo handling of the validator parameter."""

    def test_validator_stored_on_field_info(self) -> None:
        """FieldInfo stores the validator callable."""

        def hook(value: Any, ctx: ValidatorContext) -> Any:
            return value

        info = FieldInfo(validator=hook)
        assert info.validator is hook
        assert FieldInfo().validator is None

    def test_non_callable_validator_rejected(self) -> None:
        """Field(validator=...) must be callable or raise TypeError at construction."""
        with pytest.raises(TypeError) as exc_info:
            Field(validator="not-a-callable")  # type: ignore[arg-type]

        assert "validator" in str(exc_info.value)
        assert "callable" in str(exc_info.value).lower()


class TestValidatorSensitiveHardening:
    """GROUP B: masking on declared type, no-chain errors, and result re-wrapping."""

    def test_secretstr_str_result_re_wrapped(self) -> None:
        """A hook returning a plain str for a SecretStr field is re-wrapped."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=lambda v, ctx: v.get_secret_value().upper())

        config = Config.load_from_dict({"API_KEY": "sk-abc"})
        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "SK-ABC"
        assert repr(config.api_key) == "SecretStr('**********')"

    def test_dsn_str_result_re_wrapped(self) -> None:
        """A hook returning a plain str for a DSN field is re-constructed."""

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(validator=lambda v, ctx: str(v).replace("host", "host2"))

        config = Config.load_from_dict({"DB": "postgresql://user:hunter2@host/db"})
        assert isinstance(config.db, PostgresDsn)
        assert config.db.host == "host2"
        assert "hunter2" not in repr(config.db)

    def test_dsn_str_result_invalid_masked(self) -> None:
        """A hook returning an invalid str for a DSN field is masked, not leaked."""

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(validator=lambda v, ctx: "not-a-valid-dsn")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"DB": "postgresql://user:hunter2@host/db"})

        err = exc_info.value
        assert "hunter2" not in str(err)
        assert "hunter2" not in repr(err)
        assert "not-a-valid-dsn" not in str(err)

    def test_secretstr_runtime_error_masked_no_chain(self) -> None:
        """A RuntimeError on a SecretStr field is masked and leaves no chain."""

        def boom(value: Any, ctx: ValidatorContext) -> Any:
            raise RuntimeError(f"bad secret: {value.get_secret_value()}")

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=boom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "super-secret"})

        err = exc_info.value
        assert err.constraint == "validator=boom"
        assert "super-secret" not in str(err)
        assert "super-secret" not in repr(err)
        assert "bad secret" not in str(err)
        assert "bad secret" not in repr(err)
        assert err.__cause__ is None
        assert err.__context__ is None
        # Exhaustive walk: nothing in the chain carries the secret/text
        exc: BaseException | None = err
        while exc is not None:
            assert "super-secret" not in str(exc)
            assert "bad secret" not in str(exc)
            assert "super-secret" not in str(getattr(exc, "value", ""))
            exc = exc.__cause__ or exc.__context__

    def test_dsn_hook_error_password_absent_everywhere(self) -> None:
        """A RuntimeError on a DSN field never leaks the URL password."""

        def boom(value: Any, ctx: ValidatorContext) -> Any:
            raise RuntimeError(f"invalid dsn: {value}")

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(validator=boom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"DB": "postgresql://user:hunter2@host/db"})

        err = exc_info.value
        assert "hunter2" not in str(err)
        assert "hunter2" not in repr(err)
        assert "invalid dsn" not in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_dsn_hook_value_error_password_absent(self) -> None:
        """A ValueError on a DSN field masks the URL password everywhere."""

        def boom(value: Any, ctx: ValidatorContext) -> Any:
            raise ValueError(f"cannot use {value}")

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(validator=boom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"DB": "postgresql://user:hunter2@host/db"})

        err = exc_info.value
        assert "hunter2" not in str(err)
        assert "hunter2" not in repr(err)
        assert "cannot use" not in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_secretstr_hook_cve_masked_reconstructed(self) -> None:
        """A hook-raised CVE on a SecretStr field is re-constructed masked."""

        def custom(value: Any, ctx: ValidatorContext) -> Any:
            raise ConstraintViolationError(
                field_name=ctx.field_name,
                value=value,
                constraint="custom-rule",
                error_msg=f"bad: {value.get_secret_value()}",
                env_var_name=ctx.env_var_name,
            )

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=custom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "super-secret"})

        err = exc_info.value
        # constraint, value, and message are all replaced/masked
        assert err.constraint == "validator=custom"
        assert "super-secret" not in str(err)
        assert "bad:" not in str(err)
        assert "**********" in str(err)
        assert "validator=custom" in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_secretstr_hook_cve_constraint_secret_masked(self) -> None:
        """A hook CVE with the secret embedded in ``constraint=`` is masked.

        Regression test: the masked reconstruction must not preserve a
        hook-authored constraint string, since it may embed the plaintext.
        """

        def custom(value: Any, ctx: ValidatorContext) -> Any:
            raise ConstraintViolationError(
                field_name=ctx.field_name,
                value=value,
                constraint=f"must_not_equal={value.get_secret_value()}",
                error_msg="rejected",
                env_var_name=ctx.env_var_name,
            )

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=custom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "super-secret"})

        err = exc_info.value
        assert err.constraint == "validator=custom"
        assert "super-secret" not in str(err)
        assert "super-secret" not in repr(err)
        assert "must_not_equal" not in str(err)
        assert "must_not_equal" not in repr(err)
        assert err.__cause__ is None
        assert err.__context__ is None

    def test_masking_follows_declared_type_not_instance(self) -> None:
        """Masking follows the declared type even when the value isn't a SecretStr.

        A non-str default on a SecretStr field is left untouched by coercion, so
        the runtime value is an int — but the field is still declared SecretStr,
        so a hook failure is masked generically.
        """

        def boom(value: Any, ctx: ValidatorContext) -> Any:
            raise RuntimeError(f"got {value}")

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default=42, validator=boom)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({})

        err = exc_info.value
        assert "**********" in str(err)
        assert "got" not in str(err)
        assert err.__cause__ is None
        assert err.__context__ is None


class TestValidatorNoneReturn:
    """GROUP B5: a hook returning None is only valid for Optional fields."""

    def test_none_return_required_field_raises(self) -> None:
        """A hook returning None for a non-optional field raises TypeCoercionError."""

        class Config(DotEnvConfig):
            value: str = Field(validator=lambda v, ctx: None)

        with pytest.raises(TypeCoercionError, match="non-optional"):
            Config.load_from_dict({"VALUE": "x"})

    def test_none_return_required_field_reports_declared_type(self) -> None:
        """The TypeCoercionError message names the declared type, not 'unknown'.

        The plain (non-sensitive) path must thread the Optional-unwrapped
        declared type into the error so the hint reads ``valid str`` rather
        than the useless ``valid unknown``.
        """

        class Config(DotEnvConfig):
            value: str = Field(validator=lambda v, ctx: None)

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        msg = str(exc_info.value)
        assert "str" in msg
        assert "unknown" not in msg

    def test_none_return_optional_field_allowed(self) -> None:
        """A hook returning None for an Optional field loads None."""

        class Config(DotEnvConfig):
            value: str | None = Field(default="x", validator=lambda v, ctx: None)

        config = Config.load_from_dict({})
        assert config.value is None

    def test_none_return_optional_secretstr_allowed(self) -> None:
        """A hook returning None for an Optional SecretStr field loads None."""

        class Config(DotEnvConfig):
            api_key: SecretStr | None = Field(validator=lambda v, ctx: None)

        config = Config.load_from_dict({"API_KEY": "sk-abc"})
        assert config.api_key is None

    def test_none_return_required_secretstr_raises(self) -> None:
        """A hook returning None for a non-optional SecretStr field raises."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(validator=lambda v, ctx: None)

        with pytest.raises(TypeCoercionError, match="non-optional"):
            Config.load_from_dict({"API_KEY": "sk-abc"})


class TestValidatorNameRendering:
    """GROUP B8: validator name rendering is DRY and consistent."""

    def test_partial_validator_name_in_repr_and_error(self) -> None:
        """A functools.partial validator renders its name consistently."""
        from functools import partial

        def base_check(value: Any, ctx: ValidatorContext) -> Any:
            raise ValueError("nope")

        partial_check = partial(base_check)

        # FieldInfo repr
        info = FieldInfo(validator=partial_check)  # type: ignore[arg-type]
        assert "validator=partial" in repr(info)

        # Error path
        class Config(DotEnvConfig):
            value: str = Field(validator=partial_check)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        assert exc_info.value.constraint == "validator=partial"

    def test_lambda_name_in_repr(self) -> None:
        """A lambda validator renders '<lambda>' in FieldInfo repr."""

        info = FieldInfo(validator=lambda v, ctx: v)  # type: ignore[arg-type]
        assert "validator=<lambda>" in repr(info)


class TestValidatorEmptyMessage:
    """GROUP B7: an empty hook error message uses a fallback."""

    def test_empty_hook_message_uses_fallback(self) -> None:
        """An empty hook error message avoids a bare 'Error:' line."""

        def empty(value: Any, ctx: ValidatorContext) -> Any:
            raise ValueError("")

        class Config(DotEnvConfig):
            value: str = Field(validator=empty)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        assert "validator failed" in str(exc_info.value)


class TestValidatorCheapPins:
    """One-assertion pins for validator edge behaviors."""

    def test_transform_on_bool_field(self) -> None:
        """A validator can transform a bool field's coerced value."""

        class Config(DotEnvConfig):
            flag: bool = Field(default=False, validator=lambda v, ctx: not v)

        config = Config.load_from_dict({"FLAG": "true"})
        assert config.flag is False

    def test_transform_on_list_field(self) -> None:
        """A validator can transform a list field's items (e.g. uppercase them)."""

        class Config(DotEnvConfig):
            tags: list[str] = Field(
                default_factory=list, validator=lambda v, ctx: [t.upper() for t in v]
            )

        config = Config.load_from_dict({"TAGS": "a,b,c"})
        assert config.tags == ["A", "B", "C"]

    def test_one_arg_validator_typeerror_wrapped(self) -> None:
        """A 1-arg callable (no ctx) gets a TypeError that's wrapped as CVE.

        The hook signature is ``Callable[[Any, ValidatorContext], Any]``; a
        wrong-arity callable raises ``TypeError`` when called with two args,
        which is wrapped in ``ConstraintViolationError`` so callers get a clear
        validation error rather than a confusing ``TypeError``.
        """

        def one_arg(value: str) -> str:
            return value

        class Config(DotEnvConfig):
            value: str = Field(validator=one_arg)  # type: ignore[arg-type]

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"VALUE": "x"})

        assert exc_info.value.constraint == "validator=one_arg"
