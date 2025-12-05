"""Field validation logic for dotenvmodel."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from dotenvmodel.exceptions import ConstraintViolationError
from dotenvmodel.fields import FieldInfo


def validate_field(field_name: str, value: Any, field_info: FieldInfo, env_var_name: str) -> None:
    """
    Validate a field value against its constraints.

    Args:
        field_name: Name of the field being validated
        value: Value to validate
        field_info: Field metadata containing validation constraints
        env_var_name: Name of the environment variable

    Raises:
        ConstraintViolationError: If validation fails
    """
    # Skip validation for None values (handled by type coercion)
    if value is None:
        return

    # Numeric validation (int, float, Decimal)
    if isinstance(value, (int, float, Decimal)):
        _validate_numeric(field_name, value, field_info, env_var_name)

    # String validation (including SecretStr)
    from dotenvmodel.types import SecretStr

    if isinstance(value, str):
        _validate_string(field_name, value, field_info, env_var_name)
    elif isinstance(value, SecretStr):
        # Validate the secret value as a string
        _validate_string(field_name, value.get_secret_value(), field_info, env_var_name)

    # Choice validation (works for any type)
    if field_info.choices is not None:
        _validate_choices(field_name, value, field_info, env_var_name)

    # Collection size validation (for list, set, tuple, dict)
    if isinstance(value, (list, set, tuple, dict)):
        _validate_collection_size(field_name, value, field_info, env_var_name)

    # UUID version validation
    if isinstance(value, UUID):
        _validate_uuid_version(field_name, value, field_info, env_var_name)


def _validate_numeric(
    field_name: str, value: int | float | Decimal, field_info: FieldInfo, env_var_name: str
) -> None:
    """Validate numeric constraints (ge, le, gt, lt) for int, float, and Decimal."""
    if field_info.ge is not None and value < field_info.ge:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"ge={field_info.ge}",
            error_msg=f"Value must be greater than or equal to {field_info.ge}",
            env_var_name=env_var_name,
        )

    if field_info.le is not None and value > field_info.le:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"le={field_info.le}",
            error_msg=f"Value must be less than or equal to {field_info.le}",
            env_var_name=env_var_name,
        )

    if field_info.gt is not None and value <= field_info.gt:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"gt={field_info.gt}",
            error_msg=f"Value must be greater than {field_info.gt}",
            env_var_name=env_var_name,
        )

    if field_info.lt is not None and value >= field_info.lt:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"lt={field_info.lt}",
            error_msg=f"Value must be less than {field_info.lt}",
            env_var_name=env_var_name,
        )


def _validate_string(field_name: str, value: str, field_info: FieldInfo, env_var_name: str) -> None:
    """Validate string constraints (min_length, max_length, regex)."""
    if field_info.min_length is not None and len(value) < field_info.min_length:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"min_length={field_info.min_length}",
            error_msg=f"String must be at least {field_info.min_length} characters long",
            env_var_name=env_var_name,
        )

    if field_info.max_length is not None and len(value) > field_info.max_length:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"max_length={field_info.max_length}",
            error_msg=f"String must be at most {field_info.max_length} characters long",
            env_var_name=env_var_name,
        )

    if (
        field_info.regex is not None
        and field_info._compiled_regex is not None
        and not field_info._compiled_regex.match(value)
    ):
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"regex={field_info.regex!r}",
            error_msg=f"String must match pattern: {field_info.regex}",
            env_var_name=env_var_name,
        )


def _validate_choices(
    field_name: str, value: Any, field_info: FieldInfo, env_var_name: str
) -> None:
    """Validate that value is in allowed choices."""
    if field_info.choices is not None and value not in field_info.choices:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"choices={field_info.choices!r}",
            error_msg=f"Value must be one of: {field_info.choices}",
            env_var_name=env_var_name,
        )


def _validate_collection_size(
    field_name: str,
    value: list[Any] | set[Any] | tuple[Any, ...] | dict[Any, Any],
    field_info: FieldInfo,
    env_var_name: str,
) -> None:
    """Validate collection size constraints (min_items, max_items)."""
    collection_size = len(value)

    if field_info.min_items is not None and collection_size < field_info.min_items:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"min_items={field_info.min_items}",
            error_msg=f"Collection must have at least {field_info.min_items} items (got {collection_size})",
            env_var_name=env_var_name,
        )

    if field_info.max_items is not None and collection_size > field_info.max_items:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"max_items={field_info.max_items}",
            error_msg=f"Collection must have at most {field_info.max_items} items (got {collection_size})",
            env_var_name=env_var_name,
        )


def _validate_uuid_version(
    field_name: str, value: UUID, field_info: FieldInfo, env_var_name: str
) -> None:
    """Validate UUID version constraint."""
    if field_info.uuid_version is not None and value.version != field_info.uuid_version:
        raise ConstraintViolationError(
            field_name=field_name,
            value=value,
            constraint=f"uuid_version={field_info.uuid_version}",
            error_msg=f"UUID must be version {field_info.uuid_version} (got version {value.version})",
            env_var_name=env_var_name,
        )
