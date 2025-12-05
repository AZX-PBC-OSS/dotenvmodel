"""DotEnvConfig base class for configuration management."""

import logging
from pathlib import Path
from typing import Any, Self, get_args, get_origin, get_type_hints

from dotenvmodel.coercion import coerce_value
from dotenvmodel.exceptions import (
    MissingFieldError,
    MultipleValidationErrors,
    ValidationError,
)
from dotenvmodel.fields import _MISSING, FieldInfo, _RequiredSentinel
from dotenvmodel.loading import get_env_var, get_env_var_name, load_env_files
from dotenvmodel.validation import validate_field

# Module-level logger
logger = logging.getLogger("dotenvmodel")


def _is_optional_type(field_type: type) -> bool:
    """Check if a type is Optional (Union with None)."""
    origin = get_origin(field_type)
    # For Union types (including str | None syntax which creates UnionType)
    if origin is not None:
        args = get_args(field_type)
        # Check if None is one of the union members
        return type(None) in args
    return False


class ConfigMeta(type):
    """Metaclass for DotEnvConfig that discovers field definitions."""

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        # Inherit fields from parent classes
        fields: dict[str, tuple[type, FieldInfo]] = {}
        for base in bases:
            if hasattr(base, "_fields"):
                # Copy parent fields
                fields.update(base._fields)  # type: ignore[arg-type]

        # Get type hints for the class
        hints = namespace.get("__annotations__", {})

        # Discover fields from class attributes (can override parent fields)
        for field_name, field_type in hints.items():
            # Skip private attributes
            if field_name.startswith("_"):
                continue

            # Skip class-level configuration attributes (not config fields)
            if field_name == "env_prefix":
                continue

            # Get the field value from namespace
            field_value = namespace.get(field_name, _MISSING)

            # Handle different field value types
            if isinstance(field_value, FieldInfo):
                field_info = field_value
                # If field is Optional and has no default, default to None
                if (
                    field_info.default is _MISSING
                    and field_info.default_factory is None
                    and _is_optional_type(field_type)
                ):
                    field_info.default = None
                    field_info.required = False  # Update required flag
            elif isinstance(field_value, _RequiredSentinel):
                # User used Required sentinel
                field_info = FieldInfo()
            elif field_value is _MISSING:
                # No default provided
                if _is_optional_type(field_type):
                    # Optional types default to None
                    field_info = FieldInfo(default=None)
                else:
                    # Non-optional types are required
                    field_info = FieldInfo()
            elif field_value is ...:
                # Ellipsis means required
                field_info = FieldInfo()
            else:
                # Regular default value
                field_info = FieldInfo(default=field_value)

            fields[field_name] = (field_type, field_info)

            # Remove field from namespace to avoid conflicts
            namespace.pop(field_name, None)

        # Store fields in the class
        namespace["_fields"] = fields

        return super().__new__(mcs, name, bases, namespace)


