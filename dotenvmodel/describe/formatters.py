"""Type and value formatting utilities for describe output."""

from __future__ import annotations

import collections.abc
import inspect
import json
import logging
import re
import types
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from typing_extensions import TypeForm

from dotenvmodel._constants import LOGGER_NAME
from dotenvmodel._redaction import redact_url_password
from dotenvmodel.coercion import is_string_like_type
from dotenvmodel.fields import _MISSING, FieldInfo, _validator_name
from dotenvmodel.types import BaseDsn, SecretStr, is_sensitive_type

if TYPE_CHECKING:
    from dotenvmodel.config import DotEnvConfig

logger = logging.getLogger(LOGGER_NAME)

# Maximum column widths to prevent unbounded table growth
MAX_WIDTHS = {
    0: 40,  # ENV Variable
    1: 30,  # Type
    2: 8,  # Required
    3: 25,  # Default
    4: 40,  # Description
    5: 40,  # Constraints
}

# Truncation thresholds for different value types
TRUNCATE_THRESHOLD_SHORT = 20
TRUNCATE_THRESHOLD_MEDIUM = 25
TRUNCATE_THRESHOLD_LONG = 35

# Rendered for fields whose default_factory raised while being invoked for
# display; render_dotenv turns it into a commented placeholder line.
SET_PER_ENVIRONMENT = "<<set per environment>>"

# Type parsing hint mapping
TYPE_PARSING_HINTS = {
    "list": "comma-separated values",
    "set": "comma-separated unique values",
    "tuple": "comma-separated values",
    "dict": "comma-separated key:value pairs",
    "timedelta": "duration format (e.g., 5s, 1m, 1h, 1d, 1w) or seconds as int",
    "UUID": "UUID string",
    "Decimal": "decimal number string",
    "Path": "file or directory path",
    "HttpUrl": "HTTP(S) URL (e.g., https://example.com)",
    "PostgresDsn": "PostgreSQL DSN (e.g., postgresql://user:pass@localhost:5432/db)",
    "RedisDsn": "Redis DSN (e.g., redis://localhost:6379/0)",
    "Json": "valid JSON string",
    "SecretStr": "sensitive string (won't be logged)",
    "datetime": "ISO 8601 datetime string",
}


@dataclass
class FieldDescription:
    """Structured representation of a field for describe output.

    Attributes:
        env_var: The environment variable name (with prefix applied)
        field_name: The Python field name
        type_name: Human-readable type string (e.g., "list[str]")
        required: Whether the field is required
        default: Formatted default value string (e.g., "8000", "None", "-")
        description: Field description or "-" if none
        constraints: Formatted constraints string (e.g., "ge=1, le=65535")
        separator: Delimiter the field uses for collection values (default ",")
    """

    env_var: str
    field_name: str
    type_name: str
    required: bool
    default: str
    description: str
    constraints: str
    separator: str = ","


def _extract_enum_from_type(field_type: TypeForm[Any]) -> type[Enum] | None:
    """Extract enum type from a type annotation, including Union types."""
    if inspect.isclass(field_type) and issubclass(field_type, Enum):
        return field_type

    origin = get_origin(field_type)
    if origin is types.UnionType or origin is Union:
        for arg in get_args(field_type):
            if arg is not type(None) and inspect.isclass(arg) and issubclass(arg, Enum):
                return arg

    return None


