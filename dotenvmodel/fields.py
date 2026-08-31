"""Field descriptor and Required sentinel for dotenvmodel."""

import copy
import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal, TypeVar
from uuid import UUID

from dotenvmodel.types import BaseDsn, SecretStr

# Type variable for generic field types
T = TypeVar("T")

# Type of a callable decorated by @field_validator, preserved as-is
_F = TypeVar("_F", bound=Callable[..., Any])


class _MissingSentinel:
    """Sentinel to indicate a required field with no default."""

    def __repr__(self) -> str:
        return "..."


_MISSING = _MissingSentinel()


class _RequiredSentinel:
    """Sentinel to indicate a required field (explicit alternative to no default)."""

    def __repr__(self) -> str:
        return "Required"


# Public sentinel value for required fields
# Type checkers will see this as Any to avoid type errors
Required: Any = _RequiredSentinel()
"""Sentinel value marking a field as required.

Use this as a class attribute value instead of `Field()` when you want
to be explicit that a field is required. Functionally identical to
`Field()` with no arguments.

When to use:
    - When you prefer the explicit `Required` syntax over `Field()`
    - For readability when a field has no constraints or defaults

Example:
    ```python
    class Config(DotEnvConfig):
        database_url: str = Required
        api_key: str = Required
        debug: bool = Field(default=False)  # Optional
    ```

See Also:
    - [`Field`][dotenvmodel.fields.Field]: For fields with defaults or constraints.
"""


@dataclass(frozen=True)
class ValidatorContext:
    """Context passed to a field's custom ``validator`` hook.

    When to use:
        - Received as the second argument of any ``Field(validator=...)``
          callable; you never construct it yourself

    Attributes:
        field_name: The Python field name (e.g. ``"api_key"``)
        env_var_name: The resolved environment variable name, including any
            ``env_prefix`` or ``alias`` (e.g. ``"APP_API_KEY"``)

    Example:
        ```python
        def check_env_key(value: str, ctx: ValidatorContext) -> str:
            if not value.startswith("sk-"):
                raise ValueError(f"{ctx.env_var_name} must start with 'sk-'")
            return value

        class Config(DotEnvConfig):
            api_key: str = Field(validator=check_env_key)
        ```

    See Also:
        - [`Field`][dotenvmodel.fields.Field]: For attaching a validator to a field.
    """

    field_name: str
    env_var_name: str


def _validator_name(fn: Callable[..., Any]) -> str:
    """Return a display name for a validator callable.

    Falls back to the type name (e.g. ``"partial"`` for ``functools.partial``)
    so rendering is consistent across ``FieldInfo.__repr__`` and error paths.
    """
    return getattr(fn, "__name__", type(fn).__name__)


# Attribute the @field_validator decorator places on its target. The metaclass
# reads it from the class namespace to wire hooks onto fields.
_VALIDATOR_SPECS_ATTR = "__dotenvmodel_field_validator_specs__"


@dataclass(frozen=True)
class _ValidatorSpec:
    """One ``@field_validator`` registration placed on a callable."""

    field_name: str
    mode: Literal["before", "after"]


