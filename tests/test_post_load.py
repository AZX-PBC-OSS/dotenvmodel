"""Tests for the DotEnvConfig.post_load() model-level hook."""

from pathlib import Path

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    MissingFieldError,
    MultipleValidationErrors,
    ValidationError,
)


class TestPostLoadInvocation:
    """post_load fires on every load path, exactly once per load."""

    def test_fires_on_load_from_dict(self) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            name: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                calls.append("called")
                return None

        Config.load_from_dict({})
        assert calls == ["called"]

    def test_fires_on_load(self, tmp_path: Path) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            name: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                calls.append("called")
                return None

        Config.load(env_dir=tmp_path)
        assert calls == ["called"]

    def test_fires_with_validate_false(self) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            name: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                calls.append("called")
                return None

        Config.load_from_dict({}, validate=False)
        assert calls == ["called"]

    def test_mutation_persists(self) -> None:
        class Config(DotEnvConfig):
            primary: str = Field(default="main")
            secondary: str | None = Field(default=None)

            def post_load(self) -> list[ValidationError] | None:
                if self.secondary is None:
                    self.secondary = self.primary
                return None

        config = Config.load_from_dict({})
        assert config.secondary == "main"

    def test_not_fired_when_field_missing(self) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            required_field: str = Field()

            def post_load(self) -> list[ValidationError] | None:
                calls.append("called")
                return None

        with pytest.raises(MissingFieldError):
            Config.load_from_dict({})
        assert calls == []

    def test_not_fired_when_constraint_fails(self) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            port: int = Field(default=8000, le=65535)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("called")
                return None

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORT": "99999"})
        assert calls == []


class TestPostLoadReturnedErrors:
    """Returned errors follow field-error aggregation semantics."""

    def test_single_error_raised_directly(self) -> None:
        class Config(DotEnvConfig):
            a: int = Field(default=1)
            b: int = Field(default=2)

            def post_load(self) -> list[ValidationError] | None:
                return [
                    ValidationError(
                        field_name="a",
                        value=self.a,
                        error_msg="a must be >= b",
                    )
                ]

        with pytest.raises(ValidationError) as exc_info:
            Config.load_from_dict({})
        assert not isinstance(exc_info.value, MultipleValidationErrors)
        assert exc_info.value.field_name == "a"
        assert exc_info.value.error_msg == "a must be >= b"

    def test_multiple_errors_aggregate(self) -> None:
        class Config(DotEnvConfig):
            a: int = Field(default=1)
            b: int = Field(default=2)

            def post_load(self) -> list[ValidationError] | None:
                return [
                    ValidationError(field_name="a", value=self.a, error_msg="first"),
                    ConstraintViolationError(
                        field_name="b",
                        value=self.b,
                        constraint="post_load",
                        error_msg="second",
                    ),
                ]

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Config.load_from_dict({})
        assert len(exc_info.value.errors) == 2
        assert exc_info.value.errors[0].field_name == "a"
        assert exc_info.value.errors[1].field_name == "b"
        assert isinstance(exc_info.value.errors[1], ConstraintViolationError)

    def test_empty_list_is_success(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                return []

        config = Config.load_from_dict({})
        assert config.name == "x"

    def test_raised_exception_propagates_unchanged(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                raise ValueError("fatal: inconsistent config")

        with pytest.raises(ValueError, match="fatal: inconsistent config"):
            Config.load_from_dict({})
