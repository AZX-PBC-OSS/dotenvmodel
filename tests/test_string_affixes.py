"""Tests for the Field(starts_with=...) and Field(ends_with=...) constraints."""

from typing import Optional

import pytest

from dotenvmodel import ConstraintViolationError, DotEnvConfig, Field, PostgresDsn, SecretStr
from dotenvmodel.fields import FieldInfo


class TestStartsWith:
    """Test the starts_with string constraint."""

    def test_starts_with_pass(self) -> None:
        """A value with the required prefix passes."""

        class Config(DotEnvConfig):
            api_key: str = Field(starts_with="sk-")

        config = Config.load_from_dict({"API_KEY": "sk-abc123"})
        assert config.api_key == "sk-abc123"

    def test_starts_with_fail(self) -> None:
        """A value without the required prefix fails."""

        class Config(DotEnvConfig):
            api_key: str = Field(starts_with="sk-")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-abc123"})

        assert exc_info.value.constraint == "starts_with='sk-'"
        assert exc_info.value.error_msg == "String must start with: sk-"
        assert exc_info.value.field_name == "api_key"
        assert exc_info.value.env_var_name == "API_KEY"

    def test_starts_with_empty_prefix(self) -> None:
        """An empty prefix matches every string (str.startswith('') is True)."""

        class Config(DotEnvConfig):
            value: str = Field(starts_with="")

        config = Config.load_from_dict({"VALUE": "anything"})
        assert config.value == "anything"

    def test_starts_with_case_sensitive(self) -> None:
        """Prefix matching is case-sensitive."""

        class Config(DotEnvConfig):
            api_key: str = Field(starts_with="sk-")

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"API_KEY": "SK-abc123"})


class TestEndsWith:
    """Test the ends_with string constraint."""

    def test_ends_with_pass(self) -> None:
        """A value with the required suffix passes."""

        class Config(DotEnvConfig):
            token: str = Field(ends_with=".sig")

        config = Config.load_from_dict({"TOKEN": "abc123.sig"})
        assert config.token == "abc123.sig"

    def test_ends_with_fail(self) -> None:
        """A value without the required suffix fails."""

        class Config(DotEnvConfig):
            token: str = Field(ends_with=".sig")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TOKEN": "abc123.raw"})

        assert exc_info.value.constraint == "ends_with='.sig'"
        assert exc_info.value.error_msg == "String must end with: .sig"
        assert exc_info.value.field_name == "token"
        assert exc_info.value.env_var_name == "TOKEN"

    def test_ends_with_empty_suffix(self) -> None:
        """An empty suffix matches every string (str.endswith('') is True)."""

        class Config(DotEnvConfig):
            value: str = Field(ends_with="")

        config = Config.load_from_dict({"VALUE": "anything"})
        assert config.value == "anything"


class TestAffixCombinations:
    """Test affix constraints combined with other string constraints."""

    def test_starts_with_and_ends_with_together(self) -> None:
        """Both affix constraints on one field."""

        class Config(DotEnvConfig):
            wrapped: str = Field(starts_with="[", ends_with="]")

        config = Config.load_from_dict({"WRAPPED": "[value]"})
        assert config.wrapped == "[value]"

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"WRAPPED": "[value"})
        assert exc_info.value.constraint == "ends_with=']'"

    def test_combined_with_min_length(self) -> None:
        """starts_with composes with min_length; both must pass."""

        class Config(DotEnvConfig):
            api_key: str = Field(starts_with="sk-", min_length=10)

        config = Config.load_from_dict({"API_KEY": "sk-abc1234"})
        assert config.api_key == "sk-abc1234"

        # Too short: min_length checked first
        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "sk-ab"})
        assert exc_info.value.constraint == "min_length=10"

        # Long enough but wrong prefix
        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-abc1234"})
        assert exc_info.value.constraint == "starts_with='sk-'"

    def test_optional_field_missing_skips_constraint(self) -> None:
        """None values skip affix validation."""

        class Config(DotEnvConfig):
            api_key: str | None = Field(default=None, starts_with="sk-")

        config = Config.load_from_dict({})
        assert config.api_key is None

    def test_not_validated_when_validate_false(self) -> None:
        """validate=False skips affix checks."""

        class Config(DotEnvConfig):
            api_key: str = Field(starts_with="sk-")

        config = Config.load_from_dict({"API_KEY": "pk-abc123"}, validate=False)
        assert config.api_key == "pk-abc123"


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(str | None, id="pipe-none"),
        # Deliberately uses typing.Optional to exercise the typing.Union code
        # path in unwrap_optional (UP045 would modernize this away and defeat
        # the mutation pin — see test class docstring).
        pytest.param(Optional[str], id="typing-optional"),  # noqa: UP045
    ],
)
class TestAffixOnBothUnionSpellings:
    """Both ``Optional[str]`` (typing.Union) and ``str | None`` support affixes.

    A mutation removing ``origin is Union`` from ``unwrap_optional`` would break
    the ``typing.Optional`` spelling while leaving ``str | None`` intact,
    escaping the rest of the affix suite (which only uses ``str | None``). The
    describe-rendering check below exercises ``is_string_like_type`` ->
    ``unwrap_optional`` so the ``typing.Union`` branch regresses for affixes.
    """

    def test_starts_with_applies_when_present(self, field_type: object) -> None:
        class Config(DotEnvConfig):
            api_key: field_type = Field(default=None, starts_with="sk-")  # type: ignore[valid-type]

        config = Config.load_from_dict({"API_KEY": "sk-abc"})
        assert config.api_key == "sk-abc"

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-abc"})
        assert exc_info.value.constraint == "starts_with='sk-'"

    def test_ends_with_applies_when_present(self, field_type: object) -> None:
        class Config(DotEnvConfig):
            token: field_type = Field(default=None, ends_with=".sig")  # type: ignore[valid-type]

        config = Config.load_from_dict({"TOKEN": "abc.sig"})
        assert config.token == "abc.sig"

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TOKEN": "abc.raw"})
        assert exc_info.value.constraint == "ends_with='.sig'"

    def test_skipped_when_none(self, field_type: object) -> None:
        class Config(DotEnvConfig):
            api_key: field_type = Field(default=None, starts_with="sk-")  # type: ignore[valid-type]

        config = Config.load_from_dict({})
        assert config.api_key is None

    def test_affix_rendered_in_describe(self, field_type: object) -> None:
        """describe() renders affix constraints for both Union spellings.

        ``format_constraints`` gates affix rendering on
        ``is_string_like_type`` -> ``unwrap_optional``; removing the
        ``origin is Union`` branch would hide the constraint for
        ``typing.Optional`` but not for ``str | None``.
        """

        class Config(DotEnvConfig):
            api_key: field_type = Field(default=None, starts_with="sk-")  # type: ignore[valid-type]

        output = Config.describe()
        assert "starts_with='sk-'" in output


