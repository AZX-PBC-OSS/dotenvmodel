"""Special types for dotenvmodel."""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import ParseResult, unquote, urlparse
from uuid import UUID

from dotenvmodel._redaction import redact_url_password
from dotenvmodel.exceptions import TypeCoercionError

_T = TypeVar("_T")


class SecretStr:
    """A string type that hides its value in logs and repr output.

    Use this for sensitive data like API keys, passwords, and tokens to prevent
    them from appearing in logs, error messages, or debugging output.

    When to use:
        - For API keys, passwords, tokens, and other secrets
        - When config values might be logged or printed
        - When you want to prevent accidental secret exposure in repr/str

    When NOT to use:
        - For non-sensitive values (use `str` instead)
        - When you need to pickle the value (SecretStr prevents pickling for security)

    Security features:
        - Hidden in str/repr output (shows `**********`)
        - Name-mangled attribute to prevent accidental access
        - Prevents pickling to avoid serialization leaks
        - Immutable to prevent modification after creation

    Example:
        ```python
        class Config(DotEnvConfig):
            api_key: SecretStr = Field()
            password: SecretStr = Field(min_length=8)

        config = Config.load()
        print(config.api_key)                    # SecretStr('**********')
        print(repr(config.api_key))              # "SecretStr('**********')"
        print(config.api_key.get_secret_value()) # 'actual-secret-key'
        ```

    See Also:
        - [`Field`][dotenvmodel.fields.Field]: For defining SecretStr fields with constraints.
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
    """Base class for DSN (Data Source Name) types.

    This base class provides common URL validation and parsing functionality
    that can be extended by specific DSN types. You typically don't use this
    directly — use `HttpUrl`, `PostgresDsn`, or `RedisDsn` instead.

    When to subclass:
        - When you need a custom DSN type with specific scheme validation
        - When you need parsed URL components as properties

    Class Attributes:
        allowed_schemes: Tuple of allowed URL schemes (e.g., ("http", "https"))
        require_host: Whether the URL must have a host/netloc component (default True)
        default_port: Default port number when not specified in the URL

    Properties:
        parsed: The `urllib.parse.ParseResult` for the URL
        scheme: URL scheme (e.g., "https")
        host: URL hostname
        port: URL port number (or `default_port` if not specified)
        path: URL path
        query: URL query string
        username: URL username (or None)
        password: URL password, URL-decoded (or None)

    See Also:
        - [`HttpUrl`][dotenvmodel.types.HttpUrl]: For HTTP/HTTPS URLs.
        - [`PostgresDsn`][dotenvmodel.types.PostgresDsn]: For PostgreSQL DSNs.
        - [`RedisDsn`][dotenvmodel.types.RedisDsn]: For Redis DSNs.
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

    def __repr__(self) -> str:
        """Return a display form with any password redacted.

        The instance still behaves as the real connection string for drivers
        (equality, slicing, and property access use the underlying value); only
        the human-facing display hides the password.
        """
        return repr(redact_url_password(str.__str__(self)))

    def __str__(self) -> str:
        """Return a display form with any password redacted."""
        return redact_url_password(str.__str__(self))

    def __format__(self, format_spec: str) -> str:
        """Redact when interpolated (e.g. f-strings, ``%s`` logging)."""
        return format(redact_url_password(str.__str__(self)), format_spec)

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
    """A URL type that validates HTTP/HTTPS URLs.

    Validates that the URL has a valid format and uses http or https scheme.
    Works like a string but provides parsed URL components as properties.

    When to use:
        - For API endpoint URLs
        - For web service URLs
        - When you need to access URL components (host, port, path)

    Allowed schemes: `http`, `https`
    Default port: None (uses port from URL or protocol default)

    Example:
        ```python
        class Config(DotEnvConfig):
            api_url: HttpUrl = Field()
            # Environment: API_URL=https://api.example.com/v1

        config = Config.load()
        print(config.api_url)       # https://api.example.com/v1
        print(config.api_url.host)  # api.example.com
        print(config.api_url.port)  # None (no explicit port)
        print(config.api_url.path)  # /v1
        ```

    See Also:
        - [`BaseDsn`][dotenvmodel.types.BaseDsn]: Base class with all properties.
        - [`PostgresDsn`][dotenvmodel.types.PostgresDsn]: For PostgreSQL DSNs.
        - [`RedisDsn`][dotenvmodel.types.RedisDsn]: For Redis DSNs.
    """

    allowed_schemes = ("http", "https")


class PostgresDsn(BaseDsn):
    """A DSN type for PostgreSQL database URLs.

    Validates that the URL follows PostgreSQL connection string format.
    Accepts both `postgresql://` and `postgres://` schemes.
    Default port is 5432 if not specified in the URL.

    When to use:
        - For PostgreSQL connection strings
        - When you need to extract database name, username, or password

    Allowed schemes: `postgresql`, `postgres`
    Default port: 5432

    Additional Properties:
        database: Database name extracted from the URL path

    Example:
        ```python
        class Config(DotEnvConfig):
            database_url: PostgresDsn = Field()
            # Environment: DATABASE_URL=postgresql://user:pass@localhost:5432/mydb

        config = Config.load()
        print(config.database_url.host)      # localhost
        print(config.database_url.port)      # 5432
        print(config.database_url.database)  # mydb
        print(config.database_url.username)  # user
        print(config.database_url.password)  # pass (URL-decoded)
        ```

    See Also:
        - [`BaseDsn`][dotenvmodel.types.BaseDsn]: Base class with all properties.
        - [`HttpUrl`][dotenvmodel.types.HttpUrl]: For HTTP/HTTPS URLs.
    """

    allowed_schemes = ("postgresql", "postgres")
    default_port = 5432

    @property
    def database(self) -> str:
        """Get the database name from the path."""
        return self.path.lstrip("/") if self.path else ""


