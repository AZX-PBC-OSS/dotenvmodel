"""Tests for describe functionality."""

import json

from dotenvmodel import DotEnvConfig, Field, Required, SecretStr, describe_configs
from dotenvmodel.describe import (
    FieldDescription,
    describe_class,
    format_constraints,
    format_default,
    format_type_name,
    render_json,
    render_markdown,
    render_table,
)
from dotenvmodel.fields import FieldInfo


class TestFormatTypeName:
    """Test type name formatting."""

    def test_basic_types(self) -> None:
        """Test basic type formatting."""
        assert format_type_name(str) == "str"
        assert format_type_name(int) == "int"
        assert format_type_name(bool) == "bool"
        assert format_type_name(float) == "float"

    def test_optional_types(self) -> None:
        """Test optional type formatting."""
        assert format_type_name(str | None) == "str | None"
        assert format_type_name(int | None) == "int | None"

    def test_generic_types(self) -> None:
        """Test generic type formatting."""
        assert format_type_name(list[str]) == "list[str]"
        assert format_type_name(dict[str, int]) == "dict[str, int]"
        assert format_type_name(set[str]) == "set[str]"

    def test_nested_generics(self) -> None:
        """Test nested generic type formatting."""
        assert format_type_name(list[list[int]]) == "list[list[int]]"
        assert format_type_name(dict[str, list[int]]) == "dict[str, list[int]]"

    def test_special_types(self) -> None:
        """Test special type formatting."""
        assert format_type_name(SecretStr) == "SecretStr"


class TestFormatConstraints:
    """Test constraint formatting."""

    def test_numeric_constraints(self) -> None:
        """Test numeric constraint formatting."""
        field_info = FieldInfo(ge=1, le=100)
        result = format_constraints(field_info)
        assert "ge=1" in result
        assert "le=100" in result

    def test_string_constraints(self) -> None:
        """Test string constraint formatting."""
        field_info = FieldInfo(min_length=8, max_length=32)
        result = format_constraints(field_info)
        assert "min_length=8" in result
        assert "max_length=32" in result

    def test_regex_constraint(self) -> None:
        """Test regex constraint formatting."""
        field_info = FieldInfo(regex=r"^\d+$")
        result = format_constraints(field_info)
        assert "regex=" in result

    def test_choices_constraint(self) -> None:
        """Test choices constraint formatting."""
        field_info = FieldInfo(choices=["dev", "prod"])
        result = format_constraints(field_info)
        assert "choices=" in result

    def test_collection_constraints(self) -> None:
        """Test collection constraint formatting."""
        field_info = FieldInfo(min_items=1, max_items=10)
        result = format_constraints(field_info)
        assert "min_items=1" in result
        assert "max_items=10" in result

    def test_uuid_constraint(self) -> None:
        """Test UUID version constraint formatting."""
        field_info = FieldInfo(uuid_version=4)
        result = format_constraints(field_info)
        assert "uuid_version=4" in result

    def test_no_constraints(self) -> None:
        """Test formatting when no constraints are set."""
        field_info = FieldInfo(default="test")
        assert format_constraints(field_info) == "-"


class TestFormatDefault:
    """Test default value formatting."""

    def test_missing_default(self) -> None:
        """Test formatting when no default is set."""
        field_info = FieldInfo()
        assert format_default(field_info, str) == "-"

    def test_none_default(self) -> None:
        """Test None default formatting."""
        field_info = FieldInfo(default=None)
        assert format_default(field_info, str | None) == "None"

    def test_string_default(self) -> None:
        """Test string default formatting."""
        field_info = FieldInfo(default="test")
        assert format_default(field_info, str) == '"test"'

    def test_numeric_default(self) -> None:
        """Test numeric default formatting."""
        field_info = FieldInfo(default=8000)
        assert format_default(field_info, int) == "8000"

    def test_bool_default(self) -> None:
        """Test boolean default formatting."""
        field_info = FieldInfo(default=True)
        assert format_default(field_info, bool) == "True"
        field_info = FieldInfo(default=False)
        assert format_default(field_info, bool) == "False"

    def test_factory_default_list(self) -> None:
        """Test list factory default formatting."""
        field_info = FieldInfo(default_factory=list)
        assert format_default(field_info, list[str]) == "[]"

    def test_factory_default_dict(self) -> None:
        """Test dict factory default formatting."""
        field_info = FieldInfo(default_factory=dict)
        assert format_default(field_info, dict[str, str]) == "{}"

    def test_factory_default_set(self) -> None:
        """Test set factory default formatting."""
        field_info = FieldInfo(default_factory=set)
        assert format_default(field_info, set[str]) == "set()"


class TestDescribeClassmethod:
    """Test DotEnvConfig.describe() classmethod."""

    def test_basic_describe(self) -> None:
        """Test basic describe output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, description="Server port")

        output = Config.describe()
        assert "PORT" in output
        assert "int" in output
        assert "8000" in output
        assert "Server port" in output

    def test_required_field(self) -> None:
        """Test required field display."""

        class Config(DotEnvConfig):
            api_key: str = Required

        output = Config.describe()
        assert "API_KEY" in output
        assert "Yes" in output  # Required

    def test_optional_field(self) -> None:
        """Test optional field display."""

        class Config(DotEnvConfig):
            debug: bool = Field(default=False)

        output = Config.describe()
        assert "DEBUG" in output
        assert "No" in output  # Not required

    def test_with_alias(self) -> None:
        """Test field with alias."""

        class Config(DotEnvConfig):
            db_url: str = Field(alias="DATABASE_URL")

        output = Config.describe()
        assert "DATABASE_URL" in output

    def test_with_prefix(self) -> None:
        """Test class with env_prefix."""

        class Config(DotEnvConfig):
            env_prefix = "MYAPP_"
            port: int = Field(default=8000)

        output = Config.describe()
        assert "MYAPP_PORT" in output

    def test_with_constraints(self) -> None:
        """Test field with constraints."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, ge=1, le=65535)

        output = Config.describe()
        assert "ge=1" in output
        assert "le=65535" in output


