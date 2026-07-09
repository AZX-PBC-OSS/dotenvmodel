"""Type coercion logic for environment variable strings."""

import inspect
import logging
import types
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Union, get_args, get_origin
from uuid import UUID

from typing_extensions import TypeForm

from dotenvmodel._constants import LOGGER_NAME
from dotenvmodel.exceptions import TypeCoercionError

if TYPE_CHECKING:
    from dotenvmodel.fields import FieldInfo

logger = logging.getLogger(LOGGER_NAME)


def coerce_value(
    field_name: str,
    value: str | None,
    field_type: TypeForm[Any],
    env_var_name: str,
    field_info: "FieldInfo | None" = None,
) -> Any:
    """Coerce a string value from an environment variable to the target type.

    When to use:
        - Called automatically by `DotEnvConfig.load()` — rarely called directly
        - Call directly if you need to coerce a value outside of config loading

    Supported types:
        - Basic: `str`, `int`, `float`, `bool`, `Path`
        - Collections: `list[T]`, `set[T]`, `tuple[T, ...]`, `dict[K, V]`
        - Advanced: `UUID`, `Decimal`, `datetime`, `timedelta`
        - Special: `SecretStr`, `HttpUrl`, `PostgresDsn`, `RedisDsn`, `Json[T]`
        - Optional: `T | None`, `Optional[T]`
        - Literal: `Literal["a", "b"]`

    Args:
        field_name: Name of the field being coerced (for error messages)
        value: String value from environment variable (or None)
        field_type: Target type to coerce to
        env_var_name: Name of the environment variable (for error messages)
        field_info: Optional field metadata (used for separator, url_unquote, etc.)

    Returns:
        Coerced value of the target type, or None for empty optional values

    Raises:
        TypeCoercionError: If coercion fails (with helpful error message)
        TypeError: For unsupported non-optional Union types

    See Also:
        - [`FieldInfo`][dotenvmodel.fields.FieldInfo]: Provides separator and other options.
        - [`TypeCoercionError`][dotenvmodel.exceptions.TypeCoercionError]: Exception on failure.
    """
    # Handle None/Optional types
    origin = get_origin(field_type)

    # Handle Literal types first
    if origin is Literal:
        return _coerce_literal(field_name, value, field_type, env_var_name)

    # Handle non-optional Enum types directly
    # Note: Optional[Enum] is handled by Union handler first, which then recursively calls this
    if inspect.isclass(field_type) and issubclass(field_type, Enum):
        return _coerce_enum(field_name, value, field_type, env_var_name)

    # Handle Union types (including Optional[T] and str | None)
    # types.UnionType is for `str | None` syntax, typing.Union is for `Union[str, None]`
    if origin is types.UnionType or origin is Union:
        args = get_args(field_type)
        # Filter out NoneType to get non-None types
        non_none_types = [arg for arg in args if arg is not type(None)]

        if len(non_none_types) == len(args):
            # No None in args - this is a non-Optional Union (e.g., Union[str, int])
            type_names = ", ".join(
                str(arg.__name__ if hasattr(arg, "__name__") else arg) for arg in args
            )
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Union types with multiple non-None types are not supported. "
                f"Use Optional[T] or T | None for nullable fields. Got: Union[{type_names}]",
                field_type=field_type,
                env_var_name=env_var_name,
            )

        if len(non_none_types) != 1:
            # Multiple non-None types (e.g., Union[str, int, None])
            type_names = ", ".join(
                str(arg.__name__ if hasattr(arg, "__name__") else arg) for arg in non_none_types
            )
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Union types with multiple non-None types are not supported. "
                f"Got non-None types: {type_names}",
                field_type=field_type,
                env_var_name=env_var_name,
            )

        # This is Optional[T] or T | None
        if value is None or value == "":
            return None
        actual_type = non_none_types[0]
        return coerce_value(field_name, value, actual_type, env_var_name, field_info)

    # Handle other generic types (list, dict, set, tuple)
    if origin is not None and origin not in (Literal,):
        # This is a generic type like list[str], dict[str, str], etc.
        separator = field_info.separator if field_info else ","
        return _coerce_generic(
            field_name, value, field_type, origin, env_var_name, separator, field_info
        )

    # If value is None, return None (empty string handling depends on type)
    if value is None:
        return None

    # Handle bool type (empty string is falsy for bool)
    if field_type is bool:
        return _coerce_bool(field_name, value, env_var_name)

    # Handle str type explicitly - preserve empty strings
    if field_type is str:
        return value  # Allow empty strings for str fields

    # For other non-collection types (not str, not bool), empty string is treated as None
    # This will cause required fields to fail validation
    if value == "":
        return None

    # Import types module here to avoid circular imports
    from dotenvmodel import types as dotenv_types

    # Handle basic and special types using match/case
    match field_type:
        case type() if field_type is str:
            # Already handled above, but keep for completeness
            return value

        case type() if field_type is int:
            try:
                return int(value)
            except (ValueError, TypeError) as e:
                raise TypeCoercionError(
                    field_name=field_name,
                    value=value,
                    error_msg=str(e),
                    field_type=int,
                    env_var_name=env_var_name,
                ) from e

        case type() if field_type is float:
            try:
                return float(value)
            except (ValueError, TypeError) as e:
                raise TypeCoercionError(
                    field_name=field_name,
                    value=value,
                    error_msg=str(e),
                    field_type=float,
                    env_var_name=env_var_name,
                ) from e

        case type() if field_type is Path:
            path = Path(value)
            if field_info and field_info.resolve_path:
                try:
                    path = path.expanduser().resolve()
                except (OSError, RuntimeError) as e:
                    logger.warning(
                        "Failed to resolve path for field '%s' (value=%s): %s. Using raw path.",
                        field_name,
                        value,
                        e,
                    )
            if field_info and field_info.require_exists and not path.exists():
                raise TypeCoercionError(
                    field_name=field_name,
                    value=value,
                    error_msg=f"Path does not exist: {path}",
                    field_type=Path,
                    env_var_name=env_var_name,
                )
            return path

        case type() if field_type is UUID:
            return dotenv_types.coerce_uuid(value, field_name, env_var_name)

        case type() if field_type is Decimal:
            return dotenv_types.coerce_decimal(value, field_name, env_var_name)

        case type() if field_type is datetime:
            return dotenv_types.coerce_datetime(value, field_name, env_var_name)

        case type() if field_type is timedelta:
            return dotenv_types.coerce_timedelta(value, field_name, env_var_name)

        case type() if field_type is dotenv_types.SecretStr:
            # Apply URL unquoting if requested (default: True)
            if field_info and field_info.url_unquote:
                from urllib.parse import unquote

                value = unquote(value)
            return dotenv_types.SecretStr(value)

        case type() if field_type in (
            dotenv_types.HttpUrl,
            dotenv_types.PostgresDsn,
            dotenv_types.RedisDsn,
        ):
            try:
                return field_type(value)
            except ValueError as e:
                raise TypeCoercionError(
                    field_name=field_name,
                    value=value,
                    error_msg=str(e),
                    field_type=field_type,
                    env_var_name=env_var_name,
                ) from e

        case type() if hasattr(field_type, "__name__") and field_type.__name__.startswith("Json["):
            # Handle Json[T] type
            inner_type = getattr(field_type, "__inner_type__", None)
            return dotenv_types.coerce_json(value, field_name, env_var_name, inner_type)

        case _:
            # If we get here, the type is not supported
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Unsupported type: {field_type}",
                field_type=field_type,
                env_var_name=env_var_name,
            )