class RedisDsn(BaseDsn):
    """A DSN type for Redis URLs.

    Validates that the URL follows Redis connection string format.
    Accepts both `redis://` and `rediss://` (SSL) schemes.
    Default port is 6379 if not specified in the URL.

    When to use:
        - For Redis connection strings
        - When you need to extract the database number

    Allowed schemes: `redis`, `rediss` (SSL)
    Default port: 6379

    Additional Properties:
        database: Redis database number extracted from the URL path (default 0)

    Example:
        ```python
        class Config(DotEnvConfig):
            redis_url: RedisDsn = Field()
            # Environment: REDIS_URL=redis://localhost:6379/0

        config = Config.load()
        print(config.redis_url.host)      # localhost
        print(config.redis_url.port)      # 6379
        print(config.redis_url.database)  # 0
        ```

    See Also:
        - [`BaseDsn`][dotenvmodel.types.BaseDsn]: Base class with all properties.
        - [`PostgresDsn`][dotenvmodel.types.PostgresDsn]: For PostgreSQL DSNs.
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


if TYPE_CHECKING:
    # For type checkers: Json[T] is an alias for T, so config.field has type T
    Json = _T
else:
    # At runtime: Json is a class that supports __class_getitem__ for coercion

    class _JsonMeta(type):
        """Metaclass for Json to properly handle type annotations."""

        def __getitem__(cls, item: type) -> type:
            """Support generic type syntax Json[T].

            At runtime, this returns a class with __inner_type__ for coercion.
            """
            # Create a new class that remembers the inner type for runtime coercion
            new_cls: type = type(f"Json[{item}]", (cls,), {"__inner_type__": item})
            return new_cls

    class Json(metaclass=_JsonMeta):
        """A type for parsing JSON strings into Python objects.

        Use this for complex configuration that needs to be passed as JSON.
        The inner type parameter is used for documentation and basic type validation.

        When to use:
            - For feature flags stored as JSON objects
            - For lists of complex values
            - When a config value is naturally a JSON structure

        When NOT to use:
            - For simple values (use str, int, bool, etc.)
            - For comma-separated lists (use `list[str]` with separator)

        Type Validation:
            - `Json[dict]` validates that the parsed result is a dict
            - `Json[list]` validates that the parsed result is a list
            - Other inner types are accepted but not deeply validated

        Example:
            ```python
            class Config(DotEnvConfig):
                # JSON object
                feature_flags: Json[dict[str, bool]] = Field()
                # Environment: FEATURE_FLAGS={"new_ui": true, "beta_api": false}

                # JSON array
                allowed_roles: Json[list[str]] = Field()
                # Environment: ALLOWED_ROLES=["admin", "user", "guest"]

                # JSON without type validation
                raw_config: Json = Field()
                # Environment: RAW_CONFIG={"nested": {"value": 42}}

            config = Config.load()
            assert config.feature_flags == {"new_ui": True, "beta_api": False}
            assert config.allowed_roles == ["admin", "user", "guest"]
            ```

        See Also:
            - [`Field`][dotenvmodel.fields.Field]: For defining Json fields.
        """

        pass


def parse_timedelta(value: str) -> timedelta:
    """Parse a human-readable duration string into a timedelta.

    When to use:
        - Called automatically when a field is typed as `timedelta`
        - Can be called directly for parsing durations outside of config

    Supports formats like:
        - Plain integers: "90" (seconds)
        - With units: "1h30m", "90s", "1.5h", "2d"
        - Combined: "1d2h30m"

    Units (case-insensitive):
        - ms: milliseconds
        - s: seconds
        - m: minutes
        - h: hours
        - d: days
        - w: weeks

    Args:
        value: Duration string (e.g., "90", "1h30m", "2d")

    Returns:
        timedelta object representing the parsed duration

    Raises:
        ValueError: If the format is invalid

    Example:
        >>> parse_timedelta("90")
        timedelta(seconds=90)
        >>> parse_timedelta("1h30m")
        timedelta(seconds=5400)
        >>> parse_timedelta("2d")
        timedelta(days=2)
        >>> parse_timedelta("500ms")
        timedelta(milliseconds=500)

    See Also:
        - [`coerce_timedelta`][dotenvmodel.types.coerce_timedelta]: Wrapper that raises
          `TypeCoercionError` instead of `ValueError`.
    """
    # Try parsing as plain number (seconds)
    try:
        return timedelta(seconds=float(value))
    except ValueError:
        pass

    # Parse format like "1h30m", "90s", "-30m", etc.
    pattern = r"(-?[\d.]+)(ms|s|m|h|d|w)"
    matches = re.findall(pattern, value.lower())

    if not matches:
        raise ValueError(
            f"Invalid timedelta format: {value}. "
            "Expected format like '90' (seconds), '1h30m', '-30m', '2d', etc."
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
    """Coerce a string to datetime using ISO 8601 format.

    When to use:
        - Called automatically when a field is typed as `datetime`
        - Can be called directly for parsing outside of config

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
    """Coerce a string to timedelta.

    When to use:
        - Called automatically when a field is typed as `timedelta`
        - Can be called directly for parsing outside of config

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
    """Coerce a string to UUID.

    When to use:
        - Called automatically when a field is typed as `UUID`
        - Can be called directly for parsing outside of config

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
    """Coerce a string to Decimal.

    When to use:
        - Called automatically when a field is typed as `Decimal`
        - Can be called directly for parsing outside of config

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
    """Parse JSON string and optionally validate against expected type.

    When to use:
        - Called automatically when a field is typed as `Json[T]`
        - Can be called directly for parsing JSON outside of config

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

    return parsed  # type: ignore[return-value]
