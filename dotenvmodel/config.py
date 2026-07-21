"""DotEnvConfig base class for configuration management."""

import builtins
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Self, cast

from typing_extensions import TypeForm

from dotenvmodel._constants import LOGGER_NAME
from dotenvmodel.coercion import apply_strip, coerce_value, is_string_like_type, unwrap_optional
from dotenvmodel.exceptions import (
    ConstraintViolationError,
    MissingFieldError,
    MultipleValidationErrors,
    TypeCoercionError,
    ValidationError,
)
from dotenvmodel.fields import FieldInfo, ValidatorContext, _validator_name
from dotenvmodel.loading import get_env_var, get_env_var_name, load_env_files
from dotenvmodel.metaclass import ConfigMeta
from dotenvmodel.types import SecretStr, is_sensitive_type, is_sensitive_value
from dotenvmodel.validation import validate_field

logger = logging.getLogger(LOGGER_NAME)


def _masked_report_value(value: Any) -> Any:
    """Return a value whose ``repr`` masks the secret, for use in errors.

    For a sensitive-typed field the runtime value is normally already a
    ``SecretStr`` or ``BaseDsn`` (whose ``repr`` redacts it), so it is returned
    directly. When it is not — e.g. a non-str default left untouched by
    coercion on a declared-sensitive field — a fresh ``SecretStr`` mask is used
    so nothing about the real value can reach the error message.
    """
    if is_sensitive_value(value):
        return value
    return SecretStr("**********")


def _run_sensitive_validator(
    field_name: str,
    value: Any,
    unwrapped_type: type[Any],
    validator: Callable[[Any, ValidatorContext], Any],
    env_var_name: str,
    is_optional: bool,
    name: str,
    context: ValidatorContext,
) -> Any:
    """Run a validator hook for a sensitive-typed field.

    Any hook failure (``ConstraintViolationError`` or any other ``Exception``)
    is masked: nothing from the hook exception — message, ``constraint``, or
    any other text, any of which may embed the plaintext secret or a URL
    password — is carried into the raised error, which uses a generic
    ``validator=<name>`` constraint and message. The masked error is raised
    outside the ``except`` block with ``__cause__``/``__context__`` cleared
    (an empty chain). A plain-``str`` return value is re-wrapped in the
    declared type so the secret stays masked in ``repr``.

    Note:
        Traceback frame locals across the load path still reference the live
        value (this frame's ``value``, caller frames' ``raw_value`` and
        ``value``), so locals-capturing error reporting must not be enabled
        for processes loading secrets — see SECURITY.md.
    """
    failed = False
    result: Any = None
    try:
        result = validator(value, context)
        # Re-wrap a bare str so the secret stays masked in repr. A SecretStr
        # result is not a str subclass (passes through); a BaseDsn result is a
        # str subclass and an instance of the declared type (passes through).
        # Only a bare str gets (re-)constructed — a ValueError from DSN
        # construction is caught below and masked.
        if isinstance(result, str) and not isinstance(result, unwrapped_type):
            result = unwrapped_type(result)
    except Exception:
        # Carry nothing over from the hook exception — message, constraint, or
        # any other text may embed the plaintext secret. Raising the masked
        # error outside the except keeps __context__ None.
        failed = True

    if failed:
        raise ConstraintViolationError(
            field_name=field_name,
            value=_masked_report_value(value),
            constraint=f"validator={name}",
            error_msg=f"validator={name} rejected the value",
            env_var_name=env_var_name,
        ) from None

    # A None return is only valid for Optional fields.
    if result is None and not is_optional:
        raise TypeCoercionError(
            field_name=field_name,
            value=_masked_report_value(value),
            error_msg=f"validator={name} returned None for non-optional field",
            field_type=unwrapped_type,
            env_var_name=env_var_name,
        )
    return result


