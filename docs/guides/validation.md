# Validation

dotenvmodel validates field values at load time, catching configuration errors before your application starts. All validation happens once during `load()` — there is zero runtime overhead when accessing fields afterwards.

Constraints are defined as parameters to `Field()`. This page covers every supported constraint with valid and invalid examples.

For the complete API reference, see [Validation API](../api-reference/validation.md).

!!! note "Empty vs missing values"
    `Optional[T]` fields map missing **and** empty values to `None` and skip constraints, while plain `str` preserves empty strings as real values. So "validate only if present" is spelled `str | None = Field(default=None, min_length=...)`.

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
| `starts_with` | Required string prefix |
| `ends_with` | Required string suffix |

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

    # Required prefix / suffix
    client_key: str = Field(starts_with="sk-")
    signed_token: str = Field(ends_with=".sig")

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

!!! warning "Use linear-time patterns (ReDoS)"
    `regex` and `strip` with an `re.Pattern` run developer-supplied patterns against env values, which can be operator-controlled. Avoid patterns with nested quantifiers (e.g. `(a+)+`, `(a*)*`) that can cause catastrophic backtracking (ReDoS). Prefer anchored, linear-time patterns.

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

## Custom Validators

For logic the built-in constraints can't express, attach a `validator` hook. It receives the **coerced, built-in-constraint-validated** value plus a `ValidatorContext` (field name and resolved env var name), and its return value becomes the final field value — so a hook can also transform.

```python
from dotenvmodel import DotEnvConfig, Field, SecretStr, ValidatorContext

def check_api_key(value: SecretStr, ctx: ValidatorContext) -> SecretStr:
    # The hook receives the coerced value: a SecretStr stays wrapped,
    # so call get_secret_value() to inspect the plaintext.
    if not value.get_secret_value().startswith("sk-"):
        # ValueError/TypeError are wrapped in ConstraintViolationError and
        # aggregate into MultipleValidationErrors like any other failure
        raise ValueError(f"{ctx.env_var_name} must start with 'sk-'")
    return value

class Config(DotEnvConfig):
    api_key: SecretStr = Field(validator=check_api_key)

    # Transform example: normalize to lowercase
    region: str = Field(default="us-east-1", validator=lambda v, ctx: v.lower())
```

Semantics:

- The hook receives the **coerced** value. A `SecretStr` stays wrapped — use `get_secret_value()` to inspect the plaintext.
- Runs **after** built-in constraints, on non-`None` values only, and even with `validate=False` (transformation is part of loading, not validation).
- Built-in constraints are **not** re-run on a transformed value (pydantic "after"-mode semantics).
- For sensitive fields (`SecretStr`, DSN types), returning a plain `str` re-wraps it in the declared type so the secret stays masked in `repr`.
- Returning `None` on a non-`Optional` field raises `TypeCoercionError`.
- A `ValueError` or `TypeError` from the hook is wrapped in `ConstraintViolationError` with `constraint="validator=<fn name>"`.
- Raise `ConstraintViolationError` directly for a fully custom message on non-sensitive fields (passed through untouched).

!!! warning "Sensitive-field leak prevention"
    For sensitive fields (`SecretStr`, DSN types), **any** exception from the hook is masked to a generic `ConstraintViolationError` with no exception chaining — the hook's exception text is never embedded in the error or its `__cause__`/`__context__` chain, so a carelessly written hook cannot leak the secret or URL password into logs. For non-sensitive fields, `str(e)` is embedded in the error message and the original exception is chained.

---

## Cross-Field Validation with `post_load`

Constraints and per-field `validator` hooks see one value at a time. For invariants that span several fields (`lock_lease >= 4 * heartbeat_interval`) or derived values built from multiple inputs (a replica DSN falling back to the primary), override the model-level `post_load()` hook. It runs **once after all fields load cleanly**, on every load path — `load()`, `load_from_dict()`, `reload()`, and nested config loading — and always runs, even with `validate=False` (transformation is part of loading, same as the per-field `validator` hook). The default implementation is a no-op.

