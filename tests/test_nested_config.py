"""Tests for nested DotEnvConfig fields (a config field whose type is itself
a DotEnvConfig subclass, e.g. `oidc: OIDCSettings = Field(default_factory=OIDCSettings)`).

Regression coverage for a bug where a nested config's own declared field
defaults silently resolved to None: the metaclass resets every field's
class attribute to None at class-definition time (to avoid sharing mutable
FieldInfo objects across instances) and relies on _load_fields() being
called at instantiation to repopulate them. A nested field's default_factory
bare-constructs the nested class without ever calling _load_fields() on it,
so every one of its fields stayed at that reset-to-None class attribute.
"""

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.exceptions import ConstraintViolationError, MultipleValidationErrors


class Nested(DotEnvConfig):
    env_prefix = "APP_NESTED_"
    port: int = Field(default=10, ge=1, le=100)
    name: str = Field(default="nested-default")
    enabled: bool = Field(default=True)


class Outer(DotEnvConfig):
    env_prefix = "APP_"
    top: str = Field(default="top-default")
    nested: Nested = Field(default_factory=Nested)


class TestNestedConfigDefaults:
    def test_load_from_dict_resolves_nested_defaults(self) -> None:
        config = Outer.load_from_dict({})

        assert config.top == "top-default"
        assert config.nested.port == 10
        assert config.nested.name == "nested-default"
        assert config.nested.enabled is True

    def test_load_resolves_nested_defaults_with_empty_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("APP_TOP", raising=False)
        monkeypatch.delenv("APP_NESTED_PORT", raising=False)
        monkeypatch.delenv("APP_NESTED_NAME", raising=False)
        monkeypatch.delenv("APP_NESTED_ENABLED", raising=False)

        config = Outer.load()

        assert config.nested.port == 10
        assert config.nested.name == "nested-default"
        assert config.nested.enabled is True

    def test_nested_default_is_a_real_instance_not_none(self) -> None:
        config = Outer.load_from_dict({})

        assert isinstance(config.nested, Nested)
        assert config.nested.port is not None
        assert config.nested.name is not None
        assert config.nested.enabled is not None


class TestNestedConfigOverrides:
    def test_env_var_with_nested_prefix_overrides_default(self) -> None:
        config = Outer.load_from_dict({"APP_NESTED_PORT": "55"})

        assert config.nested.port == 55
        # Sibling nested fields keep their own defaults
        assert config.nested.name == "nested-default"

    def test_nested_prefix_is_independent_of_parent_prefix(self) -> None:
        config = Outer.load_from_dict({"APP_TOP": "override", "APP_NESTED_NAME": "override-nested"})

        assert config.top == "override"
        assert config.nested.name == "override-nested"

    def test_env_var_named_after_outer_field_does_not_override_nested(self) -> None:
        # Setting "APP_NESTED" (the outer field's own env var name) should
        # not be interpreted as a value for the nested config as a whole —
        # nested configs are never scalar-coerced.
        config = Outer.load_from_dict({"APP_NESTED": "not-a-real-value"})

        assert isinstance(config.nested, Nested)
        assert config.nested.port == 10


class TestNestedConfigValidation:
    def test_invalid_nested_field_raises_constraint_violation(self) -> None:
        with pytest.raises(ConstraintViolationError):
            Outer.load_from_dict({"APP_NESTED_PORT": "999"})

    def test_invalid_nested_and_outer_field_aggregate_into_multiple_errors(self) -> None:
        class OuterWithConstraint(DotEnvConfig):
            env_prefix = "APP_"
            top: int = Field(default=1, ge=1, le=10)
            nested: Nested = Field(default_factory=Nested)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            OuterWithConstraint.load_from_dict({"APP_TOP": "999", "APP_NESTED_PORT": "999"})

        assert len(exc_info.value.errors) == 2
        field_names = {e.field_name for e in exc_info.value.errors}
        assert field_names == {"top", "port"}

    def test_validate_false_skips_nested_validation(self) -> None:
        config = Outer.load_from_dict({"APP_NESTED_PORT": "999"}, validate=False)

        assert config.nested.port == 999

    def test_multiple_invalid_fields_within_single_nested_config_aggregate(self) -> None:
        # Exercises the `except MultipleValidationErrors` branch in
        # _load_fields specifically: a single nested config raising its
        # own MultipleValidationErrors (>=2 bad fields inside ONE nested
        # instance) must be caught and flattened into the parent's error
        # list, not just two independent single-field ValidationErrors
        # bubbling from two different fields (that's a different code path
        # — see test_invalid_nested_and_outer_field_aggregate_into_multiple_errors).
        class TwoConstrainedFields(DotEnvConfig):
            env_prefix = "APP_TWO_"
            a: int = Field(default=1, ge=1, le=10)
            b: int = Field(default=1, ge=1, le=10)

        class OuterWithTwoConstrainedNested(DotEnvConfig):
            env_prefix = "APP_"
            nested: TwoConstrainedFields = Field(default_factory=TwoConstrainedFields)

        with pytest.raises(MultipleValidationErrors) as exc_info:
            OuterWithTwoConstrainedNested.load_from_dict({"APP_TWO_A": "999", "APP_TWO_B": "999"})

        assert len(exc_info.value.errors) == 2
        field_names = {e.field_name for e in exc_info.value.errors}
        assert field_names == {"a", "b"}


