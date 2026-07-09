# Changelog

All notable changes to dotenvmodel are documented in the [CHANGELOG.md](https://github.com/AZX-PBC-OSS/dotenvmodel/blob/main/CHANGELOG.md) file in the repository.

## [0.2.0](https://github.com/AZX-PBC-OSS/dotenvmodel/compare/v0.1.1...v0.2.0)

### Features

- Added `describe()` method for configuration documentation
- Added `generate_env_example()` for `.env.example` file generation
- Added `describe_configs()` for documenting multiple config classes
- Added output formats: table, markdown, json, html, dotenv
- Added file export via `output` parameter
- Added line ending control via `line_ending` parameter

## [0.1.0](https://github.com/AZX-PBC-OSS/dotenvmodel/releases/tag/v0.1.0)

### Features

- `DotEnvConfig` base class with metaclass-based field discovery
- Type-safe field definitions with full IntelliSense support
- Automatic type coercion for common Python types
- Basic types: `str`, `int`, `float`, `bool`, `Path`
- Collection types: `list`, `set`, `tuple`, `dict`
- Special types: `UUID`, `Decimal`, `datetime`, `timedelta`
- URL/DSN types: `HttpUrl`, `PostgresDsn`, `RedisDsn`
- Security: `SecretStr` for sensitive values
- Flexible: `Json[T]` for typed JSON parsing
- Numeric, string, choice, collection, UUID validation constraints
- Automatic `.env` file cascading
- Configuration reload at runtime
- Environment prefixes
- Field aliases
- Comprehensive error messages
- Optional logging support
- `load_from_dict()` for testing
