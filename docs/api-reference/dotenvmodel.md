# Package Overview

The `dotenvmodel` package provides type-safe environment configuration with automatic `.env` file loading.

## Exports

The package exports the following public API:

- [`DotEnvConfig`][dotenvmodel.config.DotEnvConfig]: Base class for configuration
- [`Field`][dotenvmodel.fields.Field]: Define fields with validation and defaults
- [`Required`][dotenvmodel.fields.Required]: Sentinel for required fields
- [`SecretStr`][dotenvmodel.types.SecretStr]: String type that hides secrets in logs
- [`HttpUrl`][dotenvmodel.types.HttpUrl]: HTTP/HTTPS URL type
- [`PostgresDsn`][dotenvmodel.types.PostgresDsn]: PostgreSQL DSN type
- [`RedisDsn`][dotenvmodel.types.RedisDsn]: Redis DSN type
- [`Json`][dotenvmodel.types.Json]: JSON parsing type
- [`describe_configs`][dotenvmodel.describe.describe_configs]: Document multiple configs
- [`generate_env_example`][dotenvmodel.describe.generate_env_example]: Generate .env.example
- [`configure_logging`][dotenvmodel.logging_config.configure_logging]: Enable logging
- [`disable_logging`][dotenvmodel.logging_config.disable_logging]: Disable logging
- [`LOGGER_NAME`][dotenvmodel._constants]: Logger name constant (`"dotenvmodel"`)
- [`DotEnvModelError`][dotenvmodel.exceptions.DotEnvModelError]: Base exception
- [`ValidationError`][dotenvmodel.exceptions.ValidationError]: Validation failure
- [`MissingFieldError`][dotenvmodel.exceptions.MissingFieldError]: Missing required field
- [`TypeCoercionError`][dotenvmodel.exceptions.TypeCoercionError]: Type coercion failure
- [`ConstraintViolationError`][dotenvmodel.exceptions.ConstraintViolationError]: Constraint violation
- [`MultipleValidationErrors`][dotenvmodel.exceptions.MultipleValidationErrors]: Multiple errors

## Module Reference

::: dotenvmodel
