"""Environment variable and .env file loading logic."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Module-level logger
logger = logging.getLogger("dotenvmodel")


def load_env_files(
    env: str | None = None,
    *,
    override: bool = True,
    env_dir: Path | None = None,
) -> dict[str, str]:
    """Load environment variables from cascading .env files.

    This function implements Node.js-style .env file cascading, loading files
    in the following order (later files override earlier):
    1. `.env` (base configuration)
    2. `.env.local` (local base overrides)
    3. `.env.{env}` (environment-specific)
    4. `.env.{env}.local` (local environment overrides)

    When to use:
        - Called automatically by `DotEnvConfig.load()` — you rarely call this directly
        - Call directly if you need to load .env files without creating a config

    Args:
        env: Environment name (e.g., "dev", "prod", "test"). If None, reads from
            the `ENV` environment variable, defaults to "dev"
        override: If True, .env file values override existing environment variables.
            If False, existing env vars take precedence
        env_dir: Custom base directory for .env files. If None, uses
            the `DOTENV_DIR` environment variable or current working directory

    Returns:
        Dictionary of all environment variables after loading

    Raises:
        ValueError: If `env` contains invalid characters (only alphanumeric,
            hyphens, and underscores allowed — prevents path traversal)
        FileNotFoundError: If `env_dir` is provided but doesn't exist

    Example:
        ```python
        # Load .env files for dev environment
        env_vars = load_env_files(env="dev", override=True)

        # Use custom directory
        from pathlib import Path
        load_env_files(env="prod", env_dir=Path("/app/config"))
        ```

    See Also:
        - [`DotEnvConfig.load`][dotenvmodel.config.DotEnvConfig.load]: Loads config and .env files.
        - [`get_env_var`][dotenvmodel.loading.get_env_var]: Get a single env var by field name.
    """
    # Determine environment
    if env is None:
        env = os.getenv("ENV", "dev")

    # Validate env parameter to prevent path traversal attacks
    # Only allow alphanumeric characters, hyphens, and underscores
    if not env or not all(c.isalnum() or c in ("-", "_") for c in env):
        raise ValueError(
            f"Invalid environment name: {env!r}. "
            "Environment names must only contain alphanumeric characters, hyphens, and underscores."
        )

    logger.info(f"Loading configuration for environment: {env}")

    # Determine base directory
    if env_dir is None:
        env_dir_str = os.getenv("DOTENV_DIR")
        base_dir = Path(env_dir_str) if env_dir_str else Path.cwd()
    else:
        base_dir = env_dir

    logger.debug(f"Base directory for .env files: {base_dir}")

    # Validate base directory exists
    if not base_dir.exists():
        logger.error(f"Environment file directory does not exist: {base_dir}")
        raise FileNotFoundError(f"Environment file directory does not exist: {base_dir}")

    # Define file loading order
    env_files = [
        base_dir / ".env",  # Base shared configuration
        base_dir / ".env.local",  # Local base overrides
        base_dir / f".env.{env}",  # Environment-specific config
        base_dir / f".env.{env}.local",  # Local environment overrides
    ]

    logger.debug(f"Searching for .env files in order: {[str(f) for f in env_files]}")

    # Load each file in order
    loaded_files = []
    missing_files = []

    for file_path in env_files:
        if file_path.exists():
            logger.info(f"Loading environment variables from {file_path}")
            load_dotenv(file_path, override=override)
            loaded_files.append(str(file_path))
        else:
            logger.debug(f"{file_path} not found (skipping)")
            missing_files.append(str(file_path))

    if loaded_files:
        logger.info(f"Successfully loaded {len(loaded_files)} file(s): {', '.join(loaded_files)}")
    else:
        logger.warning(f"No .env files found in {base_dir}")

    # Return all current environment variables
    return dict(os.environ)


def get_env_var(field_name: str, alias: str | None = None, prefix: str | None = None) -> str | None:
    """Get environment variable value by field name or alias.

    When to use:
        - Called internally by `DotEnvConfig.load()` — rarely called directly
        - Use directly if you need to check a config env var without loading the full config

    Args:
        field_name: Name of the field (converted to UPPER_CASE for env var lookup)
        alias: Optional alias that overrides the field name for env var lookup.
            When provided, `prefix` is NOT applied.
        prefix: Optional class-level prefix to prepend to the env var name.
            Not applied when `alias` is provided.

    Returns:
        Environment variable value as string, or None if not set

    See Also:
        - [`get_env_var_name`][dotenvmodel.loading.get_env_var_name]: Get just the name, not the value.
    """
    # Use alias if provided, otherwise convert field_name to UPPER_CASE
    env_var_name = alias if alias else field_name.upper()

    # Prepend prefix if provided (and alias is not used, since alias is absolute)
    if prefix and not alias:
        env_var_name = f"{prefix}{env_var_name}"

    return os.getenv(env_var_name)


def get_env_var_name(field_name: str, alias: str | None = None, prefix: str | None = None) -> str:
    """Get the environment variable name for a field.

    When to use:
        - For generating documentation or .env.example files
        - For error messages that reference the env var name
        - Called internally during config loading

    Args:
        field_name: Name of the field (converted to UPPER_CASE for env var lookup)
        alias: Optional alias that overrides the field name. When provided,
            `prefix` is NOT applied.
        prefix: Optional class-level prefix to prepend. Not applied when
            `alias` is provided.

    Returns:
        The environment variable name string

    Example:
        ```python
        get_env_var_name("database_url")           # "DATABASE_URL"
        get_env_var_name("host", prefix="DB_")     # "DB_HOST"
        get_env_var_name("dsn", alias="DATABASE")  # "DATABASE" (no prefix)
        ```

    See Also:
        - [`get_env_var`][dotenvmodel.loading.get_env_var]: Get the value, not just the name.
    """
    # Use alias if provided, otherwise convert field_name to UPPER_CASE
    env_var_name = alias if alias else field_name.upper()

    # Prepend prefix if provided (and alias is not used, since alias is absolute)
    if prefix and not alias:
        env_var_name = f"{prefix}{env_var_name}"

    return env_var_name
