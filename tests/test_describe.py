"""Tests for describe functionality."""

import json

import pytest

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

    def test_callable_type_formatting(self) -> None:
        """Test Callable type annotation formatting."""
        from collections.abc import Callable

        # Test with specific parameter types
        result = format_type_name(Callable[[int, str], bool])
        assert result == "Callable[[int, str], bool]"

        # Test with ellipsis
        result = format_type_name(Callable[..., str])
        assert result == "Callable[[...], str]"

        # Test with no parameters
        result = format_type_name(Callable[[], int])
        assert result == "Callable[[], int]"

        # Test with single parameter
        result = format_type_name(Callable[[str], None])
        assert result == "Callable[[str], None]"

        # Test with nested types
        result = format_type_name(Callable[[list[int], dict[str, str]], bool])
        assert result == "Callable[[list[int], dict[str, str]], bool]"

    def test_annotated_type_formatting(self) -> None:
        """Test Annotated type formatting."""
        from typing import Annotated

        result = format_type_name(Annotated[str, "metadata"])
        assert "str" in result

    def test_literal_type_formatting(self) -> None:
        """Test Literal type formatting."""
        from typing import Literal

        result = format_type_name(Literal["a", "b", "c"])
        assert "Literal" in result

    def test_union_multiple_types(self) -> None:
        """Test Union with multiple non-None types."""
        result = format_type_name(str | int | float)
        # Should show all types joined with " | "
        assert "str" in result
        assert "int" in result
        assert "float" in result
        assert "|" in result

    def test_callable_with_ellipsis(self) -> None:
        """Test Callable with ellipsis parameter."""
        from collections.abc import Callable

        result = format_type_name(Callable[..., str])
        assert "Callable[[...], str]" in result

    def test_callable_no_args(self) -> None:
        """Test Callable without argument specification."""
        from collections.abc import Callable

        # Callable without args should return "Callable"
        result = format_type_name(Callable)
        assert result == "Callable"

    def test_generic_without_args(self) -> None:
        """Test generic type without arguments."""

        # Bare typing.List has an origin but no args
        result = format_type_name(list)
        assert result == "list"

    def test_none_type(self) -> None:
        """Test NoneType formatting."""
        assert format_type_name(type(None)) == "None"


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

    def test_gt_lt_constraints(self) -> None:
        """Test gt/lt constraint formatting."""
        field_info = FieldInfo(gt=0, lt=100)
        result = format_constraints(field_info)
        assert "gt=0" in result
        assert "lt=100" in result

    def test_custom_separator(self) -> None:
        """Test custom separator constraint formatting."""
        field_info = FieldInfo(separator=";")
        result = format_constraints(field_info)
        assert "separator=';'" in result

    def test_regex_truncation(self) -> None:
        """Test long regex pattern truncation."""
        long_regex = "a" * 30
        field_info = FieldInfo(regex=long_regex)
        result = format_constraints(field_info, truncate=True)
        assert "..." in result
        assert len(result) < len(long_regex) + 10

    def test_choices_truncation(self) -> None:
        """Test long choices list truncation."""
        long_choices = ["choice" + str(i) for i in range(20)]
        field_info = FieldInfo(choices=long_choices)
        result = format_constraints(field_info, truncate=True)
        assert "..." in result


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

    def test_secret_str_default(self) -> None:
        """Test SecretStr default is hidden."""
        field_info = FieldInfo(default=SecretStr("my_secret_value"))
        assert format_default(field_info, SecretStr) == "<secret>"

    def test_non_secret_class_with_secret_in_name(self) -> None:
        """Test that classes with 'Secret' in name but not SecretStr subclass are not hidden."""

        # Create a custom class that has "Secret" in the name but is not a SecretStr
        class MySecretConfig:
            """A class with 'Secret' in the name that should not be hidden."""

            def __init__(self, value: str) -> None:
                self.value = value

        field_info = FieldInfo(default=MySecretConfig("test_value"))
        # Should not return "<secret>" because MySecretConfig is not a subclass of SecretStr
        result = format_default(field_info, MySecretConfig)
        assert result != "<secret>"
        # The result will be a repr of the object, which may be truncated
        # Just verify it's not masked as a secret
        assert "<" in result  # Should contain angle brackets from object repr

    def test_long_string_truncation(self) -> None:
        """Test long string default truncation."""
        long_string = "a" * 30
        field_info = FieldInfo(default=long_string)
        result = format_default(field_info, str, truncate=True)
        assert result == '"aaaaaaaaaaaaaaaaa..."'
        assert len(result) < len(long_string) + 5

    def test_long_string_no_truncation(self) -> None:
        """Test long string without truncation."""
        long_string = "a" * 30
        field_info = FieldInfo(default=long_string)
        result = format_default(field_info, str, truncate=False)
        assert result == f'"{long_string}"'
        assert "..." not in result

    def test_complex_default_truncation(self) -> None:
        """Test complex default value truncation."""
        complex_default = {"key": "value" * 10}
        field_info = FieldInfo(default=complex_default)
        result = format_default(field_info, dict, truncate=True)
        assert "..." in result

    def test_complex_default_no_truncation(self) -> None:
        """Test complex default without truncation."""
        complex_default = {"key": "short"}
        field_info = FieldInfo(default=complex_default)
        result = format_default(field_info, dict, truncate=False)
        assert "..." not in result
        assert "key" in result

    def test_custom_factory_default(self) -> None:
        """Test custom factory default formatting."""

        def custom_factory() -> list[str]:
            return ["default"]

        field_info = FieldInfo(default_factory=custom_factory)
        result = format_default(field_info, list[str])
        assert "<" in result and ">" in result  # Shows <factory_name()>

    def test_float_default(self) -> None:
        """Test float default formatting."""
        field_info = FieldInfo(default=3.14)
        assert format_default(field_info, float) == "3.14"

    def test_empty_string_default(self) -> None:
        """Test empty string default formatting."""
        field_info = FieldInfo(default="")
        result = format_default(field_info, str)
        assert result == '""'


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

        output = Config.describe(output_format="table")
        assert "+" in output  # Table borders
        assert "|" in output  # Table columns
        assert "Config" in output

    def test_markdown_format(self) -> None:
        """Test markdown format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="markdown")
        assert "## Config" in output
        assert "|" in output
        assert "---" in output or "|-" in output

    def test_json_format(self) -> None:
        """Test JSON format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="json")
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

        output = Config.describe(output_format="json")
        data = json.loads(output)
        assert "should not be truncated" in data["fields"][0]["description"]

    def test_invalid_format(self) -> None:
        """Test that invalid format raises ValueError."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        with pytest.raises(ValueError, match="Unknown output_format"):
            Config.describe(output_format="xml")  # type: ignore


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

        output = describe_configs([AppConfig, DbConfig], output_format="json")
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

    def test_description_truncation(self) -> None:
        """Test that long descriptions are truncated in table format."""

        class Config(DotEnvConfig):
            field: str = Field(
                description="This is a very long description that should be truncated when displayed in table format to avoid overwhelming the output"
            )

        output = Config.describe(output_format="table")
        # Should be truncated with "..."
        assert "..." in output

    def test_description_no_truncation_json(self) -> None:
        """Test that descriptions are not truncated in JSON format."""

        class Config(DotEnvConfig):
            field: str = Field(
                description="This is a very long description that should not be truncated in JSON format because JSON can handle full-length content"
            )

        output = Config.describe(output_format="json")
        data = json.loads(output)
        # Full description should be present
        assert "should not be truncated in JSON format" in data["fields"][0]["description"]
        assert "..." not in data["fields"][0]["description"]


class TestRenderFunctions:
    """Test individual render functions."""

    def test_render_table_empty(self) -> None:
        """Test render_table with no fields."""
        output = render_table("TestConfig", "", [], "\n")
        assert "TestConfig" in output
        assert "No fields defined" in output

    def test_render_markdown_empty(self) -> None:
        """Test render_markdown with no fields."""
        output = render_markdown("TestConfig", "", [], "\n")
        assert "## TestConfig" in output
        assert "No fields defined" in output

    def test_render_json_empty(self) -> None:
        """Test render_json with no fields."""
        output = render_json("TestConfig", "", [], "\n")
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
        output = render_table("AppConfig", "APP_", [field], "\n")
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
        output = render_markdown("AppConfig", "APP_", [field], "\n")
        # Markdown escapes underscores with backslash
        assert "prefix: `APP\\_`" in output or "prefix: `APP_`" in output

    def test_markdown_pipe_escaping(self) -> None:
        """Test that pipe characters are escaped in markdown output."""
        field = FieldDescription(
            env_var="SOME|VAR",
            field_name="some_var",
            type_name="str",
            required=True,
            default="-",
            description="This | has | pipes",
            constraints="-",
        )
        output = render_markdown("TestConfig", "", [field], "\n")
        # Pipes should be escaped as \|
        assert "SOME\\|VAR" in output or "This \\| has \\| pipes" in output

    def test_newline_in_description_table(self) -> None:
        """Test that newlines in descriptions don't break table rendering."""
        field = FieldDescription(
            env_var="TEST_VAR",
            field_name="test",
            type_name="str",
            required=False,
            default="value",
            description="Line 1\nLine 2\nLine 3",
            constraints="-",
        )
        output = render_table("Config", "", [field], "\n")

        # Verify table structure is maintained
        lines = output.split("\n")
        # Count lines that start with | (data rows)
        data_rows = [line for line in lines if line.strip().startswith("|") and "TEST_VAR" in line]

        # Should only have one row for this field, even with newlines in description
        assert len(data_rows) == 1

        # The newlines should be replaced with spaces
        assert "Line 1 Line 2 Line 3" in output or "Line 1" in output

    def test_newline_in_description_markdown(self) -> None:
        """Test that newlines in descriptions don't break markdown rendering."""
        field = FieldDescription(
            env_var="TEST_VAR",
            field_name="test",
            type_name="str",
            required=False,
            default="value",
            description="Line 1\nLine 2",
            constraints="-",
        )
        output = render_markdown("Config", "", [field], "\n")

        # Verify markdown table structure is maintained
        lines = output.split("\n")
        # Count lines that are part of the table (start with |)
        # Note: markdown escapes underscores as \_
        table_rows = [
            line
            for line in lines
            if line.strip().startswith("|") and ("TEST_VAR" in line or "TEST\\_VAR" in line)
        ]

        # Should only have one row for this field
        assert len(table_rows) == 1