def format_type_name(field_type: TypeForm[Any]) -> str:
    """Format a type annotation as a readable string.

    Examples:
        int -> "int"
        list[str] -> "list[str]"
        str | None -> "str | None"
        LogLevel -> "LogLevel (debug, info, warning, error)"
    """
    if field_type is type(None):
        return "None"

    if field_type is Ellipsis:
        return "..."

    enum_type = _extract_enum_from_type(field_type)
    if enum_type is not None and field_type is enum_type:
        values = [_format_enum_member_value(m.value) for m in enum_type]
        return f"{enum_type.__name__} ({', '.join(values)})"

    origin = get_origin(field_type)

    if origin is types.UnionType or origin is Union:
        args = get_args(field_type)
        formatted_args = [format_type_name(arg) for arg in args]
        if type(None) in args:
            non_none = [a for a in formatted_args if a != "None"]
            if len(non_none) == 1:
                return f"{non_none[0]} | None"
        return " | ".join(formatted_args)

    if origin is collections.abc.Callable:
        args = get_args(field_type)
        if args and len(args) == 2:
            param_types, return_type = args
            if isinstance(param_types, (list, tuple)):
                params = ", ".join(format_type_name(p) for p in param_types)
            else:
                params = "..."
            ret = format_type_name(return_type)
            return f"Callable[[{params}], {ret}]"
        return "Callable"

    if origin is not None:
        args = get_args(field_type)
        origin_name = getattr(origin, "__name__", str(origin))
        if args:
            arg_names = ", ".join(format_type_name(a) for a in args)
            return f"{origin_name}[{arg_names}]"
        return origin_name

    type_name_str = getattr(field_type, "__name__", "")
    if isinstance(type_name_str, str) and type_name_str.startswith("Json["):
        return type_name_str.replace("<class 'dict'>", "dict").replace("<class 'list'>", "list")

    name = getattr(field_type, "__name__", None)
    if name is not None:
        return name

    return str(field_type)


def get_type_parsing_hint(field_type: type, field_info: FieldInfo | None = None) -> str:
    """Get parsing hint for a type to help developers format values."""
    origin = get_origin(field_type)

    if field_info and field_info.separator != "," and origin in (list, set, tuple):
        sep = field_info.separator
        return f"{sep}-separated values (use {sep} as delimiter)"

    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        if origin_name in TYPE_PARSING_HINTS:
            hint = TYPE_PARSING_HINTS[origin_name]
            if origin_name in ("list", "set", "tuple"):
                args = get_args(field_type)
                if args:
                    element_type = args[0]
                    element_name = getattr(element_type, "__name__", str(element_type))
                    if element_name == "int":
                        return f"{hint} (e.g., 1,2,3,4)"
                    elif element_name == "str":
                        return f"{hint} (e.g., value1,value2,value3)"
            return hint

    simple_name = getattr(field_type, "__name__", None)
    if simple_name and simple_name in TYPE_PARSING_HINTS:
        return TYPE_PARSING_HINTS[simple_name]

    return ""