class DotEnvConfig(metaclass=ConfigMeta):
    """
    Base class for type-safe environment configuration.

    Subclass this to define your configuration schema using type annotations
    and Field descriptors.

    Example:
        ```python
        class AppConfig(DotEnvConfig):
            # Required fields
            database_url: str = Field()
            api_key: str = Required

            # Optional with defaults
            debug: bool = Field(default=False)
            port: int = Field(default=8000, ge=1, le=65535)

            # With validation
            pool_size: int = Field(default=10, ge=1, le=100)

        # Load configuration
        config = AppConfig.load(env="dev")
        print(config.database_url)
        ```
    """

    _fields: dict[str, tuple[type, FieldInfo]]
    _loaded: bool = False
    _load_env: str | None = None  # Store the env used during load
    _load_override: bool = True  # Store the override flag used during load
    _load_env_dir: Path | None = None  # Store the env_dir used during load
    env_prefix: str = ""  # Class-level prefix for environment variables (default: no prefix)

    def _process_field(
        self,
        field_name: str,
        field_type: type,
        field_info: FieldInfo,
        raw_value: str | None,
        env_var_name: str,
        *,
        validate: bool = True,
    ) -> Any:
        """
        Process a single field: handle missing values, coerce, and validate.

        Args:
            field_name: Name of the field
            field_type: Type annotation for the field
            field_info: Field metadata
            raw_value: Raw string value from environment (or None)
            env_var_name: Environment variable name for error messages
            validate: Whether to perform validation (default: True)

        Returns:
            Processed and validated value

        Raises:
            MissingFieldError: If required field is missing
            ValidationError: If validation fails
        """
        # Handle missing values
        if raw_value is None:
            if field_info.required:
                raise MissingFieldError(
                    field_name=field_name,
                    field_type=field_type,
                    env_var_name=env_var_name,
                )
            else:
                value = field_info.get_default()
        else:
            # Coerce the string value to the target type
            value = coerce_value(field_name, raw_value, field_type, env_var_name, field_info)

            # Check if coercion resulted in None for a required field
            if value is None and field_info.required:
                raise MissingFieldError(
                    field_name=field_name,
                    field_type=field_type,
                    env_var_name=env_var_name,
                )

        # Validate the value (whether from default or coerced)
        if validate:
            validate_field(field_name, value, field_info, env_var_name)

        return value

    @classmethod
    def load(
        cls,
        env: str | None = None,
        *,
        override: bool = True,
        env_dir: Path | None = None,
    ) -> Self:
        """
        Load configuration from environment variables and .env files.

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, reads from
                ENV environment variable, defaults to "dev"
            override: If True, .env file values override existing environment variables.
                If False, existing env vars take precedence
            env_dir: Optional custom base directory for .env files

        Returns:
            Instance of the config class with all fields populated and validated

        Raises:
            ValidationError: If required fields are missing or validation fails
            FileNotFoundError: If custom env_dir path doesn't exist

        Example:
            ```python
            # Auto-detect environment from ENV variable
            config = Config.load()

            # Explicit environment
            config = Config.load(env="prod")

            # Don't override existing env vars
            config = Config.load(override=False)

            # Custom .env file location
            config = Config.load(env_dir=Path("/app/config"))
            ```
        """
        logger.info(f"Loading {cls.__name__} configuration")

        # Load .env files first
        load_env_files(env=env, override=override, env_dir=env_dir)

        # Create instance and load fields
        instance = cls()
        errors: list[ValidationError] = []

        # Get type hints for the class
        get_type_hints(cls)

        logger.debug(f"Processing {len(cls._fields)} field(s)")

        # Get the class prefix (if any)
        prefix = getattr(cls, "env_prefix", "")

        # Process each field
        for field_name, (field_type, field_info) in cls._fields.items():
            env_var_name = get_env_var_name(field_name, field_info.alias, prefix)
            raw_value = get_env_var(field_name, field_info.alias, prefix)

            try:
                value = instance._process_field(
                    field_name, field_type, field_info, raw_value, env_var_name
                )
                setattr(instance, field_name, value)
            except ValidationError as e:
                errors.append(e)

        # If there were validation errors, raise them
        if errors:
            logger.error(f"Configuration loading failed with {len(errors)} error(s)")
            if len(errors) == 1:
                raise errors[0]
            else:
                raise MultipleValidationErrors(errors)

        logger.info(f"{cls.__name__} configuration loaded successfully")
        logger.debug(f"Loaded fields: {', '.join(cls._fields.keys())}")

        instance._loaded = True
        # Store load parameters for reload()
        instance._load_env = env
        instance._load_override = override
        instance._load_env_dir = env_dir
        return instance

    def reload(
        self,
        env: str | None = None,
        *,
        override: bool | None = None,
        env_dir: Path | None = None,
    ) -> Self:
        """
        Reload configuration from environment variables and .env files.

        This method reloads all fields from the environment, allowing you to
        pick up changes to environment variables or .env files without creating
        a new instance.

        By default, this uses the same parameters (env, override, env_dir) that
        were used during the original load() call. You can override any of these
        by passing new values.

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, uses
                the env from the original load() call
            override: If True, .env file values override existing environment variables.
                If False, existing env vars take precedence. If None, uses the
                override value from the original load() call
            env_dir: Optional custom base directory for .env files. If None, uses
                the env_dir from the original load() call

        Returns:
            Self (the same instance with reloaded values)

        Raises:
            ValidationError: If required fields are missing or validation fails
            FileNotFoundError: If custom env_dir path doesn't exist

        Example:
            ```python
            config = AppConfig.load(env="dev", override=True)

            # ... later, environment variables change ...

            config.reload()  # Reloads with env="dev", override=True

            # Or reload with different parameters
            config.reload(env="prod")  # Switch to prod environment
            ```
        """
        logger.info(f"Reloading {self.__class__.__name__} configuration")

        # Use stored parameters if not explicitly provided
        reload_env = env if env is not None else self._load_env
        reload_override = override if override is not None else self._load_override
        reload_env_dir = env_dir if env_dir is not None else self._load_env_dir

        # Load .env files first
        load_env_files(env=reload_env, override=reload_override, env_dir=reload_env_dir)

        errors: list[ValidationError] = []

        # Get type hints for the class
        get_type_hints(self.__class__)

        logger.debug(f"Reloading {len(self._fields)} field(s)")

        # Get the class prefix (if any)
        prefix = getattr(self.__class__, "env_prefix", "")

        # Process each field
        for field_name, (field_type, field_info) in self._fields.items():
            env_var_name = get_env_var_name(field_name, field_info.alias, prefix)
            raw_value = get_env_var(field_name, field_info.alias, prefix)

            try:
                value = self._process_field(
                    field_name, field_type, field_info, raw_value, env_var_name
                )
                setattr(self, field_name, value)
            except ValidationError as e:
                errors.append(e)

        # If there were validation errors, raise them
        if errors:
            logger.error(f"Configuration reload failed with {len(errors)} error(s)")
            if len(errors) == 1:
                raise errors[0]
            else:
                raise MultipleValidationErrors(errors)

        logger.info(f"{self.__class__.__name__} configuration reloaded successfully")
        logger.debug(f"Reloaded fields: {', '.join(self._fields.keys())}")

        return self

    @classmethod
    def load_from_dict(
        cls,
        data: dict[str, str],
        *,
        validate: bool = True,
    ) -> Self:
        """
        Load configuration from a dictionary (useful for testing).

        Args:
            data: Dictionary mapping field names (or aliases) to string values
            validate: Whether to perform validation (default True)

        Returns:
            Instance of the config class

        Raises:
            ValidationError: If validation fails

        Example:
            ```python
            config = Config.load_from_dict({
                "DATABASE_URL": "postgresql://localhost/db",
                "DEBUG": "true",
                "PORT": "8000",
            })
            ```
        """
        instance = cls()
        errors: list[ValidationError] = []

        # Get type hints for the class
        get_type_hints(cls)

        # Get the class prefix (if any)
        prefix = getattr(cls, "env_prefix", "")

        # Process each field
        for field_name, (field_type, field_info) in cls._fields.items():
            env_var_name = get_env_var_name(field_name, field_info.alias, prefix)

            # Try to get value from dict using env var name or field name
            raw_value = data.get(env_var_name)
            if raw_value is None:
                raw_value = data.get(field_name)

            try:
                value = instance._process_field(
                    field_name,
                    field_type,
                    field_info,
                    raw_value,
                    env_var_name,
                    validate=validate,
                )
                setattr(instance, field_name, value)
            except ValidationError as e:
                errors.append(e)

        # If there were validation errors, raise them
        if errors:
            if len(errors) == 1:
                raise errors[0]
            else:
                raise MultipleValidationErrors(errors)

        instance._loaded = True
        return instance

    def dict(self) -> dict[str, Any]:
        """
        Return configuration as a dictionary with actual values.

        Returns:
            Dictionary mapping field names to their values

        Example:
            ```python
            config = Config.load()
            print(config.dict())
            # {'database_url': 'postgresql://...', 'debug': True, 'port': 8000}
            ```
        """
        result = {}
        for field_name in self._fields:
            if hasattr(self, field_name):
                result[field_name] = getattr(self, field_name)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key with optional default.

        Args:
            key: Field name
            default: Default value if field not found

        Returns:
            Field value or default

        Example:
            ```python
            timeout = config.get('timeout', 30)
            ```
        """
        return getattr(self, key, default)

    def __repr__(self) -> str:
        field_strs = []
        for field_name in self._fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                field_strs.append(f"{field_name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(field_strs)})"
