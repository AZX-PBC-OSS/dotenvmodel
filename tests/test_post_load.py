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


class TestPostLoadReload:
    """post_load fires on reload() too, re-evaluating the reloaded state."""

    def test_fires_on_reload(self, tmp_path: Path) -> None:
        calls: list[str] = []

        class Config(DotEnvConfig):
            name: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                calls.append("called")
                return None

        config = Config.load(env_dir=tmp_path)
        assert calls == ["called"]

        config.reload()
        assert calls == ["called", "called"]

    def test_reload_returned_error_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The hook re-runs against freshly loaded state on every reload, so
        # flipping an env var between load and reload can turn a passing hook
        # into a failing one.
        class Config(DotEnvConfig):
            name: str = Field(default="x")
            fail: bool = Field(default=False)

            def post_load(self) -> list[ValidationError] | None:
                if self.fail:
                    return [
                        ValidationError(
                            field_name="fail",
                            value=self.fail,
                            error_msg="bad combination",
                        )
                    ]
                return None

        monkeypatch.delenv("FAIL", raising=False)
        config = Config.load(env_dir=tmp_path)
        monkeypatch.setenv("FAIL", "true")
        with pytest.raises(ValidationError, match="bad combination"):
            config.reload()

    def test_failed_reload_leaves_partial_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A failed reload is not atomic: fields already reloaded keep their
        # new values, and hook mutations made before the error persist on the
        # caller-held instance. (WORKER_NAME rather than NAME — some
        # environments export NAME, which would collide with the field.)
        class Config(DotEnvConfig):
            worker_name: str = Field(default="x")
            derived: str | None = Field(default=None)
            fail: bool = Field(default=False)

            def post_load(self) -> list[ValidationError] | None:
                self.derived = f"derived:{self.worker_name}"
                if self.fail:
                    return [
                        ValidationError(
                            field_name="fail",
                            value=self.fail,
                            error_msg="bad combination",
                        )
                    ]
                return None

        monkeypatch.delenv("WORKER_NAME", raising=False)
        monkeypatch.delenv("FAIL", raising=False)
        config = Config.load(env_dir=tmp_path)
        assert config.derived == "derived:x"

        monkeypatch.setenv("WORKER_NAME", "y")
        monkeypatch.setenv("FAIL", "true")
        with pytest.raises(ValidationError, match="bad combination"):
            config.reload()
        # Both the reloaded field value and the hook mutation persist.
        assert config.worker_name == "y"
        assert config.derived == "derived:y"


