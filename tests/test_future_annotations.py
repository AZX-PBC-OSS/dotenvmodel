from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr


class TestFutureAnnotations:
    """Test that dotenvmodel works with `from __future__ import annotations` (PEP 563)."""

    def test_basic_types_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(default="test")
            port: int = Field(default=8000)
            debug: bool = Field(default=False)
            timeout: float = Field(default=30.0)

        config = Config.load_from_dict({"name": "app", "port": "9000", "debug": "true"})
        assert config.name == "app"
        assert config.port == 9000
        assert config.debug is True
        assert config.timeout == 30.0

    def test_required_field_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            api_key: str = Field()

        config = Config.load_from_dict({"API_KEY": "secret123"})
        assert config.api_key == "secret123"

    def test_optional_types_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            optional_value: str | None = Field()
            optional_port: int | None = Field()

        config = Config.load_from_dict({})
        assert config.optional_value is None
        assert config.optional_port is None

        config2 = Config.load_from_dict({"OPTIONAL_VALUE": "hello", "OPTIONAL_PORT": "8080"})
        assert config2.optional_value == "hello"
        assert config2.optional_port == 8080

    def test_collection_types_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=list)
            ports: list[int] = Field(default_factory=list)

        config = Config.load_from_dict({"HOSTS": "a,b,c", "PORTS": "1,2,3"})
        assert config.hosts == ["a", "b", "c"]
        assert config.ports == [1, 2, 3]

    def test_advanced_types_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            uid: UUID = Field()
            price: Decimal = Field()
            created: datetime = Field()
            ttl: timedelta = Field()
            path: Path = Field(default=Path("/tmp"))
            secret: SecretStr = Field()

        config = Config.load_from_dict(
            {
                "UID": "550e8400-e29b-41d4-a716-446655440000",
                "PRICE": "19.99",
                "CREATED": "2025-01-15T10:30:00",
                "TTL": "1h30m",
                "SECRET": "my-secret",
            }
        )
        assert config.uid == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert config.price == Decimal("19.99")
        assert config.created == datetime(2025, 1, 15, 10, 30, 0)  # noqa: DTZ001
        assert config.ttl == timedelta(hours=1, minutes=30)
        assert config.path == Path("/tmp")
        assert config.secret.get_secret_value() == "my-secret"

    def test_validation_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            port: int = Field(default=8000, ge=1, le=65535)
            name: str = Field(min_length=3)

        config = Config.load_from_dict({"PORT": "3000", "NAME": "hello"})
        assert config.port == 3000
        assert config.name == "hello"

    def test_env_prefix_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            env_prefix = "APP_"
            host: str = Field()
            port: int = Field(default=8000)

        config = Config.load_from_dict({"APP_HOST": "localhost", "APP_PORT": "9000"})
        assert config.host == "localhost"
        assert config.port == 9000

    def test_alias_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            db_url: str = Field(alias="DATABASE_URL")

        config = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost/db"})
        assert config.db_url == "postgresql://localhost/db"

    def test_inheritance_with_future_annotations(self) -> None:
        class BaseConfig(DotEnvConfig):
            debug: bool = Field(default=False)

        class ChildConfig(BaseConfig):
            port: int = Field(default=8000)

        config = ChildConfig.load_from_dict({"DEBUG": "true", "PORT": "9000"})
        assert config.debug is True
        assert config.port == 9000

    def test_describe_with_future_annotations(self) -> None:
        class Config(DotEnvConfig):
            port: int = Field(default=8000, ge=1, le=65535, description="Server port")
            debug: bool = Field(default=False, description="Debug mode")

        table = Config.describe()
        assert "PORT" in table
        assert "int" in table
        assert "DEBUG" in table
        assert "bool" in table

    def test_reload_with_future_annotations(self) -> None:
        import os

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        os.environ["PORT"] = "9000"
        config = Config.load()
        assert config.port == 9000

        os.environ["PORT"] = "7000"
        config.reload()
        assert config.port == 7000

        del os.environ["PORT"]