def field_validator(
    field_name: str, /, *, mode: Literal["before", "after"] = "after"
) -> Callable[[_F], _F]:
    """Register a method as a custom validation/transformation hook for one field.

    Apply inside a `DotEnvConfig` subclass; the metaclass attaches the
    decorated callable to the named field. The hook receives
    ``(value, ctx)`` — the same contract as `Field(validator=...)` — and its
    return value feeds the next pipeline stage.

    When to use:
        - When the validation logic is too long to sit inline in `Field(...)`
        - To attach several hooks to one field (stacking the decorator also
          registers one method for several fields)
        - To normalize the raw external string before built-in `strip` and
          type coercion (`mode="before"`)

    Supported callable forms (the receiver is detected from the first
    positional parameter name):
        - plain method: `def hook(self, value, ctx)` — bound to the instance
        - `@classmethod`: `def hook(cls, value, ctx)` — bound to the class
        - `@staticmethod` or module-level function: `def hook(value, ctx)` —
          no receiver; a module-level function is decorated at module level
          and assigned inside the class body

    Modes:
        - `mode="after"` (default): identical semantics to
          `Field(validator=...)` — runs on the coerced,
          built-in-constraint-validated value, may transform it (built-ins
          are not re-run), never runs on `None`, and runs even with
          `validate=False`. When both an inline `Field(validator=...)` and
          after-mode hooks exist, the inline hook runs first, then decorator
          hooks in definition order.
        - `mode="before"`: runs on the raw external value (the environment
          or `load_from_dict` string) before built-in `strip` and before
          type coercion, and may replace it — strip and coercion see the
          hook's return value, which may be a non-string (pre-typed `int`,
          `float`, `Decimal`, `str`, and `Path` values round-trip through
          coercion; other types expect their string form). Not applied to
          field defaults (defaults are author-controlled values, not
          external input needing normalization). Also runs with
          `validate=False`.

    Errors and secrets:
        A `ValueError`/`TypeError` raised by the hook is wrapped in
        `ConstraintViolationError` (`constraint="validator=<method name>"`)
        in either mode; other exceptions propagate unchanged. For sensitive
        fields (`SecretStr`, DSN types) any failure is masked generically —
        including `mode="before"` hooks, which see the raw plaintext — so
        the secret cannot leak through the hook's error text.

    Inheritance:
        Hooks are inherited. Redefining a same-named method in a subclass
        replaces that hook (redefining it without the decorator removes it);
        the parent class's hooks are never affected. Hooks survive a field
        being redeclared with a fresh `Field(...)`.

    Args:
        field_name: Name of the field the hook attaches to. The field must
            exist (on this class or a base) at class definition time, or
            class creation raises `ValueError`.
        mode: When the hook runs — `"before"` strip/coercion, or `"after"`
            coercion and built-in constraints (default).

    Raises:
        TypeError: If `field_name` is not a `str`, or the decorated target is
            not callable or does not support attribute assignment.
        ValueError: If `mode` is not `"before"` or `"after"`, or the named
            field does not exist on the class being defined.

    Example:
        ```python
        import logging

        from dotenvmodel import DotEnvConfig, Field, ValidatorContext, field_validator


        class AppConfig(DotEnvConfig):
            log_level: str = Field(default="ERROR", strip=True)

            @field_validator("log_level", mode="before")
            def uppercase_log_level(self, value: str, ctx: ValidatorContext) -> str:
                return value.upper()

            @field_validator("log_level")
            def convert_to_logging_int(self, value: str, ctx: ValidatorContext) -> int:
                return logging.getLevelNamesMapping().get(value, logging.ERROR)
        ```

    See Also:
        - [`Field`][dotenvmodel.fields.Field]: The inline single-hook form
          via `validator=`.
        - [`ValidatorContext`][dotenvmodel.fields.ValidatorContext]: The
          context argument every hook receives.
    """
    if not isinstance(field_name, str):
        raise TypeError(f"field_name must be str, got {type(field_name).__name__}")
    if mode not in ("before", "after"):
        raise ValueError(f"mode must be 'before' or 'after', got {mode!r}")
    spec = _ValidatorSpec(field_name=field_name, mode=mode)

    def decorator(fn: _F) -> _F:
        # The marker lives on the underlying function so the metaclass finds
        # it whichever order @field_validator and @staticmethod/@classmethod
        # were applied in. Callability is checked on the unwrapped target —
        # a bare classmethod object is not callable on every supported
        # Python version. The isinstance checks run against the Any-typed
        # alias so the decorated value's own type flows through unchanged.
        target: Any = fn
        if isinstance(target, (staticmethod, classmethod)):
            target = target.__func__
        if not callable(target):
            raise TypeError(f"@field_validator target must be callable, got {type(fn).__name__}")
        specs = getattr(target, _VALIDATOR_SPECS_ATTR, None)
        if specs is None:
            specs = []
            try:
                setattr(target, _VALIDATOR_SPECS_ATTR, specs)
            except AttributeError as e:
                raise TypeError(
                    "@field_validator target must support attribute assignment "
                    "(plain functions, methods, staticmethod/classmethod, and "
                    f"functools.partial do), got {type(fn).__name__}"
                ) from e
        specs.append(spec)
        return fn

    return decorator


