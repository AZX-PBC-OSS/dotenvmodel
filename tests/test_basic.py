"""Basic tests for dotenvmodel."""

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    MissingFieldError,
    Required,
    TypeCoercionError,
)


class TestBasicTypes:
    """Test basic type coercion."""

    def test_string_field(self) -> None:
        """Test string field coercion."""

        class Config(DotEnvConfig):
            name: str = Field()

        config = Config.load_from_dict({"NAME": "test"})
        assert config.name == "test"

    def test_int_field(self) -> None:
        """Test integer field coercion."""

        class Config(DotEnvConfig):
            port: int = Field()

        config = Config.load_from_dict({"PORT": "8000"})
        assert config.port == 8000
        assert isinstance(config.port, int)

    def test_float_field(self) -> None:
        """Test float field coercion."""

        class Config(DotEnvConfig):
            timeout: float = Field()

        config = Config.load_from_dict({"TIMEOUT": "30.5"})
        assert config.timeout == 30.5
        assert isinstance(config.timeout, float)

    def test_bool_field_true(self) -> None:
        """Test boolean field coercion for true values."""

        class Config(DotEnvConfig):
            debug: bool = Field()

        for value in ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON", "t", "y"]:
            config = Config.load_from_dict({"DEBUG": value})
            assert config.debug is True

    def test_bool_field_false(self) -> None:
        """Test boolean field coercion for false values."""

        class Config(DotEnvConfig):
            debug: bool = Field()

        for value in ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", "f", "n", ""]:
            config = Config.load_from_dict({"DEBUG": value})
            assert config.debug is False

    def test_bool_field_invalid(self) -> None:
        """Test boolean field coercion for invalid values."""

        class Config(DotEnvConfig):
            debug: bool = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"DEBUG": "maybe"})


class TestCollectionTypes:
    """Test collection type coercion."""

    def test_list_str(self) -> None:
        """Test list[str] coercion."""

        class Config(DotEnvConfig):
            hosts: list[str] = Field()

        config = Config.load_from_dict({"HOSTS": "localhost,example.com,*.example.com"})
        assert config.hosts == ["localhost", "example.com", "*.example.com"]

    def test_list_int(self) -> None:
        """Test list[int] coercion."""

        class Config(DotEnvConfig):
            ports: list[int] = Field()

        config = Config.load_from_dict({"PORTS": "8000,8001,8002"})
        assert config.ports == [8000, 8001, 8002]

    def test_list_with_custom_separator(self) -> None:
        """Test list with custom separator."""

        class Config(DotEnvConfig):
            tags: list[str] = Field(separator=";")

        config = Config.load_from_dict({"TAGS": "web;api;backend"})
        assert config.tags == ["web", "api", "backend"]

    def test_set_str(self) -> None:
        """Test set[str] coercion."""

        class Config(DotEnvConfig):
            roles: set[str] = Field()

        config = Config.load_from_dict({"ROLES": "admin,user,admin"})
        assert config.roles == {"admin", "user"}

    def test_tuple_str(self) -> None:
        """Test tuple[str, ...] coercion."""

        class Config(DotEnvConfig):
            coordinates: tuple[str, ...] = Field()

        config = Config.load_from_dict({"COORDINATES": "x,y,z"})
        assert config.coordinates == ("x", "y", "z")

    def test_dict_str_str(self) -> None:
        """Test dict[str, str] coercion."""

        class Config(DotEnvConfig):
            headers: dict[str, str] = Field()

        config = Config.load_from_dict({"HEADERS": "Content-Type=application/json,Accept=*/*"})
        assert config.headers == {"Content-Type": "application/json", "Accept": "*/*"}


class TestRequiredFields:
    """Test required field validation."""

    def test_required_with_sentinel(self) -> None:
        """Test required field using Required sentinel."""

        class Config(DotEnvConfig):
            api_key: str = Required

        with pytest.raises(MissingFieldError) as exc_info:
            Config.load_from_dict({})

        assert "api_key" in str(exc_info.value)
        assert "API_KEY" in str(exc_info.value)

    def test_required_with_field(self) -> None:
        """Test required field using Field() with no default."""

        class Config(DotEnvConfig):
            database_url: str = Field()

        with pytest.raises(MissingFieldError):
            Config.load_from_dict({})

    def test_required_with_ellipsis(self) -> None:
        """Test required field using ellipsis."""

        class Config(DotEnvConfig):
            secret: str = ...

        with pytest.raises(MissingFieldError):
            Config.load_from_dict({})


class TestDefaultValues:
    """Test default value handling."""

    def test_simple_default(self) -> None:
        """Test simple default value."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        config = Config.load_from_dict({})
        assert config.port == 8000

    def test_default_factory(self) -> None:
        """Test default_factory for mutable defaults."""

        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=list)

        config = Config.load_from_dict({})
        assert config.hosts == []
        assert isinstance(config.hosts, list)

    def test_override_default(self) -> None:
        """Test overriding default value."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        config = Config.load_from_dict({"PORT": "3000"})
        assert config.port == 3000


