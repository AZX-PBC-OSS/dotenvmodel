"""Rendering of parseable example values for collections and factories.

``format_default`` used to render ``default_factory`` fields as unusable
callable reprs (``<<lambda()>>``) and ``default_factory=list`` as ``[]``,
which parses back as ``["[]"]`` (issue #58, part 2). Example values now
render in the format dotenvmodel itself parses: factories are invoked once,
collections are joined with the field's separator, dicts as ``key=value``
pairs, and ``Json`` fields as JSON.
"""

import json
import logging

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import Json


def _raising_factory() -> list[str]:
    raise RuntimeError("no defaults available")


class TestFactoryExampleRendering:
    """default_factory fields render their invoked result, never a callable repr."""

    def test_lambda_list_factory_rendered_parseable(self) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=lambda: ["a", "b"])

        example = Config.generate_env_example()
        assert "# Example: HOSTS=a,b" in example
        assert "# HOSTS=a,b" in example
        assert "<lambda" not in example

    def test_factory_result_joined_with_custom_separator(self) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=lambda: ["a", "b"], separator=";")

        example = Config.generate_env_example()
        assert "# HOSTS=a;b" in example

    def test_default_factory_list_renders_empty_with_generic_example(self) -> None:
        class Config(DotEnvConfig):
            tags: list[str] = Field(default_factory=list)

        example = Config.generate_env_example()
        assert "# Example: TAGS=value1,value2,value3" in example
        assert "# TAGS=\n" in example
        assert "[]" not in example

    def test_default_factory_dict_renders_empty(self) -> None:
        class Config(DotEnvConfig):
            limits: dict[str, str] = Field(default_factory=dict)

        example = Config.generate_env_example()
        assert "# LIMITS=\n" in example

    def test_dict_factory_rendered_as_key_value_pairs(self) -> None:
        class Config(DotEnvConfig):
            labels: dict[str, str] = Field(default_factory=lambda: {"env": "dev", "tier": "web"})

        example = Config.generate_env_example()
        assert "# LABELS=env=dev,tier=web" in example

    def test_raising_factory_renders_placeholder_and_warns(self, caplog) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=_raising_factory)

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            example = Config.generate_env_example()

        assert "# HOSTS=<<set per environment>>" in example
        assert "# Example: HOSTS" not in example
        assert any("_raising_factory" in r.message for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestParseableRendering:
    """Rendered example values round-trip through dotenvmodel's own parser."""

    def test_literal_list_default_rendered_everywhere_and_parsed_back(self) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default=["a", "b"])

        assert "a,b" in Config.describe()
        example = Config.generate_env_example()
        assert "# HOSTS=a,b" in example

        config = Config.load_from_dict({"HOSTS": "a,b"})
        assert config.hosts == ["a", "b"]

    def test_set_default_rendered_joined(self) -> None:
        class Config(DotEnvConfig):
            tags: set[str] = Field(default={"alpha"})

        example = Config.generate_env_example()
        assert "# TAGS=alpha" in example

    def test_dict_literal_default_round_trips(self) -> None:
        class Config(DotEnvConfig):
            limits: dict[str, str] = Field(default={"cpu": "4", "mem": "2"})

        example = Config.generate_env_example()
        assert "# LIMITS=cpu=4,mem=2" in example

        config = Config.load_from_dict({"LIMITS": "cpu=4,mem=2"})
        assert config.limits == {"cpu": "4", "mem": "2"}

    def test_json_list_default_rendered_as_json(self) -> None:
        class Config(DotEnvConfig):
            roles: Json[list[str]] = Field(default=["admin", "user"])

        rendered = json.dumps(["admin", "user"])
        example = Config.generate_env_example()
        assert f"# ROLES={rendered}" in example

        config = Config.load_from_dict({"ROLES": rendered})
        assert config.roles == ["admin", "user"]

    def test_json_dict_factory_rendered_as_json(self) -> None:
        class Config(DotEnvConfig):
            flags: Json[dict[str, bool]] = Field(default_factory=lambda: {"beta": True})

        example = Config.generate_env_example()
        assert '# FLAGS={"beta": true}' in example
