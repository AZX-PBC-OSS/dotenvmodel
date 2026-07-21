"""Edge case tests for real-world adoption scenarios."""

from typing import Any

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.exceptions import ConstraintViolationError


class TestFieldNameEdgeCases:
    """Test field name edge cases."""

    def test_underscore_field_names(self) -> None:
        class Config(DotEnvConfig):
            my_field: str = Field()
            another_value: int = Field(default=42)

        config = Config.load_from_dict({"MY_FIELD": "hello", "ANOTHER_VALUE": "100"})
        assert config.my_field == "hello"
        assert config.another_value == 100

    def test_python_keyword_field_name(self) -> None:
        class Config(DotEnvConfig):
            type: str = Field(default="test")

        config = Config.load_from_dict({"TYPE": "foo"})
        assert config.type == "foo"

    def test_double_underscore_not_private(self) -> None:
        class Config(DotEnvConfig):
            _private: str = Field(default="hidden")
            public: str = Field()

        config = Config.load_from_dict({"PUBLIC": "visible"})
        assert config.public == "visible"
        assert "_private" not in Config.get_fields()


class TestRealWorldScenarios:
    """Test scenarios common in real applications."""

    def test_multiple_configs_shared_env(self) -> None:
        class DBConfig(DotEnvConfig):
            host: str = Field(alias="DATABASE_HOST")

        class AppConfig(DotEnvConfig):
            db_host: str = Field(alias="DATABASE_HOST")

        db = DBConfig.load_from_dict({"DATABASE_HOST": "localhost"})
        app = AppConfig.load_from_dict({"DATABASE_HOST": "localhost"})
        assert db.host == "localhost"
        assert app.db_host == "localhost"

    def test_error_recovery_after_failure(self) -> None:
        class Config(DotEnvConfig):
            port: int = Field(ge=1, le=65535)

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORT": "99999"})

        config = Config.load_from_dict({"PORT": "8080"})
        assert config.port == 8080

    def test_load_with_no_env_vars(self) -> None:
        class Config(DotEnvConfig):
            debug: bool = Field(default=False)
            port: int = Field(default=8000)

        config = Config.load_from_dict({})
        assert config.debug is False
        assert config.port == 8000

    def test_fastapi_style_singleton(self) -> None:
        class Settings(DotEnvConfig):
            app_name: str = Field(default="myapp")
            debug: bool = Field(default=False)
            database_url: str = Field()
            redis_url: str | None = Field(default=None)

        settings = Settings.load_from_dict(
            {
                "DATABASE_URL": "postgresql://localhost/myapp",
            }
        )
        assert settings.app_name == "myapp"
        assert settings.database_url == "postgresql://localhost/myapp"
        assert settings.redis_url is None

    def test_docker_compose_style_config(self) -> None:
        class Config(DotEnvConfig):
            env_prefix = "APP_"
            environment: str = Field(
                default="dev",
                choices=["dev", "test", "staging", "prod"],
            )
            workers: int = Field(default=4, ge=1, le=32)
            max_connections: int = Field(default=100, ge=1)

        config = Config.load_from_dict(
            {
                "APP_ENVIRONMENT": "prod",
                "APP_WORKERS": "8",
            }
        )
        assert config.environment == "prod"
        assert config.workers == 8
        assert config.max_connections == 100

    def test_repr_does_not_crash(self) -> None:
        from dotenvmodel.types import SecretStr

        class Config(DotEnvConfig):
            name: str = Field(default="test")
            secret: SecretStr = Field()
            port: int = Field(default=8000)

        config = Config.load_from_dict({"SECRET": "my-secret-key"})
        r = repr(config)
        assert "my-secret-key" not in r
        assert "**********" in r
        assert "test" in r
        assert "8000" in r

    def test_dict_method_all_types(self) -> None:
        from datetime import datetime
        from decimal import Decimal
        from uuid import UUID

        class Config(DotEnvConfig):
            name: str = Field(default="test")
            port: int = Field(default=8000)
            price: Decimal = Field(default=Decimal("9.99"))
            uid: UUID = Field()
            created: datetime = Field()

        config = Config.load_from_dict(
            {
                "UID": "550e8400-e29b-41d4-a716-446655440000",
                "CREATED": "2025-01-15T10:30:00",
            }
        )
        d = config.dict()
        assert d["name"] == "test"
        assert d["port"] == 8000
        assert d["price"] == Decimal("9.99")
        assert d["uid"] == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert d["created"] == datetime(2025, 1, 15, 10, 30, 0)  # noqa: DTZ001

    def test_large_config(self) -> None:
        namespace: dict[str, Any] = {"DotEnvConfig": DotEnvConfig, "Field": Field}
        fields_str = "\n".join(f"    field_{i}: int = Field(default={i})" for i in range(50))
        code = f"class BigConfig(DotEnvConfig):\n{fields_str}\n"
        exec(code, namespace)
        big_config = namespace["BigConfig"]

        config = big_config.load_from_dict({"FIELD_0": "999", "FIELD_49": "111"})
        assert config.field_0 == 999
        assert config.field_49 == 111
        assert config.field_25 == 25
        assert len(big_config.get_fields()) == 50
