"""Tests for choices validation on sensitive (secret-typed) fields."""

from pathlib import Path

import pytest

from dotenvmodel import (
    ConstraintViolationError,
    DotEnvConfig,
    Field,
    HttpUrl,
    MultipleValidationErrors,
    SecretStr,
)


class TestSecretStrChoices:
    """Choices validation on SecretStr fields."""

    def test_valid_choice_loads_as_secretstr(self) -> None:
        """A SecretStr field accepts a value matching a plain-string choice."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=["free", "pro"])

        config = Config.load_from_dict({"TIER": "pro"})

        assert isinstance(config.tier, SecretStr)
        assert config.tier.get_secret_value() == "pro"
        assert config.tier == SecretStr("pro")

    def test_invalid_choice_lists_allowed_choices(self) -> None:
        """An invalid choice raises and lists the allowed (non-secret) choices."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=["free", "pro"])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TIER": "enterprise"})

        assert "Value must be one of: ['free', 'pro']" in str(exc_info.value)

    def test_attempted_secret_not_in_error_message(self) -> None:
        """The attempted value stays masked in the single-error message."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(choices=["alpha", "beta"])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_KEY": "hunter2-top-secret"})

        assert "hunter2-top-secret" not in str(exc_info.value)

    def test_attempted_secret_not_in_aggregated_error_message(self) -> None:
        """The attempted values stay masked in MultipleValidationErrors output."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(choices=["alpha"])
            db_password: SecretStr = Field(choices=["gamma"])

        with pytest.raises(MultipleValidationErrors) as exc_info:
            Config.load_from_dict(
                {"API_KEY": "hunter2-top-secret", "DB_PASSWORD": "correct-horse-battery"}
            )

        message = str(exc_info.value)
        assert "hunter2-top-secret" not in message
        assert "correct-horse-battery" not in message

    def test_secretstr_instance_choices_round_trip(self) -> None:
        """SecretStr entries in choices compare by their plaintext."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=[SecretStr("gold"), SecretStr("platinum")])

        config = Config.load_from_dict({"TIER": "gold"})

        assert isinstance(config.tier, SecretStr)
        assert config.tier.get_secret_value() == "gold"
        assert config.tier == SecretStr("gold")

    def test_secretstr_instance_choices_stay_masked_in_error(self) -> None:
        """SecretStr-wrapped choices render masked in the violation message."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=[SecretStr("gold"), SecretStr("platinum")])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TIER": "enterprise"})

        message = str(exc_info.value)
        assert "gold" not in message
        assert "platinum" not in message
        assert "enterprise" not in message


class TestDsnChoices:
    """Choices validation on DSN fields (BaseDsn is a str subclass)."""

    def test_valid_dsn_choice_loads(self) -> None:
        """A DSN field accepts a value matching a plain-string choice."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field(
                choices=["https://api.example.com", "https://backup.example.com"]
            )

        config = Config.load_from_dict({"API_URL": "https://api.example.com"})

        assert isinstance(config.api_url, HttpUrl)
        assert config.api_url == "https://api.example.com"

    def test_invalid_dsn_choice_masks_password_in_error(self) -> None:
        """An invalid DSN choice lists the choices and redacts the URL password."""

        class Config(DotEnvConfig):
            api_url: HttpUrl = Field(
                choices=["https://api.example.com", "https://backup.example.com"]
            )

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"API_URL": "https://user:hunter2@evil.example.com"})

        message = str(exc_info.value)
        assert "Value must be one of" in message
        assert "hunter2" not in message


class TestPlainStrChoices:
    """Regression guard: plain str fields keep plaintext value reporting."""

    def test_invalid_choice_still_reports_plaintext_value(self) -> None:
        """A non-sensitive field's attempted value stays visible in the error."""

        class Config(DotEnvConfig):
            environment: str = Field(choices=["dev", "test", "prod"])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"ENVIRONMENT": "staging"})

        message = str(exc_info.value)
        assert "Value must be one of: ['dev', 'test', 'prod']" in message
        assert "'staging'" in message


