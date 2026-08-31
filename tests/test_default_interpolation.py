"""Tests: literal string field defaults are ``${VAR}`` templates resolved at load.

A ``Field(default=...)`` string — or a bare class-attribute default —
resolves its ``${VAR}`` / ``${VAR:-default}`` references at load time
through the same interpolation the ``.env`` file layer uses: the merged
dotfile layer first, ``os.environ`` as the fallback, and plain
``os.environ`` when no dotfiles were read. ``default_factory`` results are
built programmatically and stay verbatim. Resolution re-runs on every
``load()`` / ``reload()``, and the resolved value then flows through the
unchanged default machinery — str-default coercion for non-str types,
validation, and secret masking.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

import dotenvmodel.config as config_module
import dotenvmodel.loading as loading_module
from dotenvmodel import ConstraintViolationError, DotEnvConfig, Field, SecretStr
from dotenvmodel.loading import read_env_files


class TestInterpolateValueContract:
    """The single-string entry point both .env values and string defaults resolve through."""

    def test_string_without_references_passes_through_as_the_same_object(self) -> None:
        """The "${" guard: a template-free string never enters the regex path."""
        plain = "no references here"

        assert loading_module.interpolate_value(plain, {"X": "1"}) is plain

    def test_references_resolve_against_the_base(self) -> None:
        base = {"HOST": "db.internal", "PORT": "5432"}

        resolved = loading_module.interpolate_value("postgres://${HOST}:${PORT}/app", base)

        assert resolved == "postgres://db.internal:5432/app"


class TestDefaultInterpolationBase:
    """Where a default template's references resolve from."""

    def test_reference_defined_in_the_dotfile_layer(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("BASE_URL=http://files.internal\n")

        class Config(DotEnvConfig):
            api_url: str = Field(default="${BASE_URL}/api")

        config = Config.load(env_dir=tmp_path)

        assert config.api_url == "http://files.internal/api"

    def test_reference_defined_only_in_the_process_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".env").write_text("UNRELATED=1\n")
        monkeypatch.setenv("API_HOST", "api.internal")

        class Config(DotEnvConfig):
            api_url: str = Field(default="http://${API_HOST}/v1")

        config = Config.load(env_dir=tmp_path)

        assert config.api_url == "http://api.internal/v1"

    def test_merged_layer_beats_the_process_environment_in_the_default_base(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The lookup order matches the file layer's: merged dotfile values, then os.environ."""
        monkeypatch.setenv("BASE_URL", "http://from-env")
        (tmp_path / ".env").write_text("BASE_URL=http://from-file\n")

        class Config(DotEnvConfig):
            api_url: str = Field(default="${BASE_URL}/api")

        config = Config.load(env_dir=tmp_path)

        assert config.api_url == "http://from-file/api"

    def test_unset_reference_becomes_the_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MISSING", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="prefix-${MISSING}-suffix")

        config = Config.load(env_dir=tmp_path)

        assert config.value == "prefix--suffix"

    def test_read_dotfiles_false_base_is_the_process_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no dotfile layer, references resolve against os.environ alone."""
        (tmp_path / ".env").write_text("BASE_URL=http://from-file\n")
        monkeypatch.setenv("BASE_URL", "http://from-env")

        class Config(DotEnvConfig):
            api_url: str = Field(default="${BASE_URL}/api")

        config = Config.load(env_dir=tmp_path, read_dotfiles=False)

        assert config.api_url == "http://from-env/api"

    def test_override_does_not_affect_default_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """override flips per-field precedence only, never the default's reference base."""
        monkeypatch.setenv("BASE_URL", "http://from-env")
        (tmp_path / ".env").write_text("BASE_URL=http://from-file\n")

        class Config(DotEnvConfig):
            base_url: str = Field(default="unset")
            api_url: str = Field(default="${BASE_URL}/api")

        default_mode = Config.load(env_dir=tmp_path)
        assert default_mode.base_url == "http://from-env"
        assert default_mode.api_url == "http://from-file/api"

        override_mode = Config.load(env_dir=tmp_path, override=True)
        assert override_mode.base_url == "http://from-file"
        assert override_mode.api_url == "http://from-file/api"


class TestDefaultColonDashFallback:
    """The `:-` default applies only when the name is absent from the base."""

    def test_fallback_used_when_the_variable_is_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MISSING", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="${MISSING:-fallback}")

        config = Config.load(env_dir=tmp_path)

        assert config.value == "fallback"

    def test_fallback_ignored_when_the_environment_sets_the_variable_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A present-but-empty value wins over the fallback — plain dict.get semantics."""
        monkeypatch.setenv("EMPTY", "")

        class Config(DotEnvConfig):
            value: str = Field(default="${EMPTY:-fallback}")

        config = Config.load(env_dir=tmp_path)

        assert config.value == ""

    def test_fallback_ignored_when_the_dotfile_layer_sets_the_variable_empty(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text("EMPTY=\n")

        class Config(DotEnvConfig):
            value: str = Field(default="${EMPTY:-fallback}")

        config = Config.load(env_dir=tmp_path)

        assert config.value == ""

    def test_fallback_ignored_when_the_variable_is_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PRESENT", "real")

        class Config(DotEnvConfig):
            value: str = Field(default="${PRESENT:-fallback}")

        config = Config.load(env_dir=tmp_path)

        assert config.value == "real"


class TestNonReferenceSyntaxStaysLiteral:
    """Only the ${...} forms are references; everything else stays verbatim."""

    def test_bare_dollar_shorthand_and_unclosed_references_stay_literal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HOST", raising=False)

        class Config(DotEnvConfig):
            price: str = Field(default="costs $5")
            shorthand: str = Field(default="$HOST not ${HOST}")
            unclosed: str = Field(default="unclosed ${VAR and ${VAR:-x")

        config = Config.load(env_dir=tmp_path)

        assert config.price == "costs $5"
        assert config.shorthand == "$HOST not "
        assert config.unclosed == "unclosed ${VAR and ${VAR:-x"


class TestResolvedDefaultsFlowThroughExistingMachinery:
    """Interpolation happens before the str-default coercion route, validation, and masking."""

    def test_list_field_default_interpolates_then_splits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REGION", "eu")

        class Config(DotEnvConfig):
            regions: list[str] = Field(default="us,${REGION}")

        config = Config.load(env_dir=tmp_path)

        assert config.regions == ["us", "eu"]

    def test_secretstr_default_resolves_and_stays_masked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TOKEN", "tok")

        class Config(DotEnvConfig):
            password: SecretStr = Field(default="secret-${TOKEN}")

        config = Config.load(env_dir=tmp_path)

        assert config.password.get_secret_value() == "secret-tok"
        assert repr(config.password) == "SecretStr('**********')"
        assert "secret-tok" not in repr(config)

    def test_secretstr_constraint_failure_masks_the_resolved_plaintext(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TOKEN", "tok")

        class Config(DotEnvConfig):
            password: SecretStr = Field(default="short-${TOKEN}", min_length=32)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load(env_dir=tmp_path)

        assert "short-tok" not in str(exc_info.value)
        assert "**********" in str(exc_info.value)


class TestDefaultFormsAndRefresh:
    """Which defaults are templates, and when they re-resolve."""

    def test_bare_class_attribute_default_interpolates(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("BASE_URL=http://files.internal\n")

        class Config(DotEnvConfig):
            api_url: str = "${BASE_URL}/api"

        config = Config.load(env_dir=tmp_path)

        assert config.api_url == "http://files.internal/api"

    def test_default_factory_results_are_not_interpolated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A factory builds its value programmatically; ${...} text in it is data, not a template."""
        monkeypatch.setenv("X", "from-env")

        class Config(DotEnvConfig):
            value: str = Field(default_factory=lambda: "${X}")

        config = Config.load(env_dir=tmp_path)

        assert config.value == "${X}"

    def test_nested_config_default_resolves_against_the_same_layer(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("BASE_URL=http://nested.internal\n")

        class Inner(DotEnvConfig):
            api_url: str = Field(default="${BASE_URL}/api")

        class Outer(DotEnvConfig):
            inner: Inner = Field()

        config = Outer.load(env_dir=tmp_path)

        assert config.inner.api_url == "http://nested.internal/api"

    def test_reload_reresolves_against_a_changed_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".env").write_text("OTHER=1\n")

        class Config(DotEnvConfig):
            api_url: str = Field(default="http://${API_HOST}/v1")

        monkeypatch.setenv("API_HOST", "one.internal")
        config = Config.load(env_dir=tmp_path)
        assert config.api_url == "http://one.internal/v1"

        monkeypatch.setenv("API_HOST", "two.internal")
        config.reload()

        assert config.api_url == "http://two.internal/v1"


class TestInterpolationGuard:
    """The "${" guard and the one shared interpolation implementation behind both paths."""

    def test_plain_default_never_reaches_the_interpolator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def never(text: str, base: Mapping[str, str]) -> str:
            calls.append(text)
            return text

        monkeypatch.setattr(config_module, "interpolate_value", never)

        class Config(DotEnvConfig):
            plain: str = Field(default="no references here")

        config = Config.load_from_dict({})

        assert config.plain == "no references here"
        assert calls == []

    def test_template_default_resolves_through_the_shared_entry_point(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []
        original = config_module.interpolate_value

        def recording(text: str, base: Mapping[str, str]) -> str:
            seen.append(text)
            return original(text, base)

        monkeypatch.setattr(config_module, "interpolate_value", recording)
        monkeypatch.setenv("HOST", "api.internal")

        class Config(DotEnvConfig):
            api_url: str = Field(default="http://${HOST}/v1")

        config = Config.load_from_dict({})

        assert config.api_url == "http://api.internal/v1"
        assert seen == ["http://${HOST}/v1"]

    def test_file_values_resolve_through_the_same_entry_point(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []
        original = loading_module.interpolate_value

        def recording(text: str, base: Mapping[str, str]) -> str:
            seen.append(text)
            return original(text, base)

        monkeypatch.setattr(loading_module, "interpolate_value", recording)

        (tmp_path / ".env").write_text("HOST=db.internal\nURL=postgres://${HOST}/app\n")
        layer = read_env_files(env="dev", env_dir=tmp_path)

        assert layer.values["URL"] == "postgres://db.internal/app"
        assert seen == ["db.internal", "postgres://${HOST}/app"]


class TestDocumentationRendering:
    """describe()/generate_env_example() show the unresolved template, which round-trips."""

    def test_describe_shows_the_unresolved_template(self) -> None:
        class Config(DotEnvConfig):
            api_url: str = Field(default="${BASE_URL}/api")

        assert "${BASE_URL}/api" in Config.describe()

    def test_generate_env_example_line_round_trips_through_the_file_layer(
        self, tmp_path: Path
    ) -> None:
        """Uncommenting the rendered default line into .env loads the same value the default resolves to."""

        class Config(DotEnvConfig):
            api_url: str = Field(default="${BASE_URL}/api")
            fallback_url: str = Field(default="${BASE_URL}/api")

        example = Config.generate_env_example()
        assert 'API_URL="${BASE_URL}/api"' in example

        line = next(line for line in example.splitlines() if line.startswith("# API_URL="))
        (tmp_path / ".env").write_text(f"BASE_URL=http://roundtrip.internal\n{line.lstrip('# ')}\n")

        config = Config.load(env_dir=tmp_path)

        # API_URL comes from the uncommented file line; FALLBACK_URL from its
        # default — both interpolate against the same base, so they agree.
        assert config.api_url == "http://roundtrip.internal/api"
        assert config.fallback_url == config.api_url
