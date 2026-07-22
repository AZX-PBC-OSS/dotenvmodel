"""Type-safe environment configuration with automatic .env file loading.

dotenvmodel combines Pydantic-style field definitions with intelligent .env
file cascading inspired by Node.js dotenv patterns.

Quick Start:
    ```python
    from dotenvmodel import DotEnvConfig, Field

    class AppConfig(DotEnvConfig):
        database_url: str = Field()
        port: int = Field(default=8000, ge=1, le=65535)
        debug: bool = Field(default=False)

    config = AppConfig.load(env="dev")
    print(config.port)  # 8000
    ```

Public API:
    - `DotEnvConfig`: Base class for type-safe configuration
    - `Field`: Define fields with defaults, validation, and aliases
    - `Required`: Sentinel for required fields (alternative to `Field()`)
    - `ValidatorContext`: Context passed to `Field(validator=...)` hooks
    - `DotEnvConfig.post_load`: Model-level hook for cross-field validation
      and normalization after loading
    - `SecretStr`: String type that hides values in logs
    - `HttpUrl`, `PostgresDsn`, `RedisDsn`: URL/DSN types with validation
    - `Json`: Type for parsing JSON strings
    - `describe_configs`: Generate docs for multiple config classes
    - `generate_env_example`: Generate .env.example files
    - `configure_logging`, `disable_logging`: Logging utilities
    - `DotEnvModelError`, `ValidationError`, `MissingFieldError`,
      `TypeCoercionError`, `ConstraintViolationError`, `MultipleValidationErrors`:
      Exception hierarchy
"""

__version__ = "0.5.3"  # x-release-please-version
__author__ = "AZX, PBC."
__email__ = "oss@azx.io"
__license__ = "MIT"
__url__ = "https://github.com/AZX-PBC-OSS/dotenvmodel"

from dotenvmodel._constants import LOGGER_NAME
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
from dotenvmodel.fields import Field, Required, ValidatorContext
from dotenvmodel.logging_config import configure_logging, disable_logging
from dotenvmodel.types import (
    HttpUrl,
    Json,
    PostgresDsn,
    RedisDsn,
    SecretStr,
)

__all__ = [
    "LOGGER_NAME",
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
    "ValidatorContext",
    "__version__",
    "configure_logging",
    "describe_configs",
    "disable_logging",
    "generate_env_example",
]
