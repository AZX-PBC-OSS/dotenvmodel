"""Tests for advanced type coercion (Path, UUID, Decimal, datetime, timedelta)."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from dotenvmodel import ConstraintViolationError, DotEnvConfig, Field, TypeCoercionError
from dotenvmodel.types import SecretStr


class TestPathType:
    """Test Path type coercion."""

    def test_path_field(self) -> None:
        """Test Path field coercion."""

        class Config(DotEnvConfig):
            config_path: Path = Field()

        config = Config.load_from_dict({"CONFIG_PATH": "/etc/app/config"})
        assert config.config_path == Path("/etc/app/config")
        assert isinstance(config.config_path, Path)

    def test_path_with_default(self) -> None:
        """Test Path field with default."""

        class Config(DotEnvConfig):
            log_dir: Path = Field(default=Path("/var/log"))

        config = Config.load_from_dict({})
        assert config.log_dir == Path("/var/log")

    def test_path_relative(self) -> None:
        """Test relative path."""

        class Config(DotEnvConfig):
            data_dir: Path = Field()

        config = Config.load_from_dict({"DATA_DIR": "data/output"})
        assert config.data_dir == Path("data/output")


class TestUUIDType:
    """Test UUID type coercion."""

    def test_uuid_field(self) -> None:
        """Test UUID field coercion."""

        class Config(DotEnvConfig):
            tenant_id: UUID = Field()

        config = Config.load_from_dict({"TENANT_ID": "550e8400-e29b-41d4-a716-446655440000"})
        assert isinstance(config.tenant_id, UUID)
        assert str(config.tenant_id) == "550e8400-e29b-41d4-a716-446655440000"

    def test_uuid_without_hyphens(self) -> None:
        """Test UUID without hyphens."""

        class Config(DotEnvConfig):
            trace_id: UUID = Field()

        config = Config.load_from_dict({"TRACE_ID": "550e8400e29b41d4a716446655440000"})
        assert isinstance(config.trace_id, UUID)

    def test_uuid_invalid(self) -> None:
        """Test invalid UUID format."""

        class Config(DotEnvConfig):
            id: UUID = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"ID": "not-a-uuid"})

        assert "Invalid UUID format" in str(exc_info.value)

    def test_uuid_version_valid(self) -> None:
        """Test UUID version validation - valid."""

        class Config(DotEnvConfig):
            # UUID v4
            tenant_id: UUID = Field(uuid_version=4)

        # Valid UUID v4
        config = Config.load_from_dict({"TENANT_ID": "550e8400-e29b-41d4-a716-446655440000"})
        assert config.tenant_id.version == 4

    def test_uuid_version_invalid(self) -> None:
        """Test UUID version validation - invalid."""

        class Config(DotEnvConfig):
            # Require UUID v4
            tenant_id: UUID = Field(uuid_version=4)

        # UUID v1
        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TENANT_ID": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"})

        assert "UUID must be version 4" in str(exc_info.value)
        assert "got version 1" in str(exc_info.value)

    def test_uuid_version_v1(self) -> None:
        """Test UUID v1 validation."""

        class Config(DotEnvConfig):
            trace_id: UUID = Field(uuid_version=1)

        config = Config.load_from_dict({"TRACE_ID": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"})
        assert config.trace_id.version == 1

    def test_uuid_version_v3(self) -> None:
        """Test UUID v3 validation."""

        class Config(DotEnvConfig):
            namespace_id: UUID = Field(uuid_version=3)

        config = Config.load_from_dict({"NAMESPACE_ID": "6fa459ea-ee8a-3ca4-894e-db77e160355e"})
        assert config.namespace_id.version == 3

    def test_uuid_version_v5(self) -> None:
        """Test UUID v5 validation."""

        class Config(DotEnvConfig):
            resource_id: UUID = Field(uuid_version=5)

        config = Config.load_from_dict({"RESOURCE_ID": "886313e1-3b8a-5372-9b90-0c9aee199e5d"})
        assert config.resource_id.version == 5

    def test_uuid_without_version_constraint(self) -> None:
        """Test UUID without version constraint accepts any version."""

        class Config(DotEnvConfig):
            any_id: UUID = Field()

        # Should accept any valid UUID
        config = Config.load_from_dict({"ANY_ID": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"})
        assert config.any_id.version == 1

        config = Config.load_from_dict({"ANY_ID": "550e8400-e29b-41d4-a716-446655440000"})
        assert config.any_id.version == 4


class TestDecimalType:
    """Test Decimal type coercion."""

    def test_decimal_field(self) -> None:
        """Test Decimal field coercion."""

        class Config(DotEnvConfig):
            price: Decimal = Field()

        config = Config.load_from_dict({"PRICE": "19.99"})
        assert config.price == Decimal("19.99")
        assert isinstance(config.price, Decimal)

    def test_decimal_precision(self) -> None:
        """Test Decimal maintains precision."""

        class Config(DotEnvConfig):
            tax_rate: Decimal = Field()

        config = Config.load_from_dict({"TAX_RATE": "0.0825"})
        assert config.tax_rate == Decimal("0.0825")
        # Verify no floating point errors
        assert str(config.tax_rate) == "0.0825"

    def test_decimal_with_validation(self) -> None:
        """Test Decimal with numeric validation."""

        class Config(DotEnvConfig):
            discount: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

        config = Config.load_from_dict({"DISCOUNT": "0.15"})
        assert config.discount == Decimal("0.15")

    def test_decimal_invalid(self) -> None:
        """Test invalid Decimal format."""

        class Config(DotEnvConfig):
            amount: Decimal = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"AMOUNT": "not-a-number"})

        assert "Invalid decimal format" in str(exc_info.value)


class TestDatetimeType:
    """Test datetime type coercion."""

    def test_datetime_iso8601(self) -> None:
        """Test datetime parsing with ISO 8601 format."""

        class Config(DotEnvConfig):
            created_at: datetime = Field()

        config = Config.load_from_dict({"CREATED_AT": "2025-01-15T10:30:00"})
        assert isinstance(config.created_at, datetime)
        assert config.created_at.year == 2025
        assert config.created_at.month == 1
        assert config.created_at.day == 15
        assert config.created_at.hour == 10
        assert config.created_at.minute == 30

    def test_datetime_with_timezone(self) -> None:
        """Test datetime with timezone."""

        class Config(DotEnvConfig):
            timestamp: datetime = Field()

        config = Config.load_from_dict({"TIMESTAMP": "2025-01-15T10:30:00+00:00"})
        assert isinstance(config.timestamp, datetime)

    def test_datetime_invalid(self) -> None:
        """Test invalid datetime format."""

        class Config(DotEnvConfig):
            when: datetime = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"WHEN": "not-a-datetime"})

        assert "Invalid datetime format" in str(exc_info.value)


class TestTimedeltaType:
    """Test timedelta type coercion."""

    def test_timedelta_seconds(self) -> None:
        """Test timedelta with plain seconds."""

        class Config(DotEnvConfig):
            timeout: timedelta = Field()

        config = Config.load_from_dict({"TIMEOUT": "30"})
        assert config.timeout == timedelta(seconds=30)

    def test_timedelta_with_units(self) -> None:
        """Test timedelta with units."""

        class Config(DotEnvConfig):
            cache_ttl: timedelta = Field()

        config = Config.load_from_dict({"CACHE_TTL": "1h30m"})
        assert config.cache_ttl == timedelta(hours=1, minutes=30)

    def test_timedelta_days(self) -> None:
        """Test timedelta with days."""

        class Config(DotEnvConfig):
            retention: timedelta = Field()

        config = Config.load_from_dict({"RETENTION": "7d"})
        assert config.retention == timedelta(days=7)

    def test_timedelta_weeks(self) -> None:
        """Test timedelta with weeks."""

        class Config(DotEnvConfig):
            period: timedelta = Field()

        config = Config.load_from_dict({"PERIOD": "2w"})
        assert config.period == timedelta(weeks=2)

    def test_timedelta_milliseconds(self) -> None:
        """Test timedelta with milliseconds."""

        class Config(DotEnvConfig):
            latency: timedelta = Field()

        config = Config.load_from_dict({"LATENCY": "500ms"})
        assert config.latency == timedelta(milliseconds=500)

    def test_timedelta_float_hours(self) -> None:
        """Test timedelta with float hours."""

        class Config(DotEnvConfig):
            duration: timedelta = Field()

        config = Config.load_from_dict({"DURATION": "1.5h"})
        assert config.duration == timedelta(hours=1.5)

    def test_timedelta_invalid(self) -> None:
        """Test invalid timedelta format."""

        class Config(DotEnvConfig):
            wait: timedelta = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"WAIT": "not-a-duration"})

        assert "Invalid timedelta format" in str(exc_info.value)


class TestSecretStrType:
    """Test SecretStr type."""

    def test_secret_str_field(self) -> None:
        """Test SecretStr field."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

        config = Config.load_from_dict({"API_KEY": "secret-key-12345"})
        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "secret-key-12345"

    def test_secret_str_hidden_in_str(self) -> None:
        """Test that SecretStr hides value in str()."""

        class Config(DotEnvConfig):
            password: SecretStr = Field()

        config = Config.load_from_dict({"PASSWORD": "super-secret"})
        assert str(config.password) == "**********"
        assert "super-secret" not in str(config.password)

    def test_secret_str_hidden_in_repr(self) -> None:
        """Test that SecretStr hides value in repr()."""

        class Config(DotEnvConfig):
            token: SecretStr = Field()

        config = Config.load_from_dict({"TOKEN": "my-token"})
        assert repr(config.token) == "SecretStr('**********')"
        assert "my-token" not in repr(config.token)

    def test_secret_str_equality(self) -> None:
        """Test SecretStr equality."""
        secret1 = SecretStr("same-value")
        secret2 = SecretStr("same-value")
        secret3 = SecretStr("different-value")

        assert secret1 == secret2
        assert secret1 != secret3
        assert secret1 != "same-value"  # Not equal to plain string

    def test_secret_str_hashable(self) -> None:
        """Test SecretStr is hashable."""
        secret = SecretStr("my-secret")
        # Should be able to use in sets/dicts
        secret_set = {secret}
        assert secret in secret_set

    def test_secret_str_with_validation(self) -> None:
        """Test SecretStr with min_length validation."""

        class Config(DotEnvConfig):
            jwt_secret: SecretStr = Field(min_length=32)

        # Valid
        config = Config.load_from_dict({"JWT_SECRET": "a" * 32})
        assert len(config.jwt_secret.get_secret_value()) == 32

        # Invalid - too short
        # Note: SecretStr validation happens on the string value before wrapping
        from dotenvmodel import ConstraintViolationError

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"JWT_SECRET": "short"})