class TestTableTruncation:
    """Test table rendering with values exceeding column widths."""

    def test_long_env_var_truncation(self) -> None:
        """Test that very long env variable names are truncated in table."""
        long_var = "A" * 50  # Exceeds max width of 40
        field = FieldDescription(
            env_var=long_var,
            field_name="test",
            type_name="str",
            required=False,
            default="value",
            description="Test",
            constraints="-",
        )
        output = render_table("Config", "", [field], "\n")
        # Should be truncated with "..."
        assert "..." in output

    def test_long_type_name_truncation(self) -> None:
        """Test that very long type names are truncated in table."""
        long_type = "A" * 35  # Exceeds max width of 30
        field = FieldDescription(
            env_var="TEST",
            field_name="test",
            type_name=long_type,
            required=False,
            default="value",
            description="Test",
            constraints="-",
        )
        output = render_table("Config", "", [field], "\n")
        assert "..." in output

    def test_long_default_truncation(self) -> None:
        """Test that very long default values are truncated in table."""
        long_default = "A" * 30  # Exceeds max width of 25
        field = FieldDescription(
            env_var="TEST",
            field_name="test",
            type_name="str",
            required=False,
            default=long_default,
            description="Test",
            constraints="-",
        )
        output = render_table("Config", "", [field], "\n")
        assert "..." in output

    def test_long_description_truncation(self) -> None:
        """Test that very long descriptions are truncated in table."""
        long_desc = "A" * 45  # Exceeds max width of 40
        field = FieldDescription(
            env_var="TEST",
            field_name="test",
            type_name="str",
            required=False,
            default="value",
            description=long_desc,
            constraints="-",
        )
        output = render_table("Config", "", [field], "\n")
        assert "..." in output

    def test_long_constraints_truncation(self) -> None:
        """Test that very long constraints are truncated in table."""
        long_constraints = "A" * 45  # Exceeds max width of 40
        field = FieldDescription(
            env_var="TEST",
            field_name="test",
            type_name="str",
            required=False,
            default="value",
            description="Test",
            constraints=long_constraints,
        )
        output = render_table("Config", "", [field], "\n")
        assert "..." in output