def generate_constraint_examples(field_type: type, field_info: FieldInfo) -> dict[str, list[str]]:
    """Generate valid and invalid examples for field constraints."""
    valid: list[str] = []
    invalid: list[str] = []

    type_name = getattr(field_type, "__name__", str(field_type))
    origin = get_origin(field_type)
    if origin:
        type_name = getattr(origin, "__name__", str(origin))

    if (
        field_info.ge is not None
        or field_info.le is not None
        or field_info.gt is not None
        or field_info.lt is not None
    ) and type_name in ("int", "float"):
        from decimal import Decimal

        lower_raw = field_info.ge if field_info.ge is not None else field_info.gt
        upper_raw = field_info.le if field_info.le is not None else field_info.lt
        lower = Decimal(str(lower_raw)) if lower_raw is not None else None
        upper = Decimal(str(upper_raw)) if upper_raw is not None else None

        if lower is not None and upper is not None:
            mid = int((lower + upper) // 2) if type_name == "int" else (lower + upper) / 2
            valid.extend([str(lower_raw), str(mid), str(upper_raw)])
            invalid.append(f"{lower - 1} (too small)")
            invalid.append(f"{upper + 1} (too large)")
        elif lower is not None:
            valid.extend([str(lower_raw), str(lower + 10)])
            invalid.append(f"{lower - 1} (too small)")
        elif upper is not None:
            valid.extend([str(upper - 10), str(upper_raw)])
            invalid.append(f"{upper + 1} (too large)")

        invalid.append(f"abc (not a {type_name})")

    if field_info.min_length is not None or field_info.max_length is not None:
        min_len = field_info.min_length or 0
        max_len = field_info.max_length or 100

        if field_info.min_length and field_info.max_length:
            valid.append(f"{'x' * min_len} ({min_len} chars)")
            mid_len = (min_len + max_len) // 2
            valid.append(f"{'x' * mid_len} ({mid_len} chars)")
            valid.append(f"{'x' * max_len} ({max_len} chars)")
            if min_len > 0:
                invalid.append(f"{'x' * (min_len - 1)} (too short)")
            invalid.append(f"{'x' * (max_len + 1)} (too long)")
        elif field_info.min_length:
            valid.append(f"{'x' * min_len} (minimum length)")
            valid.append(f"{'x' * (min_len + 5)}")
            if min_len > 0:
                invalid.append(f"{'x' * (min_len - 1)} (too short)")
        elif field_info.max_length:
            valid.append(f"{'x' * (max_len // 2)}")
            valid.append(f"{'x' * max_len} (maximum length)")
            invalid.append(f"{'x' * (max_len + 1)} (too long)")

    if field_info.choices is not None:
        valid.extend([str(c) for c in field_info.choices[:3]])
        if len(field_info.choices) > 0:
            invalid.append("invalid_choice (not in allowed choices)")

    if field_info.min_items is not None or field_info.max_items is not None:
        min_items = field_info.min_items or 0
        max_items = field_info.max_items or 10

        if field_info.min_items and field_info.max_items:
            valid.append(f"{','.join(['item'] * min_items)} ({min_items} items)")
            valid.append(f"{','.join(['item'] * max_items)} ({max_items} items)")
            if min_items > 0:
                invalid.append(f"{','.join(['item'] * (min_items - 1))} (too few items)")
            invalid.append(f"{','.join(['item'] * (max_items + 1))} (too many items)")
        elif field_info.min_items:
            valid.append(f"{','.join(['item'] * min_items)} (minimum)")
            if min_items > 0:
                invalid.append(f"{','.join(['item'] * (min_items - 1))} (too few)")
        elif field_info.max_items:
            valid.append(f"{','.join(['item'] * max_items)} (maximum)")
            invalid.append(f"{','.join(['item'] * (max_items + 1))} (too many)")

    return {"valid": valid, "invalid": invalid}


def format_constraints(
    field_info: FieldInfo,
    truncate: bool = True,
    field_type: type | None = None,
    class_strip_strings: bool = False,
) -> str:
    """Format field constraints as a readable string."""
    constraints: list[str] = []

    enum_type = _extract_enum_from_type(field_type) if field_type is not None else None
    if enum_type is not None:
        values = [_format_enum_member_value(m.value) for m in enum_type]
        choices_str = ", ".join(values)
        if truncate and len(choices_str) > TRUNCATE_THRESHOLD_MEDIUM:
            choices_str = choices_str[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
        constraints.append(f"choices: {choices_str}")

    if field_info.ge is not None:
        constraints.append(f"ge={field_info.ge}")
    if field_info.le is not None:
        constraints.append(f"le={field_info.le}")
    if field_info.gt is not None:
        constraints.append(f"gt={field_info.gt}")
    if field_info.lt is not None:
        constraints.append(f"lt={field_info.lt}")

    if field_info.min_length is not None:
        constraints.append(f"min_length={field_info.min_length}")
    if field_info.max_length is not None:
        constraints.append(f"max_length={field_info.max_length}")
    if field_info.regex is not None:
        pattern = field_info.regex
        if truncate and len(pattern) > TRUNCATE_THRESHOLD_SHORT:
            pattern = pattern[: TRUNCATE_THRESHOLD_SHORT - 3] + "..."
        constraints.append(f"regex={pattern}")

    # String-only constraints: only render for string-like types (or when
    # field_type is unknown, i.e. direct calls without field_type — preserves
    # backward compatibility for unit tests that call format_constraints directly).
    is_string_like = field_type is None or is_string_like_type(field_type)

    if is_string_like:
        if field_info.starts_with is not None:
            constraints.append(f"starts_with={field_info.starts_with!r}")
        if field_info.ends_with is not None:
            constraints.append(f"ends_with={field_info.ends_with!r}")

    if field_info.choices is not None:
        choices_str = ", ".join(str(c) for c in field_info.choices)
        if truncate and len(choices_str) > TRUNCATE_THRESHOLD_MEDIUM:
            choices_str = choices_str[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
        constraints.append(f"choices=[{choices_str}]")

    if field_info.min_items is not None:
        constraints.append(f"min_items={field_info.min_items}")
    if field_info.max_items is not None:
        constraints.append(f"max_items={field_info.max_items}")

    if field_info.uuid_version is not None:
        constraints.append(f"uuid_version={field_info.uuid_version}")

    if field_info.separator != ",":
        constraints.append(f"separator={field_info.separator!r}")

    # Effective strip mode: field-level overrides class-level inheritance.
    # strip=None inherits class_strip_strings; strip=False explicitly disables.
    effective_strip = field_info.strip if field_info.strip is not None else class_strip_strings

    if is_string_like:
        if effective_strip is True:
            constraints.append("strip")
        elif isinstance(effective_strip, str):
            constraints.append(f"strip({effective_strip!r})")
        elif isinstance(effective_strip, re.Pattern):
            constraints.append(f"strip({effective_strip.pattern!r})")

    if field_info.validator is not None:
        constraints.append(f"validator={_validator_name(field_info.validator)}")

    return ", ".join(constraints) if constraints else "-"


def _union_members(field_type: TypeForm[Any] | types.UnionType) -> list[Any]:
    """Return the non-None members of an Optional/Union, else ``[field_type]``.

    Handles multi-member unions (``PostgresDsn | RedisDsn | None``) so a DSN or
    SecretStr anywhere in the union is still recognised for redaction.
    """
    origin = get_origin(field_type)
    if origin is types.UnionType or origin is Union:
        return [a for a in get_args(field_type) if a is not type(None)]
    return [field_type]


def _is_type_in_union(field_type: TypeForm[Any] | types.UnionType, target: type) -> bool:
    """True if any member of ``field_type`` is a subclass of ``target``."""
    return any(isinstance(m, type) and issubclass(m, target) for m in _union_members(field_type))


def _is_json_typed(field_type: TypeForm[Any] | types.UnionType) -> bool:
    """True if any member of ``field_type`` is a runtime ``Json[...]`` type.

    Mirrors the coercion-side detection (``__name__`` starts with
    ``"Json["``) so example rendering matches what ``coerce_value`` parses.
    """
    return any(
        isinstance(m, type) and getattr(m, "__name__", "").startswith("Json[")
        for m in _union_members(field_type)
    )


def _is_sensitive_collection(field_type: TypeForm[Any] | types.UnionType) -> bool:
    """True when a list/set/tuple/dict annotation holds sensitive members.

    ``Optional``/``Union`` is unwrapped first so ``list[SecretStr] | None``
    is caught. Any sensitive member argument (``SecretStr`` or a ``BaseDsn``
    subclass — for dicts, keys and values both) masks the whole collection:
    element-wise rendering would leak each secret.
    """
    for member in _union_members(field_type):
        origin = get_origin(member)
        if origin in (list, set, tuple, dict) and any(
            is_sensitive_type(arg) for arg in get_args(member)
        ):
            return True
    return False


def _format_enum_member_value(value: object) -> str:
    """Render an Enum member's value for display, masking sensitive values.

    ``str(member.value)`` on a ``SecretStr`` shows asterisks (not the
    ``<secret>`` sentinel) and on a ``BaseDsn`` shows the raw connection
    string with its password, so sensitive member values are handled here
    once, shared by the type-name, constraints, and default renderers.
    """
    if isinstance(value, SecretStr):
        return "<secret>"
    if isinstance(value, BaseDsn):
        return redact_url_password(str.__str__(value))
    return str(value)


def _render_collection_item(item: Any) -> str:
    """Render a collection item, unwrapping ``Enum`` members to their values.

    ``str(Color.RED)`` is ``"Color.RED"``, which fails coercion when the
    rendered example is uncommented; the member's value round-trips.
    """
    return str(item.value if isinstance(item, Enum) else item)


def _bounded(rendered: str, truncate: bool) -> str:
    """Cap a joined/JSON default at ``TRUNCATE_THRESHOLD_MEDIUM`` when truncating.

    Truncated display formats (table, markdown) bound collection renders
    the way the repr path always has; the dotenv format renders
    untruncated so ``.env.example`` values stay complete and
    round-trippable.
    """
    if truncate and len(rendered) > TRUNCATE_THRESHOLD_MEDIUM:
        return rendered[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
    return rendered


def _render_default_value(
    value: Any,
    field_info: FieldInfo,
    field_type: TypeForm[Any],
    truncate: bool,
) -> str:
    """Render a default value in the format dotenvmodel itself parses back.

    Split out from ``format_default`` so the whole rendering pipeline can
    be guarded by its never-crash handler.
    """
    if value is None:
        return "None"

    if isinstance(value, Enum):
        member_value = value.value
        # An Enum wrapping a SecretStr/DSN bypasses the scalar redaction
        # checks below (str(member.value) prints the raw secret); mask it here.
        if isinstance(member_value, SecretStr):
            return "<secret>"
        if isinstance(member_value, BaseDsn):
            # Match the scalar DSN default render: quoted, password redacted.
            return f'"{_format_enum_member_value(member_value)}"'
        return str(member_value)

    # Recognise DSN/SecretStr even inside an Optional/multi-member Union
    # (e.g. `PostgresDsn | RedisDsn | None`) so nested defaults are redacted.
    if _is_type_in_union(field_type, SecretStr):
        return "<secret>"

    # DSN defaults may embed credentials; redact the password before display.
    if _is_type_in_union(field_type, BaseDsn) and isinstance(value, str):
        return f'"{redact_url_password(str.__str__(value))}"'

    if _is_json_typed(field_type) and isinstance(value, (list, dict)):
        return _bounded(json.dumps(value), truncate)

    # Empty collections reveal nothing; "" (which parses back as an empty
    # collection) must win over the sensitive-collection mask below. This
    # sits after the Json branch so an empty Json default keeps its "[]".
    if isinstance(value, (list, set, tuple, dict)) and not value:
        return ""

    # Sensitive collections (list[SecretStr], set[BaseDsn],
    # dict[str, SecretStr], Optional[...]) mask wholesale: element-wise
    # rendering would leak each secret.
    if _is_sensitive_collection(field_type):
        return "<secret>"

    if isinstance(value, str):
        if is_string_like_type(field_type):
            # Str-typed fields keep the quoted rendering (pinned behavior).
            if truncate and len(value) > TRUNCATE_THRESHOLD_SHORT:
                return f'"{value[: TRUNCATE_THRESHOLD_SHORT - 3]}..."'
            return f'"{value}"'
        # A str default for a non-str field is coerced at load (e.g.
        # list[str] splits it on the separator); quoting it would corrupt
        # the round trip (['"a', 'b"']), so render it unquoted.
        if truncate and len(value) > TRUNCATE_THRESHOLD_SHORT:
            return value[: TRUNCATE_THRESHOLD_SHORT - 3] + "..."
        return value

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, timedelta):
        return str(value)

    if isinstance(value, Path):
        return f"Path({str(value)!r})"

    # Collections render exactly as _coerce_list/_coerce_dict parse them
    # back; empty collections render as an empty value (not "[]", which
    # would parse back as a list containing the string "[]"). Enum items
    # unwrap to their values so the joined output parses back.
    if isinstance(value, (list, tuple)):
        return _bounded(
            field_info.separator.join(_render_collection_item(item) for item in value),
            truncate,
        )

    if isinstance(value, set):
        # Hash order varies with PYTHONHASHSEED; sort the rendered strings
        # so .env.example output is deterministic (no diff churn).
        items = sorted(_render_collection_item(item) for item in value)
        return _bounded(field_info.separator.join(items), truncate)

    if isinstance(value, dict):
        return _bounded(
            field_info.separator.join(
                f"{k}={_render_collection_item(v)}" for k, v in value.items()
            ),
            truncate,
        )

    repr_str = repr(value)
    if truncate and len(repr_str) > TRUNCATE_THRESHOLD_MEDIUM:
        return repr_str[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
    return repr_str


def format_default(field_info: FieldInfo, field_type: TypeForm[Any], truncate: bool = True) -> str:
    """Format a field's default value for display.

    Renders values in the format dotenvmodel itself parses so generated
    ``.env.example`` files round-trip: ``list``/``set``/``tuple`` defaults
    are joined with the field's ``separator``, ``dict`` defaults as
    ``key=value`` pairs, and ``Json[...]`` fields as JSON. A
    ``default_factory`` is invoked once to render its result. Rendering
    never crashes: a factory that raises, or a value that fails to render
    (e.g. a non-serializable ``Json[...]`` default), logs a warning and
    returns the ``SET_PER_ENVIRONMENT`` placeholder instead. Warnings
    carry the exception type only — messages can embed secret values.
    When ``truncate`` is true, joined/JSON renders are capped at
    ``TRUNCATE_THRESHOLD_MEDIUM``; the dotenv format renders untruncated
    so example values stay complete.
    """
    if field_info.default is _MISSING and field_info.default_factory is None:
        return "-"

    if field_info.default_factory is not None:
        factory = field_info.default_factory
        try:
            value = factory()
        except Exception as exc:
            # Log the exception type only: messages can embed secret values.
            logger.warning(
                "default_factory %s raised while rendering an example value "
                "(%s); rendering the '%s' placeholder instead",
                _validator_name(factory),
                type(exc).__name__,
                SET_PER_ENVIRONMENT,
            )
            return SET_PER_ENVIRONMENT
    else:
        value = field_info.default

    try:
        return _render_default_value(value, field_info, field_type, truncate)
    except Exception as exc:
        # The rendering pipeline must never crash generation (a broken
        # repr, an unserializable Json default, an exotic __str__). Log
        # the exception type only: messages can embed secret values.
        logger.warning(
            "rendering a default value failed (%s); rendering the '%s' placeholder instead",
            type(exc).__name__,
            SET_PER_ENVIRONMENT,
        )
        return SET_PER_ENVIRONMENT


def describe_class(
    config_cls: type[DotEnvConfig],
    truncate: bool = True,
) -> tuple[str, str, list[FieldDescription]]:
    """Extract field descriptions from a config class.

    Returns:
        Tuple of (class_name, env_prefix, list of FieldDescription)
    """
    from dotenvmodel.loading import get_env_var_name

    class_name = config_cls.__name__
    prefix = getattr(config_cls, "env_prefix", "")
    class_strip_strings = getattr(config_cls, "strip_strings", False)
    fields: list[FieldDescription] = []

    for field_name, (field_type, field_info) in config_cls.get_fields().items():
        env_var = get_env_var_name(field_name, field_info.alias, prefix)
        type_name = format_type_name(field_type)
        default_str = format_default(field_info, field_type, truncate=truncate)
        constraints_str = format_constraints(
            field_info,
            truncate=truncate,
            field_type=field_type,
            class_strip_strings=class_strip_strings,
        )
        description = field_info.description or "-"

        if truncate and len(description) > TRUNCATE_THRESHOLD_LONG:
            description = description[: TRUNCATE_THRESHOLD_LONG - 3] + "..."

        fields.append(
            FieldDescription(
                env_var=env_var,
                field_name=field_name,
                type_name=type_name,
                required=field_info.required,
                default=default_str,
                description=description,
                constraints=constraints_str,
                separator=field_info.separator,
            )
        )

    return class_name, prefix, fields