def _run_plain_validator(
    field_name: str,
    value: Any,
    validator: Callable[[Any, ValidatorContext], Any],
    env_var_name: str,
    is_optional: bool,
    name: str,
    context: ValidatorContext,
    unwrapped_type: Any,
) -> Any:
    """Run a validator hook for a non-sensitive field.

    ``ConstraintViolationError`` passes through untouched;
    ``ValueError``/``TypeError`` are wrapped in ``ConstraintViolationError``
    (chained to the original) so they aggregate into ``MultipleValidationErrors``;
    other exceptions bubble up as programming errors. An empty hook message uses
    a fallback so the error never renders a bare ``"Error:"`` line.
    """
    constraint = f"validator={name}"
    hook_error: ValueError | TypeError | None = None
    result: Any = None
    try:
        result = validator(value, context)
    except ConstraintViolationError:
        raise  # Custom messages pass through untouched
    except (ValueError, TypeError) as e:
        hook_error = e

    if hook_error is not None:
        msg = str(hook_error) or "validator failed"
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=constraint,
            error_msg=msg,
            env_var_name=env_var_name,
        ) from hook_error

    # A None return is only valid for Optional fields.
    if result is None and not is_optional:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg=f"validator={name} returned None for non-optional field",
            field_type=unwrapped_type,
            env_var_name=env_var_name,
        )
    return result


def _run_field_validator(
    field_name: str,
    value: Any,
    field_type: TypeForm[Any],
    validator: Callable[[Any, ValidatorContext], Any],
    env_var_name: str,
) -> Any:
    """Run a field's custom ``validator`` hook and return the final value.

    The hook receives the coerced, built-in-constraint-validated value plus a
    ``ValidatorContext``; its return value replaces the field value (built-in
    constraints are not re-run on a transformed value).

    Masking is decided by the declared type (Optional-unwrapped), not by
    ``isinstance(value)``, so a default-path value that has not been wrapped
    cannot bypass redaction. For sensitive fields (``SecretStr``/``BaseDsn``)
    any hook failure is masked generically with the secret appearing nowhere in
    the error or its chain; for non-sensitive fields ``ValueError``/``TypeError``
    text is embedded and chained.

    Raises:
        ConstraintViolationError: If the hook raises, or returns ``None`` for a
            non-optional field's type-coercion counterpart.
        TypeCoercionError: If the hook returns ``None`` for a non-optional field.
    """
    unwrapped_type = unwrap_optional(field_type)
    sensitive = is_sensitive_type(field_type)
    is_optional = unwrapped_type is not field_type
    name = _validator_name(validator)
    context = ValidatorContext(field_name=field_name, env_var_name=env_var_name)

    if sensitive:
        # is_sensitive_type() returned True, so the unwrapped type is a class
        # (SecretStr or a BaseDsn subclass) — safe to treat as a callable type.
        return _run_sensitive_validator(
            field_name,
            value,
            cast(type[Any], unwrapped_type),
            validator,
            env_var_name,
            is_optional,
            name,
            context,
        )
    return _run_plain_validator(
        field_name,
        value,
        validator,
        env_var_name,
        is_optional,
        name,
        context,
        unwrapped_type,
    )


def _raise_collected(errors: list[ValidationError] | None) -> None:
    """Raise collected validation errors, preserving single-error types.

    Shared by the field-error loop and the `post_load` hook in
    `DotEnvConfig._load_fields`. A single error is raised unchanged so its
    specific type (e.g. `MissingFieldError`, `ConstraintViolationError`)
    reaches the caller; several are aggregated into
    `MultipleValidationErrors`. `None` and an empty list both mean success.

    Args:
        errors: Collected errors, or `None` when the source reports success.

    Raises:
        ValidationError: The single collected error, raised unchanged.
        MultipleValidationErrors: If two or more errors were collected.
    """
    if not errors:
        return
    if len(errors) == 1:
        raise errors[0]
    raise MultipleValidationErrors(errors)


