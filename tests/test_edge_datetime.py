"""Edge case tests for datetime and timedelta handling."""

from datetime import UTC, datetime, timedelta

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.exceptions import TypeCoercionError


class TestDatetimeEdgeCases:
    """Test datetime coercion edge cases."""

    def test_timezone_utc_z_suffix(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        config = Config.load_from_dict({"DT": "2025-01-15T10:30:00Z"})
        assert config.dt.tzinfo is not None
        assert config.dt == datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

    def test_timezone_positive_offset(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        config = Config.load_from_dict({"DT": "2025-01-15T10:30:00+05:00"})
        assert config.dt.tzinfo is not None
        assert config.dt.utcoffset() == timedelta(hours=5)

    def test_timezone_negative_offset(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        config = Config.load_from_dict({"DT": "2025-01-15T10:30:00-08:00"})
        assert config.dt.tzinfo is not None
        assert config.dt.utcoffset() == timedelta(hours=-8)

    def test_microseconds(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        config = Config.load_from_dict({"DT": "2025-01-15T10:30:00.123456"})
        assert config.dt.microsecond == 123456

    def test_date_only(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        config = Config.load_from_dict({"DT": "2025-01-15"})
        assert config.dt == datetime(2025, 1, 15, 0, 0, 0)  # noqa: DTZ001

    def test_time_only_fails(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"DT": "10:30:00"})

    def test_invalid_datetime(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"DT": "not-a-date"})

    def test_datetime_with_validation(self) -> None:
        class Config(DotEnvConfig):
            dt: datetime = Field()

        config = Config.load_from_dict({"DT": "2025-06-15T12:00:00Z"})
        assert config.dt.month == 6


class TestTimedeltaEdgeCases:
    """Test timedelta parsing edge cases."""

    def test_negative_minutes(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "-30m"})
        assert config.td == timedelta(minutes=-30)

    def test_negative_hours(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "-2h"})
        assert config.td == timedelta(hours=-2)

    def test_milliseconds(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "500ms"})
        assert config.td == timedelta(milliseconds=500)

    def test_float_hours(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "1.5h"})
        assert config.td == timedelta(hours=1, minutes=30)

    def test_half_day(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "0.5d"})
        assert config.td == timedelta(hours=12)

    def test_combined_units(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "1h30m45s"})
        assert config.td == timedelta(hours=1, minutes=30, seconds=45)

    def test_weeks_and_days(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "2w3d"})
        assert config.td == timedelta(weeks=2, days=3)

    def test_plain_seconds_float(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "90.5"})
        assert config.td == timedelta(seconds=90, milliseconds=500)

    def test_large_days(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "999d"})
        assert config.td == timedelta(days=999)

    def test_zero_seconds(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "0s"})
        assert config.td == timedelta(seconds=0)

    def test_zero_milliseconds(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        config = Config.load_from_dict({"TD": "0ms"})
        assert config.td == timedelta(milliseconds=0)

    def test_invalid_format(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"TD": "abc"})

    def test_invalid_unit(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"TD": "1x"})

    def test_unit_only(self) -> None:
        class Config(DotEnvConfig):
            td: timedelta = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"TD": "h"})
