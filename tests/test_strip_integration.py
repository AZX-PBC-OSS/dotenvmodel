"""Integration tests for strip/validator through the real load() and reload() entry points.

These exercise the full pipeline (environment + .env files -> _process_field)
rather than ``load_from_dict``, following the conventions in ``test_loading.py``
and ``test_reload.py``: ``monkeypatch.setenv`` for real env vars, ``tmp_path``
for ``DOTENV_DIR`` / ``env_dir``, and ``tmp_path / ".env"`` for .env files.
"""

from pathlib import Path

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.fields import ValidatorContext


class TestStripThroughLoad:
    """strip applies when reading real environment variables via Config.load()."""

    def test_strip_applies_to_env_var(self, monkeypatch) -> None:
        """A padded env var is stripped to the inner value via load()."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)

        monkeypatch.setenv("NAME", "  hello  ")
        config = Config.load()
        assert config.name == "hello"

    def test_strip_false_preserves_padding(self, monkeypatch) -> None:
        """A strip=False field keeps its padding even with class strip_strings=True."""

        class Config(DotEnvConfig):
            strip_strings: bool = True

            name: str = Field(strip=False)

        monkeypatch.setenv("NAME", "  hello  ")
        config = Config.load()
        assert config.name == "  hello  "


class TestStripThroughReload:
    """reload() re-runs strip on the updated environment."""

    def test_reload_picks_up_new_padded_value(self, monkeypatch) -> None:
        """After setenv changes a padded value, reload strips the new value."""

        class Config(DotEnvConfig):
            name: str = Field(strip=True)

        monkeypatch.setenv("NAME", "  first  ")
        config = Config.load()
        assert config.name == "first"

        monkeypatch.setenv("NAME", "  second  ")
        config.reload()
        assert config.name == "second"


class TestValidatorThroughLoad:
    """A validator hook runs and transforms via the real load() entry point."""

    def test_validator_transforms_env_value(self, monkeypatch) -> None:
        """A validator that uppercases runs through Config.load()."""

        def upper(value: str, ctx: ValidatorContext) -> str:
            return value.upper()

        class Config(DotEnvConfig):
            region: str = Field(validator=upper)

        monkeypatch.setenv("REGION", "eu-west-1")
        config = Config.load()
        assert config.region == "EU-WEST-1"


class TestValidatorThroughReload:
    """A validator hook re-runs and transforms via the real reload() entry point."""

    def test_validator_transforms_on_reload(self, monkeypatch) -> None:
        """After setenv changes the value, reload re-applies the validator transform."""

        def upper(value: str, ctx: ValidatorContext) -> str:
            return value.upper()

        class Config(DotEnvConfig):
            region: str = Field(validator=upper)

        monkeypatch.setenv("REGION", "eu-west-1")
        config = Config.load()
        assert config.region == "EU-WEST-1"

        monkeypatch.setenv("REGION", "us-east-2")
        config.reload()
        assert config.region == "US-EAST-2"


class TestStripOnQuotedDotenvValue:
    """A QUOTED .env value (which python-dotenv does not trim) is stripped.

    python-dotenv trims UNQUOTED values, so quotes are required to exercise the
    strip path through the .env file cascade.
    """

    def test_quoted_value_stripped_when_strip_on(self, tmp_path: Path) -> None:
        """strip_strings=True strips a quoted padded .env value."""

        class Config(DotEnvConfig):
            strip_strings: bool = True

            name: str = Field()

        (tmp_path / ".env").write_text('NAME="  hello  "\n')
        config = Config.load(env_dir=tmp_path)
        assert config.name == "hello"

    def test_quoted_value_preserved_when_strip_off(self, tmp_path: Path) -> None:
        """Without strip, a quoted padded .env value keeps its padding."""

        class Config(DotEnvConfig):
            name: str = Field()

        (tmp_path / ".env").write_text('NAME="  hello  "\n')
        config = Config.load(env_dir=tmp_path)
        assert config.name == "  hello  "