def _coerce_enum(
    field_name: str,
    value: str | None,
    field_type: type[Enum],
    env_var_name: str,
) -> Enum:
    """
    Coerce a string value to an Enum member.

    Tries to match by:
    1. Enum value (case-sensitive)
    2. Enum name (case-insensitive)

    Args:
        field_name: Name of the field
        value: String value from environment variable
        field_type: Enum class to coerce to
        env_var_name: Environment variable name

    Returns:
        Enum member instance

    Raises:
        TypeCoercionError: If value doesn't match any enum member
    """
    if value is None or value == "":
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg="Value cannot be None or empty for Enum type",
            field_type=field_type,
            env_var_name=env_var_name,
        )

    # Try matching by value first (exact match, including combined flags)
    try:
        return field_type(int(value))
    except (ValueError, KeyError, TypeError):
        pass

    # Try matching by string representation of value
    for member in field_type:
        if str(member.value) == value:
            return member

    # Try matching by name (case-insensitive, including aliases)
    value_upper = value.upper()
    for name, member in field_type.__members__.items():
        if name.upper() == value_upper:
            return member

    # No match found - provide helpful error
    valid_values = [str(m.value) for m in field_type]
    valid_names = [m.name for m in field_type]

    raise TypeCoercionError(
        field_name=field_name,
        value=value,
        error_msg=(
            f"Invalid {field_type.__name__} value. "
            f"Must be one of: {', '.join(valid_values)} "
            f"(or by name: {', '.join(valid_names)})"
        ),
        field_type=field_type,
        env_var_name=env_var_name,
    )


def _coerce_bool(field_name: str, value: str, env_var_name: str) -> bool:
    """Coerce a string to a boolean."""
    lower_value = value.lower().strip()

    # True values
    if lower_value in ("true", "1", "yes", "on", "t", "y"):
        return True

    # False values
    if lower_value in ("false", "0", "no", "off", "f", "n", ""):
        return False

    # Invalid value
    raise TypeCoercionError(
        field_name=field_name,
        value=value,
        error_msg="Invalid boolean value. Expected one of: true, false, 1, 0, yes, no, on, off, t, f, y, n (case-insensitive)",
        field_type=bool,
        env_var_name=env_var_name,
    )


