# Error Handling

dotenvmodel provides a structured exception hierarchy with clear, actionable error messages. This guide covers each exception type, catching patterns, and how to display all errors at once.

## Exception Hierarchy

All dotenvmodel exceptions inherit from `DotEnvModelError`:

```text
DotEnvModelError (base)
├── ValidationError
│   ├── MissingFieldError
│   ├── TypeCoercionError
│   └── ConstraintViolationError
└── MultipleValidationErrors
```

- **`DotEnvModelError`** — Base exception for all dotenvmodel errors
- **`ValidationError`** — Base class for all validation failures (coercion + constraints)
- **`MissingFieldError`** — A required field is not set
- **`TypeCoercionError`** — A value cannot be converted to the target type
- **`ConstraintViolationError`** — A value fails a validation constraint
- **`MultipleValidationErrors`** — Multiple fields failed validation simultaneously

## MissingFieldError

Raised when a required field has no value in any source (environment variables, `.env` files, or dict).

```python
from dotenvmodel import DotEnvConfig, Field, MissingFieldError

class AppConfig(DotEnvConfig):
    api_key: str = Field()
    database_url: str = Field()

try:
    config = AppConfig.load()
except MissingFieldError as e:
    print(e)
```

!!! example "Error Output"

    ```text
    MissingFieldError: Required field 'api_key' is not set.

    Environment variable name: API_KEY
    Field type: str
    Hint: Set API_KEY in your environment or .env file
    ```

### Useful Attributes

| Attribute | Description |
|-----------|-------------|
| `field_name` | Name of the missing field |
| `env_var_name` | The environment variable name that should be set |
| `field_type` | The expected type (or `None`) |

## TypeCoercionError

Raised when a string value from the environment cannot be converted to the field's target type.

```python
from dotenvmodel import DotEnvConfig, Field, TypeCoercionError

class AppConfig(DotEnvConfig):
    port: int = Field(default=8000)

try:
    config = AppConfig.load_from_dict({"PORT": "abc"})
except TypeCoercionError as e:
    print(e)
```

!!! example "Error Output"

    ```text
    TypeCoercionError: Failed to coerce field 'port' to type int.

    Value: "abc"
    Environment variable: PORT
    Error: invalid literal for int() with base 10: 'abc'
    Hint: Ensure PORT contains a valid int
    ```

### Useful Attributes

| Attribute | Description |
|-----------|-------------|
| `field_name` | Name of the field that failed coercion |
| `value` | The string value that couldn't be coerced |
| `error_msg` | Description of why coercion failed |
| `field_type` | The target type |
| `env_var_name` | The environment variable name |

## ConstraintViolationError

Raised when a value passes type coercion but fails a validation constraint (e.g., port out of range, string too short).

```python
from dotenvmodel import DotEnvConfig, Field, ConstraintViolationError

class AppConfig(DotEnvConfig):
    port: int = Field(default=8000, ge=1, le=65535)

try:
    config = AppConfig.load_from_dict({"PORT": "99999"})
except ConstraintViolationError as e:
    print(e)
```

!!! example "Error Output"

    ```text
    ConstraintViolationError: Field 'port' violates constraint.

    Value: 99999
    Constraint: le=65535
    Error: Value must be less than or equal to 65535
    Hint: Set PORT to a value that satisfies the constraint
    ```

### Useful Attributes

| Attribute | Description |
|-----------|-------------|
| `field_name` | Name of the field that violated a constraint |
| `value` | The value that violated the constraint |
| `constraint` | The constraint that was violated (e.g., `"le=65535"`) |
| `error_msg` | Human-readable constraint error |
| `env_var_name` | The environment variable name |

## MultipleValidationErrors

When multiple fields fail validation, all errors are collected and raised together rather than failing on the first error. This provides a better developer experience by showing all problems at once.

