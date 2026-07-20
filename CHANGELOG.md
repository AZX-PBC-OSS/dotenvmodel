# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.3.2...v0.4.0) (2026-07-20)


### Features

* add strip, starts_with/ends_with, and custom validator hook to Field ([#36](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/36)) ([8e4210e](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/8e4210e80e5888ef0b769bbf966f486c7b4b526e))

## [0.3.2](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.3.1...v0.3.2) (2026-07-15)


### Bug Fixes

* resolve nested DotEnvConfig field defaults not being loaded ([#34](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/34)) ([4a3bb88](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/4a3bb8864dad044977d7b72be41e15307fff8f4d))

## [0.3.1](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.3.0...v0.3.1) (2026-07-13)


### Bug Fixes

* redact credentials in DSN repr, errors, docs, and secret exception chains ([#29](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/29)) ([cfdd218](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/cfdd218ff157d41f7af06c1beaf4c539080fa2dd))

## [0.3.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.2.0...v0.3.0) (2026-07-09)


### Features

* release readiness for public open-source release ([#20](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/20)) ([43937d0](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/43937d06faeb5b687b545daefc4166aa17612a18))

## [0.2.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.1.1...v0.2.0) (2025-12-05)


### Features

* add describe functionality for configuration classes and related tests ([#6](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/6)) ([49767ea](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/49767ea34e8216706a0071072cb92452890451f3))

## [0.1.1](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.1.0...v0.1.1) (2025-12-05)


### Bug Fixes

* update PyPI publishing workflow configuration ([f854abb](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/f854abb08272c51e1a872d4062230f8b2e7d5c21))
* update PyPI publishing workflow configuration ([8c3ed30](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/8c3ed301b7aa3fffcffb2343a0f194cce639832a))

## 0.1.0 (2025-12-05)


### Features

* v0.1.0 - Complete type-safe environment configuration library ([#1](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/1)) ([7e9b2a9](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/7e9b2a9cf01db778b0855df40745eac1d2134de5))

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

[0.1.0]: https://github.com/AZX-PBC-OSS/dotenvmodel/releases/tag/v0.1.0
