"""DotEnvConfig base class for configuration management."""

import builtins
import logging
from pathlib import Path
from typing import Any, Literal, Self

from dotenvmodel._constants import LOGGER_NAME
from dotenvmodel.coercion import coerce_value
from dotenvmodel.exceptions import (
    MissingFieldError,
    MultipleValidationErrors,
    ValidationError,
)
from dotenvmodel.fields import FieldInfo
from dotenvmodel.loading import get_env_var, get_env_var_name, load_env_files
from dotenvmodel.metaclass import ConfigMeta
from dotenvmodel.validation import validate_field

logger = logging.getLogger(LOGGER_NAME)


class DotEnvConfig(metaclass=ConfigMeta):
    """Base class for type-safe environment configuration.

    Subclass this to define your configuration schema using type annotations
    and `Field()` descriptors. The metaclass automatically discovers fields,
    and `load()` reads from environment variables and `.env` files.

    When to use:
        - When you need type-safe configuration from environment variables
        - When you want automatic `.env` file loading with cascading
        - When you need validation constraints on config values
        - When you want IDE autocomplete and type checker support for config

    When NOT to use:
        - If you need configuration from YAML/TOML/JSON files (this library
          is specifically for environment variables and `.env` files)
        - If you need non-optional Union types (e.g., `str | int`)

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

    See Also:
        - [`Field`][dotenvmodel.fields.Field]: For defining field constraints and defaults.
        - [`load`][dotenvmodel.config.DotEnvConfig.load]: For loading from environment.
        - [`load_from_dict`][dotenvmodel.config.DotEnvConfig.load_from_dict]: For testing.
    """

    _fields: builtins.dict[str, tuple[type, FieldInfo]]
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

    def _load_fields(
        self,
        env_source: dict[str, str] | None,
        *,
        validate: bool = True,
    ) -> None:
        """Process all fields from the given source, setting attributes on self.

        Args:
            env_source: If None, reads from environment variables. If a dict,
                reads from the dict (for load_from_dict / testing).
            validate: Whether to perform validation (default True).

        Raises:
            ValidationError: If any field fails validation. Collects all errors
                and raises them together.
        """
        cls = self.__class__
        prefix = getattr(cls, "env_prefix", "")
        errors: list[ValidationError] = []

        for field_name, (field_type, field_info) in cls._fields.items():
            env_var_name = get_env_var_name(field_name, field_info.alias, prefix)

            if env_source is not None:
                raw_value = env_source.get(env_var_name)
                if raw_value is None:
                    raw_value = env_source.get(field_name)
            else:
                raw_value = get_env_var(field_name, field_info.alias, prefix)

            try:
                value = self._process_field(
                    field_name,
                    field_type,
                    field_info,
                    raw_value,
                    env_var_name,
                    validate=validate,
                )
                setattr(self, field_name, value)
            except ValidationError as e:
                errors.append(e)

        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise MultipleValidationErrors(errors)

    @classmethod
    def load(
        cls,
        env: str | None = None,
        *,
        override: bool = True,
        env_dir: Path | None = None,
    ) -> Self:
        """Load configuration from environment variables and .env files.

        When to use:
            - In application startup to load config from the environment
            - When you want automatic `.env` file cascading
            - When you need validated, type-safe configuration

        When NOT to use:
            - In tests: use `load_from_dict()` instead for deterministic test data
            - If you already have values in a dict: use `load_from_dict()`

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, reads from
                the `ENV` environment variable, defaults to "dev"
            override: If True, .env file values override existing environment variables.
                If False, existing env vars take precedence over .env files
            env_dir: Custom base directory for .env files. If None, uses
                the `DOTENV_DIR` environment variable or current working directory

        Returns:
            Instance of the config class with all fields populated and validated

        Raises:
            MissingFieldError: If a required field is not set in any source
            TypeCoercionError: If a value cannot be coerced to the field type
            ConstraintViolationError: If a value fails validation constraints
            MultipleValidationErrors: If multiple fields fail validation simultaneously
            FileNotFoundError: If `env_dir` is provided but doesn't exist
            ValueError: If `env` contains invalid characters (path traversal protection)

        Example:
            ```python
            # Auto-detect environment from ENV variable
            config = Config.load()

            # Explicit environment
            config = Config.load(env="prod")

            # Don't override existing env vars
            config = Config.load(override=False)

            # Custom .env file location
            from pathlib import Path
            config = Config.load(env_dir=Path("/app/config"))
            ```

        See Also:
            - [`reload`][dotenvmodel.config.DotEnvConfig.reload]: Reload after env changes.
            - [`load_from_dict`][dotenvmodel.config.DotEnvConfig.load_from_dict]: For testing.
        """
        logger.info(f"Loading {cls.__name__} configuration")

        load_env_files(env=env, override=override, env_dir=env_dir)

        instance = cls()
        logger.debug(f"Processing {len(cls._fields)} field(s)")

        instance._load_fields(None)

        logger.info(f"{cls.__name__} configuration loaded successfully")
        logger.debug(f"Loaded fields: {', '.join(cls._fields.keys())}")

        instance._loaded = True
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
        """Reload configuration from environment variables and .env files.

        This method reloads all fields from the environment, allowing you to
        pick up changes to environment variables or .env files without creating
        a new instance.

        When to use:
            - After receiving a SIGHUP signal to hot-reload configuration
            - After programmatically changing environment variables
            - When switching environments at runtime (e.g., dev to prod)

        By default, this uses the same parameters (env, override, env_dir) that
        were used during the original `load()` call. You can override any of these
        by passing new values.

        Args:
            env: Environment name (e.g., "dev", "prod", "test"). If None, uses
                the env from the original load() call
            override: If True, .env file values override existing environment variables.
                If False, existing env vars take precedence. If None, uses the
                override value from the original load() call
            env_dir: Custom base directory for .env files. If None, uses
                the env_dir from the original load() call

        Returns:
            Self (the same instance with reloaded values, useful for method chaining)

        Raises:
            MissingFieldError: If a required field is not set after reload
            TypeCoercionError: If a value cannot be coerced after reload
            ConstraintViolationError: If a value fails validation after reload
            MultipleValidationErrors: If multiple fields fail after reload

        Example:
            ```python
            config = AppConfig.load(env="dev", override=True)

            # ... later, environment variables change ...
            import os
            os.environ["PORT"] = "9000"

            # Reload picks up the new value
            config.reload()
            print(config.port)  # 9000

            # Or reload with different parameters
            config.reload(env="prod")  # Switch to prod environment
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: Initial loading.
        """
        logger.info(f"Reloading {self.__class__.__name__} configuration")

        reload_env = env if env is not None else self._load_env
        reload_override = override if override is not None else self._load_override
        reload_env_dir = env_dir if env_dir is not None else self._load_env_dir

        load_env_files(env=reload_env, override=reload_override, env_dir=reload_env_dir)

        logger.debug(f"Reloading {len(self._fields)} field(s)")
        self._load_fields(None)

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
        """Load configuration from a dictionary (useful for testing).

        When to use:
            - In unit tests for deterministic, isolated config loading
            - When you have config values from a non-env source (e.g., a database)
            - When you want to bypass .env file loading entirely

        When NOT to use:
            - In production: use `load()` to read from environment and .env files

        Args:
            data: Dictionary mapping environment variable names (or field names) to
                string values. Keys can be either the env var name (e.g., "DATABASE_URL")
                or the field name (e.g., "database_url") — env var names take precedence
            validate: Whether to perform validation (default True). Set to False
                to skip validation for performance or testing edge cases

        Returns:
            Instance of the config class with all fields populated

        Raises:
            MissingFieldError: If a required field is missing from the dict
            TypeCoercionError: If a value cannot be coerced to the field type
            ConstraintViolationError: If a value fails validation constraints
            MultipleValidationErrors: If multiple fields fail validation simultaneously

        Example:
            ```python
            config = Config.load_from_dict({
                "DATABASE_URL": "postgresql://localhost/db",
                "DEBUG": "true",
                "PORT": "8000",
            })

            # Skip validation
            config = Config.load_from_dict(data, validate=False)
            ```

        See Also:
            - [`load`][dotenvmodel.config.DotEnvConfig.load]: For production loading.
        """
        instance = cls()
        instance._load_fields(data, validate=validate)
        instance._loaded = True
        return instance

    def dict(self) -> dict[str, Any]:
        """Return configuration as a dictionary with actual values.

        Returns:
            Dictionary mapping field names to their current values

        Example:
            ```python
            config = Config.load()
            print(config.dict())
            # {'database_url': 'postgresql://...', 'debug': True, 'port': 8000}
            ```

        See Also:
            - [`get`][dotenvmodel.config.DotEnvConfig.get]: Get a single value with default.
        """
        result = {}
        for field_name in self._fields:
            if hasattr(self, field_name):
                result[field_name] = getattr(self, field_name)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key with optional default.

        Args:
            key: Field name to look up
            default: Default value if field not found (default None)

        Returns:
            Field value if the field exists and is set, otherwise the default value

        Example:
            ```python
            timeout = config.get('timeout', 30)  # Returns 30 if timeout not set
            ```

        See Also:
            - [`dict`][dotenvmodel.config.DotEnvConfig.dict]: Get all values as dict.
        """
        return getattr(self, key, default)

    def __repr__(self) -> str:
        field_strs = []
        for field_name in self._fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                field_strs.append(f"{field_name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(field_strs)})"

    @classmethod
    def get_fields(cls) -> builtins.dict[str, tuple[type, FieldInfo]]:
        """Get all fields defined on this configuration class.

        Returns a copy of the fields dictionary to prevent external modification.

        Returns:
            Dictionary mapping field names to tuples of (type, FieldInfo)

        Example:
            ```python
            fields = AppConfig.get_fields()
            for name, (field_type, field_info) in fields.items():
                print(f"{name}: {field_type}, required={field_info.required}")
            ```

        See Also:
            - [`FieldInfo`][dotenvmodel.fields.FieldInfo]: Field metadata class.
        """
        return cls._fields.copy()

    @classmethod
    def describe(
        cls,
        output_format: Literal["table", "markdown", "json", "html", "dotenv"] = "table",
        output: str | Path | None = None,
        line_ending: str | None = None,
    ) -> str:
        """
        Generate documentation describing this configuration class.

        Shows all environment variables, their types, whether they're required,
        default values, descriptions, and validation constraints.

        Args:
            output_format: Output format - "table" (ASCII), "markdown", "json", "html", or "dotenv"
            output: Optional file path to save the output to
            line_ending: Line ending to use (e.g., "\\n", "\\r\\n", "\\r").
                If None, uses platform default (os.linesep)

        Returns:
            Formatted string describing the configuration

        Example:
            ```python
            class AppConfig(DotEnvConfig):
                port: int = Field(default=8000, ge=1, le=65535, description="Server port")
                debug: bool = Field(default=False, description="Enable debug mode")

            # Print to console
            print(AppConfig.describe())

            # Save markdown to file
            AppConfig.describe(output_format="markdown", output="docs/config.md")

            # Generate .env.example
            AppConfig.describe(output_format="dotenv", output=".env.example")

            # Use Unix line endings regardless of platform
            AppConfig.describe(output_format="markdown", line_ending="\\n")

            # Use Windows line endings
            AppConfig.describe(output_format="markdown", line_ending="\\r\\n")
            ```
        """
        from dotenvmodel.describe import describe_single

        return describe_single(
            cls, output_format=output_format, output=output, line_ending=line_ending
        )

    @classmethod
    def generate_env_example(
        cls,
        output: str | Path | None = None,
    ) -> str:
        """
        Generate a .env.example file for onboarding new developers.

        This creates a template file showing all environment variables with:
        - Comments describing each field
        - Type and constraint information
        - Example values
        - Required vs optional fields

        Args:
            output: Optional file path to save the .env.example to (e.g., ".env.example")

        Returns:
            .env.example file content

        Example:
            ```python
            class AppConfig(DotEnvConfig):
                port: int = Field(default=8000, ge=1, le=65535, description="Server port")
                api_key: str = Field(description="API key for external service")
                debug: bool = Field(default=False, description="Enable debug mode")

            # Generate and save .env.example
            AppConfig.generate_env_example(output=".env.example")

            # Or print to console
            print(AppConfig.generate_env_example())

            # Output:
            # # Configuration for AppConfig
            #
            # # Server port
            # # Type: int | Constraints: ge=1, le=65535
            # # Example: PORT=8000
            # # PORT=8000
            #
            # # API key for external service
            # # Type: str
            # # Example: API_KEY=your_value_here
            # API_KEY=
            # ...
            ```
        """
        from dotenvmodel.describe import generate_env_example

        return generate_env_example(cls, output=output)
