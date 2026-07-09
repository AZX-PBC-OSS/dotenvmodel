"""Edge case tests for number formats."""

from decimal import Decimal

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.exceptions import TypeCoercionError


class TestFloatEdgeCases:
    """Test float coercion edge cases."""

    def test_scientific_notation_positive(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "1e5"})
        assert config.f == 100000.0

    def test_scientific_notation_negative_exponent(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "1.5e-3"})
        assert config.f == 0.0015

    def test_scientific_notation_uppercase(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "1E10"})
        assert config.f == 10000000000.0

    def test_negative_float(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "-3.14"})
        assert config.f == -3.14

    def test_leading_dot(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": ".5"})
        assert config.f == 0.5

    def test_trailing_dot(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "5."})
        assert config.f == 5.0

    def test_zero_float(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "0.0"})
        assert config.f == 0.0

    def test_very_small_float(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "1e-300"})
        assert config.f == 1e-300

    def test_positive_sign(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": "+3.14"})
        assert config.f == 3.14

    def test_whitespace_trimmed(self) -> None:
        class Config(DotEnvConfig):
            f: float = Field()

        config = Config.load_from_dict({"F": " 3.14 "})
        assert config.f == 3.14


class TestIntEdgeCases:
    """Test int coercion edge cases."""

    def test_negative_int(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": "-42"})
        assert config.i == -42

    def test_leading_zeros(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": "007"})
        assert config.i == 7

    def test_all_zeros(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": "000"})
        assert config.i == 0

    def test_underscore_separators(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": "1_000_000"})
        assert config.i == 1000000

    def test_positive_sign(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": "+42"})
        assert config.i == 42

    def test_whitespace_trimmed(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": " 42 "})
        assert config.i == 42

    def test_very_large_int(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        config = Config.load_from_dict({"I": "999999999999999999999"})
        assert config.i == 999999999999999999999

    def test_hex_fails(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"I": "0x1F"})

    def test_binary_fails(self) -> None:
        class Config(DotEnvConfig):
            i: int = Field()

        with pytest.raises(TypeCoercionError):
            Config.load_from_dict({"I": "0b101"})


class TestDecimalEdgeCases:
    """Test Decimal coercion edge cases."""

    def test_high_precision(self) -> None:
        class Config(DotEnvConfig):
            d: Decimal = Field()

        config = Config.load_from_dict({"D": "0.123456789012345678901234567890"})
        assert config.d == Decimal("0.123456789012345678901234567890")

    def test_scientific_notation(self) -> None:
        class Config(DotEnvConfig):
            d: Decimal = Field()

        config = Config.load_from_dict({"D": "1.5e10"})
        assert config.d == Decimal("1.5E+10")

    def test_very_large_decimal(self) -> None:
        class Config(DotEnvConfig):
            d: Decimal = Field()

        config = Config.load_from_dict({"D": "999999999999999999999"})
        assert config.d == Decimal("999999999999999999999")

    def test_negative_decimal(self) -> None:
        class Config(DotEnvConfig):
            d: Decimal = Field()

        config = Config.load_from_dict({"D": "-0.001"})
        assert config.d == Decimal("-0.001")

    def test_positive_sign(self) -> None:
        class Config(DotEnvConfig):
            d: Decimal = Field()

        config = Config.load_from_dict({"D": "+3.14"})
        assert config.d == Decimal("3.14")
