"""Tests for SecretStr security features."""

import pickle

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import SecretStr


class TestSecretStrSecurity:
    """Test SecretStr security features."""

    def test_prevent_direct_attribute_access_old_name(self) -> None:
        """Test that direct _value attribute access is blocked."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

        config = Config.load_from_dict({"API_KEY": "super-secret"})

        # Old attribute name should not exist
        with pytest.raises(AttributeError):
            _ = config.api_key._value

    def test_prevent_direct_attribute_access_new_name(self) -> None:
        """Test that direct _secret attribute access is blocked (name mangling)."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

        config = Config.load_from_dict({"API_KEY": "super-secret"})

        # Direct _secret access should be blocked due to name mangling
        with pytest.raises(AttributeError):
            _ = config.api_key._secret

    def test_get_secret_value_works(self) -> None:
        """Test that get_secret_value() is the correct way to access the secret."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

        config = Config.load_from_dict({"API_KEY": "super-secret"})

        # Proper API should work
        assert config.api_key.get_secret_value() == "super-secret"

    def test_prevent_pickling(self) -> None:
        """Test that SecretStr cannot be pickled."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

        config = Config.load_from_dict({"API_KEY": "super-secret"})

        # Pickling should fail
        with pytest.raises(TypeError) as exc_info:
            pickle.dumps(config.api_key)

        assert "cannot be pickled" in str(exc_info.value)
        assert "security" in str(exc_info.value).lower()

    def test_prevent_modification(self) -> None:
        """Test that SecretStr is immutable."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()

        config = Config.load_from_dict({"API_KEY": "super-secret"})

        # Attempting to modify should fail
        with pytest.raises(AttributeError) as exc_info:
            config.api_key.new_attr = "value"

        assert "immutable" in str(exc_info.value).lower()

    def test_prevent_deletion(self) -> None:
        """Test that attributes cannot be deleted."""
        secret = SecretStr("test")

        with pytest.raises(AttributeError) as exc_info:
            del secret._SecretStr__secret

        assert "immutable" in str(exc_info.value).lower()

    def test_name_mangling_is_applied(self) -> None:
        """Test that name mangling is properly applied to the secret attribute."""
        secret = SecretStr("test-value")

        # The mangled name should be accessible (for testing purposes)
        # but this is intentionally obscure
        assert hasattr(secret, "_SecretStr__secret")
        assert secret._SecretStr__secret == "test-value"

        # But the unmangled name should not exist
        assert not hasattr(secret, "__secret")
        assert not hasattr(secret, "_secret")

    def test_config_dict_hides_secrets(self) -> None:
        """Test that secrets are hidden in config.dict() output."""

        class Config(DotEnvConfig):
            api_key: SecretStr = Field()
            public_value: str = Field()

        config = Config.load_from_dict(
            {
                "API_KEY": "super-secret",
                "PUBLIC_VALUE": "visible",
            }
        )

        config_dict = config.dict()
        # SecretStr object is in dict, but when converted to string it's hidden
        assert str(config_dict["api_key"]) == "**********"
        assert config_dict["public_value"] == "visible"
