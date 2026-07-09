"""Type and value formatting utilities for describe output."""

from __future__ import annotations

import collections.abc
import inspect
import types
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin

from typing_extensions import TypeForm

from dotenvmodel.fields import _MISSING, FieldInfo
from dotenvmodel.types import SecretStr

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
    """

    env_var: str
    field_name: str
    type_name: str
    required: bool
    default: str
    description: str
    constraints: str


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
        values = [str(m.value) for m in enum_type]
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
    field_info: FieldInfo, truncate: bool = True, field_type: type | None = None
) -> str:
    """Format field constraints as a readable string."""
    constraints: list[str] = []

    enum_type = _extract_enum_from_type(field_type) if field_type is not None else None
    if enum_type is not None:
        values = [str(m.value) for m in enum_type]
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

    return ", ".join(constraints) if constraints else "-"


def format_default(field_info: FieldInfo, field_type: TypeForm[Any], truncate: bool = True) -> str:
    """Format default value for display."""
    if field_info.default is _MISSING and field_info.default_factory is None:
        return "-"

    if field_info.default_factory is not None:
        factory = field_info.default_factory
        if factory is list:
            return "[]"
        if factory is dict:
            return "{}"
        if factory is set:
            return "set()"
        return f"<{getattr(factory, '__name__', 'factory')}()>"

    default = field_info.default

    if default is None:
        return "None"

    if isinstance(default, Enum):
        return str(default.value)

    if isinstance(field_type, type) and issubclass(field_type, SecretStr):
        return "<secret>"

    if isinstance(default, str):
        if truncate and len(default) > TRUNCATE_THRESHOLD_SHORT:
            return f'"{default[: TRUNCATE_THRESHOLD_SHORT - 3]}..."'
        return f'"{default}"'

    if isinstance(default, bool):
        return str(default)

    if isinstance(default, (int, float)):
        return str(default)

    if isinstance(default, timedelta):
        return str(default)

    if isinstance(default, Path):
        return f"Path({str(default)!r})"

    repr_str = repr(default)
    if truncate and len(repr_str) > TRUNCATE_THRESHOLD_MEDIUM:
        return repr_str[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
    return repr_str


def describe_class(
    config_cls: type,  # type: ignore[type-arg]
    truncate: bool = True,
) -> tuple[str, str, list[FieldDescription]]:
    """Extract field descriptions from a config class.

    Returns:
        Tuple of (class_name, env_prefix, list of FieldDescription)
    """
    from dotenvmodel.loading import get_env_var_name

    class_name = config_cls.__name__
    prefix = getattr(config_cls, "env_prefix", "")
    fields: list[FieldDescription] = []

    for field_name, (field_type, field_info) in config_cls.get_fields().items():
        env_var = get_env_var_name(field_name, field_info.alias, prefix)
        type_name = format_type_name(field_type)
        default_str = format_default(field_info, field_type, truncate=truncate)
        constraints_str = format_constraints(field_info, truncate=truncate, field_type=field_type)
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
            )
        )

    return class_name, prefix, fields