class TestDescribeFormats:
    """Test different output formats."""

    def test_table_format(self) -> None:
        """Test table format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(format="table")
        assert "+" in output  # Table borders
        assert "|" in output  # Table columns
        assert "Config" in output

    def test_markdown_format(self) -> None:
        """Test markdown format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(format="markdown")
        assert "## Config" in output
        assert "|" in output
        assert "---" in output or "|-" in output

    def test_json_format(self) -> None:
        """Test JSON format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(format="json")
        data = json.loads(output)
        assert "class_name" in data
        assert data["class_name"] == "Config"
        assert "fields" in data
        assert len(data["fields"]) == 1

    def test_json_full_values(self) -> None:
        """Test JSON format includes full values without truncation."""

        class Config(DotEnvConfig):
            description: str = Field(
                description="This is a very long description that should not be truncated in JSON format"
            )

        output = Config.describe(format="json")
        data = json.loads(output)
        assert "should not be truncated" in data["fields"][0]["description"]


class TestDescribeConfigs:
    """Test describe_configs() for multiple classes."""

    def test_multiple_classes(self) -> None:
        """Test describing multiple classes."""

        class AppConfig(DotEnvConfig):
            port: int = Field(default=8000)

        class DbConfig(DotEnvConfig):
            db_url: str = Field()

        output = describe_configs([AppConfig, DbConfig])
        assert "AppConfig" in output
        assert "DbConfig" in output
        assert "PORT" in output
        assert "DB_URL" in output

    def test_multiple_classes_json(self) -> None:
        """Test describing multiple classes as JSON."""

        class AppConfig(DotEnvConfig):
            port: int = Field(default=8000)

        class DbConfig(DotEnvConfig):
            db_url: str = Field()

        output = describe_configs([AppConfig, DbConfig], format="json")
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["class_name"] == "AppConfig"
        assert data[1]["class_name"] == "DbConfig"

    def test_empty_list(self) -> None:
        """Test describing empty list of classes."""
        output = describe_configs([])
        assert "No configuration classes provided" in output


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_config(self) -> None:
        """Test describing empty config class."""

        class EmptyConfig(DotEnvConfig):
            pass

        output = EmptyConfig.describe()
        assert "EmptyConfig" in output
        assert "No fields defined" in output

    def test_inherited_fields(self) -> None:
        """Test describing class with inherited fields."""

        class BaseConfig(DotEnvConfig):
            debug: bool = Field(default=False)

        class AppConfig(BaseConfig):
            port: int = Field(default=8000)

        output = AppConfig.describe()
        assert "DEBUG" in output
        assert "PORT" in output

    def test_optional_type(self) -> None:
        """Test optional type display."""

        class Config(DotEnvConfig):
            optional_field: str | None = Field()

        output = Config.describe()
        assert "str | None" in output

    def test_collection_type(self) -> None:
        """Test collection type display."""

        class Config(DotEnvConfig):
            tags: list[str] = Field(default_factory=list)

        output = Config.describe()
        assert "list[str]" in output
        assert "[]" in output  # default_factory=list


class TestRenderFunctions:
    """Test individual render functions."""

    def test_render_table_empty(self) -> None:
        """Test render_table with no fields."""
        output = render_table("TestConfig", "", [])
        assert "TestConfig" in output
        assert "No fields defined" in output

    def test_render_markdown_empty(self) -> None:
        """Test render_markdown with no fields."""
        output = render_markdown("TestConfig", "", [])
        assert "## TestConfig" in output
        assert "No fields defined" in output

    def test_render_json_empty(self) -> None:
        """Test render_json with no fields."""
        output = render_json("TestConfig", "", [])
        data = json.loads(output)
        assert data["class_name"] == "TestConfig"
        assert data["fields"] == []

    def test_render_table_with_prefix(self) -> None:
        """Test render_table shows prefix in title."""
        field = FieldDescription(
            env_var="APP_PORT",
            field_name="port",
            type_name="int",
            required=False,
            default="8000",
            description="Server port",
            constraints="-",
        )
        output = render_table("AppConfig", "APP_", [field])
        assert "prefix: APP_" in output

    def test_render_markdown_with_prefix(self) -> None:
        """Test render_markdown shows prefix in title."""
        field = FieldDescription(
            env_var="APP_PORT",
            field_name="port",
            type_name="int",
            required=False,
            default="8000",
            description="Server port",
            constraints="-",
        )
        output = render_markdown("AppConfig", "APP_", [field])
        assert "prefix: `APP_`" in output


class TestDescribeClass:
    """Test describe_class function."""

    def test_describe_class_returns_tuple(self) -> None:
        """Test describe_class returns correct tuple."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        class_name, prefix, fields = describe_class(Config)
        assert class_name == "Config"
        assert prefix == ""
        assert len(fields) == 1
        assert isinstance(fields[0], FieldDescription)

    def test_describe_class_with_prefix(self) -> None:
        """Test describe_class with env_prefix."""

        class Config(DotEnvConfig):
            env_prefix = "MYAPP_"
            port: int = Field(default=8000)

        _, prefix, fields = describe_class(Config)
        assert prefix == "MYAPP_"
        assert fields[0].env_var == "MYAPP_PORT"