class DotEnvConfig(metaclass=ConfigMeta):
    """Base class for type-safe environment configuration.

    Subclass this to define your configuration schema using type annotations
    and `Field()` descriptors. The metaclass automatically discovers fields,
    and `load()` reads from environment variables and `.env` files.

    When to use:
        - When you need type-safe configuration from environment variables
        - When you want automatic `.env` file loading with cascading
        - When you need validation constraints on config values
        - When you want IDE autocomplete and type checker support for config

    When NOT to use:
        - If you need configuration from YAML/TOML/JSON files (this library
          is specifically for environment variables and `.env` files)
        - If you need non-optional Union types (e.g., `str | int`)

    Class attributes:
        env_prefix: Prefix prepended to every field's environment variable
            name (default `""`, no prefix). Fields with an `alias` ignore it.
        strip_strings: Default strip mode for string-like fields (default
            `False`). When `True`, raw values of `str`/`SecretStr` (and their
            Optional forms and `str` subclasses) are whitespace-stripped before
            coercion. Per-field `Field(strip=...)` overrides this setting.

    Example:
        ```python
        class AppConfig(DotEnvConfig):
            env_prefix: str = "APP_"
            strip_strings: bool = True

            # Required fields
            database_url: str = Field()
            api_key: str = Required

            # Optional with defaults
            debug: bool = Field(default=False)
            port: int = Field(default=8000, ge=1, le=65535)

            # With validation
            pool_size: int = Field(default=10, ge=1, le=100)

            # Opt out of the class-level stripping for this field
            literal: str = Field(strip=False)

        # Load configuration
        config = AppConfig.load(env="dev")
        print(config.database_url)
        ```

    See Also:
        - [`Field`][dotenvmodel.fields.Field]: For defining field constraints and defaults.
        - [`load`][dotenvmodel.config.DotEnvConfig.load]: For loading from environment.
        - [`load_from_dict`][dotenvmodel.config.DotEnvConfig.load_from_dict]: For testing.
    """

    _fields: builtins.dict[str, tuple[type, FieldInfo]]
    _loaded: bool = False
    _load_env: str | None = None  # Store the env used during load
    _load_override: bool = True  # Store the override flag used during load
    _load_env_dir: Path | None = None  # Store the env_dir used during load
    env_prefix: str = ""  # Class-level prefix for environment variables (default: no prefix)
    strip_strings: bool = False  # Class-level default for stripping string values

    def _process_field(
        self,
        field_name: str,
        field_type: type,
        field_info: FieldInfo,
        raw_value: str | None,
        env_var_name: str,
        *,
        env_source: builtins.dict[str, str] | None = None,
        validate: bool = True,
    ) -> Any:
        """
        Process a single field: handle missing values, coerce, and validate.

        Args:
            field_name: Name of the field
            field_type: Type annotation for the field
            field_info: Field metadata
            raw_value: Raw string value from environment (or None)
            env_var_name: Environment variable name for error messages
            env_source: The source passed to the enclosing `_load_fields` call
                (None for real env vars, or a dict for `load_from_dict`).
                Forwarded to nested `DotEnvConfig` fields so they resolve
                from the same source as their parent.
            validate: Whether to perform validation (default: True)

        Returns:
            Processed and validated value

        Raises:
            MissingFieldError: If required field is missing
            TypeCoercionError: If the value cannot be coerced to the field type,
                or if a custom validator returns None for a non-optional field
            ConstraintViolationError: If the value fails a built-in constraint
                or the custom validator hook rejects it
            ValidationError: If validation fails (umbrella; the specific
                subclasses above are the common cases)
        """
        # Nested DotEnvConfig fields (e.g. `oidc: OIDCSettings`) are not a
        # scalar to coerce — a nested config resolves its own fields from
        # the same env_source using its own env_prefix, so it must always
        # go through _load_fields() regardless of whether raw_value (the
        # value of an env var literally named after the field, which no
        # one sets) is present. A bare `field_type()` here would silently
        # produce an unloaded instance whose fields never got populated.
        #
        # Note: this only matches a plain `type` — `Optional[Nested]` /
        # `Nested | None` is a Union, not a `type`, so it does NOT take
        # this branch and instead falls through to the Optional handling
        # in coerce_value(), which just returns None for a missing literal
        # env var without trying the nested prefix. See
        # TestOptionalNestedConfigLimitation below — tracked as a known
        # follow-up, not fixed here.
        #
        # Note: field_info.required is deliberately not consulted here —
        # a `Field()`-required (no default) nested config now always
        # resolves successfully using the nested class's own defaults,
        # rather than raising MissingFieldError. "Required" is expressed
        # on the nested class's own fields instead. See
        # TestRequiredNestedConfigField below for the pinned behavior.
        if isinstance(field_type, type) and issubclass(field_type, DotEnvConfig):
            nested = field_type()
            nested._load_fields(env_source, validate=validate)
            return nested

        # Handle missing values
        if raw_value is None:
            if field_info.required:
                raise MissingFieldError(
                    field_name=field_name,
                    field_type=field_type,
                    env_var_name=env_var_name,
                )
            else:
                value = field_info.get_default()
                # Route str defaults for non-str field types through coercion.
                # Historically the verbatim default bypassed coerce_value, so a
                # SecretStr str-default leaked as a plaintext str (repr exposed
                # it, the pickle guard was bypassed, get_secret_value raised),
                # an int str-default skipped constraints, a bool str-default
                # stayed truthy, and DSN/UUID/Path/Json/list str-defaults were
                # type-confused. The unwrap gate (unwrapped type is exactly
                # ``str``) keeps str defaults for str-ish fields — including
                # Optional[str] default='' — untouched, preserving the
                # Optional empty-string -> None semantics. Non-str defaults
                # (int 8000, default_factory=list) are left alone. Validation
                # runs afterwards on the typed value, so constraints now fire.
                if isinstance(value, str) and unwrap_optional(field_type) is not str:
                    value = coerce_value(field_name, value, field_type, env_var_name, field_info)
        else:
            # Strip string-like raw values before coercion. This is value
            # processing, not validation — it runs regardless of the
            # validate flag, so min_length etc. see the final string.
            if is_string_like_type(field_type):
                strip_mode = field_info.strip
                if strip_mode is None:
                    strip_mode = type(self).strip_strings
                raw_value = apply_strip(raw_value, strip_mode)

            # Coerce the string value to the target type
            value = coerce_value(field_name, raw_value, field_type, env_var_name, field_info)

            # Check if coercion resulted in None for a required field
            if value is None and field_info.required:
                raise MissingFieldError(
                    field_name=field_name,
                    field_type=field_type,
                    env_var_name=env_var_name,
                )

        # Validate the value (whether from default or coerced)
        if validate:
            validate_field(field_name, value, field_info, env_var_name)

        # Custom validator hook: runs even when validate=False (it may
        # transform the value — transformation is part of loading, not
        # validation), but never on None values.
        if field_info.validator is not None and value is not None:
            value = _run_field_validator(
                field_name, value, field_type, field_info.validator, env_var_name
            )

        return value

    def _load_fields(
        self,
        env_source: dict[str, str] | None,
        *,
        validate: bool = True,
    ) -> None:
        """Process all fields from the given source, setting attributes on self.

        Args:
            env_source: If None, reads from environment variables. If a dict,
                reads from the dict (for load_from_dict / testing).
            validate: Whether to perform validation (default True).

        Raises:
            ValidationError: If any field fails validation. Collects all errors
                and raises them together.
        """
        cls = self.__class__
        prefix = cls.env_prefix
        errors: list[ValidationError] = []

        for field_name, (field_type, field_info) in cls._fields.items():
            env_var_name = get_env_var_name(field_name, field_info.alias, prefix)

            if env_source is not None:
                raw_value = env_source.get(env_var_name)
                if raw_value is None:
                    raw_value = env_source.get(field_name)
            else:
                raw_value = get_env_var(field_name, field_info.alias, prefix)

            try:
                value = self._process_field(
                    field_name,
                    field_type,
                    field_info,
                    raw_value,
                    env_var_name,
                    env_source=env_source,
                    validate=validate,
                )
                setattr(self, field_name, value)
            except ValidationError as e:
                errors.append(e)
            except MultipleValidationErrors as e:
                # Raised when a nested DotEnvConfig field (see
                # _process_field) has multiple invalid fields of its own —
                # flatten into this level's collection instead of letting
                # it escape uncaught past the aggregation loop.
                errors.extend(e.errors)

        _raise_collected(errors)
        _raise_collected(self.post_load())

    @classmethod
    def load(
        cls,
        env: str | None = None,
        *,
        override: bool = True,
        env_dir: Path | None = None,
    ) -> Self:
        """Load configuration from environment variables and .env files.

        When to use:
            - In application startup to load config from the environment
            - When you want automatic `.env` file cascading
            - When you need validated, type-safe configuration

        When NOT to use:
            - In tests: use `load_from_dict()` instead for deterministic test data
            - If you already have values in a dict: use `load_from_dict()`

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, reads from
                the `ENV` environment variable, defaults to "dev"
            override: If True, .env file values override existing environment variables.
                If False, existing env vars take precedence over .env files
            env_dir: Custom base directory for .env files. If None, uses
                the `DOTENV_DIR` environment variable or current working directory

        Returns:
            Instance of the config class with all fields populated and validated

        Raises:
            MissingFieldError: If a required field is not set in any source
            TypeCoercionError: If a value cannot be coerced to the field type
            ConstraintViolationError: If a value fails validation constraints
            MultipleValidationErrors: If multiple fields fail validation simultaneously
            FileNotFoundError: If `env_dir` is provided but doesn't exist
            ValueError: If `env` contains invalid characters (path traversal protection)

        Example:
            ```python
            # Auto-detect environment from ENV variable
            config = Config.load()

            # Explicit environment
            config = Config.load(env="prod")

            # Don't override existing env vars
            config = Config.load(override=False)

            # Custom .env file location
            from pathlib import Path
            config = Config.load(env_dir=Path("/app/config"))
            ```

        See Also:
            - [`reload`][dotenvmodel.config.DotEnvConfig.reload]: Reload after env changes.
            - [`load_from_dict`][dotenvmodel.config.DotEnvConfig.load_from_dict]: For testing.
        """
        logger.info(f"Loading {cls.__name__} configuration")

        load_env_files(env=env, override=override, env_dir=env_dir)

        instance = cls()
        logger.debug(f"Processing {len(cls._fields)} field(s)")

        instance._load_fields(None)

        logger.info(f"{cls.__name__} configuration loaded successfully")
        logger.debug(f"Loaded fields: {', '.join(cls._fields.keys())}")

        instance._loaded = True
        instance._load_env = env
        instance._load_override = override
        instance._load_env_dir = env_dir
        return instance

    def reload(
        self,
        env: str | None = None,
        *,
        override: bool | None = None,
        env_dir: Path | None = None,
    ) -> Self:
        """Reload configuration from environment variables and .env files.

        This method reloads all fields from the environment, allowing you to
        pick up changes to environment variables or .env files without creating
        a new instance.

        When to use:
            - After receiving a SIGHUP signal to hot-reload configuration
            - After programmatically changing environment variables
            - When switching environments at runtime (e.g., dev to prod)

        By default, this uses the same parameters (env, override, env_dir) that
        were used during the original `load()` call. You can override any of these
        by passing new values.

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, uses
                the env from the original load() call
            override: If True, .env file values override existing environment variables.
                If False, existing env vars take precedence. If None, uses the
                override value from the original load() call
            env_dir: Custom base directory for .env files. If None, uses
                the env_dir from the original load() call

        Returns:
            Self (the same instance with reloaded values, useful for method chaining)

        Raises:
            MissingFieldError: If a required field is not set after reload
            TypeCoercionError: If a value cannot be coerced after reload
            ConstraintViolationError: If a value fails validation after reload
            MultipleValidationErrors: If multiple fields fail after reload

        Example:
            ```python
            config = AppConfig.load(env="dev", override=True)

            # ... later, environment variables change ...
            import os
            os.environ["PORT"] = "9000"

            # Reload picks up the new value
            config.reload()
            print(config.port)  # 9000

            # Or reload with different parameters
            config.reload(env="prod")  # Switch to prod environment
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: Initial loading.
        """
        logger.info(f"Reloading {self.__class__.__name__} configuration")

        reload_env = env if env is not None else self._load_env
        reload_override = override if override is not None else self._load_override
        reload_env_dir = env_dir if env_dir is not None else self._load_env_dir

        load_env_files(env=reload_env, override=reload_override, env_dir=reload_env_dir)

        logger.debug(f"Reloading {len(self._fields)} field(s)")
        self._load_fields(None)

        logger.info(f"{self.__class__.__name__} configuration reloaded successfully")
        logger.debug(f"Reloaded fields: {', '.join(self._fields.keys())}")

        return self

    @classmethod
    def load_from_dict(
        cls,
        data: dict[str, str],
        *,
        validate: bool = True,
    ) -> Self:
        """Load configuration from a dictionary (useful for testing).

        When to use:
            - In unit tests for deterministic, isolated config loading
            - When you have config values from a non-env source (e.g., a database)
            - When you want to bypass .env file loading entirely

        When NOT to use:
            - In production: use `load()` to read from environment and .env files

        Args:
            data: Dictionary mapping environment variable names (or field names) to
                string values. Keys can be either the env var name (e.g., "DATABASE_URL")
                or the field name (e.g., "database_url") — env var names take precedence
            validate: Whether to perform validation (default True). Set to False
                to skip validation for performance or testing edge cases

        Returns:
            Instance of the config class with all fields populated

        Raises:
            MissingFieldError: If a required field is missing from the dict
            TypeCoercionError: If a value cannot be coerced to the field type
            ConstraintViolationError: If a value fails validation constraints
            MultipleValidationErrors: If multiple fields fail validation simultaneously

        Example:
            ```python
            config = Config.load_from_dict({
                "DATABASE_URL": "postgresql://localhost/db",
                "DEBUG": "true",
                "PORT": "8000",
            })

            # Skip validation
            config = Config.load_from_dict(data, validate=False)
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: For production loading.
        """
        instance = cls()
        instance._load_fields(data, validate=validate)
        instance._loaded = True
        return instance

    def post_load(self) -> list[ValidationError] | None:
        """Normalize derived values and run cross-field validation after loading.

        Runs once after all fields are loaded and validated, on every load
        path: `load()`, `load_from_dict()`, `reload()`, and nested config
        loading. Always runs, including with `validate=False` (consistent
        with the per-field `validator` hook: transformation is part of
        loading). The default implementation is a no-op.

        Usage modes (combinable in one body):

        - Fix / transform: mutate `self` (e.g. apply fallback values),
          return `None`.
        - Cross-validate: return a list of `ValidationError`. One error is
          raised directly; several are raised as `MultipleValidationErrors`.
        - Continue: log or swallow issues internally, return `None`.
        - Fatal: raise; the exception propagates unchanged.

        Tag each returned error with the primary field name and reference
        other participating fields in `error_msg`. Do not embed secret
        values in `error_msg` — the library redacts the `value` attribute
        but cannot mask prose. The hook runs only when every field loaded
        cleanly, and does not run on bare `Cls()` construction.

        Returns:
            `None` or an empty list on success; a list of `ValidationError`
            describing cross-field violations otherwise.

        Example:
            ```python
            class DatabaseConfig(DotEnvConfig):
                primary_dsn: str = Field()
                replica_dsn: str | None = Field(default=None)
                pool_min: int = Field(default=1)
                pool_max: int = Field(default=10)

                def post_load(self) -> list[ValidationError] | None:
                    # Fix / transform: fall back to the primary DSN.
                    if self.replica_dsn is None:
                        self.replica_dsn = self.primary_dsn

                    # Cross-validate: pool bounds must stay coherent.
                    if self.pool_min > self.pool_max:
                        return [
                            ValidationError(
                                field_name="pool_min",
                                value=self.pool_min,
                                error_msg="pool_min must be <= pool_max",
                            )
                        ]
                    return None
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: Triggers this hook.
            - [`reload`][dotenvmodel.config.DotEnvConfig.reload]: Re-runs this hook.
            - [`Field`][dotenvmodel.fields.Field]: Per-field `validator` hook for
              single-field validation and transformation.
            - [`MultipleValidationErrors`][dotenvmodel.exceptions.MultipleValidationErrors]:
              Raised when this hook returns several errors.
        """
        return None

    def dict(self) -> dict[str, Any]:
        """Return configuration as a dictionary with actual values.

        Returns:
            Dictionary mapping field names to their current values

        Example:
            ```python
            config = Config.load()
            print(config.dict())
            # {'database_url': 'postgresql://...', 'debug': True, 'port': 8000}
            ```

        See Also:
            - [`get`][dotenvmodel.config.DotEnvConfig.get]: Get a single value with default.
        """
        result = {}
        for field_name in self._fields:
            if hasattr(self, field_name):
                result[field_name] = getattr(self, field_name)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key with optional default.

        Args:
            key: Field name to look up
            default: Default value if field not found (default None)

        Returns:
            Field value if the field exists and is set, otherwise the default value

        Example:
            ```python
            timeout = config.get('timeout', 30)  # Returns 30 if timeout not set
            ```

        See Also:
            - [`dict`][dotenvmodel.config.DotEnvConfig.dict]: Get all values as dict.
        """
        return getattr(self, key, default)

    def __repr__(self) -> str:
        field_strs = []
        for field_name in self._fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                field_strs.append(f"{field_name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(field_strs)})"

    @classmethod
    def get_fields(cls) -> builtins.dict[str, tuple[type, FieldInfo]]:
        """Get all fields defined on this configuration class.

        Returns a copy of the fields dictionary to prevent external modification.

        Returns:
            Dictionary mapping field names to tuples of (type, FieldInfo)

        Example:
            ```python
            fields = AppConfig.get_fields()
            for name, (field_type, field_info) in fields.items():
                print(f"{name}: {field_type}, required={field_info.required}")
            ```

        See Also:
            - [`FieldInfo`][dotenvmodel.fields.FieldInfo]: Field metadata class.
        """
        return cls._fields.copy()

    @classmethod
    def describe(
        cls,
        output_format: Literal["table", "markdown", "json", "html", "dotenv"] = "table",
        output: str | Path | None = None,
        line_ending: str | None = None,
    ) -> str:
        """
        Generate documentation describing this configuration class.

        Shows all environment variables, their types, whether they're required,
        default values, descriptions, and validation constraints.

        Args:
            output_format: Output format - "table" (ASCII), "markdown", "json", "html", or "dotenv"
            output: Optional file path to save the output to
            line_ending: Line ending to use (e.g., "\\n", "\\r\\n", "\\r").
                If None, uses platform default (os.linesep)

        Returns:
            Formatted string describing the configuration

        Example:
            ```python
            class AppConfig(DotEnvConfig):
                port: int = Field(default=8000, ge=1, le=65535, description="Server port")
                debug: bool = Field(default=False, description="Enable debug mode")

            # Print to console
            print(AppConfig.describe())

            # Save markdown to file
            AppConfig.describe(output_format="markdown", output="docs/config.md")

            # Generate .env.example
            AppConfig.describe(output_format="dotenv", output=".env.example")

            # Use Unix line endings regardless of platform
            AppConfig.describe(output_format="markdown", line_ending="\\n")

            # Use Windows line endings
            AppConfig.describe(output_format="markdown", line_ending="\\r\\n")
            ```
        """
        from dotenvmodel.describe import describe_single

        return describe_single(
            cls, output_format=output_format, output=output, line_ending=line_ending
        )

    @classmethod
    def generate_env_example(
        cls,
        output: str | Path | None = None,
    ) -> str:
        """
        Generate a .env.example file for onboarding new developers.

        This creates a template file showing all environment variables with:
        - Comments describing each field
        - Type and constraint information
        - Example values
        - Required vs optional fields

        Args:
            output: Optional file path to save the .env.example to (e.g., ".env.example")

        Returns:
            .env.example file content

        Example:
            ```python
            class AppConfig(DotEnvConfig):
                port: int = Field(default=8000, ge=1, le=65535, description="Server port")
                api_key: str = Field(description="API key for external service")
                debug: bool = Field(default=False, description="Enable debug mode")

            # Generate and save .env.example
            AppConfig.generate_env_example(output=".env.example")

            # Or print to console
            print(AppConfig.generate_env_example())

            # Output:
            # # Configuration for AppConfig
            #
            # # Server port
            # # Type: int | Constraints: ge=1, le=65535
            # # Example: PORT=8000
            # # PORT=8000
            #
            # # API key for external service
            # # Type: str
            # # Example: API_KEY=your_value_here
            # API_KEY=
            # ...
            ```
        """
        from dotenvmodel.describe import generate_env_example

        return generate_env_example(cls, output=output)
