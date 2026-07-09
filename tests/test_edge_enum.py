"""Edge case tests for Enum handling."""

from enum import Enum, IntEnum, IntFlag, auto

from dotenvmodel import DotEnvConfig, Field


class TestIntEnum:
    """Test IntEnum support."""

    def test_int_enum_by_value(self) -> None:
        class Color(IntEnum):
            RED = 1
            GREEN = 2
            BLUE = 3

        class Config(DotEnvConfig):
            color: Color = Field()

        config = Config.load_from_dict({"COLOR": "1"})
        assert config.color == Color.RED
        assert config.color.value == 1

    def test_int_enum_by_name(self) -> None:
        class Color(IntEnum):
            RED = 1
            GREEN = 2
            BLUE = 3

        class Config(DotEnvConfig):
            color: Color = Field()

        config = Config.load_from_dict({"COLOR": "RED"})
        assert config.color == Color.RED

    def test_int_enum_name_case_insensitive(self) -> None:
        class Color(IntEnum):
            RED = 1
            GREEN = 2
            BLUE = 3

        class Config(DotEnvConfig):
            color: Color = Field()

        config = Config.load_from_dict({"COLOR": "green"})
        assert config.color == Color.GREEN


class TestIntFlagCombined:
    """Test IntFlag with combined values."""

    def test_int_flag_single(self) -> None:
        class Access(IntFlag):
            READ = 4
            WRITE = 2
            EXEC = 1

        class Config(DotEnvConfig):
            access: Access = Field()

        config = Config.load_from_dict({"ACCESS": "4"})
        assert config.access == Access.READ

    def test_int_flag_combined(self) -> None:
        class Access(IntFlag):
            READ = 4
            WRITE = 2
            EXEC = 1

        class Config(DotEnvConfig):
            access: Access = Field()

        config = Config.load_from_dict({"ACCESS": "6"})
        assert config.access == Access.READ | Access.WRITE

    def test_int_flag_all(self) -> None:
        class Access(IntFlag):
            READ = 4
            WRITE = 2
            EXEC = 1

        class Config(DotEnvConfig):
            access: Access = Field()

        config = Config.load_from_dict({"ACCESS": "7"})
        assert config.access == Access.READ | Access.WRITE | Access.EXEC

    def test_int_flag_by_name(self) -> None:
        class Access(IntFlag):
            READ = 4
            WRITE = 2
            EXEC = 1

        class Config(DotEnvConfig):
            access: Access = Field()

        config = Config.load_from_dict({"ACCESS": "READ"})
        assert config.access == Access.READ


class TestEnumAuto:
    """Test Enum with auto() values."""

    def test_auto_by_value(self) -> None:
        class Status(Enum):
            PENDING = auto()
            ACTIVE = auto()
            CLOSED = auto()

        class Config(DotEnvConfig):
            status: Status = Field()

        config = Config.load_from_dict({"STATUS": "1"})
        assert config.status == Status.PENDING

    def test_auto_by_name(self) -> None:
        class Status(Enum):
            PENDING = auto()
            ACTIVE = auto()
            CLOSED = auto()

        class Config(DotEnvConfig):
            status: Status = Field()

        config = Config.load_from_dict({"STATUS": "ACTIVE"})
        assert config.status == Status.ACTIVE


class TestEnumAliases:
    """Test Enum with alias members (duplicate values)."""

    def test_alias_by_value(self) -> None:
        class Role(Enum):
            ADMIN = "admin"
            SUPERUSER = "admin"
            USER = "user"

        class Config(DotEnvConfig):
            role: Role = Field()

        config = Config.load_from_dict({"ROLE": "admin"})
        assert config.role == Role.ADMIN

    def test_alias_by_name(self) -> None:
        class Role(Enum):
            ADMIN = "admin"
            SUPERUSER = "admin"
            USER = "user"

        class Config(DotEnvConfig):
            role: Role = Field()

        config = Config.load_from_dict({"ROLE": "SUPERUSER"})
        assert config.role == Role.ADMIN
        assert config.role.value == "admin"


class TestEnumFloatValues:
    """Test Enum with float values."""

    def test_float_value_by_value(self) -> None:
        class Temp(Enum):
            HOT = 100.5
            COLD = -0.5

        class Config(DotEnvConfig):
            temp: Temp = Field()

        config = Config.load_from_dict({"TEMP": "100.5"})
        assert config.temp == Temp.HOT

    def test_float_value_by_name(self) -> None:
        class Temp(Enum):
            HOT = 100.5
            COLD = -0.5

        class Config(DotEnvConfig):
            temp: Temp = Field()

        config = Config.load_from_dict({"TEMP": "COLD"})
        assert config.temp == Temp.COLD
        assert config.temp.value == -0.5


class TestEnumSpacesInValues:
    """Test Enum with spaces in values."""

    def test_spaces_in_value(self) -> None:
        class LogLevel(Enum):
            DEBUG = "debug mode"
            INFO = "info mode"

        class Config(DotEnvConfig):
            level: LogLevel = Field()

        config = Config.load_from_dict({"LEVEL": "debug mode"})
        assert config.level == LogLevel.DEBUG

    def test_spaces_by_name(self) -> None:
        class LogLevel(Enum):
            DEBUG = "debug mode"
            INFO = "info mode"

        class Config(DotEnvConfig):
            level: LogLevel = Field()

        config = Config.load_from_dict({"LEVEL": "INFO"})
        assert config.level == LogLevel.INFO


class TestEnumDefaultAndOptional:
    """Test Enum with defaults and optional types."""

    def test_enum_default(self) -> None:
        class Status(Enum):
            PENDING = "pending"
            ACTIVE = "active"

        class Config(DotEnvConfig):
            status: Status = Field(default=Status.PENDING)

        config = Config.load_from_dict({})
        assert config.status == Status.PENDING

    def test_optional_enum_none(self) -> None:
        class Status(Enum):
            PENDING = "pending"
            ACTIVE = "active"

        class Config(DotEnvConfig):
            status: Status | None = Field()

        config = Config.load_from_dict({})
        assert config.status is None

    def test_optional_enum_with_value(self) -> None:
        class Status(Enum):
            PENDING = "pending"
            ACTIVE = "active"

        class Config(DotEnvConfig):
            status: Status | None = Field()

        config = Config.load_from_dict({"STATUS": "active"})
        assert config.status == Status.ACTIVE
