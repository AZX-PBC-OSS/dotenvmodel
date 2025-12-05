"""Type coercion logic for environment variable strings."""

import types
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, get_args, get_origin
from uuid import UUID

from dotenvmodel.exceptions import TypeCoercionError

if TYPE_CHECKING:
    from dotenvmodel.fields import FieldInfo


def coerce_value(
    field_name: str,
    value: str | None,
    field_type: type,
    env_var_name: str,
    field_info: "FieldInfo | None" = None,
) -> Any:
    """
    Coerce a string value from environment variable to the target type.

    Args:
        field_name: Name of the field being coerced
        value: String value from environment variable (or None)
        field_type: Target type to coerce to
        env_var_name: Name of the environment variable
        field_info: Optional field metadata (for separator, etc.)

    Returns:
        Coerced value of the target type

    Raises:
        TypeCoercionError: If coercion fails
    """
    # Handle None/Optional types
    origin = get_origin(field_type)

    # Handle Literal types first
    if origin is Literal:
        return _coerce_literal(field_name, value, field_type, env_var_name)

    # Handle Union types (including Optional[T] and str | None)
    # Check for UnionType (str | None) or typing.Union
    if origin is types.UnionType or (origin is not None and type(None) in get_args(field_type)):
        args = get_args(field_type)
        if type(None) in args:
            # This is Optional[T] or T | None
            if value is None or value == "":
                return None
            # Get the non-None type
            actual_type = args[0] if args[1] is type(None) else args[1]
            return coerce_value(field_name, value, actual_type, env_var_name, field_info)
        else:
            # Non-Optional Union types (e.g., Union[str, int] or str | int) are not supported
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

    # Handle other generic types (list, dict, set, tuple)
    if origin is not None and origin not in (Literal,):
        # This is a generic type like list[str], dict[str, str], etc.
        separator = field_info.separator if field_info else ","
        return _coerce_generic(field_name, value, field_type, origin, env_var_name, separator)

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
            return Path(value)

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


def _coerce_literal(field_name: str, value: str | None, field_type: type, env_var_name: str) -> Any:
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
    field_type: type,
    origin: Any,
    env_var_name: str,
    separator: str = ",",
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
        return _coerce_list(field_name, value, args, env_var_name, separator)

    if origin is set:
        return _coerce_set(field_name, value, args, env_var_name, separator)

    if origin is tuple:
        return _coerce_tuple(field_name, value, args, env_var_name, separator)

    if origin is dict:
        return _coerce_dict(field_name, value, args, env_var_name, separator)

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
            coerced = coerce_value(field_name, item, element_type, env_var_name)
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
) -> set[Any]:
    """Coerce a separated string to a set."""
    list_result = _coerce_list(field_name, value, args, env_var_name, separator)
    return set(list_result)


def _coerce_tuple(
    field_name: str,
    value: str,
    args: tuple[type, ...],
    env_var_name: str,
    separator: str = ",",
) -> tuple[Any, ...]:
    """Coerce a separated string to a tuple."""
    list_result = _coerce_list(field_name, value, args, env_var_name, separator)
    return tuple(list_result)


def _coerce_dict(
    field_name: str,
    value: str,
    args: tuple[type, ...],
    env_var_name: str,
    separator: str = ",",
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
            coerced_key = coerce_value(field_name, key_str, key_type, env_var_name)
            coerced_val = coerce_value(field_name, val_str, value_type, env_var_name)

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
