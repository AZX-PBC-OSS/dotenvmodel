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
import os
import subprocess
import sys
from enum import Enum

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import Json


def _raising_factory() -> list[str]:
    raise RuntimeError("no defaults available")


class Color(Enum):
    RED = "red"
    GREEN = "green"


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


class TestEnumCollectionRendering:
    """Enum members inside collections render as their values so examples parse.

    ``str(Color.RED)`` is ``"Color.RED"``, which fails coercion when the
    example line is uncommented; the member's value round-trips.
    """

    def test_list_enum_default_renders_values_and_round_trips(self) -> None:
        class Config(DotEnvConfig):
            colors: list[Color] = Field(default=[Color.RED, Color.GREEN])

        example = Config.generate_env_example()
        assert "# COLORS=red,green" in example
        assert "Color.RED" not in example

        config = Config.load_from_dict({"COLORS": "red,green"})
        assert config.colors == [Color.RED, Color.GREEN]

    def test_set_enum_default_renders_sorted_values(self) -> None:
        class Config(DotEnvConfig):
            colors: set[Color] = Field(default={Color.GREEN, Color.RED})

        example = Config.generate_env_example()
        assert "# COLORS=green,red" in example

        config = Config.load_from_dict({"COLORS": "red,green"})
        assert config.colors == {Color.RED, Color.GREEN}

    def test_dict_enum_values_render_unwrapped(self) -> None:
        class Config(DotEnvConfig):
            palette: dict[str, Color] = Field(default={"alert": Color.RED, "ok": Color.GREEN})

        example = Config.generate_env_example()
        assert "# PALETTE=alert=red,ok=green" in example

        config = Config.load_from_dict({"PALETTE": "alert=red,ok=green"})
        assert config.palette == {"alert": Color.RED, "ok": Color.GREEN}


class TestDeterministicSetRendering:
    """Set defaults render sorted, so output does not churn with PYTHONHASHSEED."""

    def test_multi_element_set_default_renders_sorted(self) -> None:
        class Config(DotEnvConfig):
            tags: set[str] = Field(default={"zulu", "alpha", "mike"})

        example = Config.generate_env_example()
        assert "# TAGS=alpha,mike,zulu" in example

    def test_set_rendering_identical_across_hash_seeds(self) -> None:
        program = (
            "from dotenvmodel import DotEnvConfig, Field\n"
            "class Config(DotEnvConfig):\n"
            "    tags: set[str] = Field(default={'zulu', 'alpha', 'mike', 'sierra', 'tango'})\n"
            "print(Config.generate_env_example())\n"
        )
        outputs = set()
        for seed in ("0", "12345"):
            result = subprocess.run(
                [sys.executable, "-c", program],
                timeout=60,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            assert result.returncode == 0, f"child failed:\n{result.stderr}"
            outputs.add(result.stdout)
        assert len(outputs) == 1
