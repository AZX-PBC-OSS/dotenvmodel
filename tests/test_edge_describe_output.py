"""Tests for describe() output correctness across all types."""

from datetime import timedelta
from enum import Enum
from pathlib import Path

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import HttpUrl, Json, PostgresDsn, SecretStr


class TestDescribeTypeNames:
    """Test that type names are displayed correctly in describe() output."""

    def test_tuple_ellipsis_not_shown_as_Ellipsis(self) -> None:
        class Config(DotEnvConfig):
            coords: tuple[str, ...] = Field()

        table = Config.describe()
        assert "tuple[str, ...]" in table
        assert "Ellipsis" not in table

    def test_json_dict_type_name_clean(self) -> None:
        class Config(DotEnvConfig):
            flags: Json[dict] = Field(default_factory=dict)

        table = Config.describe()
        assert "Json[dict]" in table
        assert "<class 'dict'>" not in table

    def test_json_list_type_name_clean(self) -> None:
        class Config(DotEnvConfig):
            data: Json[list] = Field(default_factory=list)

        table = Config.describe()
        assert "Json[list]" in table
        assert "<class 'list'>" not in table

    def test_json_typed_subscript_clean(self) -> None:
        class Config(DotEnvConfig):
            flags: Json[dict[str, bool]] = Field(default_factory=dict)

        table = Config.describe()
        assert "Json[dict[str, bool]]" in table

    def test_timedelta_default_not_repr(self) -> None:
        class Config(DotEnvConfig):
            ttl: timedelta = Field(default=timedelta(hours=1))

        table = Config.describe()
        assert "1:00:00" in table
        assert "datetime.timedelta" not in table

    def test_path_default_clean(self) -> None:
        class Config(DotEnvConfig):
            data_dir: Path = Field(default=Path("/data"))

        table = Config.describe()
        assert "Path('/data')" in table
        assert "PosixPath" not in table

    def test_enum_shows_values_in_type_name(self) -> None:
        class LogLevel(Enum):
            DEBUG = "debug"
            INFO = "info"

        class Config(DotEnvConfig):
            level: LogLevel = Field(default=LogLevel.DEBUG)

        table = Config.describe()
        assert "LogLevel" in table
        assert "debug" in table
        assert "info" in table


class TestGenerateEnvExampleTypeNames:
    """Test that type names are correct in generate_env_example() output."""

    def test_tuple_ellipsis_in_env_example(self) -> None:
        class Config(DotEnvConfig):
            coords: tuple[str, ...] = Field()

        example = Config.generate_env_example()
        assert "tuple[str, ...]" in example
        assert "Ellipsis" not in example

    def test_json_dict_in_env_example(self) -> None:
        class Config(DotEnvConfig):
            flags: Json[dict] = Field(default_factory=dict)

        example = Config.generate_env_example()
        assert "Json[dict]" in example
        assert "<class 'dict'>" not in example

    def test_timedelta_default_in_env_example(self) -> None:
        class Config(DotEnvConfig):
            ttl: timedelta = Field(default=timedelta(minutes=30))

        example = Config.generate_env_example()
        assert "0:30:00" in example
        assert "datetime.timedelta" not in example


class TestDescribeJsonFormat:
    """Test that JSON describe output has correct field structure."""

    def test_json_output_has_type_name(self) -> None:
        import json

        class Config(DotEnvConfig):
            name: str = Field()
            port: int = Field(default=8000)

        output = json.loads(Config.describe(output_format="json"))
        assert "fields" in output
        assert len(output["fields"]) == 2
        for field in output["fields"]:
            assert "type_name" in field
            assert "env_var" in field
            assert "required" in field
            assert "default" in field

    def test_json_output_all_types(self) -> None:
        import json

        class Config(DotEnvConfig):
            name: str = Field()
            port: int = Field(default=8000)
            secret: SecretStr = Field()
            url: HttpUrl = Field()
            db: PostgresDsn = Field()
            flags: Json[dict[str, bool]] = Field(default_factory=dict)
            ttl: timedelta = Field(default=timedelta(hours=1))
            path: Path = Field(default=Path("/data"))

        output = json.loads(Config.describe(output_format="json"))
        type_names = {f["type_name"] for f in output["fields"]}
        assert "str" in type_names
        assert "int" in type_names
        assert "SecretStr" in type_names
        assert "HttpUrl" in type_names
        assert "PostgresDsn" in type_names
        assert "Json[dict[str, bool]]" in type_names
        assert "timedelta" in type_names
        assert "Path" in type_names
