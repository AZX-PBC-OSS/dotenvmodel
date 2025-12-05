"""Exception types for dotenvmodel."""

from typing import Any


class DotEnvModelError(Exception):
    """Base exception for all dotenvmodel errors."""

    pass


class ValidationError(DotEnvModelError):
    """Raised when field validation fails."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        error_msg: str,
        field_type: type | None = None,
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
        msg += f"  Value: {self.value!r}\n"
        if self.field_type:
            msg += f"  Expected type: {self.field_type.__name__}\n"
        msg += f"  Error: {self.error_msg}\n"
        msg += f"  Environment variable: {self.env_var_name}"
        return msg


class MissingFieldError(ValidationError):
    """Raised when a required field is missing."""

    def __init__(
        self, field_name: str, field_type: type | None = None, env_var_name: str | None = None
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
    """Raised when type coercion fails."""

    def _format_message(self) -> str:
        """Format a detailed error message for type coercion failures."""
        type_name = "unknown"
        if self.field_type:
            type_name = getattr(self.field_type, "__name__", str(self.field_type))
        msg = f"TypeCoercionError: Failed to coerce field '{self.field_name}' to type {type_name}.\n\n"
        msg += f"Value: {self.value!r}\n"
        msg += f"Environment variable: {self.env_var_name}\n"
        msg += f"Error: {self.error_msg}\n"
        msg += f"Hint: Ensure {self.env_var_name} contains a valid {type_name}"
        return msg


class ConstraintViolationError(ValidationError):
    """Raised when a validation constraint is violated."""

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
        msg += f"Value: {self.value!r}\n"
        msg += f"Constraint: {self.constraint}\n"
        msg += f"Error: {self.error_msg}\n"
        msg += f"Hint: Set {self.env_var_name} to a value that satisfies the constraint"
        return msg


class MultipleValidationErrors(DotEnvModelError):
    """Raised when multiple validation errors occur."""

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
                msg += f"   Value: {error.value!r}\n"
            msg += f"   Environment variable: {error.env_var_name}\n"
            if hasattr(error, "constraint"):
                msg += f"   Constraint: {error.constraint}\n"
            msg += "\n"
        return msg.rstrip()