class TestSecretStrMasking:
    """Test SecretStr values are properly masked in describe output."""

    def test_secretstr_default_is_masked(self) -> None:
        """Test that SecretStr default values are masked."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default=SecretStr("super-secret-key"))

        output = Config.describe()
        assert "<secret>" in output
        assert "super-secret-key" not in output

    def test_secretstr_masking_all_formats(self) -> None:
        """Test that SecretStr is masked in all output formats."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default=SecretStr("my-secret"))

        for fmt in ["table", "markdown", "json"]:
            output = Config.describe(output_format=fmt)
            assert "<secret>" in output or '"<secret>"' in output
            assert "my-secret" not in output

    def test_secretstr_in_table_format(self) -> None:
        """Test that SecretStr is masked in table format."""

        class Config(DotEnvConfig):
            password: SecretStr = Field(default=SecretStr("password123"))

        output = Config.describe(output_format="table")
        assert "<secret>" in output
        assert "password123" not in output
        # Ensure table structure is intact
        assert "|" in output
        assert "+" in output

    def test_secretstr_in_markdown_format(self) -> None:
        """Test that SecretStr is masked in markdown format."""

        class Config(DotEnvConfig):
            token: SecretStr = Field(default=SecretStr("secret-token"))

        output = Config.describe(output_format="markdown")
        assert "`<secret>`" in output
        assert "secret-token" not in output
        # Ensure markdown structure is intact
        assert "##" in output
        assert "|" in output

    def test_secretstr_in_json_format(self) -> None:
        """Test that SecretStr is masked in JSON format."""

        class Config(DotEnvConfig):
            api_secret: SecretStr = Field(default=SecretStr("secret-value"))

        output = Config.describe(output_format="json")
        data = json.loads(output)
        assert data["fields"][0]["default"] == "<secret>"
        assert "secret-value" not in output

    def test_secretstr_with_description(self) -> None:
        """Test that SecretStr masking works with field descriptions."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(
                default=SecretStr("hidden-key"), description="API authentication key"
            )

        output = Config.describe()
        assert "<secret>" in output
        assert "hidden-key" not in output
        assert "API authentication key" in output

    def test_secretstr_required_field(self) -> None:
        """Test that required SecretStr fields are handled correctly."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Required

        output = Config.describe()
        # Required fields should show "-" as default, not a secret value
        assert "Yes" in output  # Required column
        # Should not contain any secret markers for required fields
        lines = output.split("\n")
        for line in lines:
            if "API_KEY" in line:
                # The default column should show "-" for required fields
                assert "<secret>" not in line or "|-" in line

    def test_secretstr_multiple_fields(self) -> None:
        """Test that multiple SecretStr fields are all masked."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(default=SecretStr("key-1"))
            db_password: SecretStr = Field(default=SecretStr("pass-2"))
            auth_token: SecretStr = Field(default=SecretStr("token-3"))

        output = Config.describe()
        # All secrets should be masked
        assert output.count("<secret>") >= 3
        assert "key-1" not in output
        assert "pass-2" not in output
        assert "token-3" not in output

    def test_secretstr_with_constraints(self) -> None:
        """Test that SecretStr masking works with field constraints."""

        class Config(DotEnvConfig):
            password: SecretStr = Field(
                default=SecretStr("secure-password"), min_length=8, max_length=32
            )

        output = Config.describe()
        assert "<secret>" in output
        assert "secure-password" not in output
        assert "min_length=8" in output
        assert "max_length=32" in output

    def test_format_default_masks_secretstr(self) -> None:
        """Test that format_default function properly masks SecretStr."""
        field_info = FieldInfo(default=SecretStr("test-secret"))

        # Test masking for SecretStr type
        result = format_default(field_info, SecretStr)
        assert result == "<secret>"
        assert "test-secret" not in result


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


class TestNewFormats:
    """Test new output formats (HTML, dotenv)."""

    def test_html_format_basic(self) -> None:
        """Test HTML format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, description="Server port")
            debug: bool = Field(default=False)

        output = Config.describe(output_format="html")

        # Verify HTML structure
        assert "<!DOCTYPE html>" in output
        assert "<html>" in output
        assert "<table>" in output
        assert "<th>ENV Variable</th>" in output

        # Verify content
        assert "PORT" in output
        assert "DEBUG" in output
        assert "8000" in output
        assert "Server port" in output

    def test_html_format_with_prefix(self) -> None:
        """Test HTML format shows prefix correctly."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            port: int = Field(default=8000)

        output = Config.describe(output_format="html")

        assert "APP_" in output
        assert "prefix" in output

    def test_html_format_escapes_special_chars(self) -> None:
        """Test that HTML format escapes special characters."""

        class Config(DotEnvConfig):
            field: str = Field(description="Description with <tags> & special chars")

        output = Config.describe(output_format="html")

        # Should be escaped
        assert "&lt;tags&gt;" in output
        assert "&amp;" in output
        # Should NOT contain unescaped
        assert "<tags>" not in output or output.count("<tags>") == 0  # Only in HTML tags

    def test_html_format_secret_styling(self) -> None:
        """Test that secrets get special styling in HTML."""

        class Config(DotEnvConfig):
            password: SecretStr = Field(default=SecretStr("secret"))

        output = Config.describe(output_format="html")

        assert "&lt;secret&gt;" in output
        # Check for secret class (may be combined with other classes)
        assert "secret" in output and (
            "class='default secret'" in output or 'class="default secret"' in output
        )

    def test_dotenv_format_basic(self) -> None:
        """Test .env format output."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, description="Server port")
            api_key: str = Field(description="API key")

        output = Config.describe(output_format="dotenv")

        # Verify header
        assert "# Configuration for Config" in output

        # Verify descriptions
        assert "# Server port" in output
        assert "# API key" in output

        # Verify type info
        assert "# Type: int" in output
        assert "# Type: str" in output

        # Verify variable lines
        assert "PORT=" in output
        assert "API_KEY=" in output

    def test_dotenv_format_required_vs_optional(self) -> None:
        """Test that required fields are uncommented, optional are commented."""

        class Config(DotEnvConfig):
            required_field: str = Required
            optional_field: str = Field(default="default_value")

        output = Config.describe(output_format="dotenv")

        # Required field should be uncommented (no value)
        assert "\nREQUIRED_FIELD=\n" in output

        # Optional field should be commented with default (string defaults have quotes)
        assert '# OPTIONAL_FIELD="default_value"' in output

    def test_dotenv_format_with_prefix(self) -> None:
        """Test .env format shows prefix in header."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            port: int = Field(default=8000)

        output = Config.describe(output_format="dotenv")

        assert "# All variables prefixed with: APP_" in output
        assert "APP_PORT=" in output

    def test_dotenv_format_secrets_masked(self) -> None:
        """Test that secrets are commented with placeholder."""

        class Config(DotEnvConfig):
            password: SecretStr = Field(default=SecretStr("my_actual_secret"))

        output = Config.describe(output_format="dotenv")

        # Secret should be commented with placeholder
        assert "# PASSWORD=your_secret_here" in output
        # Should NOT contain actual secret value
        assert "my_actual_secret" not in output

    def test_dotenv_format_with_constraints(self) -> None:
        """Test that constraints are shown in .env format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, ge=1, le=65535)

        output = Config.describe(output_format="dotenv")

        assert "# Type: int | Constraints: ge=1, le=65535" in output


