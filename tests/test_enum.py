"""Tests for Python Enum support in DotEnvConfig."""

from enum import Enum, IntEnum

import pytest

from dotenvmodel import DotEnvConfig, Field, MissingFieldError, TypeCoercionError


class LogLevel(str, Enum):  # noqa: UP042
    """String-based enum for log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Environment(str, Enum):  # noqa: UP042
    """String-based enum for environments."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Priority(int, Enum):
    """Integer-based enum for priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Status(str, Enum):  # noqa: UP042
    """Enum with mixed-case names."""

    Active = "active"
    Inactive = "inactive"
    Pending = "pending"


class TestBasicEnumSupport:
    """Test basic enum coercion functionality."""

    def test_string_enum_by_value(self) -> None:
        """Test string-based enum coercion by value."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        config = Config.load_from_dict({"LOG_LEVEL": "debug"})
        assert config.log_level == LogLevel.DEBUG
        assert isinstance(config.log_level, LogLevel)
        assert config.log_level.value == "debug"
        assert config.log_level.name == "DEBUG"

    def test_string_enum_by_name_uppercase(self) -> None:
        """Test string-based enum coercion by name (uppercase)."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        config = Config.load_from_dict({"LOG_LEVEL": "DEBUG"})
        assert config.log_level == LogLevel.DEBUG
        assert config.log_level.value == "debug"

    def test_string_enum_by_value_lowercase(self) -> None:
        """Test string-based enum coercion by value (lowercase).

        Note: 'info' matches LogLevel.INFO.value, not the name 'INFO'.
        Value matching is tried first, then name matching (case-insensitive).
        """

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        config = Config.load_from_dict({"LOG_LEVEL": "info"})
        assert config.log_level == LogLevel.INFO

    def test_string_enum_by_name_mixedcase(self) -> None:
        """Test string-based enum coercion by name (mixed case)."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        config = Config.load_from_dict({"LOG_LEVEL": "WaRnInG"})
        assert config.log_level == LogLevel.WARNING

    def test_int_enum_by_value(self) -> None:
        """Test integer-based enum coercion by value."""

        class Config(DotEnvConfig):
            priority: Priority = Field()

        config = Config.load_from_dict({"PRIORITY": "3"})
        assert config.priority == Priority.HIGH
        assert isinstance(config.priority, Priority)
        assert config.priority.value == 3
        assert config.priority.name == "HIGH"

    def test_int_enum_by_name(self) -> None:
        """Test integer-based enum coercion by name."""

        class Config(DotEnvConfig):
            priority: Priority = Field()

        config = Config.load_from_dict({"PRIORITY": "CRITICAL"})
        assert config.priority == Priority.CRITICAL
        assert config.priority.value == 4

    def test_enum_with_default(self) -> None:
        """Test enum field with default value."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)

        config = Config.load_from_dict({})
        assert config.log_level == LogLevel.INFO

    def test_enum_override_default(self) -> None:
        """Test overriding enum default value."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)

        config = Config.load_from_dict({"LOG_LEVEL": "error"})
        assert config.log_level == LogLevel.ERROR

    def test_required_enum(self) -> None:
        """Test required enum field (no default)."""

        class Config(DotEnvConfig):
            environment: Environment = Field()

        config = Config.load_from_dict({"ENVIRONMENT": "prod"})
        assert config.environment == Environment.PROD

    def test_optional_enum_with_none(self) -> None:
        """Test optional enum field with None value."""

        class Config(DotEnvConfig):
            fallback_level: LogLevel | None = Field(default=None)

        config = Config.load_from_dict({})
        assert config.fallback_level is None

    def test_optional_enum_with_value(self) -> None:
        """Test optional enum field with actual value."""

        class Config(DotEnvConfig):
            fallback_level: LogLevel | None = Field(default=None)

        config = Config.load_from_dict({"FALLBACK_LEVEL": "warning"})
        assert config.fallback_level == LogLevel.WARNING

    def test_multiple_enum_fields(self) -> None:
        """Test config with multiple different enum fields."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)
            environment: Environment = Field()
            priority: Priority = Field(default=Priority.MEDIUM)

        config = Config.load_from_dict(
            {"LOG_LEVEL": "debug", "ENVIRONMENT": "staging", "PRIORITY": "1"}
        )
        assert config.log_level == LogLevel.DEBUG
        assert config.environment == Environment.STAGING
        assert config.priority == Priority.LOW


class TestEnumErrorCases:
    """Test error handling for enum fields."""

    def test_invalid_enum_value(self) -> None:
        """Test that invalid enum value raises TypeCoercionError."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"LOG_LEVEL": "trace"})

        assert "Invalid LogLevel value" in str(exc_info.value)
        assert "debug, info, warning, error" in str(exc_info.value)
        assert "DEBUG, INFO, WARNING, ERROR" in str(exc_info.value)

    def test_none_value_for_required_enum(self) -> None:
        """Test that None value for required enum raises error."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        with pytest.raises(MissingFieldError) as exc_info:
            Config.load_from_dict({})

        assert "LOG_LEVEL" in str(exc_info.value)

    def test_empty_string_for_required_enum(self) -> None:
        """Test that empty string for required enum raises error."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"LOG_LEVEL": ""})

        assert "Value cannot be None or empty" in str(exc_info.value)

    def test_invalid_int_enum_value(self) -> None:
        """Test that invalid integer enum value raises error."""

        class Config(DotEnvConfig):
            priority: Priority = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"PRIORITY": "99"})

        assert "Invalid Priority value" in str(exc_info.value)
        assert "1, 2, 3, 4" in str(exc_info.value)

    def test_error_message_includes_valid_values(self) -> None:
        """Test that error message includes all valid enum values."""

        class Config(DotEnvConfig):
            environment: Environment = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"ENVIRONMENT": "local"})

        error_msg = str(exc_info.value)
        assert "dev" in error_msg
        assert "staging" in error_msg
        assert "prod" in error_msg


