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
    """
    Load environment variables from cascading .env files.

    This function implements Node.js-style .env file cascading, loading files
    in the following order (later files override earlier):
    1. .env (base configuration)
    2. .env.local (local base overrides)
    3. .env.{env} (environment-specific)
    4. .env.{env}.local (local environment overrides)

    Args:
        env: Environment name (e.g., "dev", "prod", "test"). If None, reads from
            ENV environment variable, defaults to "dev"
        override: If True, .env file values override existing environment variables.
            If False, existing env vars take precedence
        env_dir: Optional custom base directory for .env files. If None, uses
            DOTENV_DIR environment variable or current working directory

    Returns:
        Dictionary of all environment variables after loading

    Example:
        >>> load_env_files(env="dev", override=True)
        {'DATABASE_URL': 'postgresql://localhost/myapp_dev', ...}
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
    """
    Get environment variable value by field name or alias.

    Args:
        field_name: Name of the field
        alias: Optional alias for the environment variable
        prefix: Optional prefix to prepend to the environment variable name

    Returns:
        Environment variable value or None if not set
    """
    # Use alias if provided, otherwise convert field_name to UPPER_CASE
    env_var_name = alias if alias else field_name.upper()

    # Prepend prefix if provided (and alias is not used, since alias is absolute)
    if prefix and not alias:
        env_var_name = f"{prefix}{env_var_name}"

    return os.getenv(env_var_name)


def get_env_var_name(field_name: str, alias: str | None = None, prefix: str | None = None) -> str:
    """
    Get the environment variable name for a field.

    Args:
        field_name: Name of the field
        alias: Optional alias for the environment variable
        prefix: Optional prefix to prepend to the environment variable name

    Returns:
        Environment variable name
    """
    # Use alias if provided, otherwise convert field_name to UPPER_CASE
    env_var_name = alias if alias else field_name.upper()

    # Prepend prefix if provided (and alias is not used, since alias is absolute)
    if prefix and not alias:
        env_var_name = f"{prefix}{env_var_name}"

    return env_var_name