class TestAffixSecretStrMasking:
    """Test that SecretStr affix errors never carry plaintext."""

    def test_starts_with_secret_masked(self) -> None:
        """The SecretStr wrapper (masked) is reported, never the plaintext."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(starts_with="sk-")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "pk-super-secret-value"})

        msg = str(exc_info.value)
        assert "pk-super-secret-value" not in msg
        assert "**********" in msg
        assert exc_info.value.constraint == "starts_with='sk-'"

    def test_ends_with_secret_masked(self) -> None:
        """Same masking for ends_with on SecretStr fields."""

        class Config(DotEnvConfig):
            token: SecretStr = Field(ends_with=".sig")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TOKEN": "super-secret-token"})

        msg = str(exc_info.value)
        assert "super-secret-token" not in msg
        assert "**********" in msg

    def test_starts_with_secret_pass(self) -> None:
        """SecretStr values are checked against their plaintext."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(starts_with="sk-")

        config = Config.load_from_dict({"API_KEY": "sk-super-secret"})
        assert config.api_key.get_secret_value() == "sk-super-secret"


class TestAffixDsnMasking:
    """Test that DSN affix errors never leak the URL password."""

    def test_starts_with_dsn_password_masked(self) -> None:
        """A starts_with failure on a PostgresDsn does not leak the password.

        ``postgres://`` is a valid PostgresDsn scheme but does not start with
        the required ``postgresql://`` prefix, so the affix check fails.
        """

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(starts_with="postgresql://")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"DB": "postgres://user:hunter2@host/db"})

        msg = str(exc_info.value)
        assert "hunter2" not in msg
        assert exc_info.value.constraint == "starts_with='postgresql://'"

    def test_ends_with_dsn_password_masked(self) -> None:
        """An ends_with failure on a PostgresDsn does not leak the password."""

        class Config(DotEnvConfig):
            db: PostgresDsn = Field(ends_with="/prod")

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"DB": "postgresql://user:hunter2@host/db"})

        msg = str(exc_info.value)
        assert "hunter2" not in msg
        assert exc_info.value.constraint == "ends_with='/prod'"


class TestAffixFieldInfoValidation:
    """Test FieldInfo constructor type-checks for affix constraints."""

    def test_starts_with_non_string_raises(self) -> None:
        """starts_with must be a str."""
        with pytest.raises(TypeError) as exc_info:
            Field(starts_with=123)  # type: ignore[arg-type]

        assert "starts_with" in str(exc_info.value)
        assert "str" in str(exc_info.value)

    def test_ends_with_non_string_raises(self) -> None:
        """ends_with must be a str."""
        with pytest.raises(TypeError) as exc_info:
            Field(ends_with=b".sig")  # type: ignore[arg-type]

        assert "ends_with" in str(exc_info.value)
        assert "str" in str(exc_info.value)

    def test_affixes_stored_on_field_info(self) -> None:
        """FieldInfo stores the affix constraints."""
        info = FieldInfo(starts_with="sk-", ends_with=".sig")
        assert info.starts_with == "sk-"
        assert info.ends_with == ".sig"
        assert FieldInfo().starts_with is None
        assert FieldInfo().ends_with is None