class TestFileExport:
    """Test file export functionality."""

    def test_describe_with_output_saves_file(self, tmp_path) -> None:
        """Test that output parameter saves to file."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output_file = tmp_path / "config.md"
        result = Config.describe(output_format="markdown", output=str(output_file))

        # File should exist
        assert output_file.exists()

        # Content should match return value
        assert output_file.read_text() == result

        # Should contain expected content
        assert "PORT" in result

    def test_generate_env_example_with_output(self, tmp_path) -> None:
        """Test generate_env_example saves to file."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, description="Server port")

        output_file = tmp_path / ".env.example"
        result = Config.generate_env_example(output=str(output_file))

        # File should exist
        assert output_file.exists()

        # Content should match
        assert output_file.read_text() == result

        # Should be dotenv format
        assert "# Server port" in result
        assert "PORT=" in result

    def test_describe_configs_with_output(self, tmp_path) -> None:
        """Test describe_configs saves to file."""
        from dotenvmodel import describe_configs

        class Config1(DotEnvConfig):
            port: int = Field(default=8000)

        class Config2(DotEnvConfig):
            url: str = Field()

        output_file = tmp_path / "configs.md"
        result = describe_configs(
            [Config1, Config2], output_format="markdown", output=str(output_file)
        )

        assert output_file.exists()
        assert "Config1" in result
        assert "Config2" in result

    def test_html_output_to_file(self, tmp_path) -> None:
        """Test HTML output can be saved to file."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output_file = tmp_path / "config.html"
        result = Config.describe(output_format="html", output=str(output_file))

        assert output_file.exists()
        assert "<!DOCTYPE html>" in result


class TestTypeParsingHints:
    """Test type parsing hint functionality."""

    def test_get_type_parsing_hint_list(self) -> None:
        """Test parsing hint for list types."""
        from dotenvmodel.describe import get_type_parsing_hint

        hint = get_type_parsing_hint(list[str], None)
        assert "comma-separated" in hint
        assert "value1,value2,value3" in hint

    def test_get_type_parsing_hint_list_int(self) -> None:
        """Test parsing hint for list[int]."""
        from dotenvmodel.describe import get_type_parsing_hint

        hint = get_type_parsing_hint(list[int], None)
        assert "comma-separated" in hint
        assert "1,2,3,4" in hint

    def test_get_type_parsing_hint_custom_separator(self) -> None:
        """Test parsing hint shows custom separator."""
        from dotenvmodel.describe import get_type_parsing_hint
        from dotenvmodel.fields import FieldInfo

        field_info = FieldInfo(separator=";")
        hint = get_type_parsing_hint(list[str], field_info)

        assert ";" in hint
        assert "separated" in hint

    def test_get_type_parsing_hint_timedelta(self) -> None:
        """Test parsing hint for timedelta."""
        from datetime import timedelta

        from dotenvmodel.describe import get_type_parsing_hint

        hint = get_type_parsing_hint(timedelta, None)
        assert "duration" in hint
        assert "5s" in hint
        assert "1m" in hint
        assert "1h" in hint

    def test_get_type_parsing_hint_secretstr(self) -> None:
        """Test parsing hint for SecretStr."""
        from dotenvmodel.describe import get_type_parsing_hint

        hint = get_type_parsing_hint(SecretStr, None)
        assert "sensitive" in hint or "logged" in hint


class TestConstraintExamples:
    """Test constraint example generation."""

    def test_generate_numeric_constraint_examples(self) -> None:
        """Test examples for numeric constraints."""
        from dotenvmodel.describe import generate_constraint_examples
        from dotenvmodel.fields import FieldInfo

        field_info = FieldInfo(ge=1, le=100)
        examples = generate_constraint_examples(int, field_info)

        assert "valid" in examples
        assert "invalid" in examples

        # Should have valid examples
        assert len(examples["valid"]) > 0
        assert "1" in examples["valid"]
        assert "100" in examples["valid"]

        # Should have invalid examples
        assert len(examples["invalid"]) > 0
        assert any("too small" in ex for ex in examples["invalid"])
        assert any("too large" in ex for ex in examples["invalid"])

    def test_generate_string_length_examples(self) -> None:
        """Test examples for string length constraints."""
        from dotenvmodel.describe import generate_constraint_examples
        from dotenvmodel.fields import FieldInfo

        field_info = FieldInfo(min_length=8, max_length=32)
        examples = generate_constraint_examples(str, field_info)

        # Should have examples at boundaries
        assert any("8 chars" in ex for ex in examples["valid"])
        assert any("32 chars" in ex for ex in examples["valid"])

        # Should have invalid examples
        assert any("too short" in ex for ex in examples["invalid"])
        assert any("too long" in ex for ex in examples["invalid"])

    def test_generate_choices_examples(self) -> None:
        """Test examples for choices constraint."""
        from dotenvmodel.describe import generate_constraint_examples
        from dotenvmodel.fields import FieldInfo

        field_info = FieldInfo(choices=["dev", "staging", "prod"])
        examples = generate_constraint_examples(str, field_info)

        # Should show valid choices
        assert "dev" in examples["valid"]
        assert "staging" in examples["valid"]
        assert "prod" in examples["valid"]

        # Should show invalid example
        assert any("not in allowed choices" in ex for ex in examples["invalid"])

    def test_generate_collection_size_examples(self) -> None:
        """Test examples for collection size constraints."""
        from dotenvmodel.describe import generate_constraint_examples
        from dotenvmodel.fields import FieldInfo

        field_info = FieldInfo(min_items=2, max_items=5)
        examples = generate_constraint_examples(list, field_info)

        # Should have examples with correct number of items
        assert any("2 items" in ex for ex in examples["valid"])
        assert any("5 items" in ex for ex in examples["valid"])

        # Should show boundaries
        assert any("too few" in ex for ex in examples["invalid"])
        assert any("too many" in ex for ex in examples["invalid"])


class TestGenerateEnvExample:
    """Test generate_env_example classmethod."""

    def test_generate_env_example_basic(self) -> None:
        """Test basic generate_env_example functionality."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, description="Server port")

        output = Config.generate_env_example()

        assert "# Configuration for Config" in output
        assert "# Server port" in output
        assert "PORT=" in output

    def test_generate_env_example_function(self) -> None:
        """Test module-level generate_env_example function."""
        from dotenvmodel import generate_env_example

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = generate_env_example(Config)

        assert "PORT=" in output

    def test_generate_env_example_equals_dotenv_format(self) -> None:
        """Test that generate_env_example produces same output as dotenv format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000, description="Server port")
            debug: bool = Field(default=False)

        env_example = Config.generate_env_example()
        dotenv_format = Config.describe(output_format="dotenv")

        # Should be identical
        assert env_example == dotenv_format


class TestLineEndings:
    """Test line ending customization feature."""

    def test_unix_line_endings_in_table_format(self) -> None:
        """Test Unix line endings (\\n) in table format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)
            debug: bool = Field(default=False)

        output = Config.describe(output_format="table", line_ending="\n")

        # Should contain Unix line endings
        assert "\n" in output
        # Should NOT contain Windows line endings
        assert "\r\n" not in output

    def test_windows_line_endings_in_table_format(self) -> None:
        """Test Windows line endings (\\r\\n) in table format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)
            debug: bool = Field(default=False)

        output = Config.describe(output_format="table", line_ending="\r\n")

        # Should contain Windows line endings
        assert "\r\n" in output

    def test_old_mac_line_endings_in_table_format(self) -> None:
        """Test old Mac line endings (\\r) in table format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)
            debug: bool = Field(default=False)

        output = Config.describe(output_format="table", line_ending="\r")

        # Should contain carriage returns
        assert "\r" in output
        # Should NOT contain newlines
        assert "\n" not in output

    def test_platform_default_line_endings(self) -> None:
        """Test platform default line endings (None)."""
        import os

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="table", line_ending=None)

        # Should use platform default
        assert os.linesep in output

    def test_line_endings_table_format(self) -> None:
        """Test line endings work in table format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="table", line_ending="\r\n")

        assert "\r\n" in output
        assert "PORT" in output

    def test_line_endings_markdown_format(self) -> None:
        """Test line endings work in markdown format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="markdown", line_ending="\r\n")

        assert "\r\n" in output
        assert "## Config" in output

    def test_line_endings_json_format(self) -> None:
        """Test line endings work in JSON format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        # JSON internally uses \n for formatting, but the custom line ending
        # is applied to the final result
        output = Config.describe(output_format="json", line_ending="\r\n")

        # JSON should be parseable
        data = json.loads(output)
        assert data["class_name"] == "Config"

        # After parsing, JSON pretty-printing should have custom line endings
        assert "\r\n" in output

    def test_line_endings_html_format(self) -> None:
        """Test line endings work in HTML format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="html", line_ending="\r\n")

        assert "\r\n" in output
        assert "<!DOCTYPE html>" in output

    def test_line_endings_dotenv_format(self) -> None:
        """Test line endings work in dotenv format."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)

        output = Config.describe(output_format="dotenv", line_ending="\r\n")

        assert "\r\n" in output
        assert "PORT=" in output

    def test_line_endings_in_describe_configs(self) -> None:
        """Test line endings in describe_configs() for multiple classes."""

        class Config1(DotEnvConfig):
            port: int = Field(default=8000)

        class Config2(DotEnvConfig):
            debug: bool = Field(default=False)

        output = describe_configs([Config1, Config2], output_format="markdown", line_ending="\r\n")

        # Should use Windows line endings
        assert "\r\n" in output

        # Both configs should be present
        assert "Config1" in output
        assert "Config2" in output

        # The separator between configs should also use custom line ending
        # For markdown, separator is: \n\n---\n\n
        # With \r\n it becomes: \r\n\r\n---\r\n\r\n
        assert "\r\n\r\n---\r\n\r\n" in output

    def test_line_endings_in_file_output(self, tmp_path) -> None:
        """Test line endings are preserved when writing to file."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)
            debug: bool = Field(default=False)

        output_file = tmp_path / "test_output.md"
        result = Config.describe(
            output_format="markdown", line_ending="\r\n", output=str(output_file)
        )

        # File should exist
        assert output_file.exists()

        # Read file content in binary mode to preserve line endings
        content = output_file.read_bytes()

        # Should contain Windows line endings
        assert b"\r\n" in content

        # Return value should match file content
        assert result.encode() == content

    def test_different_line_endings_multiple_configs_table(self) -> None:
        """Test custom line endings with multiple configs in table format."""

        class AppConfig(DotEnvConfig):
            port: int = Field(default=8000)

        class DbConfig(DotEnvConfig):
            url: str = Field()

        # Test with Unix line endings
        output_unix = describe_configs(
            [AppConfig, DbConfig], output_format="table", line_ending="\n"
        )
        assert "\n" in output_unix
        assert "\r\n" not in output_unix

        # Test with Windows line endings
        output_windows = describe_configs(
            [AppConfig, DbConfig], output_format="table", line_ending="\r\n"
        )
        assert "\r\n" in output_windows

    def test_line_endings_with_empty_config(self) -> None:
        """Test line endings with empty config class."""

        class EmptyConfig(DotEnvConfig):
            pass

        output = EmptyConfig.describe(output_format="table", line_ending="\r\n")

        # Should contain custom line endings
        assert "\r\n" in output
        assert "No fields defined" in output

    def test_line_endings_consistency_across_formats(self) -> None:
        """Test that custom line endings are consistent across all formats."""

        class Config(DotEnvConfig):
            port: int = Field(default=8000)
            debug: bool = Field(default=False)

        # Test each format with Windows line endings
        for fmt in ["table", "markdown", "html", "dotenv"]:
            output = Config.describe(output_format=fmt, line_ending="\r\n")
            assert "\r\n" in output, f"Format {fmt} should contain \\r\\n line endings"

    def test_unix_line_endings_in_describe_configs_json(self) -> None:
        """Test Unix line endings in describe_configs with JSON format."""

        class Config1(DotEnvConfig):
            port: int = Field(default=8000)

        class Config2(DotEnvConfig):
            debug: bool = Field(default=False)

        output = describe_configs([Config1, Config2], output_format="json", line_ending="\n")

        # JSON should be parseable
        data = json.loads(output)
        assert len(data) == 2

        # Should contain Unix line endings
        assert "\n" in output
        assert "\r\n" not in output


