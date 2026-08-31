"""DotEnvConfig base class for configuration management."""

import builtins
import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar, Literal, Self, cast

from typing_extensions import TypeForm

from dotenvmodel._constants import LOGGER_NAME
from dotenvmodel.caching import (
    acquire_cached,
    begin_override,
    clear_cached,
    end_override,
)
from dotenvmodel.coercion import apply_strip, coerce_value, is_string_like_type, unwrap_optional
from dotenvmodel.exceptions import (
    ConstraintViolationError,
    MissingFieldError,
    MultipleValidationErrors,
    TypeCoercionError,
    ValidationError,
)
from dotenvmodel.fields import FieldInfo, ValidatorContext, _validator_name
from dotenvmodel.loading import (
    DotenvLayer,
    LoadParams,
    get_env_var_name,
    read_env_files,
    resolve_load_params,
)
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


def _layer_for(params: LoadParams) -> DotenvLayer | None:
    """Read the merged dotfile layer for *params*, or ``None`` when dotfiles are skipped.

    Shared by ``load()`` and ``reload()``: both resolve the same layer from
    the same resolved parameters, differing only in their surrounding
    logging and bookkeeping.
    """
    if not params.read_dotfiles:
        return None
    return read_env_files(env=params.env, env_dir=params.env_dir, load_local=params.load_local)