class TestOptionalNestedConfigLimitation:
    """Pins a KNOWN, UNFIXED gap: `Optional[Nested]` / `Nested | None` does
    not take the nested-loading branch (it's a Union, not a plain `type`),
    so it falls through to Optional scalar handling and silently discards
    the nested config instead of resolving it. This behavior is identical
    before and after the nested-config-defaults fix — not a regression,
    but a documented limitation so it isn't rediscovered as a surprise.
    """

    def test_optional_nested_config_silently_resolves_to_none(self) -> None:
        class OuterOptional(DotEnvConfig):
            env_prefix = "APP_"
            nested: Nested | None = Field(default=None)

        config = OuterOptional.load_from_dict({"APP_NESTED_PORT": "55"})

        # Known limitation: the override is silently discarded rather than
        # applied — `nested` stays None even though APP_NESTED_PORT was set.
        assert config.nested is None


class TestRequiredNestedConfigField:
    """Pins the (new, intentional) behavior for a nested config field with
    no default_factory: field_info.required is not consulted for nested
    DotEnvConfig fields, so it always resolves via the nested class's own
    defaults rather than raising MissingFieldError. "Required" is expected
    to be expressed on the nested class's own fields instead.
    """

    def test_required_nested_field_resolves_via_nested_defaults(self) -> None:
        class OuterRequiredNested(DotEnvConfig):
            env_prefix = "APP_"
            nested: Nested = Field()  # no default_factory — required=True

        config = OuterRequiredNested.load_from_dict({})

        assert isinstance(config.nested, Nested)
        assert config.nested.port == 10


class TestNestedConfigReload:
    def test_reload_picks_up_nested_env_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NESTED_PORT", "20")
        config = Outer.load()
        assert config.nested.port == 20

        monkeypatch.setenv("APP_NESTED_PORT", "30")
        config.reload()
        assert config.nested.port == 30


class TestNestedConfigIntrospection:
    def test_dict_includes_nested_instance(self) -> None:
        config = Outer.load_from_dict({})

        as_dict = config.dict()
        assert isinstance(as_dict["nested"], Nested)
        assert as_dict["nested"].port == 10

    def test_repr_renders_nested_instance(self) -> None:
        config = Outer.load_from_dict({})

        rendered = repr(config)
        assert "Nested(" in rendered
        assert "port=10" in rendered


class TestDeeplyNestedConfig:
    def test_two_levels_of_nesting_resolve_defaults(self) -> None:
        class Inner(DotEnvConfig):
            env_prefix = "APP_MID_INNER_"
            value: int = Field(default=7)

        class Mid(DotEnvConfig):
            env_prefix = "APP_MID_"
            inner: Inner = Field(default_factory=Inner)
            label: str = Field(default="mid-default")

        class Top(DotEnvConfig):
            env_prefix = "APP_"
            mid: Mid = Field(default_factory=Mid)

        config = Top.load_from_dict({})

        assert config.mid.label == "mid-default"
        assert config.mid.inner.value == 7

    def test_two_levels_of_nesting_apply_overrides(self) -> None:
        class Inner(DotEnvConfig):
            env_prefix = "APP_MID_INNER_"
            value: int = Field(default=7)

        class Mid(DotEnvConfig):
            env_prefix = "APP_MID_"
            inner: Inner = Field(default_factory=Inner)

        class Top(DotEnvConfig):
            env_prefix = "APP_"
            mid: Mid = Field(default_factory=Mid)

        config = Top.load_from_dict({"APP_MID_INNER_VALUE": "42"})

        assert config.mid.inner.value == 42
