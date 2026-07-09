# Validation

dotenvmodel validates field values at load time, catching configuration errors before your application starts. All validation happens once during `load()` — there is zero runtime overhead when accessing fields afterwards.

Constraints are defined as parameters to `Field()`. This page covers every supported constraint with valid and invalid examples.

For the complete API reference, see [Validation API](../api-reference/validation.md).

---

## Numeric Constraints

Numeric constraints apply to `int`, `float`, and `Decimal` fields.

| Parameter | Operator | Description |
|-----------|----------|-------------|
| `ge` | `>=` | Value must be greater than or equal |
| `le` | `<=` | Value must be less than or equal |
| `gt` | `>` | Value must be greater than |
| `lt` | `<` | Value must be less than |

### Examples

```python
from decimal import Decimal
from dotenvmodel import DotEnvConfig, Field

class Config(DotEnvConfig):
    # Greater than or equal (>=)
    min_connections: int = Field(ge=1)

    # Less than or equal (<=)
    max_connections: int = Field(le=100)

    # Greater than (>)
    timeout: float = Field(gt=0)

    # Less than (<)
    percentage: float = Field(lt=100.0)

    # Combined constraints
    port: int = Field(default=8000, ge=1, le=65535)
    pool_size: int = Field(default=10, ge=1, le=100)

    # Works with Decimal too
    tax_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('1'))
```

!!! example "Valid vs Invalid"
    === "Valid"

        ```bash
        # .env
        MIN_CONNECTIONS=5
        MAX_CONNECTIONS=50
        TIMEOUT=30.0
        PERCENTAGE=75.5
        PORT=8000
        ```

        ```python
        config = Config.load()  # All validations pass
        ```

    === "Invalid"

        ```bash
        # .env
        MIN_CONNECTIONS=0    # violates ge=1
        MAX_CONNECTIONS=150  # violates le=100
        TIMEOUT=0            # violates gt=0
        PERCENTAGE=100.0     # violates lt=100.0
        PORT=99999           # violates le=65535
        ```

        ```python
        # Raises ConstraintViolationError:
        # Field 'port' violates constraint.
        # Value: 99999
        # Constraint: le=65535
        # Error: Value must be less than or equal to 65535
        ```

!!! warning "Contradictory constraints"
    `Field()` raises `ValueError` at class definition time if you specify impossible constraints: `ge > le`, `gt >= lt`. This fails fast so you catch the bug immediately, not at runtime.

---

## String Constraints

String constraints apply to `str` and `SecretStr` fields.

| Parameter | Description |
|-----------|-------------|
| `min_length` | Minimum string length (inclusive) |
| `max_length` | Maximum string length (inclusive) |
| `regex` | Regular expression pattern the string must match (uses `re.match`) |

### Examples

```python
from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr

class Config(DotEnvConfig):
    # Minimum length
    api_key: str = Field(min_length=32)

    # Maximum length
    username: str = Field(max_length=20)

    # Regex pattern
    email: str = Field(regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')

    # Combined constraints
    password: str = Field(
        min_length=8,
        max_length=128,
        regex=r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).+$'
    )

    # SecretStr supports the same constraints
    secret: SecretStr = Field(min_length=32)
```

!!! example "Valid vs Invalid"
    === "Valid"

        ```bash
        # .env
        API_KEY=this-is-a-very-long-api-key-with-32+chars
        USERNAME=johndoe
        EMAIL=john.doe@example.com
        PASSWORD=SecurePass123
        ```

        ```python
        config = Config.load()  # All validations pass
        ```

    === "Invalid"

        ```bash
        # .env
        API_KEY=short              # violates min_length=32
        USERNAME=a_very_long_name  # violates max_length=20
        EMAIL=not-an-email         # violates regex pattern
        PASSWORD=weak              # violates min_length=8 and regex
        ```

        ```python
        # Raises ConstraintViolationError:
        # Field 'api_key' violates constraint.
        # Value: "short"
        # Constraint: min_length=32
        # Error: String must be at least 32 characters long
        ```

!!! note "Regex uses `re.match`"
    The `regex` constraint uses `re.match`, which anchors at the **start** of the string. Include `^` and `$` in your pattern to anchor both ends, as shown in the examples above.

---

## Choice Validation

The `choices` parameter restricts a field to a list of allowed values. Validation happens **after** type coercion, so the coerced value must be in the list.

```python
class Config(DotEnvConfig):
    environment: str = Field(
        default="dev",
        choices=["dev", "test", "staging", "prod"],
    )

    log_level: str = Field(
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
```

!!! example "Valid vs Invalid"
    === "Valid"

        ```bash
        # .env
        ENVIRONMENT=staging
        LOG_LEVEL=DEBUG
        ```

        ```python
        config = Config.load()
        assert config.environment == "staging"
        assert config.log_level == "DEBUG"
        ```

    === "Invalid"

        ```bash
        # .env
        ENVIRONMENT=production  # not in choices
        LOG_LEVEL=TRACE         # not in choices
        ```

        ```python
        # Raises ConstraintViolationError:
        # Field 'environment' violates constraint.
        # Value: "production"
        # Constraint: choices=['dev', 'test', 'staging', 'prod']
        # Error: Value must be one of: ['dev', 'test', 'staging', 'prod']
        ```