```python
from dotenvmodel import DotEnvConfig, Field, MultipleValidationErrors

class AppConfig(DotEnvConfig):
    api_key: str = Field(min_length=32)
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=16)

try:
    config = AppConfig.load_from_dict({
        "API_KEY": "too-short",
        "PORT": "99999",
        "WORKERS": "0",
    })
except MultipleValidationErrors as e:
    for error in e.errors:
        print(f"  - {error.field_name}: {error.error_msg}")
```

!!! example "Error Output"

    ```text
    MultipleValidationErrors: Configuration validation failed with 3 error(s):

    1. ConstraintViolationError: String length 9 is less than minimum 32
       Field: api_key
       Value: 'too-short'
       Environment variable: API_KEY
       Constraint: min_length=32

    2. ConstraintViolationError: Value must be less than or equal to 65535
       Field: port
       Value: 99999
       Environment variable: PORT
       Constraint: le=65535

    3. ConstraintViolationError: Value must be greater than or equal to 1
       Field: workers
       Value: 0
       Environment variable: WORKERS
       Constraint: ge=1
    ```

### Useful Attributes

| Attribute | Description |
|-----------|-------------|
| `errors` | List of `ValidationError` instances (one per failed field) |

## Catching Patterns

### Catch Specific Exceptions

Catch individual exception types when you want different handling for different error kinds:

```python
from dotenvmodel import (
    DotEnvConfig, Field,
    MissingFieldError, TypeCoercionError, ConstraintViolationError,
)

try:
    config = AppConfig.load()
except MissingFieldError as e:
    print(f"Missing: {e.env_var_name}")
    print(f"Hint: {e}")
    sys.exit(1)
except TypeCoercionError as e:
    print(f"Invalid type for {e.env_var_name}: {e.error_msg}")
    sys.exit(1)
except ConstraintViolationError as e:
    print(f"Constraint failed for {e.field_name}: {e.constraint}")
    sys.exit(1)
```

### Catch All Validation Errors

Catch `ValidationError` to handle all validation failures (missing, coercion, constraint) uniformly:

```python
from dotenvmodel import DotEnvConfig, Field, ValidationError

try:
    config = AppConfig.load()
except ValidationError as e:
    print(f"Config error in {e.field_name}: {e.error_msg}")
    sys.exit(1)
```

### Catch All dotenvmodel Errors

Catch `DotEnvModelError` to handle any dotenvmodel error, including `MultipleValidationErrors`:

```python
from dotenvmodel import DotEnvConfig, Field, DotEnvModelError

try:
    config = AppConfig.load()
except DotEnvModelError as e:
    print(f"Configuration error: {e}")
    sys.exit(1)
```

!!! tip "Catching order"

    When using multiple `except` blocks, order matters. Always catch specific exceptions before general ones:

    ```python
    except MissingFieldError:      # Most specific
    except TypeCoercionError:      # Specific
    except ConstraintViolationError:  # Specific
    except ValidationError:        # General validation
    except DotEnvModelError:       # Most general (catches MultipleValidationErrors too)
    ```

### Handling MultipleValidationErrors

When you want to show all errors at once, catch `MultipleValidationErrors`:

```python
from dotenvmodel import DotEnvConfig, Field, MultipleValidationErrors

try:
    config = AppConfig.load()
except MultipleValidationErrors as e:
    print(f"Configuration failed with {len(e.errors)} error(s):\n")
    for error in e.errors:
        print(f"  - {error.field_name} ({error.env_var_name}): {error.error_msg}")
    sys.exit(1)
```

!!! note "MultipleValidationErrors vs individual errors"

    dotenvmodel collects all validation errors and raises `MultipleValidationErrors` when more than one field fails. If only one field fails, the specific exception (`MissingFieldError`, `TypeCoercionError`, or `ConstraintViolationError`) is raised directly.

## See Also

- [Exceptions API Reference](../api-reference/exceptions.md) — Full exception class hierarchy and attributes
- [Validation](validation.md) — Defining constraints that trigger `ConstraintViolationError`
- [Field Definitions](fields.md) — `Field()` parameters for required fields and constraints