def _coerce_literal(
    field_name: str, value: str | None, field_type: TypeForm[Any], env_var_name: str
) -> Any:
    """Coerce a value to a Literal type."""
    if value is None:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg="Value cannot be None for Literal type",
            field_type=field_type,
            env_var_name=env_var_name,
        )

    allowed_values = get_args(field_type)
    if value in allowed_values:
        return value

    raise TypeCoercionError(
        field_name=field_name,
        value=value,
        error_msg=f"Value must be one of: {allowed_values}",
        field_type=field_type,
        env_var_name=env_var_name,
    )


def _coerce_generic(
    field_name: str,
    value: str | None,
    field_type: TypeForm[Any],
    origin: Any,
    env_var_name: str,
    separator: str = ",",
    field_info: "FieldInfo | None" = None,
) -> Any:
    """Coerce a value to a generic type (list, dict, set, tuple)."""
    if value is None or value == "":
        # Return empty collection for generic types
        if origin is list:
            return []
        if origin is set:
            return set()
        if origin is tuple:
            return ()
        if origin is dict:
            return {}
        return None

    # Get the type arguments
    args = get_args(field_type)

    if origin is list:
        return _coerce_list(field_name, value, args, env_var_name, separator, field_info)

    if origin is set:
        return _coerce_set(field_name, value, args, env_var_name, separator, field_info)

    if origin is tuple:
        return _coerce_tuple(field_name, value, args, env_var_name, separator, field_info)

    if origin is dict:
        return _coerce_dict(field_name, value, args, env_var_name, separator, field_info)

    raise TypeCoercionError(
        field_name=field_name,
        value=value,
        error_msg=f"Unsupported generic type: {origin}",
        field_type=field_type,
        env_var_name=env_var_name,
    )


def _coerce_list(
    field_name: str,
    value: str,
    args: tuple[type, ...],
    env_var_name: str,
    separator: str = ",",
    field_info: "FieldInfo | None" = None,
) -> list[Any]:
    """Coerce a separated string to a list."""
    if not value:
        return []

    items = [item.strip() for item in value.split(separator)]

    # If no type argument, return list of strings
    if not args:
        return items

    # Coerce each item to the element type
    element_type = args[0]
    result = []
    for item in items:
        try:
            coerced = coerce_value(field_name, item, element_type, env_var_name, field_info)
            # Skip None values for non-optional types (empty items in non-str lists)
            # For list[str], empty items are preserved as ""
            # For list[int], empty items are skipped entirely
            if coerced is None and element_type is not str:
                # Check if element type is Optional
                from typing import get_args, get_origin

                origin = get_origin(element_type)
                if origin is None or type(None) not in get_args(element_type):
                    # Not Optional, skip None values
                    continue
            result.append(coerced)
        except TypeCoercionError as e:
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Failed to coerce list element '{item}': {e.error_msg}",
                field_type=list,
                env_var_name=env_var_name,
            ) from e

    return result


def _coerce_set(
    field_name: str,
    value: str,
    args: tuple[type, ...],
    env_var_name: str,
    separator: str = ",",
    field_info: "FieldInfo | None" = None,
) -> set[Any]:
    """Coerce a separated string to a set."""
    list_result = _coerce_list(field_name, value, args, env_var_name, separator, field_info)
    return set(list_result)


def _coerce_tuple(
    field_name: str,
    value: str,
    args: tuple[type, ...],
    env_var_name: str,
    separator: str = ",",
    field_info: "FieldInfo | None" = None,
) -> tuple[Any, ...]:
    """Coerce a separated string to a tuple."""
    list_result = _coerce_list(field_name, value, args, env_var_name, separator, field_info)
    return tuple(list_result)


def _coerce_dict(
    field_name: str,
    value: str,
    args: tuple[type, ...],
    env_var_name: str,
    separator: str = ",",
    field_info: "FieldInfo | None" = None,
) -> dict[Any, Any]:
    """Coerce a separated string of key=value pairs to a dict."""
    if not value:
        return {}

    result = {}
    pairs = [pair.strip() for pair in value.split(separator)]

    key_type = args[0] if len(args) >= 1 else str
    value_type = args[1] if len(args) >= 2 else str

    for pair in pairs:
        if "=" not in pair:
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Invalid dict format. Expected 'key=value', got: {pair}",
                field_type=dict,
                env_var_name=env_var_name,
            )

        key_str, val_str = pair.split("=", 1)
        key_str = key_str.strip()
        val_str = val_str.strip()

        try:
            coerced_key = coerce_value(field_name, key_str, key_type, env_var_name, field_info)
            coerced_val = coerce_value(field_name, val_str, value_type, env_var_name, field_info)

            # Skip None keys (empty keys for non-str types) - this would be invalid
            if coerced_key is None and key_type is not str:
                from typing import get_args, get_origin

                origin = get_origin(key_type)
                if origin is None or type(None) not in get_args(key_type):
                    continue  # Skip this pair

            # For values, we allow None if value_type is Optional
            result[coerced_key] = coerced_val
        except TypeCoercionError as e:
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Failed to coerce dict pair '{pair}': {e.error_msg}",
                field_type=dict,
                env_var_name=env_var_name,
            ) from e

    return result
