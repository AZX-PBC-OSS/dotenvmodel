"""Tests for JSON type parsing."""

import pytest

from dotenvmodel import DotEnvConfig, Field, TypeCoercionError
from dotenvmodel.types import Json


class TestJsonType:
    """Test Json[T] type."""

    def test_json_dict(self) -> None:
        """Test JSON parsing to dict."""

        class Config(DotEnvConfig):
            feature_flags: Json[dict[str, bool]] = Field()

        config = Config.load_from_dict({"FEATURE_FLAGS": '{"new_ui": true, "beta_api": false}'})

        assert isinstance(config.feature_flags, dict)
        assert config.feature_flags == {"new_ui": True, "beta_api": False}

    def test_json_list(self) -> None:
        """Test JSON parsing to list."""

        class Config(DotEnvConfig):
            allowed_roles: Json[list[str]] = Field()

        config = Config.load_from_dict({"ALLOWED_ROLES": '["admin", "user", "guest"]'})

        assert isinstance(config.allowed_roles, list)
        assert config.allowed_roles == ["admin", "user", "guest"]

    def test_json_nested_structure(self) -> None:
        """Test JSON parsing with nested structure."""

        class Config(DotEnvConfig):
            service_config: Json[dict[str, dict[str, str]]] = Field()

        config = Config.load_from_dict(
            {
                "SERVICE_CONFIG": '{"api": {"host": "localhost", "port": "8080"}, "db": {"host": "dbserver"}}'
            }
        )

        assert config.service_config == {
            "api": {"host": "localhost", "port": "8080"},
            "db": {"host": "dbserver"},
        }

    def test_json_numbers(self) -> None:
        """Test JSON parsing with numbers."""

        class Config(DotEnvConfig):
            settings: Json[dict[str, int]] = Field()

        config = Config.load_from_dict({"SETTINGS": '{"timeout": 30, "retries": 3}'})

        assert config.settings == {"timeout": 30, "retries": 3}
        assert isinstance(config.settings["timeout"], int)

    def test_json_mixed_types(self) -> None:
        """Test JSON parsing with mixed types."""

        class Config(DotEnvConfig):
            config: Json[dict] = Field()

        config = Config.load_from_dict(
            {"CONFIG": '{"name": "app", "version": 1, "enabled": true, "tags": ["prod", "stable"]}'}
        )

        assert config.config["name"] == "app"
        assert config.config["version"] == 1
        assert config.config["enabled"] is True
        assert config.config["tags"] == ["prod", "stable"]

    def test_json_empty_object(self) -> None:
        """Test JSON parsing empty object."""

        class Config(DotEnvConfig):
            empty: Json[dict] = Field()

        config = Config.load_from_dict({"EMPTY": "{}"})
        assert config.empty == {}

    def test_json_empty_array(self) -> None:
        """Test JSON parsing empty array."""

        class Config(DotEnvConfig):
            empty: Json[list] = Field()

        config = Config.load_from_dict({"EMPTY": "[]"})
        assert config.empty == []

    def test_json_invalid_syntax(self) -> None:
        """Test JSON parsing with invalid syntax."""

        class Config(DotEnvConfig):
            data: Json[dict] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"DATA": '{"invalid": json}'})

        assert "Invalid JSON format" in str(exc_info.value)

    def test_json_type_mismatch_dict(self) -> None:
        """Test JSON parsing type mismatch - expected dict, got list."""

        class Config(DotEnvConfig):
            settings: Json[dict] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"SETTINGS": '["not", "a", "dict"]'})

        assert "Expected JSON object (dict)" in str(exc_info.value)

    def test_json_type_mismatch_list(self) -> None:
        """Test JSON parsing type mismatch - expected list, got dict."""

        class Config(DotEnvConfig):
            items: Json[list] = Field()

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"ITEMS": '{"not": "a list"}'})

        assert "Expected JSON array (list)" in str(exc_info.value)

    def test_json_with_default(self) -> None:
        """Test JSON field with default value."""

        class Config(DotEnvConfig):
            options: Json[dict] = Field(default_factory=dict)

        config = Config.load_from_dict({})
        assert config.options == {}

    def test_json_unicode(self) -> None:
        """Test JSON parsing with Unicode characters."""

        class Config(DotEnvConfig):
            labels: Json[dict[str, str]] = Field()

        config = Config.load_from_dict({"LABELS": '{"message": "Hello 世界", "emoji": "🚀"}'})

        assert config.labels["message"] == "Hello 世界"
        assert config.labels["emoji"] == "🚀"

    def test_json_escaped_quotes(self) -> None:
        """Test JSON parsing with escaped quotes."""

        class Config(DotEnvConfig):
            data: Json[dict] = Field()

        config = Config.load_from_dict({"DATA": '{"quote": "He said \\"hello\\""}'})
        assert config.data["quote"] == 'He said "hello"'

    def test_json_null_values(self) -> None:
        """Test JSON parsing with null values."""

        class Config(DotEnvConfig):
            data: Json[dict] = Field()

        config = Config.load_from_dict({"DATA": '{"value": null, "name": "test"}'})
        assert config.data["value"] is None
        assert config.data["name"] == "test"
