"""Tests for field options propagating into collection elements."""

from pathlib import Path

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr


class TestSecretStrInCollections:
    """Test that url_unquote works for SecretStr inside collections."""

    def test_url_unquote_in_list(self) -> None:
        class Config(DotEnvConfig):
            keys: list[SecretStr] = Field(default_factory=list)

        config = Config.load_from_dict({"KEYS": "key%2B1,key%2D2"})
        assert config.keys[0].get_secret_value() == "key+1"
        assert config.keys[1].get_secret_value() == "key-2"

    def test_url_unquote_in_dict_values(self) -> None:
        class Config(DotEnvConfig):
            secrets: dict[str, SecretStr] = Field(default_factory=dict)

        config = Config.load_from_dict({"SECRETS": "key=value%2B1"})
        assert config.secrets["key"].get_secret_value() == "value+1"

    def test_url_unquote_disabled_in_list(self) -> None:
        class Config(DotEnvConfig):
            keys: list[SecretStr] = Field(default_factory=list, url_unquote=False)

        config = Config.load_from_dict({"KEYS": "key%2B1"})
        assert config.keys[0].get_secret_value() == "key%2B1"


class TestPathInCollections:
    """Test that resolve_path works for Path inside collections."""

    def test_resolve_path_in_list(self) -> None:
        class Config(DotEnvConfig):
            paths: list[Path] = Field(default_factory=list)

        config = Config.load_from_dict({"PATHS": "~/logs,/var/log"})
        assert config.paths[0] == Path.home() / "logs"
        assert config.paths[1] == Path("/var/log")

    def test_resolve_path_disabled_in_list(self) -> None:
        class Config(DotEnvConfig):
            paths: list[Path] = Field(default_factory=list, resolve_path=False)

        config = Config.load_from_dict({"PATHS": "~/logs"})
        assert config.paths[0] == Path("~/logs")


class TestListComplexTypes:
    """Test lists of complex types."""

    def test_list_uuid(self) -> None:
        from uuid import UUID

        class Config(DotEnvConfig):
            uuids: list[UUID] = Field(default_factory=list)

        config = Config.load_from_dict(
            {"UUIDS": "550e8400-e29b-41d4-a716-446655440000,660e8400-e29b-41d4-a716-446655440000"}
        )
        assert len(config.uuids) == 2
        assert config.uuids[0] == UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_list_decimal(self) -> None:
        from decimal import Decimal

        class Config(DotEnvConfig):
            prices: list[Decimal] = Field(default_factory=list)

        config = Config.load_from_dict({"PRICES": "1.5,2.5,3.5"})
        assert config.prices == [Decimal("1.5"), Decimal("2.5"), Decimal("3.5")]

    def test_list_datetime(self) -> None:
        from datetime import datetime

        class Config(DotEnvConfig):
            times: list[datetime] = Field(default_factory=list)

        config = Config.load_from_dict({"TIMES": "2025-01-15T10:30:00,2025-06-01T08:00:00"})
        assert config.times[0] == datetime(2025, 1, 15, 10, 30, 0)  # noqa: DTZ001
        assert config.times[1] == datetime(2025, 6, 1, 8, 0, 0)  # noqa: DTZ001

    def test_list_timedelta(self) -> None:
        from datetime import timedelta

        class Config(DotEnvConfig):
            durations: list[timedelta] = Field(default_factory=list)

        config = Config.load_from_dict({"DURATIONS": "1h,30m,90s"})
        assert config.durations[0] == timedelta(hours=1)
        assert config.durations[1] == timedelta(minutes=30)
        assert config.durations[2] == timedelta(seconds=90)


class TestDictComplexTypes:
    """Test dicts with non-string types."""

    def test_dict_str_int(self) -> None:
        class Config(DotEnvConfig):
            ports: dict[str, int] = Field(default_factory=dict)

        config = Config.load_from_dict({"PORTS": "web=8080,api=3000"})
        assert config.ports == {"web": 8080, "api": 3000}

    def test_dict_empty_values(self) -> None:
        class Config(DotEnvConfig):
            headers: dict[str, str] = Field(default_factory=dict)

        config = Config.load_from_dict({"HEADERS": "X-Forwarded-For=,Content-Type=text/html"})
        assert config.headers == {"X-Forwarded-For": "", "Content-Type": "text/html"}


class TestMultipleValidationErrorsSecretMasking:
    """Test that SecretStr values are masked in aggregate error messages."""

    def test_multiple_errors_no_secret_leak(self) -> None:
        class Config(DotEnvConfig):
            key1: SecretStr = Field(min_length=32)
            key2: SecretStr = Field(min_length=32)

        try:
            Config.load_from_dict({"KEY1": "short", "KEY2": "also-short"})
            raise AssertionError("Should have raised")
        except Exception as e:
            msg = str(e)
            assert "short" not in msg
            assert "also-short" not in msg
            assert "**********" in msg
