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
    - `field_validator`: Decorator attaching custom validation/transformation
      hooks to fields by name, before or after type coercion
    - `DotEnvConfig.post_load`: Model-level hook for cross-field validation
      and normalization after loading
    - `DotEnvConfig.cached` / `DotEnvConfig.reset_cached` / `DotEnvConfig.cached_override`:
      Process-wide thread-safe singleton accessor, its reset, and a scoped
      self-restoring override for test isolation
    - `SecretStr`: String type that hides values in logs
    - `HttpUrl`, `PostgresDsn`, `RedisDsn`: URL/DSN types with validation
    - `Json`: Type for parsing JSON strings
    - `LoadParams`: Frozen record of resolved load parameters (env, override,
      env_dir, read_dotfiles, read_environ, load_local), as returned by
      `DotEnvConfig.loaded_with()`
    - `read_env_files`: Read the merged .env cascade without touching the
      process environment
    - `DotenvLayer`: The merged-cascade record (values, base_dir, files)
      returned by `read_env_files()`
    - `describe_configs`: Generate docs for multiple config classes
    - `generate_env_example`: Generate .env.example files
    - `configure_logging`, `disable_logging`: Logging utilities
    - `DotEnvModelError`, `ValidationError`, `MissingFieldError`,
      `TypeCoercionError`, `ConstraintViolationError`, `MultipleValidationErrors`:
      Exception hierarchy
"""

__version__ = "1.1.0"  # x-release-please-version
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
from dotenvmodel.fields import Field, Required, ValidatorContext, field_validator
from dotenvmodel.loading import DotenvLayer, LoadParams, read_env_files
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
    "DotenvLayer",
    "Field",
    "HttpUrl",
    "Json",
    "LoadParams",
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
    "field_validator",
    "generate_env_example",
    "read_env_files",
]
