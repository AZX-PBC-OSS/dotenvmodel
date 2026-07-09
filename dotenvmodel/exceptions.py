"""Exception types for dotenvmodel."""

from typing import Any

from typing_extensions import TypeForm

from dotenvmodel._redaction import redact_url_password


def _value_repr(value: Any) -> str:
    """Repr a field value for error messages, redacting URL passwords."""
    if isinstance(value, str):
        return repr(redact_url_password(str.__str__(value)))
    return repr(value)


class DotEnvModelError(Exception):
    """Base exception for all dotenvmodel errors.

    All other dotenvmodel exceptions inherit from this. Catch this if you
    want to handle any dotenvmodel error in a single except block.

    When to catch:
        - When you want to handle all config errors uniformly
        - As a fallback when specific error handling isn't needed

    Example:
        ```python
        try:
            config = AppConfig.load()
        except DotEnvModelError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)
        ```

    See Also:
        - [`ValidationError`][dotenvmodel.exceptions.ValidationError]: For validation failures.
        - [`MissingFieldError`][dotenvmodel.exceptions.MissingFieldError]: For missing required fields.
    """

    pass


class ValidationError(DotEnvModelError):
    """Raised when field validation fails.

    This is the base class for specific validation errors. It's raised
    when a field value fails type coercion or constraint validation.

    When to catch:
        - When you want to handle all validation errors (coercion + constraint)
        - As a parent class for `MissingFieldError`, `TypeCoercionError`,
          and `ConstraintViolationError`

    Attributes:
        field_name: Name of the field that failed validation
        value: The value that failed validation
        error_msg: Human-readable error description
        field_type: The expected type (or None)
        env_var_name: The environment variable name for error messages

    Example:
        ```python
        try:
            config = Config.load_from_dict({"PORT": "abc"})
        except ValidationError as e:
            print(f"Field: {e.field_name}")
            print(f"Error: {e.error_msg}")
        ```

    See Also:
        - [`DotEnvModelError`][dotenvmodel.exceptions.DotEnvModelError]: Base exception.
        - [`TypeCoercionError`][dotenvmodel.exceptions.TypeCoercionError]: Type coercion failures.
        - [`ConstraintViolationError`][dotenvmodel.exceptions.ConstraintViolationError]: Constraint failures.
    """

    def __init__(
        self,
        field_name: str,
        value: Any,
        error_msg: str,
        field_type: TypeForm[Any] | None = None,
        env_var_name: str | None = None,
    ) -> None:
        self.field_name = field_name
        self.value = value
        self.error_msg = error_msg
        self.field_type = field_type
        self.env_var_name = env_var_name or field_name.upper()
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format a detailed error message."""
        msg = f"Field '{self.field_name}' validation failed:\n"
        msg += f"  Value: {_value_repr(self.value)}\n"
        if self.field_type:
            type_name = getattr(self.field_type, "__name__", str(self.field_type))
            msg += f"  Expected type: {type_name}\n"
        msg += f"  Error: {self.error_msg}\n"
        msg += f"  Environment variable: {self.env_var_name}"
        return msg


class MissingFieldError(ValidationError):
    """Raised when a required field is not set.

    This error occurs when a required field has no value in any source
    (environment variables, .env files, or dict).

    When to catch:
        - When you want to provide specific error messages for missing config
        - When you want to show which env vars need to be set

    Attributes:
        field_name: Name of the missing field
        env_var_name: The environment variable name that should be set
        field_type: The expected type (or None)

    Example:
        ```python
        try:
            config = AppConfig.load()
        except MissingFieldError as e:
            print(f"Missing: {e.env_var_name}")
            print(f"Hint: {e}")
        ```

    See Also:
        - [`ValidationError`][dotenvmodel.exceptions.ValidationError]: Parent class.
    """

    def __init__(
        self,
        field_name: str,
        field_type: TypeForm[Any] | None = None,
        env_var_name: str | None = None,
    ) -> None:
        env_name = env_var_name or field_name.upper()
        super().__init__(
            field_name=field_name,
            value=None,
            error_msg="Required field is not set",
            field_type=field_type,
            env_var_name=env_name,
        )

    def _format_message(self) -> str:
        """Format a detailed error message for missing fields."""
        msg = f"MissingFieldError: Required field '{self.field_name}' is not set.\n\n"
        msg += f"Environment variable name: {self.env_var_name}\n"
        if self.field_type:
            type_name = getattr(self.field_type, "__name__", str(self.field_type))
            msg += f"Field type: {type_name}\n"
        msg += f"Hint: Set {self.env_var_name} in your environment or .env file"
        return msg


class TypeCoercionError(ValidationError):
    """Raised when type coercion fails.

    This error occurs when a string value from the environment cannot be
    converted to the field's target type (e.g., "abc" to int).

    When to catch:
        - When you want to show helpful messages for invalid config values
        - When you want to identify which env var has a formatting issue

    Attributes:
        field_name: Name of the field that failed coercion
        value: The string value that couldn't be coerced
        error_msg: Description of why coercion failed
        field_type: The target type
        env_var_name: The environment variable name

    Example:
        ```python
        try:
            config = Config.load_from_dict({"PORT": "abc"})
        except TypeCoercionError as e:
            print(f"{e.env_var_name}: {e.error_msg}")
            # PORT: invalid literal for int() with base 10: 'abc'
        ```

    See Also:
        - [`ValidationError`][dotenvmodel.exceptions.ValidationError]: Parent class.
    """

    def _format_message(self) -> str:
        """Format a detailed error message for type coercion failures."""
        type_name = "unknown"
        if self.field_type:
            type_name = getattr(self.field_type, "__name__", str(self.field_type))
        msg = f"TypeCoercionError: Failed to coerce field '{self.field_name}' to type {type_name}.\n\n"
        msg += f"Value: {_value_repr(self.value)}\n"
        msg += f"Environment variable: {self.env_var_name}\n"
        msg += f"Error: {self.error_msg}\n"
        msg += f"Hint: Ensure {self.env_var_name} contains a valid {type_name}"
        return msg


class ConstraintViolationError(ValidationError):
    """Raised when a validation constraint is violated.

    This error occurs when a value passes type coercion but fails a
    validation constraint (e.g., port > 65535, string too short).

    When to catch:
        - When you want to show which constraint was violated
        - When you want to help users fix invalid config values

    Attributes:
        field_name: Name of the field that violated a constraint
        value: The value that violated the constraint
        constraint: The constraint that was violated (e.g., "ge=1")
        error_msg: Human-readable constraint error
        env_var_name: The environment variable name

    Example:
        ```python
        try:
            config = Config.load_from_dict({"PORT": "99999"})
        except ConstraintViolationError as e:
            print(f"{e.field_name}: {e.constraint} - {e.error_msg}")
            # port: le=65535 - Value must be less than or equal to 65535
        ```

    See Also:
        - [`ValidationError`][dotenvmodel.exceptions.ValidationError]: Parent class.
        - [`Field`][dotenvmodel.fields.Field]: For defining constraints.
    """

    def __init__(
        self,
        field_name: str,
        value: Any,
        constraint: str,
        error_msg: str,
        env_var_name: str | None = None,
    ) -> None:
        self.constraint = constraint
        super().__init__(
            field_name=field_name,
            value=value,
            error_msg=error_msg,
            env_var_name=env_var_name,
        )

    def _format_message(self) -> str:
        """Format a detailed error message for constraint violations."""
        msg = f"ConstraintViolationError: Field '{self.field_name}' violates constraint.\n\n"
        msg += f"Value: {_value_repr(self.value)}\n"
        msg += f"Constraint: {self.constraint}\n"
        msg += f"Error: {self.error_msg}\n"
        msg += f"Hint: Set {self.env_var_name} to a value that satisfies the constraint"
        return msg


class MultipleValidationErrors(DotEnvModelError):
    """Raised when multiple validation errors occur simultaneously.

    When loading a config with multiple invalid fields, all errors are
    collected and raised together in this exception rather than failing
    on the first error.

    When to catch:
        - When you want to show all config errors at once (better UX)
        - When you want to identify all missing/invalid fields in one pass

    Attributes:
        errors: List of `ValidationError` instances (one per failed field)

    Example:
        ```python
        try:
            config = AppConfig.load()
        except MultipleValidationErrors as e:
            for error in e.errors:
                print(f"  - {error.field_name}: {error.error_msg}")
        ```

    See Also:
        - [`ValidationError`][dotenvmodel.exceptions.ValidationError]: Individual errors.
    """

    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = errors
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format a detailed error message for multiple validation errors."""
        msg = f"MultipleValidationErrors: Configuration validation failed with {len(self.errors)} error(s):\n\n"
        for i, error in enumerate(self.errors, 1):
            msg += f"{i}. {error.__class__.__name__}: {error.error_msg}\n"
            msg += f"   Field: {error.field_name}\n"
            if error.value is not None:
                msg += f"   Value: {_value_repr(error.value)}\n"
            msg += f"   Environment variable: {error.env_var_name}\n"
            if hasattr(error, "constraint") and error.constraint is not None:  # type: ignore[attr-defined]
                msg += f"   Constraint: {error.constraint}\n"  # type: ignore[attr-defined]
            msg += "\n"
        return msg.rstrip()