class TestPostLoadNested:
    """Nested configs fire their own post_load; errors flatten into the parent."""

    def test_nested_hook_fires(self) -> None:
        calls: list[str] = []

        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("inner")
                return None

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

        Outer.load_from_dict({})
        assert calls == ["inner"]

    def test_nested_hook_runs_before_parent(self) -> None:
        calls: list[str] = []

        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("inner")
                return None

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("outer")
                return None

        Outer.load_from_dict({})
        assert calls == ["inner", "outer"]

    def test_single_nested_error_flattens(self) -> None:
        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                return [ValidationError(field_name="port", value=self.port, error_msg="inner bad")]

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

        with pytest.raises(ValidationError) as exc_info:
            Outer.load_from_dict({})
        assert not isinstance(exc_info.value, MultipleValidationErrors)
        assert exc_info.value.field_name == "port"
        assert exc_info.value.error_msg == "inner bad"

    def test_multiple_nested_errors_flatten(self) -> None:
        returned: list[ValidationError] = []

        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                returned.extend(
                    [
                        ValidationError(field_name="port", value=self.port, error_msg="e1"),
                        ConstraintViolationError(
                            field_name="port",
                            value=self.port,
                            constraint="post_load",
                            error_msg="e2",
                        ),
                    ]
                )
                return returned

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Outer.load_from_dict({})
        assert [e.error_msg for e in exc_info.value.errors] == ["e1", "e2"]
        # Flattening preserves the hook's own error objects, not copies.
        assert exc_info.value.errors[0] is returned[0]
        assert exc_info.value.errors[1] is returned[1]

    def test_parent_hook_not_run_when_nested_hook_fails(self) -> None:
        calls: list[str] = []

        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                return [ValidationError(field_name="port", value=self.port, error_msg="inner bad")]

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("outer")
                return None

        with pytest.raises(ValidationError, match="inner bad"):
            Outer.load_from_dict({})
        assert calls == []

    def test_hooks_not_run_when_nested_field_fails(self) -> None:
        # Gating holds at every level: a nested field failure means the nested
        # hook never runs on a dirty state, and the parent's hook never runs.
        calls: list[str] = []

        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1, le=100)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("inner")
                return None

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

            def post_load(self) -> list[ValidationError] | None:
                calls.append("outer")
                return None

        with pytest.raises(ConstraintViolationError):
            Outer.load_from_dict({"INNER_PORT": "999"})
        assert calls == []

    def test_nested_raised_validation_error_aggregates_with_parent_errors(self) -> None:
        # A ValidationError subclass raised (not returned) by a nested hook
        # exits nested._load_fields() inside the parent's _process_field, where
        # the parent's field loop catches it exactly like a nested field
        # failure: with other parent-level errors present it aggregates into
        # MultipleValidationErrors instead of propagating unchanged.
        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                raise ConstraintViolationError(
                    field_name="port",
                    value=self.port,
                    constraint="post_load",
                    error_msg="inner exploded",
                )

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)
            host: str = Field(min_length=3)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Outer.load_from_dict({"OUTER_HOST": "ab"})
        assert len(exc_info.value.errors) == 2
        nested_error = exc_info.value.errors[0]
        assert isinstance(nested_error, ConstraintViolationError)
        assert nested_error.field_name == "port"
        assert nested_error.error_msg == "inner exploded"
        assert exc_info.value.errors[1].field_name == "host"

    def test_nested_raised_non_validation_error_propagates_raw(self) -> None:
        # A non-ValidationError raised by a nested hook is not caught by the
        # parent's field loop: it propagates unchanged, even though a
        # parent-level field failure was genuinely collected first (host is
        # declared before inner, so its error is already in the collection
        # when the nested hook raises).
        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                raise ValueError("fatal: inconsistent config")

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            host: str = Field(min_length=3)
            inner: Inner = Field(default_factory=Inner)

        with pytest.raises(ValueError, match="fatal: inconsistent config") as exc_info:
            Outer.load_from_dict({"OUTER_HOST": "ab"})
        assert not isinstance(exc_info.value, MultipleValidationErrors)

    def test_nested_raised_multiple_validation_errors_flattens(self) -> None:
        # A MultipleValidationErrors raised (not returned) by a nested hook is
        # caught by the parent's dedicated handler and flattened: its members
        # join the parent's collection alongside ordinary field failures, with
        # no MVE nested inside the aggregate.
        raised: list[ValidationError] = []

        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                raised.extend(
                    [
                        ValidationError(field_name="port", value=self.port, error_msg="e1"),
                        ConstraintViolationError(
                            field_name="port",
                            value=self.port,
                            constraint="post_load",
                            error_msg="e2",
                        ),
                    ]
                )
                raise MultipleValidationErrors(raised)

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)
            host: str = Field(min_length=3)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Outer.load_from_dict({"OUTER_HOST": "ab"})
        assert [e.error_msg for e in exc_info.value.errors] == [
            "e1",
            "e2",
            "String must be at least 3 characters long",
        ]
        # Flattening preserves the hook's own error objects, not copies.
        assert exc_info.value.errors[0] is raised[0]
        assert exc_info.value.errors[1] is raised[1]
        assert exc_info.value.errors[2].field_name == "host"
        assert not any(isinstance(e, MultipleValidationErrors) for e in exc_info.value.errors)

    def test_nested_raised_solo_multiple_validation_errors_unwraps(self) -> None:
        # A nested-raised MultipleValidationErrors holding a single error goes
        # through the same flattening: the parent's collection ends up with
        # one member, which is re-raised as-is — the caller sees the bare
        # ValidationError, not the MVE wrapper.
        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                raise MultipleValidationErrors(
                    [
                        ConstraintViolationError(
                            field_name="port",
                            value=self.port,
                            constraint="post_load",
                            error_msg="inner bad",
                        )
                    ]
                )

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Outer.load_from_dict({})
        assert not isinstance(exc_info.value, MultipleValidationErrors)
        assert exc_info.value.field_name == "port"
        assert exc_info.value.error_msg == "inner bad"

    def test_nested_returned_error_aggregates_with_parent_errors(self) -> None:
        # Return-style composition: the nested hook's returned error flattens
        # into the parent's collection alongside an ordinary parent field
        # failure, one MultipleValidationErrors in field-processing order.
        class Inner(DotEnvConfig):
            env_prefix = "INNER_"
            port: int = Field(default=1)

            def post_load(self) -> list[ValidationError] | None:
                return [ValidationError(field_name="port", value=self.port, error_msg="inner bad")]

        class Outer(DotEnvConfig):
            env_prefix = "OUTER_"
            inner: Inner = Field(default_factory=Inner)
            host: str = Field(min_length=3)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Outer.load_from_dict({"OUTER_HOST": "ab"})
        assert len(exc_info.value.errors) == 2
        assert exc_info.value.errors[0].field_name == "port"
        assert exc_info.value.errors[0].error_msg == "inner bad"
        assert exc_info.value.errors[1].field_name == "host"
