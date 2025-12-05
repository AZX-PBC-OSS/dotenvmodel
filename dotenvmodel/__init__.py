"""Type-safe environment configuration with automatic .env file loading."""

__version__ = "0.2.0"

from dotenvmodel.config import DotEnvConfig
from dotenvmodel.describe import describe_configs, generate_env_example
from dotenvmodel.exceptions import (
    ConstraintViolationError,
    DotEnvModelError,
    MissingFieldError,
    MultipleValidationErrors,
    TypeCoercionError,
    ValidationError,
)
from dotenvmodel.fields import Field, Required
from dotenvmodel.logging_config import configure_logging, disable_logging
from dotenvmodel.types import (
    HttpUrl,
    Json,
    PostgresDsn,
    RedisDsn,
    SecretStr,
)

__all__ = [
    "ConstraintViolationError",
    "DotEnvConfig",
    "DotEnvModelError",
    "Field",
    "HttpUrl",
    "Json",
    "MissingFieldError",
    "MultipleValidationErrors",
    "PostgresDsn",
    "RedisDsn",
    "Required",
    "SecretStr",
    "TypeCoercionError",
    "ValidationError",
    "__version__",
    "configure_logging",
    "describe_configs",
    "disable_logging",
    "generate_env_example",
]