class TestEnumEdgeCases:
    """Test edge cases for enum handling."""

    def test_enum_with_mixed_case_names(self) -> None:
        """Test enum with mixed-case member names."""

        class Config(DotEnvConfig):
            status: Status = Field()

        # Match by value
        config = Config.load_from_dict({"STATUS": "active"})
        assert config.status == Status.Active

        # Match by name (case-insensitive)
        config2 = Config.load_from_dict({"STATUS": "INACTIVE"})
        assert config2.status == Status.Inactive

    def test_enum_with_description(self) -> None:
        """Test enum field with description."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(description="Logging level for application")

        config = Config.load_from_dict({"LOG_LEVEL": "info"})
        assert config.log_level == LogLevel.INFO

    def test_enum_with_alias(self) -> None:
        """Test enum field with alias."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(alias="LOGGING_LEVEL")

        config = Config.load_from_dict({"LOGGING_LEVEL": "error"})
        assert config.log_level == LogLevel.ERROR

    def test_enum_with_env_prefix(self) -> None:
        """Test enum field with env_prefix."""

        class Config(DotEnvConfig):
            env_prefix = "APP_"
            log_level: LogLevel = Field()

        config = Config.load_from_dict({"APP_LOG_LEVEL": "warning"})
        assert config.log_level == LogLevel.WARNING

    def test_int_enum_class(self) -> None:
        """Test IntEnum subclass support."""

        class IntPriority(IntEnum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3

        class Config(DotEnvConfig):
            priority: IntPriority = Field()

        config = Config.load_from_dict({"PRIORITY": "2"})
        assert config.priority == IntPriority.MEDIUM
        assert isinstance(config.priority, IntPriority)
        assert config.priority.value == 2


class TestEnumIntegration:
    """Test enum integration with other features."""

    def test_enum_with_reload(self, monkeypatch) -> None:
        """Test enum field with reload() method."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)

        monkeypatch.setenv("LOG_LEVEL", "debug")
        config = Config.load()
        assert config.log_level == LogLevel.DEBUG

        monkeypatch.setenv("LOG_LEVEL", "error")
        config.reload()
        assert config.log_level == LogLevel.ERROR

    def test_enum_in_describe_output(self) -> None:
        """Test that enum appears correctly in describe() output."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")

        output = Config.describe(output_format="table")
        assert "LogLevel" in output
        # Note: table format may truncate long type names
        assert "debug" in output
        assert "info" in output  # Default value and in type
        assert "choices:" in output

    def test_enum_in_describe_markdown(self) -> None:
        """Test that enum appears correctly in markdown describe() output."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)

        output = Config.describe(output_format="markdown")
        assert "LogLevel" in output
        assert "debug, info, warning, error" in output

    def test_enum_in_describe_dotenv(self) -> None:
        """Test that enum appears correctly in dotenv describe() output."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)

        output = Config.describe(output_format="dotenv")
        assert "LogLevel" in output
        assert "LOG_LEVEL" in output

    def test_enum_constraints_in_describe(self) -> None:
        """Test that enum choices appear in constraints column."""

        class Config(DotEnvConfig):
            environment: Environment = Field()

        output = Config.describe(output_format="table")
        assert "choices:" in output
        assert "dev" in output
        assert "staging" in output
        assert "prod" in output