class TestValidation:
    """Test field validation."""

    def test_numeric_ge(self) -> None:
        """Test greater than or equal validation."""

        class Config(DotEnvConfig):
            port: int = Field(ge=1)

        # Valid
        config = Config.load_from_dict({"PORT": "1"})
        assert config.port == 1

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORT": "0"})

    def test_numeric_le(self) -> None:
        """Test less than or equal validation."""

        class Config(DotEnvConfig):
            port: int = Field(le=65535)

        # Valid
        config = Config.load_from_dict({"PORT": "65535"})
        assert config.port == 65535

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORT": "65536"})

    def test_numeric_gt(self) -> None:
        """Test greater than validation."""

        class Config(DotEnvConfig):
            timeout: float = Field(gt=0)

        # Valid
        config = Config.load_from_dict({"TIMEOUT": "0.1"})
        assert config.timeout == 0.1

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"TIMEOUT": "0"})

    def test_numeric_lt(self) -> None:
        """Test less than validation."""

        class Config(DotEnvConfig):
            timeout: float = Field(lt=3600)

        # Valid
        config = Config.load_from_dict({"TIMEOUT": "3599.9"})
        assert config.timeout == 3599.9

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"TIMEOUT": "3600"})

    def test_string_min_length(self) -> None:
        """Test string minimum length validation."""

        class Config(DotEnvConfig):
            api_key: str = Field(min_length=32)

        # Valid
        config = Config.load_from_dict({"API_KEY": "a" * 32})
        assert len(config.api_key) == 32

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"API_KEY": "short"})

    def test_string_max_length(self) -> None:
        """Test string maximum length validation."""

        class Config(DotEnvConfig):
            name: str = Field(max_length=10)

        # Valid
        config = Config.load_from_dict({"NAME": "short"})
        assert config.name == "short"

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"NAME": "verylongname"})

    def test_string_regex(self) -> None:
        """Test string regex validation."""

        class Config(DotEnvConfig):
            email: str = Field(regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")

        # Valid
        config = Config.load_from_dict({"EMAIL": "test@example.com"})
        assert config.email == "test@example.com"

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"EMAIL": "invalid-email"})

    def test_choices(self) -> None:
        """Test choices validation."""

        class Config(DotEnvConfig):
            env: str = Field(choices=["dev", "test", "prod"])

        # Valid
        config = Config.load_from_dict({"ENV": "dev"})
        assert config.env == "dev"

        # Invalid
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"ENV": "staging"})


class TestFieldAlias:
    """Test field alias functionality."""

    def test_alias(self) -> None:
        """Test field with alias."""

        class Config(DotEnvConfig):
            postgres_dsn: str = Field(alias="DATABASE_URL")

        config = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost/db"})
        assert config.postgres_dsn == "postgresql://localhost/db"

    def test_alias_priority_over_field_name(self) -> None:
        """Test that alias takes priority over field name."""

        class Config(DotEnvConfig):
            db_url: str = Field(alias="DATABASE_URL")

        # Should use DATABASE_URL, not DB_URL
        config = Config.load_from_dict({"DATABASE_URL": "postgresql://localhost/db"})
        assert config.db_url == "postgresql://localhost/db"


class TestConfigMethods:
    """Test DotEnvConfig methods."""

    def test_dict_method(self) -> None:
        """Test dict() method."""

        class Config(DotEnvConfig):
            name: str = Field(default="test")
            port: int = Field(default=8000)

        config = Config.load_from_dict({})
        result = config.dict()

        assert result == {"name": "test", "port": 8000}

    def test_get_method(self) -> None:
        """Test get() method."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        config = Config.load_from_dict({})

        assert config.get("port") == 8000
        assert config.get("missing") is None
        assert config.get("missing", 3000) == 3000

    def test_repr(self) -> None:
        """Test __repr__ method."""

        class Config(DotEnvConfig):
            name: str = Field(default="test")
            port: int = Field(default=8000)

        config = Config.load_from_dict({})
        repr_str = repr(config)

        assert "Config" in repr_str
        assert "name='test'" in repr_str
        assert "port=8000" in repr_str


"""Test empty string handling for str fields."""


def test_empty_string_preserved_for_str_field():
    """Test that empty strings are preserved for non-optional str fields."""

    class Config(DotEnvConfig):
        name: str = Field()

    config = Config.load_from_dict({"NAME": ""})
    assert config.name == ""
    assert isinstance(config.name, str)


def test_empty_string_becomes_none_for_optional_str():
    """Test that empty strings become None for Optional[str] fields."""

    class Config(DotEnvConfig):
        name: str | None = Field()

    config = Config.load_from_dict({"NAME": ""})
    assert config.name is None


def test_empty_string_with_default():
    """Test empty string behavior with default values."""

    class Config(DotEnvConfig):
        name: str = Field(default="default_name")

    config = Config.load_from_dict({"NAME": ""})
    assert config.name == ""  # Empty string overrides default


def test_whitespace_only_strings_preserved():
    """Test that whitespace-only strings are preserved for str fields."""

    class Config(DotEnvConfig):
        value: str = Field()

    config = Config.load_from_dict({"VALUE": "   "})
    assert config.value == "   "
    assert len(config.value) == 3
