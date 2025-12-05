"""Field descriptor and Required sentinel for dotenvmodel."""

import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any, TypeVar

# Type variable for generic field types
T = TypeVar("T")


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


class FieldInfo:
    """
    Information about a configuration field.

    This class holds all metadata about a field including its default value,
    validation constraints, and documentation.
    """

    def __init__(
        self,
        default: Any = _MISSING,
        *,
        default_factory: Callable[[], Any] | None = None,
        alias: str | None = None,
        description: str | None = None,
        # Numeric validation
        ge: int | float | None = None,
        le: int | float | None = None,
        gt: int | float | None = None,
        lt: int | float | None = None,
        # String validation
        min_length: int | None = None,
        max_length: int | None = None,
        regex: str | None = None,
        # General validation
        choices: list[Any] | None = None,
        # Collection validation
        min_items: int | None = None,
        max_items: int | None = None,
        # UUID validation
        uuid_version: int | None = None,
        # Collection parsing
        separator: str = ",",
        # SecretStr options
        url_unquote: bool = True,
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

        # General constraints
        self.choices = choices

        # Collection constraints
        self.min_items = min_items
        self.max_items = max_items

        # UUID constraints
        self.uuid_version = uuid_version

        # Collection parsing
        self.separator = separator

        # SecretStr options
        self.url_unquote = url_unquote

        # Mark if field is required
        self.required = default is _MISSING and default_factory is None

    def get_default(self) -> Any:
        """Get the default value for this field."""
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is _MISSING:
            return _MISSING
        return self.default

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
        if self.choices is not None:
            parts.append(f"choices={self.choices!r}")
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
    ge: int | float | None = None,
    le: int | float | None = None,
    gt: int | float | None = None,
    lt: int | float | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    regex: str | None = None,
    choices: list[Any] | None = None,
    min_items: int | None = None,
    max_items: int | None = None,
    uuid_version: int | None = None,
    separator: str = ",",
    url_unquote: bool = True,
) -> Any:
    """
    Define a configuration field with validation and default values.

    Args:
        default: Default value if environment variable not set
        default_factory: Callable that returns default value (for mutable defaults)
        alias: Alternative environment variable name to read from
        description: Human-readable description for documentation
        ge: Greater than or equal to (>=)
        le: Less than or equal to (<=)
        gt: Greater than (>)
        lt: Less than (<)
        min_length: Minimum string length
        max_length: Maximum string length
        regex: Regular expression pattern to match
        choices: List of allowed values
        min_items: Minimum number of items in collection (list, set, tuple, dict)
        max_items: Maximum number of items in collection (list, set, tuple, dict)
        uuid_version: Required UUID version (1, 3, 4, or 5)
        separator: Separator for list/set/tuple parsing (default: ",")

    Returns:
        FieldInfo instance containing field metadata

    Example:
        ```python
        class Config(DotEnvConfig):
            # Required field (no default)
            database_url: str = Field()

            # Optional with default
            debug: bool = Field(default=False)

            # With validation
            port: int = Field(default=8000, ge=1, le=65535)

            # With alias
            postgres_dsn: str = Field(alias="DATABASE_URL")

            # List with custom separator
            tags: list[str] = Field(default_factory=list, separator=";")

            # Collection size constraints
            allowed_ips: list[str] = Field(min_items=1, max_items=10)

            # UUID version constraint
            tenant_id: UUID = Field(uuid_version=4)
        ```
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
        choices=choices,
        min_items=min_items,
        max_items=max_items,
        uuid_version=uuid_version,
        separator=separator,
        url_unquote=url_unquote,
    )
