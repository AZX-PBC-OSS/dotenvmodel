"""Special types for dotenvmodel."""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import ParseResult, unquote, urlparse
from uuid import UUID

from dotenvmodel.exceptions import TypeCoercionError


class SecretStr:
    """
    A string type that hides its value in logs and repr output.

    Use this for sensitive data like API keys, passwords, and tokens to prevent
    them from appearing in logs, error messages, or debugging output.

    Security features:
    - Hidden in str/repr output
    - Name-mangled attribute to prevent accidental access
    - Prevents pickling to avoid serialization leaks
    - Immutable to prevent modification

    Example:
        ```python
        class Config(DotEnvConfig):
            api_key: SecretStr = Field()
            password: SecretStr = Field(min_length=8)

        config = Config.load()
        print(config.api_key)  # SecretStr('**********')
        print(config.api_key.get_secret_value())  # 'actual-secret-key'
        ```
    """

    __slots__ = ("__secret",)

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_SecretStr__secret", value)

    def get_secret_value(self) -> str:
        """Get the actual secret value."""
        return self.__secret  # type: ignore[attr-defined]

    def __str__(self) -> str:
        return "**********"

    def __repr__(self) -> str:
        return "SecretStr('**********')"

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent attribute modification."""
        raise AttributeError("SecretStr is immutable")

    def __delattr__(self, name: str) -> None:
        """Prevent attribute deletion."""
        raise AttributeError("SecretStr is immutable")

    def __reduce__(self) -> tuple:
        """Prevent pickling by raising an error."""
        raise TypeError(
            "SecretStr cannot be pickled for security reasons. "
            "Extract the secret value with get_secret_value() before pickling if needed."
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretStr):
            return self.__secret == other.__secret  # type: ignore[attr-defined]
        return False

    def __hash__(self) -> int:
        return hash(self.__secret)  # type: ignore[attr-defined]


class BaseDsn(str):
    """
    Base class for DSN (Data Source Name) types.

    This base class provides common URL validation and parsing functionality
    that can be extended by specific DSN types.

    Args:
        allowed_schemes: Tuple of allowed URL schemes (e.g., ("http", "https"))
        require_host: Whether the URL must have a host/netloc component
        default_port: Default port number for this DSN type
    """

    # Class attributes that subclasses should override
    allowed_schemes: tuple[str, ...] = ()
    require_host: bool = True
    default_port: int | None = None

    def __new__(cls, value: str) -> "BaseDsn":
        """Validate and create DSN instance."""
        parsed = urlparse(value)

        # Check for scheme
        if not parsed.scheme:
            schemes_str = " or ".join(cls.allowed_schemes)
            raise ValueError(f"URL must have a scheme ({schemes_str})")

        # Validate scheme
        if cls.allowed_schemes and parsed.scheme not in cls.allowed_schemes:
            schemes_str = " or ".join(cls.allowed_schemes)
            raise ValueError(f"URL scheme must be {schemes_str}, got: {parsed.scheme}")

        # Check for host if required
        if cls.require_host and not parsed.netloc:
            raise ValueError("URL must have a host")

        return str.__new__(cls, value)

    @property
    def parsed(self) -> ParseResult:
        """Get the parsed URL components."""
        return urlparse(self)

    @property
    def scheme(self) -> str:
        """Get the URL scheme."""
        return self.parsed.scheme

    @property
    def host(self) -> str:
        """Get the URL host."""
        return self.parsed.hostname or ""

    @property
    def port(self) -> int | None:
        """Get the URL port or default port."""
        return self.parsed.port or self.default_port

    @property
    def path(self) -> str:
        """Get the URL path."""
        return self.parsed.path

    @property
    def query(self) -> str:
        """Get the URL query string."""
        return self.parsed.query

    @property
    def username(self) -> str | None:
        """Get the URL username."""
        return self.parsed.username

    @property
    def password(self) -> str | None:
        """Get the URL password (decoded from percent-encoding)."""
        if self.parsed.password:
            return unquote(self.parsed.password)
        return None


class HttpUrl(BaseDsn):
    """
    A URL type that validates HTTP/HTTPS URLs.

    Validates that the URL has a valid format and uses http or https scheme.

    Example:
        ```python
        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()
            # Environment: API_URL=https://api.example.com/v1
        ```
    """

    allowed_schemes = ("http", "https")


class PostgresDsn(BaseDsn):
    """
    A DSN type for PostgreSQL database URLs.

    Validates that the URL follows PostgreSQL connection string format.
    Accepts both postgresql:// and postgres:// schemes.

    Example:
        ```python
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()
            # Environment: DATABASE_URL=postgresql://user:pass@localhost:5432/db
        ```
    """

    allowed_schemes = ("postgresql", "postgres")
    default_port = 5432

    @property
    def database(self) -> str:
        """Get the database name from the path."""
        return self.path.lstrip("/") if self.path else ""


class RedisDsn(BaseDsn):
    """
    A DSN type for Redis URLs.

    Validates that the URL follows Redis connection string format.
    Accepts both redis:// and rediss:// (SSL) schemes.

    Example:
        ```python
        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()
            # Environment: REDIS_URL=redis://localhost:6379/0
        ```
    """

    allowed_schemes = ("redis", "rediss")
    default_port = 6379

    @property
    def database(self) -> int:
        """Get the Redis database number from the path."""
        if self.path and self.path != "/":
            try:
                return int(self.path.lstrip("/"))
            except ValueError:
                return 0
        return 0


class Json[T]:
    """
    A type for parsing JSON strings into Python objects.

    Use this for complex configuration that needs to be passed as JSON.

    Example:
        ```python
        class Config(DotEnvConfig):
            feature_flags: Json[dict[str, bool]] = Field()
            # Environment: FEATURE_FLAGS={"new_ui": true, "beta_api": false}

            allowed_roles: Json[list[str]] = Field()
            # Environment: ALLOWED_ROLES=["admin", "user", "guest"]
        ```
    """

    def __class_getitem__(cls, item: type[T]) -> type["Json[T]"]:
        """Support generic type syntax Json[T]."""
        # Return a new class that remembers the inner type
        return type(f"Json[{item}]", (Json,), {"__inner_type__": item})


def parse_timedelta(value: str) -> timedelta:
    """
    Parse a human-readable duration string into a timedelta.

    Supports formats like:
    - Plain integers: "90" (seconds)
    - With units: "1h30m", "90s", "1.5h", "2d"

    Units:
    - ms: milliseconds
    - s: seconds
    - m: minutes
    - h: hours
    - d: days
    - w: weeks

    Example:
        >>> parse_timedelta("90")
        timedelta(seconds=90)
        >>> parse_timedelta("1h30m")
        timedelta(seconds=5400)
        >>> parse_timedelta("2d")
        timedelta(days=2)

    Args:
        value: Duration string

    Returns:
        timedelta object

    Raises:
        ValueError: If the format is invalid
    """
    # Try parsing as plain number (seconds)
    try:
        return timedelta(seconds=float(value))
    except ValueError:
        pass

    # Parse format like "1h30m", "90s", etc.
    pattern = r"([\d.]+)(ms|s|m|h|d|w)"
    matches = re.findall(pattern, value.lower())

    if not matches:
        raise ValueError(
            f"Invalid timedelta format: {value}. "
            "Expected format like '90' (seconds), '1h30m', '2d', etc."
        )

    total_seconds = 0.0
    for amount_str, unit in matches:
        amount = float(amount_str)

        if unit == "ms":
            total_seconds += amount / 1000
        elif unit == "s":
            total_seconds += amount
        elif unit == "m":
            total_seconds += amount * 60
        elif unit == "h":
            total_seconds += amount * 3600
        elif unit == "d":
            total_seconds += amount * 86400
        elif unit == "w":
            total_seconds += amount * 604800

    return timedelta(seconds=total_seconds)


def coerce_datetime(value: str, field_name: str, env_var_name: str) -> datetime:
    """
    Coerce a string to datetime using ISO 8601 format.

    Args:
        value: ISO 8601 datetime string
        field_name: Field name for error messages
        env_var_name: Environment variable name for error messages

    Returns:
        datetime object

    Raises:
        TypeCoercionError: If parsing fails
    """
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg=f"Invalid datetime format. Expected ISO 8601 format (e.g., '2025-01-15T10:30:00'). Error: {e}",
            field_type=datetime,
            env_var_name=env_var_name,
        ) from e


def coerce_timedelta(value: str, field_name: str, env_var_name: str) -> timedelta:
    """
    Coerce a string to timedelta.

    Supports:
    - Plain integers: "90" (seconds)
    - Human-readable: "1h30m", "90s", "2d"

    Args:
        value: Duration string
        field_name: Field name for error messages
        env_var_name: Environment variable name for error messages

    Returns:
        timedelta object

    Raises:
        TypeCoercionError: If parsing fails
    """
    try:
        return parse_timedelta(value)
    except ValueError as e:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg=str(e),
            field_type=timedelta,
            env_var_name=env_var_name,
        ) from e


def coerce_uuid(value: str, field_name: str, env_var_name: str) -> UUID:
    """
    Coerce a string to UUID.

    Args:
        value: UUID string (with or without hyphens)
        field_name: Field name for error messages
        env_var_name: Environment variable name for error messages

    Returns:
        UUID object

    Raises:
        TypeCoercionError: If parsing fails
    """
    try:
        return UUID(value)
    except ValueError as e:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg=f"Invalid UUID format. Error: {e}",
            field_type=UUID,
            env_var_name=env_var_name,
        ) from e


def coerce_decimal(value: str, field_name: str, env_var_name: str) -> Decimal:
    """
    Coerce a string to Decimal.

    Args:
        value: Numeric string
        field_name: Field name for error messages
        env_var_name: Environment variable name for error messages

    Returns:
        Decimal object

    Raises:
        TypeCoercionError: If parsing fails
    """
    try:
        return Decimal(value)
    except (ValueError, InvalidOperation) as e:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg=f"Invalid decimal format. Error: {e}",
            field_type=Decimal,
            env_var_name=env_var_name,
        ) from e


def coerce_json[T](
    value: str, field_name: str, env_var_name: str, expected_type: type[T] | None = None
) -> T:
    """
    Parse JSON string and optionally validate against expected type.

    Args:
        value: JSON string
        field_name: Field name for error messages
        env_var_name: Environment variable name for error messages
        expected_type: Optional type to validate against

    Returns:
        Parsed JSON object

    Raises:
        TypeCoercionError: If parsing fails or type doesn't match
    """
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as e:
        raise TypeCoercionError(
            field_name=field_name,
            value=value,
            error_msg=f"Invalid JSON format. Error: {e}",
            field_type=expected_type or dict,
            env_var_name=env_var_name,
        ) from e

    # Basic type validation if expected_type provided
    if expected_type is not None:
        if expected_type is dict and not isinstance(parsed, dict):
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Expected JSON object (dict), got {type(parsed).__name__}",
                field_type=dict,
                env_var_name=env_var_name,
            )
        elif expected_type is list and not isinstance(parsed, list):
            raise TypeCoercionError(
                field_name=field_name,
                value=value,
                error_msg=f"Expected JSON array (list), got {type(parsed).__name__}",
                field_type=list,
                env_var_name=env_var_name,
            )

    return parsed
