# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.6.3...v1.0.0) (2026-08-31)


### ⚠ BREAKING CHANGES

* a string default containing ${VAR} text resolves at load time instead of being taken literally; an unset reference yields "" where the raw ${...} text was kept before.
* load()/reload()/cached() no longer mutate os.environ — call python-dotenv load_dotenv() yourself if you relied on injection. override default flipped True -> False; real env vars now beat .env files unless override=True or DOTENV_OVERRIDE=true. load_env_files() removed in favor of read_env_files(), a pure reader returning a DotenvLayer (later file wins, bare keys left unset like load_dotenv()). loaded_with() returns LoadParams instead of a 3-tuple and raises RuntimeError on instances never loaded from the environment. boolean load params are now bool | None with DOTENV_OVERRIDE/DOTENV_READ_DOTFILES/DOTENV_LOAD_LOCAL env-var overrides (unrecognized values warn and fall back to the default). .local files are skipped by default when env is test (case-insensitive) — extending the Next.js/dotenv-flow rule, which skips only .env.local in test, to all .local files, because a gitignored .env.test.local must not decide test outcomes either (load_local=True or DOTENV_LOAD_LOCAL=true restores them).

### Features

* field_validator decorator with before and after modes ([#65](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/65)) ([f50b97d](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/f50b97dd08521f07a50905e3f4ff000483be6bd5))
* interpolate references in string defaults ([#62](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/62)) ([27ec71d](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/27ec71d074e5ce4baebfc51db5f7d9ac4911b362))
* resolve config without mutating os.environ ([#60](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/60)) ([15b6386](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/15b6386fe93b3f6451f6f80c022b5d371aad73e4))


### Bug Fixes

* compare unwrapped secrets against choices ([#63](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/63)) ([c7abdeb](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/c7abdeb1fabeb2a7948b718de28ee9a2d0b7f672))


### Continuous Integration

* pin actions, gate publishing, trim permissions, lock the sdist ([#64](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/64)) ([1c382b3](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/1c382b3eff0e82f2b6c33140bb2753350076c24c))

## [0.6.3](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.6.2...v0.6.3) (2026-07-28)


### Bug Fixes

* reload() must update the instance's recorded load arguments ([#56](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/56)) ([a293461](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/a2934612da52130cc539be65bd1fe196a4381dde))

## [0.6.2](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.6.1...v0.6.2) (2026-07-28)


### Bug Fixes

* warn on cached() argument disagreement, not on non-default args ([#54](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/54)) ([ba80777](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/ba80777e7486797d8a33d27b124b069f90664de6))

## [0.6.1](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.6.0...v0.6.1) (2026-07-27)


### Bug Fixes

* eliminate cross-class reentrancy deadlock in cached() locking ([#52](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/52)) ([592297a](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/592297a1823b2c26b00f974882834e5ace8bc968))

## [0.6.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.5.4...v0.6.0) (2026-07-27)


### Features

* add cached() / reset_cached() / cached_override() singleton accessor ([#51](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/51)) ([638f8cc](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/638f8cc8515398ad983bc321dd906effe4df17f8))


### Continuous Integration

* bump setup-uv to v9.0.0 ([#48](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/48)) ([21bcc4f](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/21bcc4f96d16a1e075d3c59ba3291cb1f9af32d6))

## [0.5.4](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.5.3...v0.5.4) (2026-07-22)


### Continuous Integration

* local self-contained publish workflow with attestations off ([#46](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/46)) ([1f72487](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/1f724876329ef4244c78289d7524254405b4cc10))

## [0.5.3](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.5.2...v0.5.3) (2026-07-22)


### Continuous Integration

* publish via centralized reusable workflow ([#44](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/44)) ([d653161](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/d653161cc426161838580bd0772ebb65b488198f))

## [0.5.2](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.5.1...v0.5.2) (2026-07-22)


### Continuous Integration

* standardize publish workflow on org template (pypa action, conditional attestations) ([#42](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/42)) ([32960d4](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/32960d404867e044b9287644319de805459e15df))

## [0.5.1](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.5.0...v0.5.1) (2026-07-22)


### Continuous Integration

* activate release-please manifest mode; fix stale version seeds ([#40](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/40)) ([91fb40a](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/91fb40acb5a176b8dcb8a269c008f4ca7c5c7219))

## [0.5.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.4.0...v0.5.0) (2026-07-21)


### Features

* add post_load hook for cross-field validation and normalization ([78bcef1](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/78bcef18b90354ea29050f30c8548a193e78c0e3))
* add post_load hook for cross-field validation and normalization ([#39](https://github.com/AZX-PBC-OSS/dotenvmodel/issues/39)) ([39241ed](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/39241ed09ca416c38869076cfe6e22a7c94b2d95))


### Bug Fixes

* mask hook-authored constraint in sensitive validator errors ([6f99371](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/6f99371c5038d60020c68524c05f766d1bfc0ddd))


### Documentation

* correct post_load raise-propagation boundary, document partial reload ([9ec9a00](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/9ec9a00fdfb0e2d455830690489d4c7b5215a92c))
* document post_load cross-field validation hook ([536c981](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/536c981b201d169a219c49af16e45cdd92202443))
* post_load discoverability and secrets-warning scope ([895566e](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/895566e365c1d32952b06d59e4063cf7cf2ace8c))
* qualify post_load claims for validate=False and reload paths ([0786c8d](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/0786c8da115e2d033cad278a97557425ffad4c63))
* qualify post_load raise propagation for nested ValidationError ([40416b6](https://github.com/AZX-PBC-OSS/dotenvmodel/commit/40416b69c15e33b3234fd8ee6531a743589f4e27))

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