def _resolve_raw_value(
    env_var_name: str,
    dotenv_layer: DotenvLayer | None,
    override: bool,
) -> str | None:
    """Resolve one field's raw value across the process-env and dotfile layers.

    With ``override`` False (the default) the process environment wins;
    with ``override`` True the merged dotfile layer wins. The losing layer
    is the fallback, and ``None`` (field default) only when both are unset.
    """
    os_value = os.getenv(env_var_name)
    file_value = dotenv_layer.values.get(env_var_name) if dotenv_layer is not None else None
    if override:
        value, source = (
            (file_value, "dotfile layer") if file_value is not None else (os_value, "process env")
        )
    else:
        value, source = (
            (os_value, "process env") if os_value is not None else (file_value, "dotfile layer")
        )
    # Log the source only, never the value — a raw value may be a secret.
    if value is not None:
        logger.debug(f"{env_var_name}: resolved from {source}")
    else:
        logger.debug(f"{env_var_name}: unset in every layer, using the field default")
    return value


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
    # Resolved load settings from the most recent load()/reload(); None
    # until an environment load succeeds. load_from_dict() records nothing
    # — a dict load has no environment parameters to record, so
    # loaded_with() raises for its instances.
    _load_params: LoadParams | None = None
    # Bare annotation only — no assignment. An actual `= None` here would
    # place a real entry in DotEnvConfig.__dict__, making has_cached() treat
    # the base class as already-cached and letting reset_cached() delete the
    # class-body default (an irreversible process-wide mutation). The
    # annotation alone gives type checkers the declaration without a runtime
    # entry; per-subclass entries are set by the caching module.
    _cached_instance: ClassVar["DotEnvConfig | None"]
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
        dotenv_layer: DotenvLayer | None = None,
        override: bool = False,
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
            dotenv_layer: The merged dotfile layer passed to the enclosing
                `_load_fields` call. Forwarded to nested `DotEnvConfig`
                fields so they resolve file values through the same layers
                as their parent.
            override: The override policy of the enclosing load, forwarded
                to nested `DotEnvConfig` fields alongside `dotenv_layer`.

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
            nested._load_fields(
                env_source,
                validate=validate,
                dotenv_layer=dotenv_layer,
                override=override,
            )
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
        dotenv_layer: DotenvLayer | None = None,
        override: bool = False,
    ) -> None:
        """Process all fields from the given source, setting attributes on self.

        Args:
            env_source: If None, reads from environment variables. If a dict,
                reads from the dict (for load_from_dict / testing).
            validate: Whether to perform validation (default True).
            dotenv_layer: The merged .env cascade for this load, or None
                when no dotfiles were read (dict loads, or
                read_dotfiles=False). Only consulted when env_source is
                None: each field resolves process env first unless
                `override`, falling back to the other layer.
            override: Whether the dotfile layer beats the process
                environment (only meaningful alongside a dotenv_layer, with
                env_source None).

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
                raw_value = _resolve_raw_value(env_var_name, dotenv_layer, override)

            try:
                value = self._process_field(
                    field_name,
                    field_type,
                    field_info,
                    raw_value,
                    env_var_name,
                    env_source=env_source,
                    validate=validate,
                    dotenv_layer=dotenv_layer,
                    override=override,
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
        override: bool | None = None,
        env_dir: Path | str | None = None,
        read_dotfiles: bool | None = None,
        load_local: bool | None = None,
    ) -> Self:
        """Load configuration from environment variables and .env files.

        Each field is resolved across three layers; the process environment
        is never written:

        - default (`override=False`): process environment -> merged dotfile cascade -> field default
        - `override=True` (opt-in): merged dotfile cascade -> process environment -> field default

        The dotfile cascade (`.env`, `.env.local`, `.env.{env}`,
        `.env.{env}.local`) is merged once per load with later files
        winning, then the override policy is applied once against the
        whole merged layer.

        Every parameter follows explicit argument > environment variable > default:

        | Parameter | Env var | Default |
        |---|---|---|
        | `env` | `ENV` | `"dev"` |
        | `env_dir` | `DOTENV_DIR` | `Path.cwd()` |
        | `override` | `DOTENV_OVERRIDE` | `False` |
        | `read_dotfiles` | `DOTENV_READ_DOTFILES` | `True` |
        | `load_local` | `DOTENV_LOAD_LOCAL` | `False` when the resolved env is `"test"`, else `True` |

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
            override: If True, .env file values take precedence over existing
                environment variables. If False or None-without-`DOTENV_OVERRIDE`
                (the default), existing environment variables take precedence
                over .env files
            env_dir: Custom base directory for .env files — a `str` is
                accepted and converted to a `Path`. If None, uses
                the `DOTENV_DIR` environment variable or current working directory
            read_dotfiles: If False, skip the .env cascade entirely — no files
                are probed, no "No .env files found" warning is logged, and a
                missing `env_dir` does not raise; fields resolve from the
                process environment and defaults only (`override` becomes moot)
            load_local: If False, `.env.local` and `.env.{env}.local` are not
                read in any environment. If None, `DOTENV_LOAD_LOCAL` applies,
                else the default: skip `.local` files only when the resolved
                env is "test" (case-insensitive) — extending the
                Next.js/dotenv-flow rule, which skips only `.env.local` in
                test, to all `.local` files, because a gitignored
                `.env.test.local` must not decide test outcomes either;
                `.env.{env}` itself, e.g. `.env.test`, is still read

        Returns:
            Instance of the config class with all fields populated and validated

        Raises:
            MissingFieldError: If a required field is not set in any source
            TypeCoercionError: If a value cannot be coerced to the field type
            ConstraintViolationError: If a value fails validation constraints
            MultipleValidationErrors: If multiple fields fail validation simultaneously
            FileNotFoundError: If dotfiles are read (read_dotfiles is not
                False) and the resolved env_dir doesn't exist
            ValueError: If `env` contains invalid characters (path traversal protection)

        Note:
            `load()` never mutates `os.environ`; code that wants dotfile
            values injected into the process environment should call
            python-dotenv's `load_dotenv()` directly.

        Example:
            ```python
            # Auto-detect environment from ENV variable
            config = Config.load()

            # Explicit environment
            config = Config.load(env="prod")

            # Opt in: dotfiles beat the process environment
            config = Config.load(override=True)

            # Custom .env file location
            from pathlib import Path
            config = Config.load(env_dir=Path("/app/config"))
            ```

        See Also:
            - [`reload`][dotenvmodel.config.DotEnvConfig.reload]: Reload after env changes.
            - [`load_from_dict`][dotenvmodel.config.DotEnvConfig.load_from_dict]: For testing.
        """
        logger.info(f"Loading {cls.__name__} configuration")

        params = resolve_load_params(
            env,
            override=override,
            env_dir=env_dir,
            read_dotfiles=read_dotfiles,
            load_local=load_local,
        )
        dotenv_layer = _layer_for(params)

        instance = cls()
        logger.debug(f"Processing {len(cls._fields)} field(s)")

        instance._load_fields(None, dotenv_layer=dotenv_layer, override=params.override)

        logger.info(f"{cls.__name__} configuration loaded successfully")
        logger.debug(f"Loaded fields: {', '.join(cls._fields.keys())}")

        instance._loaded = True
        instance._load_params = params
        return instance

    def loaded_with(self) -> LoadParams:
        """The resolved `LoadParams` this instance was last loaded with.

        `reload()` uses it to repeat a load without restating its arguments — so a SIGHUP
        handler calling `reload()` with no arguments keeps the original precedence and
        file-discovery settings rather than silently reverting to the defaults.
        `cached()`'s warm path uses it to tell a caller who agrees with how the cache was
        built from one who disagrees.

        Exposed rather than read field-by-field so there is one definition of "how was this
        loaded", and callers outside this class do not reach into private attributes.
        Values reflect the most recent `reload()`, not only the original `load()`; the
        recorded values are the *resolved* ones (booleans never `None`, `env_dir` the
        resolved base directory), so a bare `reload()` is stable across cwd changes.

        Raises:
            RuntimeError: If the instance was never loaded from the
                environment — instances from `load_from_dict()` or bare
                construction have no recorded parameters.
        """
        if self._load_params is None:
            raise RuntimeError(
                f"{type(self).__name__} instance was never loaded from the "
                "environment; loaded_with() is only available after "
                "load()/reload()/cached()."
            )
        return self._load_params

    def reload(
        self,
        env: str | None = None,
        *,
        override: bool | None = None,
        env_dir: Path | str | None = None,
        read_dotfiles: bool | None = None,
        load_local: bool | None = None,
    ) -> Self:
        """Reload configuration from environment variables and .env files.

        This method reloads all fields from the environment, allowing you to
        pick up changes to environment variables or .env files without creating
        a new instance.

        When to use:
            - After receiving a SIGHUP signal to hot-reload configuration
            - After programmatically changing environment variables
            - When switching environments at runtime (e.g., dev to prod)

        By default, this repeats the same five resolved parameters (env,
        override, env_dir, read_dotfiles, load_local) recorded by the
        original `load()` — the recorded values win over the `DOTENV_*`
        env-var tier, so a bare `reload()` never silently changes behavior.
        You can override any of them by passing new values. An instance
        loaded via `load_from_dict()` has nothing recorded; its `reload()`
        resolves all five from the tiers.

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, uses
                the env from the original load() call
            override: If True, .env file values take precedence over existing
                environment variables. If None, uses the override value from
                the original load() call
            env_dir: Custom base directory for .env files — a `str` is
                accepted and converted to a `Path`. If None, uses the
                env_dir from the original load() call
            read_dotfiles: If False, skip the .env cascade entirely (see
                `load()`). If None, uses the value from the original load() call
            load_local: Whether to include `.local` files (see `load()`).
                If None, uses the value from the original load() call

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

            # Reload picks up the new value, keeping env="dev" and override=True
            config.reload()
            print(config.port)  # 9000

            # Or reload with different parameters
            config.reload(env="prod")  # Switch to prod environment
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: Initial loading.
        """
        logger.info(f"Reloading {self.__class__.__name__} configuration")

        recorded = self._load_params
        if recorded is not None:
            env = recorded.env if env is None else env
            override = recorded.override if override is None else override
            env_dir = recorded.env_dir if env_dir is None else env_dir
            read_dotfiles = recorded.read_dotfiles if read_dotfiles is None else read_dotfiles
            load_local = recorded.load_local if load_local is None else load_local

        params = resolve_load_params(
            env,
            override=override,
            env_dir=env_dir,
            read_dotfiles=read_dotfiles,
            load_local=load_local,
        )
        dotenv_layer = _layer_for(params)

        logger.debug(f"Reloading {len(self._fields)} field(s)")
        self._load_fields(None, dotenv_layer=dotenv_layer, override=params.override)

        logger.info(f"{self.__class__.__name__} configuration reloaded successfully")
        logger.debug(f"Reloaded fields: {', '.join(self._fields.keys())}")

        self._load_params = params
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

    @classmethod
    def cached(
        cls,
        env: str | None = None,
        *,
        override: bool | None = None,
        env_dir: Path | str | None = None,
        read_dotfiles: bool | None = None,
        load_local: bool | None = None,
    ) -> Self:
        """Return the process-wide cached instance for this exact config class, loading it on first call.

        Lazy and thread-safe: concurrent first callers race on a lock; only one
        calls `load()`, the rest block and receive the same instance. Subsequent
        calls (from any thread) return the cached instance immediately without
        re-reading the environment, ignoring any arguments passed after the first
        call (a warning is logged if the caller's arguments resolve differently
        from the `LoadParams` the cached instance holds).

        The cached instance is stored as a private class attribute on the config
        class itself (not in a module-level registry), so its lifetime is tied
        to the class object — when nothing else references the class, both the
        class and its cached instance become collectible together.

        Calling `.reload()` on the returned instance mutates it in place; since
        `cached()` always returns the same object, subsequent `cached()` calls
        see the reloaded values.

        This is the supported way to get a single shared instance in application
        code. Call `reset_cached()` to force the next `cached()` call to reload —
        this is the supported way to exercise more than one configuration in the
        same process (e.g. between tests).

        When to use:
            - In application code to obtain a single shared config instance
            - When you want lazy initialization that reads the environment only
              on first access
            - When you need thread-safe singleton initialization without
              hand-rolling your own lock

        When NOT to use:
            - In tests that need different configurations per test: use
              `cached_override()` for a scoped, self-restoring override, or call
              `reset_cached()` in a fixture between tests; otherwise use
              `load()` or `load_from_dict()` instead of `cached()`
            - When you need multiple instances with different parameters
            - From within a `post_load()` hook or field `validator` on the same
              class: a reentrant `cached()` call for the same class while its
              first load is still in flight raises `RuntimeError` (see below).
              Calling `cached()` for *other* classes from those hooks is
              supported.

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, reads
                from the `ENV` environment variable, defaults to "dev". Only
                used on the first call; ignored once the cache is warm.
            override: If True, .env file values take precedence over existing
                environment variables. If False or None (the default),
                existing environment variables take precedence over .env
                files. Only used on the first call; ignored once the cache
                is warm.
            env_dir: Custom base directory for .env files — a `str` is
                accepted and converted to a `Path`. If None, uses
                the `DOTENV_DIR` environment variable or current working directory.
                Only used on the first call; ignored once the cache is warm.
            read_dotfiles: If False, skip the .env cascade entirely (see
                `load()`). Only used on the first call; ignored once the
                cache is warm.
            load_local: Whether to include `.local` files (see `load()`).
                Only used on the first call; ignored once the cache is warm.

        Returns:
            The cached instance of this config class. On the first call, loads
            and caches a new instance; on subsequent calls, returns the
            existing cached instance.

        Raises:
            MissingFieldError: If a required field is not set in any source
                (only on first call)
            TypeCoercionError: If a value cannot be coerced to the field type
                (only on first call)
            ConstraintViolationError: If a value fails validation constraints
                (only on first call)
            MultipleValidationErrors: If multiple fields fail validation
                simultaneously (only on first call)
            RuntimeError: If `cached()` is called reentrantly for the same
                class from within that class's own `load()` / `post_load()` /
                field `validator` hooks. The internal lock is reentrant, so
                the nested call would not deadlock — it would see a cold
                cache and recurse into `load()` without bound; it is rejected
                instead. A circular cross-class hook chain (A's hook loads B,
                B's hook loads A) collapses back onto the first class and
                raises the same `RuntimeError`. Calling `cached()` for other
                classes from hooks is supported. Hooks that need the instance
                mid-load should use `self`, or call `cls.load()` directly with
                re-entry guarding (an unconditional `cls.load()` inside
                `post_load()` re-runs the hooks and recurses until
                `RecursionError`).

        Example:
            ```python
            # Application code — first call loads, rest reuse
            config = AppConfig.cached()
            config.port  # 8000

            # In tests, reset between configurations
            AppConfig.reset_cached()
            os.environ["PORT"] = "9000"
            config = AppConfig.cached()
            config.port  # 9000

            # reload() on the cached instance is visible to all holders
            config.reload(env="prod")
            AppConfig.cached().port  # prod value
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: One-shot loading.
            - [`reset_cached`][dotenvmodel.config.DotEnvConfig.reset_cached]:
              Clear the cache for this class.
            - [`cached_override`][dotenvmodel.config.DotEnvConfig.cached_override]:
              Scoped, self-restoring override for tests.
        """
        return cast(
            Self,
            acquire_cached(cls, env, override, env_dir, read_dotfiles, load_local),
        )

    @classmethod
    def reset_cached(cls) -> None:
        """Clear this class's cached `cached()` instance, if any.

        The next call to `cached()` will call `load()` again. Use this in test
        teardown/fixtures when a test changes environment variables and needs
        `cached()` to observe the new values. For a single test that needs a
        different config, prefer `cached_override()` (scoped and self-restoring).
        Only affects this exact class — other `DotEnvConfig` subclasses' caches
        are unaffected.

        When to use:
            - In test fixtures to ensure each test gets a fresh config
            - After changing environment variables to force `cached()` to
              re-read the environment

        Raises:
            RuntimeError: If called for this class from within that same
                class's own in-flight `load()` / `post_load()` / field
                `validator` hook: the load installs its instance when it
                completes, which would silently undo the reset. Calling
                `reset_cached()` for *other* classes from hooks is fine.

        Example:
            ```python
            @pytest.fixture(autouse=True)
            def reset_config_cache():
                yield
                AppConfig.reset_cached()
            ```

        See Also:
            - [`cached`][dotenvmodel.config.DotEnvConfig.cached]: Get the
              cached instance.
        """
        clear_cached(cls)

    @classmethod
    @contextmanager
    def cached_override(cls, instance: Self) -> Iterator[Self]:
        """Temporarily replace the cached() instance for this class inside a `with` block.

        On exit, restores whatever was cached before the `with` block started —
        the previous instance if one existed, or nothing (uncached) if `cached()`
        had never been called. Restoration happens even if the `with` block
        raises. This is a scoped, self-cleaning alternative to `reset_cached()`
        for tests: a forgotten `reset_cached()` call leaks state into the next
        test, whereas `cached_override()` cannot forget to clean up.

        Warning:
            ``cached_override()`` is not designed for use while other threads
            may concurrently call ``cached()`` on the same class. The override
            window (between the initial set and the final restore) is not
            synchronized against concurrent readers beyond the lock-protected
            set/restore operations themselves. Overlapping a
            ``cached_override()`` block with genuinely concurrent cross-thread
            ``cached()`` calls on the same class is unsupported and racy in
            terms of *which* threads observe the override vs. the restored
            value during the transition, even though no data corruption occurs.

        Args:
            instance: The instance `cached()` should return for the duration of
                the `with` block.

        Yields:
            `instance`, unchanged, for convenience in a `with ... as` binding.

        Raises:
            RuntimeError: If entered for this class from within that same
                class's own in-flight `load()` / `post_load()` / field
                `validator` hook: the load installs its instance when it
                completes, which would silently discard the override. Calling
                `cached_override()` for *other* classes from hooks is fine.

        Example:
            ```python
            test_config = AppConfig.load_from_dict({"PORT": "9000"})
            with AppConfig.cached_override(test_config):
                assert AppConfig.cached() is test_config
            # Previous cached() state (or absence of one) is restored here.
            ```

        See Also:
            - [`reset_cached`][dotenvmodel.config.DotEnvConfig.reset_cached]:
              Unconditional clear, not scoped/auto-restoring.
        """
        had_cached, previous = begin_override(cls, instance)
        try:
            yield instance
        finally:
            end_override(cls, had_cached, previous)

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
        - Fatal: raise; an exception that is neither `ValidationError`
          nor `MultipleValidationErrors` propagates unchanged.

        Tag each returned error with the primary field name and reference
        other participating fields in `error_msg`. Do not embed secret
        values in `error_msg` — the library redacts the `value` attribute
        but cannot mask prose. The same applies to exceptions raised from
        the hook: they propagate unmasked, so never interpolate secrets
        into a raised exception's message. The hook runs only when every
        field loaded cleanly, and does not run on bare `Cls()` construction.

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