class TestComprehensiveIntegration:
    """Comprehensive integration tests with all features combined."""

    def test_complex_config_all_features(self) -> None:
        """Test describing config with all feature types combined."""

        class ComplexConfig(DotEnvConfig):
            env_prefix = "APP_"

            # Required field with alias and constraints
            api_key: str = Field(
                alias="API_SECRET", min_length=32, description="API authentication key"
            )

            # Optional with numeric constraints
            port: int | None = Field(default=8000, ge=1, le=65535, description="Server port number")

            # Collection with defaults and constraints
            tags: list[str] = Field(
                default_factory=list,
                min_items=0,
                max_items=10,
                description="Service tags for categorization",
            )

            # Secret type with constraints
            password: SecretStr = Field(
                default=SecretStr("default-password"),
                min_length=8,
                max_length=64,
                description="Database password",
            )

            # String with regex pattern
            environment: str = Field(
                default="development",
                regex=r"^(development|staging|production)$",
                description="Runtime environment",
            )

            # Boolean with default
            debug: bool = Field(default=False, description="Enable debug mode")

        # Test table format
        output = ComplexConfig.describe()

        # Verify all fields present
        assert "API_SECRET" in output
        assert "APP_PORT" in output
        assert "APP_TAGS" in output
        assert "APP_PASSWORD" in output
        assert "APP_ENVIRONMENT" in output
        assert "APP_DEBUG" in output

        # Verify types
        assert "str" in output
        assert "int | None" in output
        assert "list[str]" in output
        assert "SecretStr" in output
        assert "bool" in output

        # Verify constraints
        assert "min_length=32" in output
        assert "ge=1" in output
        assert "le=65535" in output
        assert "min_items=0" in output
        assert "max_items=10" in output
        assert "regex=" in output

        # Verify security: password default should be masked
        assert "<secret>" in output
        assert "default-password" not in output

        # Verify descriptions are present
        assert "API authentication key" in output
        assert "Server port" in output
        assert "Service tags" in output

        # Verify defaults
        assert "8000" in output
        assert "[]" in output  # list default_factory
        assert "development" in output
        assert "False" in output

    def test_complex_config_json_format(self) -> None:
        """Test complex config in JSON format with full data."""

        class ComplexConfig(DotEnvConfig):
            api_key: str = Field(min_length=32, description="API key")
            port: int = Field(default=8000, ge=1, le=65535)
            tags: list[str] = Field(default_factory=list)
            password: SecretStr = Field(default=SecretStr("secret"))

        output = ComplexConfig.describe(output_format="json")
        data = json.loads(output)

        # Verify structure
        assert data["class_name"] == "ComplexConfig"
        assert len(data["fields"]) == 4

        # Verify field data
        api_key_field = next(f for f in data["fields"] if f["field_name"] == "api_key")
        assert api_key_field["required"] is True
        assert "min_length=32" in api_key_field["constraints"]

        port_field = next(f for f in data["fields"] if f["field_name"] == "port")
        assert port_field["default"] == "8000"

        password_field = next(f for f in data["fields"] if f["field_name"] == "password")
        assert password_field["default"] == "<secret>"

    def test_complex_config_markdown_format(self) -> None:
        """Test complex config in markdown format."""

        class ComplexConfig(DotEnvConfig):
            api_key: str = Field(description="API key")
            port: int = Field(default=8000)

        output = ComplexConfig.describe(output_format="markdown")

        # Verify markdown structure
        assert "## ComplexConfig" in output
        assert "|" in output
        assert "---" in output or "|-" in output

        # Verify content (markdown escapes underscores)
        assert "API_KEY" in output or "API\\_KEY" in output
        assert "PORT" in output

    def test_multiple_configs_integration(self) -> None:
        """Test describing multiple complex configs together."""

        class AppConfig(DotEnvConfig):
            env_prefix = "APP_"
            port: int = Field(default=8000, ge=1, le=65535)
            debug: bool = Field(default=False)

        class DatabaseConfig(DotEnvConfig):
            env_prefix = "DB_"
            url: str = Field(description="Database connection URL")
            password: SecretStr = Field(default=SecretStr("secret"))
            pool_size: int = Field(default=10, ge=1, le=100)

        class CacheConfig(DotEnvConfig):
            env_prefix = "CACHE_"
            host: str = Field(default="localhost")
            port: int = Field(default=6379)
            ttl: int = Field(default=3600, ge=0)

        # Test table format with multiple configs
        output = describe_configs([AppConfig, DatabaseConfig, CacheConfig])

        # Verify all config classes present
        assert "AppConfig" in output
        assert "DatabaseConfig" in output
        assert "CacheConfig" in output

        # Verify fields from each config
        assert "APP_PORT" in output
        assert "APP_DEBUG" in output
        assert "DB_URL" in output
        assert "DB_PASSWORD" in output
        assert "DB_POOL_SIZE" in output
        assert "CACHE_HOST" in output
        assert "CACHE_PORT" in output
        assert "CACHE_TTL" in output

        # Verify secret masking works across configs
        assert "<secret>" in output
        assert "secret" not in output or output.count("secret") == 1  # Only in field name

        # Test JSON format with multiple configs
        json_output = describe_configs(
            [AppConfig, DatabaseConfig, CacheConfig], output_format="json"
        )
        json_data = json.loads(json_output)

        assert isinstance(json_data, list)
        assert len(json_data) == 3
        assert json_data[0]["class_name"] == "AppConfig"
        assert json_data[1]["class_name"] == "DatabaseConfig"
        assert json_data[2]["class_name"] == "CacheConfig"