!!! tip "Choices work with any type"
    `choices` validates after type coercion, so you can use it with `int`, `bool`, or any type. For example: `port: int = Field(default=80, choices=[80, 443, 8080])`.

---

## Collection Size Constraints

The `min_items` and `max_items` parameters constrain the number of items in `list`, `set`, `tuple`, and `dict` fields.

```python
class Config(DotEnvConfig):
    # At least one host required
    allowed_hosts: list[str] = Field(
        default_factory=list,
        min_items=1,
    )

    # At most 10 IPs
    allowed_ips: list[str] = Field(
        default_factory=list,
        max_items=10,
    )

    # Between 1 and 5 tags
    tags: list[str] = Field(
        default_factory=list,
        min_items=1,
        max_items=5,
        separator=";",
    )
```

!!! example "Valid vs Invalid"
    === "Valid"

        ```bash
        # .env
        ALLOWED_HOSTS=localhost,example.com
        ALLOWED_IPS=10.0.0.1,10.0.0.2
        TAGS=web;api;backend
        ```

        ```python
        config = Config.load()  # All validations pass
        ```

    === "Invalid"

        ```bash
        # .env
        ALLOWED_HOSTS=         # empty, violates min_items=1
        ALLOWED_IPS=1.1.1.1,2.2.2.2,3.3.3.3,4.4.4.4,5.5.5.5,6.6.6.6,7.7.7.7,8.8.8.8,9.9.9.9,10.10.10.10,11.11.11.11  # 11 items, violates max_items=10
        TAGS=a;b;c;d;e;f       # 6 items, violates max_items=5
        ```

        ```python
        # Raises ConstraintViolationError:
        # Field 'allowed_hosts' violates constraint.
        # Value: []
        # Constraint: min_items=1
        # Error: Collection must have at least 1 items (got 0)
        ```

---

## UUID Version

The `uuid_version` parameter requires a `UUID` field to be a specific version (`1`, `3`, `4`, or `5`).

```python
from uuid import UUID
from dotenvmodel import DotEnvConfig, Field

class Config(DotEnvConfig):
    # Must be a version 4 UUID
    tenant_id: UUID = Field(uuid_version=4)

    # Must be a version 1 UUID
    request_id: UUID = Field(uuid_version=1)
```

!!! example "Valid vs Invalid"
    === "Valid"

        ```bash
        # .env — version 4 UUID
        TENANT_ID=550e8400-e29b-41d4-a716-446655440000
        ```

        ```python
        config = Config.load()
        assert config.tenant_id.version == 4
        ```

    === "Invalid"

        ```bash
        # .env — this is a version 1 UUID, but field requires version 4
        TENANT_ID=a0eebc99-9c0b-11ee-8e8f-1b4e4d5c6f00
        ```

        ```python
        # Raises ConstraintViolationError:
        # Field 'tenant_id' violates constraint.
        # Value: UUID('a0eebc99-9c0b-11ee-8e8f-1b4e4d5c6f00')
        # Constraint: uuid_version=4
        # Error: UUID must be version 4 (got version 1)
        ```

---

## Combining Constraints

You can combine multiple constraints on a single field. All constraints are checked, and the first violation raises a `ConstraintViolationError`.

```python
class Config(DotEnvConfig):
    # Numeric range + choices
    port: int = Field(default=8000, ge=1, le=65535, choices=[80, 443, 8000, 8080])

    # String length + regex + choices
    env: str = Field(
        default="dev",
        min_length=2,
        max_length=10,
        choices=["dev", "test", "staging", "prod"],
    )

    # Collection size + custom separator
    allowed_origins: list[str] = Field(
        default_factory=list,
        min_items=1,
        max_items=10,
        separator="|",
    )
```

---

## Error Handling

When validation fails, dotenvmodel raises a `ConstraintViolationError` (a subclass of `ValidationError`). If multiple fields fail simultaneously, all errors are collected and raised together as a `MultipleValidationErrors` exception.

```python
from dotenvmodel import (
    DotEnvConfig,
    Field,
    ConstraintViolationError,
    MultipleValidationErrors,
)

class Config(DotEnvConfig):
    port: int = Field(ge=1, le=65535)
    host: str = Field(min_length=3)

try:
    config = Config.load_from_dict({"PORT": "99999", "HOST": "ab"})
except ConstraintViolationError as e:
    print(f"Field: {e.field_name}")
    print(f"Constraint: {e.constraint}")
    print(f"Error: {e.error_msg}")
except MultipleValidationErrors as e:
    for error in e.errors:
        print(f"  - {error.field_name}: {error.error_msg}")
```

See the [Error Handling guide](error-handling.md) for the full exception hierarchy and catching patterns.

---

## See Also

- [Field Definitions](fields.md) — all `Field()` parameters
- [Supported Types](types.md) — which types support which constraints
- [Error Handling](error-handling.md) — exception hierarchy and error messages
- [Validation API](../api-reference/validation.md) — auto-generated API reference