class TestEnumWithComplexTypes:
    """Test enum with other type features."""

    def test_optional_enum_union_syntax(self) -> None:
        """Test optional enum using Union syntax."""

        class Config(DotEnvConfig):
            log_level: LogLevel | None = Field(default=None)

        config = Config.load_from_dict({})
        assert config.log_level is None

        config2 = Config.load_from_dict({"LOG_LEVEL": "debug"})
        assert config2.log_level == LogLevel.DEBUG

    def test_enum_field_access(self) -> None:
        """Test accessing enum field properties."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field(default=LogLevel.INFO)

        config = Config.load_from_dict({"LOG_LEVEL": "warning"})

        # Test we get proper enum instance
        assert config.log_level.value == "warning"
        assert config.log_level.name == "WARNING"
        assert isinstance(config.log_level, Enum)
        assert isinstance(config.log_level, LogLevel)

    def test_enum_comparison(self) -> None:
        """Test enum comparison operations."""

        class Config(DotEnvConfig):
            log_level: LogLevel = Field()

        config = Config.load_from_dict({"LOG_LEVEL": "error"})

        assert config.log_level == LogLevel.ERROR
        assert config.log_level != LogLevel.INFO
        assert config.log_level is LogLevel.ERROR


class TestEnumInCollections:
    """Test enum support in collection types."""

    def test_list_of_enums(self) -> None:
        """Test list[Enum] coercion."""

        class Config(DotEnvConfig):
            allowed_levels: list[LogLevel] = Field()

        config = Config.load_from_dict({"ALLOWED_LEVELS": "debug,info,error"})
        assert config.allowed_levels == [LogLevel.DEBUG, LogLevel.INFO, LogLevel.ERROR]
        assert all(isinstance(level, LogLevel) for level in config.allowed_levels)

    def test_list_of_enums_by_name(self) -> None:
        """Test list[Enum] coercion using names."""

        class Config(DotEnvConfig):
            levels: list[LogLevel] = Field()

        config = Config.load_from_dict({"LEVELS": "DEBUG,INFO,WARNING"})
        assert config.levels == [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING]

    def test_list_of_enums_invalid_element(self) -> None:
        """Test list[Enum] with invalid element raises proper error."""

        class Config(DotEnvConfig):
            levels: list[LogLevel] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"LEVELS": "debug,invalid,info"})

        assert "Failed to coerce list element" in str(exc_info.value)
        assert "invalid" in str(exc_info.value).lower()

    def test_set_of_enums(self) -> None:
        """Test set[Enum] coercion."""

        class Config(DotEnvConfig):
            unique_envs: set[Environment] = Field()

        config = Config.load_from_dict({"UNIQUE_ENVS": "dev,staging,dev"})
        assert config.unique_envs == {Environment.DEV, Environment.STAGING}
        assert len(config.unique_envs) == 2

    def test_list_of_int_enums(self) -> None:
        """Test list[IntEnum] coercion."""

        class Config(DotEnvConfig):
            priorities: list[Priority] = Field()

        config = Config.load_from_dict({"PRIORITIES": "1,3,4"})
        assert config.priorities == [Priority.LOW, Priority.HIGH, Priority.CRITICAL]

    def test_empty_list_of_enums(self) -> None:
        """Test empty list[Enum] coercion."""

        class Config(DotEnvConfig):
            levels: list[LogLevel] = Field()

        config = Config.load_from_dict({"LEVELS": ""})
        assert config.levels == []


class TestEnumWithDuplicateValues:
    """Test enum with duplicate values (aliases)."""

    def test_enum_with_value_aliases(self) -> None:
        """Test enum with duplicate values (aliases) returns canonical member."""

        class StatusWithAliases(str, Enum):  # noqa: UP042
            ACTIVE = "active"
            RUNNING = "active"  # Alias for ACTIVE
            IDLE = "idle"

        class Config(DotEnvConfig):
            status: StatusWithAliases = Field()

        # Should match the canonical member (ACTIVE, not the alias RUNNING)
        config = Config.load_from_dict({"STATUS": "active"})
        assert config.status == StatusWithAliases.ACTIVE
        assert config.status.name == "ACTIVE"

    def test_enum_alias_name_matchable(self) -> None:
        """Test that alias names are matchable via __members__.

        In Python Enums, aliases (members with duplicate values) appear in
        __members__ but not in iteration. We use __members__ for name matching
        so that aliases like "RUNNING" resolve to the canonical member (ACTIVE).
        """

        class StatusWithAliases(str, Enum):  # noqa: UP042
            ACTIVE = "active"
            RUNNING = "active"  # Alias for ACTIVE
            IDLE = "idle"

        class Config(DotEnvConfig):
            status: StatusWithAliases = Field()

        # Alias names ARE matchable - they resolve to the canonical member
        config = Config.load_from_dict({"STATUS": "RUNNING"})
        assert config.status == StatusWithAliases.ACTIVE


class TestOptionalEnumDescribe:
    """Test that Optional[Enum] shows constraints correctly in describe output."""

    def test_optional_enum_shows_choices_in_constraints(self) -> None:
        """Test that Optional[Enum] fields show enum choices in constraints."""

        class Config(DotEnvConfig):
            level: LogLevel | None = Field(default=None)

        output = Config.describe(output_format="table")
        assert "choices:" in output
        # Verify enum values are shown
        assert "debug" in output

    def test_optional_enum_describe_markdown(self) -> None:
        """Test Optional[Enum] in markdown describe output."""

        class Config(DotEnvConfig):
            env: Environment | None = Field(default=None)

        output = Config.describe(output_format="markdown")
        assert "choices:" in output
        assert "dev" in output
