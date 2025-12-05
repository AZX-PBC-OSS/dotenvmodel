"""Field descriptor and Required sentinel for dotenvmodel."""

import re
from collections.abc import Callable
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
    ) -> None:
        # Validate that only one default mechanism is used
        if default is not _MISSING and default is not ... and default_factory is not None:
            raise ValueError("Cannot specify both 'default' and 'default_factory'")

        # Treat ellipsis as _MISSING (Pydantic-style required indicator)
        if default is ...:
            default = _MISSING

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
        self._compiled_regex = re.compile(regex) if regex else None

        # General constraints
        self.choices = choices

        # Collection constraints
        self.min_items = min_items
        self.max_items = max_items

        # UUID constraints
        self.uuid_version = uuid_version

        # Collection parsing
        self.separator = separator

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
    )