def _hook_bind(func: Callable[..., Any]) -> Literal["instance", "class", "none"]:
    """Decide how a decorated hook callable receives its receiver.

    The first positional parameter's name is the convention: ``self`` binds
    the loading instance, ``cls`` binds the config class, and anything else
    — including callables with no inspectable signature — is called with
    just ``(value, ctx)``, the `@staticmethod`/module-function form.

    Args:
        func: The unwrapped callable the decorator marked

    Returns:
        The binding form for `DotEnvConfig` hook dispatch
    """
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return "none"
    positional = [
        param
        for param in signature.parameters.values()
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if not positional:
        return "none"
    first = positional[0].name
    if first == "self":
        return "instance"
    if first == "cls":
        return "class"
    return "none"


@dataclass(frozen=True)
class _ValidatorHook:
    """A `@field_validator` hook attached to a field, with its binding form.

    Instances are built by the metaclass and live on
    `FieldInfo.before_validators` / `FieldInfo.after_validators`.
    """

    method_name: str
    func: Callable[..., Any]
    bind: Literal["instance", "class", "none"]

    def resolve(self, instance: Any) -> Callable[[Any, ValidatorContext], Any]:
        """Return the hook as a plain ``(value, ctx) -> value`` callable.

        The receiver is bound per the detected form: the loading instance
        for ``self`` methods, the config class for ``cls`` methods, and
        nothing for static/module-function forms.
        """
        receiver: Any = None
        if self.bind == "instance":
            receiver = instance
        elif self.bind == "class":
            receiver = type(instance)
        return _BoundValidatorHook(self.func, receiver, self.method_name)


class _BoundValidatorHook:
    """Adapter calling a decorator-attached hook as ``(value, ctx) -> value``.

    Carries the method name as ``__name__`` so error rendering shows
    ``validator=<method name>``, exactly like the inline
    `Field(validator=...)` path.
    """

    def __init__(self, func: Callable[..., Any], receiver: Any, name: str) -> None:
        self._func = func
        self._receiver = receiver
        self.__name__ = name

    def __call__(self, value: Any, context: ValidatorContext) -> Any:
        if self._receiver is None:
            return self._func(value, context)
        return self._func(self._receiver, value, context)


# Immutable default types are handed out as-is: sharing them is safe.
# Membership is by EXACT type (pydantic's smart_deepcopy semantics) —
# subclasses of str/int/bytes/etc. can carry mutable state, so they fall
# through to copy.deepcopy. datetime subclasses date but is listed for
# clarity. Path instances (PosixPath/WindowsPath), DSN subclasses
# (HttpUrl, PostgresDsn, RedisDsn), and Enum members are not exact
# members; deepcopy handles them (enum singletons come back identical).
_IMMUTABLE_DEFAULT_TYPES: frozenset[type[Any]] = frozenset(
    {
        type(None),
        bool,
        int,
        float,
        complex,
        str,
        bytes,
        range,
        date,
        datetime,
        time,
        timedelta,
        Decimal,
        UUID,
        SecretStr,
        BaseDsn,
    }
)


def smart_deepcopy(value: Any) -> Any:
    """Return a value safe to hand out as a per-load default.

    Values whose exact type is immutable (``None``, ``bool``, ``int``,
    ``float``, ``complex``, ``str``, ``bytes``, ``range``, dates/times,
    ``timedelta``, ``Decimal``, ``UUID``, ``SecretStr``, ``BaseDsn``) are
    returned as-is at zero cost. Empty ``list``/``dict``/``set`` values get
    a shallow ``copy()`` — they hold nothing that could be shared.
    Everything else — non-empty or possibly nested containers, subclasses
    (which can carry mutable state), custom objects — is
    ``copy.deepcopy``-ed; singletons such as ``Enum`` members come back
    from ``deepcopy`` as the same object.

    This mirrors pydantic's ``smart_deepcopy`` (exact-type membership) so
    that a literal mutable default such as ``Field(default=["localhost"])``
    is isolated per ``load()`` call instead of being shared — and mutated —
    across every instance.

    Args:
        value: The literal default value to copy.

    Returns:
        The same object for exact-type immutable values, otherwise an
        independent copy.
    """
    if type(value) in _IMMUTABLE_DEFAULT_TYPES:
        return value
    if type(value) in (list, dict, set) and not value:
        return value.copy()
    return copy.deepcopy(value)


class FieldInfo:
    """Information about a configuration field.

    This class holds all metadata about a field including its default value,
    validation constraints, and documentation. You typically don't create
    `FieldInfo` directly — use the `Field()` function instead.

    When to use directly:
        - Rarely. Use `Field()` in almost all cases.
        - When introspecting field metadata via `get_fields()`

    Attributes:
        default: Default value if env var not set (or `_MISSING` if required)
        default_factory: Callable that returns a default value (for mutable defaults)
        alias: Alternative environment variable name (overrides prefix)
        description: Human-readable description for documentation
        ge: Greater-than-or-equal constraint (>=)
        le: Less-than-or-equal constraint (<=)
        gt: Greater-than constraint (>)
        lt: Less-than constraint (<)
        min_length: Minimum string length
        max_length: Maximum string length
        regex: Regular expression pattern to match
        starts_with: Required string prefix
        ends_with: Required string suffix
        strip: Strip mode for string values (bool, char-set str, or re.Pattern)
        choices: List of allowed values
        validator: Custom validation/transformation hook
        before_validators: `field_validator(mode="before")` hooks attached to
            this field (wired by the metaclass, not settable via `Field()`)
        after_validators: `field_validator(mode="after")` hooks attached to
            this field (wired by the metaclass, not settable via `Field()`)
        min_items: Minimum items in a collection
        max_items: Maximum items in a collection
        uuid_version: Required UUID version (1, 3, 4, or 5)
        separator: Delimiter for parsing list/set/tuple/dict from string (default ",")
        url_unquote: Whether to URL-unquote SecretStr values (default True)
        required: Whether the field is required (computed from default)

    See Also:
        - [`Field`][dotenvmodel.fields.Field]: The function you should use to create fields.
    """

    # Instance attribute type annotations
    default: Any
    default_factory: Callable[[], Any] | None
    alias: str | None
    description: str | None
    ge: int | float | Decimal | None
    le: int | float | Decimal | None
    gt: int | float | Decimal | None
    lt: int | float | Decimal | None
    min_length: int | None
    max_length: int | None
    regex: str | None
    _compiled_regex: re.Pattern[str] | None
    starts_with: str | None
    ends_with: str | None
    strip: bool | str | re.Pattern[str] | None
    choices: list[Any] | None
    validator: Callable[[Any, ValidatorContext], Any] | None
    before_validators: list[_ValidatorHook]
    after_validators: list[_ValidatorHook]
    min_items: int | None
    max_items: int | None
    uuid_version: int | None
    separator: str
    url_unquote: bool
    resolve_path: bool
    require_exists: bool
    required: bool

    def __init__(
        self,
        default: Any = _MISSING,
        *,
        default_factory: Callable[[], Any] | None = None,
        alias: str | None = None,
        description: str | None = None,
        # Numeric validation
        ge: int | float | Decimal | None = None,
        le: int | float | Decimal | None = None,
        gt: int | float | Decimal | None = None,
        lt: int | float | Decimal | None = None,
        # String validation
        min_length: int | None = None,
        max_length: int | None = None,
        regex: str | None = None,
        starts_with: str | None = None,
        ends_with: str | None = None,
        # String processing
        strip: bool | str | re.Pattern[str] | None = None,
        # General validation
        choices: list[Any] | None = None,
        # Custom validation
        validator: Callable[[Any, ValidatorContext], Any] | None = None,
        # Collection validation
        min_items: int | None = None,
        max_items: int | None = None,
        # UUID validation
        uuid_version: int | None = None,
        # Collection parsing
        separator: str = ",",
        # SecretStr options
        url_unquote: bool = True,
        # Path options
        resolve_path: bool = True,
        require_exists: bool = False,
    ) -> None:
        # Validate that only one default mechanism is used
        if default is not _MISSING and default is not ... and default_factory is not None:
            raise ValueError("Cannot specify both 'default' and 'default_factory'")

        # Treat ellipsis as _MISSING (Pydantic-style required indicator)
        if default is ...:
            default = _MISSING

        # Validate numeric constraint types
        for param_name, param_value in [("ge", ge), ("le", le), ("gt", gt), ("lt", lt)]:
            if param_value is not None and not isinstance(param_value, (int, float, Decimal)):
                raise TypeError(
                    f"{param_name} must be int, float, or Decimal, got {type(param_value).__name__}"
                )

        # Validate length/size constraint types
        for param_name, param_value in [
            ("min_length", min_length),
            ("max_length", max_length),
            ("min_items", min_items),
            ("max_items", max_items),
        ]:
            if param_value is not None and (not isinstance(param_value, int) or param_value < 0):
                raise ValueError(
                    f"{param_name} must be a non-negative integer, got {param_value!r}"
                )

        # Validate UUID version
        if uuid_version is not None and uuid_version not in (1, 3, 4, 5):
            raise ValueError(f"uuid_version must be 1, 3, 4, or 5, got {uuid_version}")

        # Validate string affix constraint types
        for param_name, param_value in [("starts_with", starts_with), ("ends_with", ends_with)]:
            if param_value is not None and not isinstance(param_value, str):
                raise TypeError(f"{param_name} must be str, got {type(param_value).__name__}")

        # Validate strip mode
        if strip is not None:
            if isinstance(strip, str):
                if not strip:
                    raise ValueError(f"strip must be a non-empty string, got {strip!r}")
            elif isinstance(strip, re.Pattern):
                if isinstance(strip.pattern, bytes):
                    raise TypeError(
                        f"strip re.Pattern must use a str pattern, got a bytes pattern: {strip.pattern!r}"
                    )
            elif not isinstance(strip, bool):
                raise TypeError(
                    f"strip must be bool, str, or re.Pattern, got {type(strip).__name__}"
                )

        # Validate custom validator is callable
        if validator is not None and not callable(validator):
            raise TypeError(f"validator must be callable, got {type(validator).__name__}")

        # Validate contradictory constraints
        if ge is not None and le is not None and ge > le:
            raise ValueError(f"ge ({ge}) cannot be greater than le ({le})")
        if gt is not None and lt is not None and gt >= lt:
            raise ValueError(f"gt ({gt}) must be less than lt ({lt})")
        if min_length is not None and max_length is not None and min_length > max_length:
            raise ValueError(
                f"min_length ({min_length}) cannot be greater than max_length ({max_length})"
            )
        if min_items is not None and max_items is not None and min_items > max_items:
            raise ValueError(
                f"min_items ({min_items}) cannot be greater than max_items ({max_items})"
            )

        self.default = default
        self.default_factory = default_factory
        self.alias = alias
        self.description = description

        # Numeric constraints
        self.ge = ge
        self.le = le
        self.gt = gt
        self.lt = lt

        # String constraints
        self.min_length = min_length
        self.max_length = max_length
        self.regex = regex
        # Compile regex pattern with error handling
        if regex:
            try:
                self._compiled_regex = re.compile(regex)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {regex!r} - {e}") from e
        else:
            self._compiled_regex = None
        self.starts_with = starts_with
        self.ends_with = ends_with

        # String processing
        self.strip = strip

        # General constraints
        self.choices = choices

        # Custom validation hook
        self.validator = validator

        # Decorator (@field_validator) hooks; the metaclass fills these in.
        # Inline Field(validator=...) stays the single hook settable here.
        self.before_validators: list[_ValidatorHook] = []
        self.after_validators: list[_ValidatorHook] = []

        # Collection constraints
        self.min_items = min_items
        self.max_items = max_items

        # UUID constraints
        self.uuid_version = uuid_version

        # Collection parsing
        self.separator = separator

        # SecretStr options
        self.url_unquote = url_unquote

        # Path options
        self.resolve_path = resolve_path
        self.require_exists = require_exists

        # Mark if field is required
        self.required = default is _MISSING and default_factory is None

    def get_default(self) -> Any:
        """Get the default value for this field.

        Literal defaults pass through ``smart_deepcopy`` so every load
        receives an independent value: mutating one instance's default
        cannot leak into other instances or future loads (pydantic parity).
        Literal defaults must therefore be deep-copyable — a default
        holding state ``copy.deepcopy`` cannot handle (a lock, a socket)
        raises here; use ``default_factory`` for such values. Immutable
        defaults are returned as-is. ``default_factory`` is invoked on
        every load and its result is handed out as-is, never copied: if
        the factory returns a shared object, that object stays shared.
        """
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is _MISSING:
            return _MISSING
        return smart_deepcopy(self.default)

    @property
    def has_default(self) -> bool:
        """Check if this field has a default value."""
        return not self.required

    def __repr__(self) -> str:
        parts = []
        if self.default is not _MISSING:
            parts.append(f"default={self.default!r}")
        if self.default_factory is not None:
            parts.append(f"default_factory={self.default_factory!r}")
        if self.alias:
            parts.append(f"alias={self.alias!r}")
        if self.description:
            parts.append(f"description={self.description!r}")

        # Add constraints
        if self.ge is not None:
            parts.append(f"ge={self.ge}")
        if self.le is not None:
            parts.append(f"le={self.le}")
        if self.gt is not None:
            parts.append(f"gt={self.gt}")
        if self.lt is not None:
            parts.append(f"lt={self.lt}")
        if self.min_length is not None:
            parts.append(f"min_length={self.min_length}")
        if self.max_length is not None:
            parts.append(f"max_length={self.max_length}")
        if self.regex is not None:
            parts.append(f"regex={self.regex!r}")
        if self.starts_with is not None:
            parts.append(f"starts_with={self.starts_with!r}")
        if self.ends_with is not None:
            parts.append(f"ends_with={self.ends_with!r}")
        if self.strip is not None:
            parts.append(f"strip={self.strip!r}")
        if self.choices is not None:
            parts.append(f"choices={self.choices!r}")
        if self.validator is not None:
            parts.append(f"validator={_validator_name(self.validator)}")
        if self.min_items is not None:
            parts.append(f"min_items={self.min_items}")
        if self.max_items is not None:
            parts.append(f"max_items={self.max_items}")
        if self.uuid_version is not None:
            parts.append(f"uuid_version={self.uuid_version}")
        if self.separator != ",":  # Only show if non-default
            parts.append(f"separator={self.separator!r}")

        return f"FieldInfo({', '.join(parts)})"


def Field(
    default: Any = _MISSING,
    *,
    default_factory: Callable[[], Any] | None = None,
    alias: str | None = None,
    description: str | None = None,
    ge: int | float | Decimal | None = None,
    le: int | float | Decimal | None = None,
    gt: int | float | Decimal | None = None,
    lt: int | float | Decimal | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    regex: str | None = None,
    starts_with: str | None = None,
    ends_with: str | None = None,
    strip: bool | str | re.Pattern[str] | None = None,
    choices: list[Any] | None = None,
    validator: Callable[[Any, ValidatorContext], Any] | None = None,
    min_items: int | None = None,
    max_items: int | None = None,
    uuid_version: int | None = None,
    separator: str = ",",
    url_unquote: bool = True,
    resolve_path: bool = True,
    require_exists: bool = False,
) -> Any:
    """Define a configuration field with validation and default values.

    When to use:
        - Always use `Field()` (or `Required`) to define config fields
        - Use `Field()` with no arguments for a required string field
        - Use `Field(...)` (ellipsis) for any required field — Pydantic-style
        - Use `Field(default=value)` for optional fields with defaults

    When to use `default` vs `default_factory`:
        - Use `default` for immutable values (str, int, float, bool, None).
          Literal defaults must be deep-copyable (each load deep-copies
          them); use `default_factory` for values that are not
        - Mutable `default` values (list, dict, set) are safe — each load
          deep-copies them — but `default_factory` avoids that per-load
          copy cost
        - `default_factory` is invoked on every load and its result is
          handed out as-is, never copied — construct new values inside
          the factory; a factory returning a shared object keeps it shared

    Args:
        default: Default value if environment variable not set. Use `...` (ellipsis)
            or omit for required fields. Use a value for optional fields. Literal
            defaults must be deep-copyable (deep-copied per load); use
            `default_factory` for values that are not (locks, sockets).
        default_factory: Callable that returns a default value. Prefer this over a
            mutable `default` (e.g. a list or dict) to avoid the per-load deep-copy
            cost; the factory is invoked on every load and its result is handed
            out as-is, never copied — construct new values inside the factory.
            Example: `default_factory=list`
        alias: Alternative environment variable name to read from. When set, the
            field name is not used for env var lookup, and `env_prefix` is NOT applied.
            Example: `alias="DATABASE_URL"` reads from `DATABASE_URL` regardless of prefix.
        description: Human-readable description shown in `describe()` output and
            `generate_env_example()` files. Useful for team documentation.
        ge: Greater than or equal to (>=). For int, float, and Decimal fields.
            Example: `ge=1` ensures value >= 1
        le: Less than or equal to (<=). For int, float, and Decimal fields.
            Example: `le=65535` ensures value <= 65535
        gt: Greater than (>). For int, float, and Decimal fields.
            Example: `gt=0` ensures value > 0
        lt: Less than (<). For int, float, and Decimal fields.
            Example: `lt=100` ensures value < 100
        min_length: Minimum string length (inclusive). For str and SecretStr fields.
            Example: `min_length=8` ensures string is at least 8 characters
        max_length: Maximum string length (inclusive). For str and SecretStr fields.
            Example: `max_length=128` ensures string is at most 128 characters
        regex: Regular expression pattern the string must match (using `re.match`).
            For str and SecretStr fields. Example: `regex=r'^[a-z]+$'`
        starts_with: Required string prefix. For str and str subclasses (including
            SecretStr and DSN types like HttpUrl, PostgresDsn, RedisDsn).
            Example: `starts_with="sk-"` ensures the value starts with "sk-"
        ends_with: Required string suffix. For str and str subclasses (including
            SecretStr and DSN types like HttpUrl, PostgresDsn, RedisDsn).
            Example: `ends_with=".sig"` ensures the value ends with ".sig"
        strip: Strip mode applied to the raw string before coercion. Applies to
            str, SecretStr, their Optional forms, and str subclasses (e.g. HttpUrl):

            - `None` (default): inherit the class-level `strip_strings` setting
            - `True`: strip leading/trailing whitespace (`value.strip()`)
            - `False`: no stripping, even when the class sets `strip_strings=True`
            - non-empty str: char-set stripping (`value.strip(chars)`)
            - `re.Pattern`: remove every match (`pattern.sub("", value)`)

            Example: `strip=True` or `strip=",'\""`
        choices: List of allowed values. The env var value must be in this list
            (after type coercion). Example: `choices=["dev", "test", "prod"]`
        validator: Custom hook called with the coerced, built-in-constraint-validated
            value and a `ValidatorContext`; its return value becomes the final field
            value (built-in constraints are NOT re-run on a transformed value).
            Runs even when `validate=False`, but never on None values. A `ValueError`
            or `TypeError` from the hook is wrapped in `ConstraintViolationError`
            (for SecretStr fields, with a generic message so the hook's text cannot
            leak the secret); raising `ConstraintViolationError` directly passes
            through with your custom message.
            Example: `validator=lambda v, ctx: v.lower()`
        min_items: Minimum number of items in a collection (list, set, tuple, dict).
            Example: `min_items=1` ensures at least one item
        max_items: Maximum number of items in a collection (list, set, tuple, dict).
            Example: `max_items=10` ensures at most 10 items
        uuid_version: Required UUID version (1, 3, 4, or 5). For UUID fields.
            Example: `uuid_version=4` ensures the UUID is version 4
        separator: Delimiter for parsing list/set/tuple/dict from a string.
            Default is comma (","). Example: `separator=";"` for semicolon-delimited
        url_unquote: Whether to URL-unquote SecretStr values (default True).
            Useful when secrets come from URL-encoded env vars.
        resolve_path: Whether to resolve Path values (expanduser + resolve).
            Default True. Set to False to keep paths raw.
        require_exists: Whether a Path field must point to an existing path.
            Default False.

    Returns:
        FieldInfo instance containing field metadata. Used by the `DotEnvConfig`
        metaclass to discover and process fields.

    Raises:
        ValueError: If both `default` and `default_factory` are specified,
            if constraint values are invalid (e.g., `ge > le`),
            if `min_length > max_length`, if `uuid_version` is not 1/3/4/5,
            or if `strip` is an empty string
        TypeError: If numeric constraints (`ge`, `le`, `gt`, `lt`) are not
            int, float, or Decimal, if `starts_with`/`ends_with` are not str,
            or if `strip` is not a bool, str, or re.Pattern (a re.Pattern with
            a bytes pattern is also rejected)

    Example:
        ```python
        class Config(DotEnvConfig):
            # Required field (no default)
            database_url: str = Field()

            # Required field (Pydantic-style with ellipsis)
            api_key: str = Field(...)

            # Optional with default
            debug: bool = Field(default=False)

            # With validation
            port: int = Field(default=8000, ge=1, le=65535)

            # With alias (overrides env_prefix)
            postgres_dsn: str = Field(alias="DATABASE_URL")

            # Mutable default with default_factory
            hosts: list[str] = Field(default_factory=list)

            # List with custom separator
            tags: list[str] = Field(default_factory=list, separator=";")

            # Collection size constraints
            allowed_ips: list[str] = Field(min_items=1, max_items=10)

            # UUID version constraint
            tenant_id: UUID = Field(uuid_version=4)

            # Choice validation
            env: str = Field(default="dev", choices=["dev", "test", "prod"])

            # SecretStr with length constraint
            api_key: SecretStr = Field(min_length=32)

            # Strip whitespace from the raw value before coercion
            name: str = Field(strip=True)

            # Char-set and regex strip modes
            tag: str = Field(strip=",'\"")          # str.strip(chars) semantics
            key: str = Field(strip=re.compile(r"^['\"]+|['\"]+$"))  # remove every match

            # Prefix/suffix constraints
            client_key: str = Field(starts_with="sk-")
            signed_token: str = Field(ends_with=".sig")

            # Custom validator (may also transform the value)
            region: str = Field(default="us-east-1", validator=lambda v, ctx: v.lower())
        ```

    See Also:
        - [`Required`][dotenvmodel.fields.Required]: Sentinel for required fields.
        - [`FieldInfo`][dotenvmodel.fields.FieldInfo]: The class returned by `Field()`.
        - [`field_validator`][dotenvmodel.fields.field_validator]: Decorator form
          for attaching hooks by field name, with before/after modes.
    """
    return FieldInfo(
        default=default,
        default_factory=default_factory,
        alias=alias,
        description=description,
        ge=ge,
        le=le,
        gt=gt,
        lt=lt,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        starts_with=starts_with,
        ends_with=ends_with,
        strip=strip,
        choices=choices,
        validator=validator,
        min_items=min_items,
        max_items=max_items,
        uuid_version=uuid_version,
        separator=separator,
        url_unquote=url_unquote,
        resolve_path=resolve_path,
        require_exists=require_exists,
    )