class TestSecretStrDefaultChoices:
    """Choices validation on the str-default coercion path of SecretStr fields."""

    def test_valid_default_loads_as_secretstr(self) -> None:
        """A str default matching a choice is coerced to a SecretStr that passes choices."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(default="free", choices=["free", "pro"])

        config = Config.load_from_dict({})

        assert isinstance(config.tier, SecretStr)
        assert config.tier.get_secret_value() == "free"
        assert config.tier == SecretStr("free")

    def test_invalid_default_raises_masked(self) -> None:
        """A str default outside the choices raises without echoing the default's plaintext."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(default="enterprise", choices=["free", "pro"])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({})

        message = str(exc_info.value)
        assert "Value must be one of: ['free', 'pro']" in message
        assert "enterprise" not in message


class TestSecretStrChoicesFromEnvFile:
    """Choices validation on SecretStr values loaded from .env files."""

    def test_valid_choice_loads_from_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """A .env file value matching a choice loads as a SecretStr via load()."""

        (tmp_path / ".env").write_text("API_KEY=alpha\n")
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("ENV", raising=False)

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(choices=["alpha", "beta"])

        config = Config.load(env_dir=tmp_path)

        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "alpha"

    def test_invalid_choice_from_env_file_raises_masked(self, tmp_path: Path, monkeypatch) -> None:
        """An invalid .env file value raises without echoing the file's plaintext."""

        (tmp_path / ".env").write_text("API_KEY=hunter2-file-secret\n")
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("ENV", raising=False)

        class Config(DotEnvConfig):
            api_key: SecretStr = Field(choices=["alpha", "beta"])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load(env_dir=tmp_path)

        message = str(exc_info.value)
        assert "Value must be one of: ['alpha', 'beta']" in message
        assert "hunter2-file-secret" not in message


class TestOptionalSecretStrChoices:
    """Choices validation on Optional[SecretStr] fields; None skips choices entirely."""

    def test_provided_valid_choice_loads(self) -> None:
        """A provided value matching a choice loads as a SecretStr on an Optional field."""

        class Config(DotEnvConfig):
            api_key: SecretStr | None = Field(choices=["alpha", "beta"])

        config = Config.load_from_dict({"API_KEY": "alpha"})

        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "alpha"

    def test_missing_value_yields_none(self) -> None:
        """A missing value yields None, which never reaches choices validation."""

        class Config(DotEnvConfig):
            api_key: SecretStr | None = Field(choices=["alpha", "beta"])

        config = Config.load_from_dict({})

        assert config.api_key is None

    def test_empty_value_yields_none(self) -> None:
        """An empty value coerces to None and never reaches choices validation."""

        class Config(DotEnvConfig):
            api_key: SecretStr | None = Field(choices=["alpha", "beta"])

        config = Config.load_from_dict({"API_KEY": ""})

        assert config.api_key is None


class TestMixedWrappedChoices:
    """Mixed plain-str and SecretStr-wrapped entries in a choices list."""

    def test_plain_string_entry_matches(self) -> None:
        """A value matching the plain-string entry of a mixed choices list loads."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=["free", SecretStr("gold")])

        config = Config.load_from_dict({"TIER": "free"})

        assert isinstance(config.tier, SecretStr)
        assert config.tier.get_secret_value() == "free"

    def test_wrapped_entry_matches_by_plaintext(self) -> None:
        """A value matching the wrapped entry's plaintext of a mixed choices list loads."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=["free", SecretStr("gold")])

        config = Config.load_from_dict({"TIER": "gold"})

        assert isinstance(config.tier, SecretStr)
        assert config.tier.get_secret_value() == "gold"

    def test_error_masks_wrapped_entry_plaintext(self) -> None:
        """A violation on a mixed choices list renders the wrapped choice masked."""

        class Config(DotEnvConfig):
            tier: SecretStr = Field(choices=["free", SecretStr("gold")])

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"TIER": "enterprise"})

        message = str(exc_info.value)
        assert "Value must be one of: ['free', SecretStr('**********')]" in message
        assert "gold" not in message
        assert "enterprise" not in message

    def test_plain_str_field_matches_wrapped_choice(self) -> None:
        """A plain str field accepts the plaintext of a SecretStr-wrapped choice."""

        class Config(DotEnvConfig):
            plan: str = Field(choices=[SecretStr("gold")])

        config = Config.load_from_dict({"PLAN": "gold"})

        assert isinstance(config.plan, str)
        assert config.plan == "gold"