```python
from dotenvmodel import DotEnvConfig, Field, ValidationError

class WorkerConfig(DotEnvConfig):
    primary_dsn: str = Field(default="postgresql://localhost/primary")
    replica_dsn: str | None = Field(default=None)
    heartbeat_interval: int = Field(default=5, ge=1)  # seconds
    lock_lease: int = Field(default=30, ge=1)         # seconds

    def post_load(self) -> list[ValidationError] | None:
        # Fix / transform: derived value — fall back to the primary DSN.
        if self.replica_dsn is None:
            self.replica_dsn = self.primary_dsn

        # Cross-validate: invariant spanning two fields.
        if self.lock_lease < 4 * self.heartbeat_interval:
            return [
                ValidationError(
                    field_name="lock_lease",  # tag the primary field
                    value=self.lock_lease,
                    error_msg="lock_lease must be >= 4 * heartbeat_interval",
                )
            ]
        return None
```

!!! example "Valid vs Invalid"
    === "Valid"

        ```python
        config = WorkerConfig.load_from_dict({})
        # Fallback applied even though no env vars were set:
        assert config.replica_dsn == "postgresql://localhost/primary"
        ```

    === "Invalid"

        ```bash
        # .env — 10 < 4 * 5
        LOCK_LEASE=10
        ```

        ```python
        # Raises ValidationError:
        # Field 'lock_lease' validation failed:
        #   Value: 10
        #   Error: lock_lease must be >= 4 * heartbeat_interval
        #   Environment variable: LOCK_LEASE
        ```

Usage modes (combinable in one body):

| Mode | How | Use for |
|------|-----|---------|
| Fix / transform | Mutate `self`, return `None` | Derived values, fallbacks, normalization |
| Cross-validate | Return `list[ValidationError]` | Invariants spanning multiple fields |
| Continue | Log or swallow issues internally, return `None` | Non-fatal drift you only want to observe |
| Fatal | `raise` | Unexpected/programming errors — an exception that is neither `ValidationError` nor `MultipleValidationErrors` propagates unchanged (never wrapped or aggregated), even from a nested hook |

Semantics:

- Return `None` or `[]` → success. One returned error → raised directly, its exact type preserved (e.g. `ConstraintViolationError`). Several → raised as `MultipleValidationErrors`.
- Returned errors are the same `ValidationError` objects field validation produces, so introspection is uniform: iterating `MultipleValidationErrors.errors` yields `field_name`, `env_var_name`, `value`, and `error_msg` per error, whether the failure came from a constraint, a per-field `validator`, or `post_load`. See [Error Handling](error-handling.md).
- The hook runs **only when every field loaded cleanly** — cross-field checks always see **coerced** values; constraint validation has also been applied unless you loaded with `validate=False` (which skips constraints but still runs the hook). A nested config's hook fires when the nested instance finishes loading, before the parent's hook; its returned errors flatten into the parent's collection. A `ValidationError` or `MultipleValidationErrors` **raised** (rather than returned) by a nested hook is treated the same way — its errors join the parent's collection like nested field failures: a single collected error is re-raised as-is (a solo raised `MultipleValidationErrors` surfaces as its bare member), several aggregate into `MultipleValidationErrors`.
- **Hook-author contract:** tag each returned error with the *primary* field name (`lock_lease` above) and reference the other participating fields in `error_msg`. `env_var_name` defaults to the uppercased field name if not passed.

!!! warning "Keep secrets out of error messages"
    The library redacts the `value` attribute for `SecretStr`/DSN fields when formatting raised errors, but it cannot mask prose you write. Never embed secret values in `error_msg`.

!!! note "When the hook does not run"
    `post_load()` does not run on bare `Cls()` construction (no load path is involved), and it does not run if any field fails to load. On `reload()` the hook re-runs against the freshly reloaded state; if it (or field validation) fails mid-reload, the instance may be **partially reloaded** — the same caveat as field errors during reload.

!!! tip "Pattern lineage"
    The hook follows pydantic's `model_validator(mode="after")` (run after all fields validate; mutate and return `self`) and the zod/t3-env final-schema `.transform()` pattern (one post-hook that can both transform values and accumulate multiple issues).

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
