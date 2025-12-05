# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/AZX-PBC/dotenvmodel/compare/v0.1.0...v0.1.1) (2025-12-05)


### Bug Fixes

* update PyPI publishing workflow configuration ([f854abb](https://github.com/AZX-PBC/dotenvmodel/commit/f854abb08272c51e1a872d4062230f8b2e7d5c21))
* update PyPI publishing workflow configuration ([8c3ed30](https://github.com/AZX-PBC/dotenvmodel/commit/8c3ed301b7aa3fffcffb2343a0f194cce639832a))

## 0.1.0 (2025-12-05)


### Features

* v0.1.0 - Complete type-safe environment configuration library ([#1](https://github.com/AZX-PBC/dotenvmodel/issues/1)) ([7e9b2a9](https://github.com/AZX-PBC/dotenvmodel/commit/7e9b2a9cf01db778b0855df40745eac1d2134de5))

## [0.1.0] - 2025-12-05

### Added

- **Core Configuration System**
  - `DotEnvConfig` base class with metaclass-based field discovery
  - Type-safe field definitions with full IntelliSense support
  - Automatic type coercion for common Python types

- **Type Support**
  - Basic types: `str`, `int`, `float`, `bool`, `Path`
  - Collection types: `list`, `set`, `tuple`, `dict`
  - Special types: `UUID`, `Decimal`, `datetime`, `timedelta`
  - URL/DSN types: `HttpUrl`, `PostgresDsn`, `RedisDsn`
  - Security: `SecretStr` for sensitive values
  - Flexible: `Json[T]` for typed JSON parsing

- **Validation**
  - Numeric constraints: `ge`, `le`, `gt`, `lt`
  - String constraints: `min_length`, `max_length`, `regex`
  - Choice validation
  - Collection size constraints: `min_items`, `max_items`
  - UUID version validation

- **Environment Management**
  - Automatic .env file loading with cascading (`.env`, `.env.{env}`, `.env.{env}.local`)
  - Support for multiple environments (dev, prod, test, staging)
  - Custom .env file locations via `env_dir` parameter
  - Override control with `override` parameter

- **Advanced Features**
  - **Configuration Reload**: `reload()` method to update config at runtime without creating new instances
  - **Environment Prefixes**: Class-level `env_prefix` to namespace environment variables
  - Field aliases for environment variable names
  - Default values and factories
  - Optional fields with proper None handling

- **Developer Experience**
  - Comprehensive error messages with helpful hints
  - Optional logging support for debugging
  - `load_from_dict()` for testing without environment variables
  - Helper methods: `dict()`, `get()`, `__repr__()`

- **Testing & Quality**
  - 315 comprehensive tests
  - 98% code coverage
  - Full type safety with py.typed marker
  - Linting with ruff
  - CI/CD ready configuration

- **Documentation**
  - Comprehensive README with examples
  - Type safety and IntelliSense documentation
  - Complete API documentation
  - Advanced usage patterns and best practices

### Changed

- N/A (initial release)

### Deprecated

- N/A (initial release)

### Removed

- N/A (initial release)

### Fixed

- N/A (initial release)

### Security

- No known security issues

[0.1.0]: https://github.com/azxio/dotenvmodel/releases/tag/v0.1.0
