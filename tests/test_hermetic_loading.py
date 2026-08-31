"""Tests for hermetic loading: environ isolation, layered resolution, pure .env reading.

Covers the resolution model behind ``DotEnvConfig.load()`` — layered lookup
across the process environment, the merged dotfile cascade, and field
defaults, with no ``os.environ`` mutation — plus the suite-wide
``os.environ`` isolation that makes the ``DOTENV_*`` env-var channel safe
to use between tests.
"""

import inspect
import os
from pathlib import Path

import pytest

from dotenvmodel import DotEnvConfig, Field, LoadParams, MissingFieldError
from dotenvmodel.loading import (
    get_env_var,
    read_env_files,
    resolve_bool,
    resolve_env_dir,
    resolve_env_name,
    resolve_load_params,
)


class TestEnvironIsolationFixture:
    """The autouse os.environ snapshot/scrub fixture in tests/conftest.py."""

    def test_isolate_environ_applies_to_every_test(self, request: pytest.FixtureRequest) -> None:
        """``_isolate_environ`` is autouse: no test opts in, so none can opt out.

        Without autouse, a single test forgetting to request isolation would
        let an ambient ``DOTENV_OVERRIDE`` flip precedence for every test
        that runs after it — exactly the cross-test pollution this fixture
        exists to prevent.
        """
        assert "_isolate_environ" in request.fixturenames

    def test_setup_pops_the_knob_vars(self) -> None:
        """Setup removes ENV/DOTENV_* so ambient values cannot steer the test."""
        from tests.conftest import _snapshot_and_restore_environ

        os.environ["ENV"] = "prod"
        os.environ["DOTENV_DIR"] = "/somewhere"
        os.environ["DOTENV_OVERRIDE"] = "true"
        os.environ["DOTENV_READ_DOTFILES"] = "false"
        os.environ["DOTENV_LOAD_LOCAL"] = "true"

        gen = _snapshot_and_restore_environ()
        next(gen)  # setup

        for var in (
            "ENV",
            "DOTENV_DIR",
            "DOTENV_OVERRIDE",
            "DOTENV_READ_DOTFILES",
            "DOTENV_LOAD_LOCAL",
        ):
            assert var not in os.environ

        with pytest.raises(StopIteration):
            next(gen)  # teardown restores the pre-test snapshot

        assert os.environ["ENV"] == "prod"
        assert os.environ["DOTENV_DIR"] == "/somewhere"
        assert os.environ["DOTENV_OVERRIDE"] == "true"
        assert os.environ["DOTENV_READ_DOTFILES"] == "false"
        assert os.environ["DOTENV_LOAD_LOCAL"] == "true"

    def test_teardown_restores_the_exact_snapshot(self) -> None:
        """Values added or removed during the test do not survive it."""
        from tests.conftest import _snapshot_and_restore_environ

        os.environ["HERMETIC_PRESENT"] = "kept"  # in the snapshot, deleted mid-test
        before = dict(os.environ)

        gen = _snapshot_and_restore_environ()
        next(gen)  # setup

        os.environ["HERMETIC_LEAK"] = "leaked"
        del os.environ["HERMETIC_PRESENT"]

        with pytest.raises(StopIteration):
            next(gen)  # teardown

        assert dict(os.environ) == before
        assert "HERMETIC_LEAK" not in os.environ
        assert os.environ["HERMETIC_PRESENT"] == "kept"


class TestNonMutation:
    """load()/reload()/cached() resolve dotfiles without injecting them into os.environ."""

    @pytest.mark.parametrize("override", [None, False, True])
    def test_load_leaves_os_environ_untouched(self, tmp_path: Path, override: bool | None) -> None:
        """Populated .env files must not leak into the process environment.

        The old load() called python-dotenv load_dotenv(), so every key in
        every probed file (VALUE, OTHER — vars no test ever set) landed in
        os.environ and outlived the call.
        """
        (tmp_path / ".env").write_text("VALUE=from_file\nOTHER=also_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        before = dict(os.environ)
        # override=None exercises the default (argument tier skipped), same
        # as omitting the parameter entirely.
        config = Config.load(env_dir=tmp_path, override=override)
        assert config.value == "from_file"
        assert dict(os.environ) == before
        assert "OTHER" not in os.environ

    def test_reload_leaves_os_environ_untouched(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=tmp_path)
        before = dict(os.environ)
        (tmp_path / ".env").write_text("VALUE=updated_file\n")
        config.reload()
        assert config.value == "updated_file"
        assert dict(os.environ) == before

    def test_cached_leaves_os_environ_untouched(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        before = dict(os.environ)
        config = Config.cached(env_dir=tmp_path)
        assert config.value == "from_file"
        assert dict(os.environ) == before


class TestPrecedence:
    """Layered lookup: process env -> merged dotfiles -> field default (override flips the first two)."""

    def test_env_var_only_resolves_from_env_in_both_modes(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("VALUE", "from_env")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path).value == "from_env"
        assert Config.load(env_dir=tmp_path, override=True).value == "from_env"

    def test_file_only_resolves_from_file_in_both_modes(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("VALUE", raising=False)
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path).value == "from_file"
        assert Config.load(env_dir=tmp_path, override=True).value == "from_file"

    def test_both_set_env_wins_by_default(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path).value == "from_env"

    def test_both_set_file_wins_with_override_true(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path, override=True).value == "from_file"

    def test_neither_set_falls_back_to_field_default(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("VALUE", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path).value == "default"


class TestCascadeLayer:
    """Inside the file layer, later (more specific) files win — the #59 inverted-cascade bug."""

    def test_env_specific_local_file_beats_base_file(self, tmp_path: Path) -> None:
        """The regression: .env sets X=base, .env.dev.local sets X=local -> "local" wins.

        The old per-file load_dotenv(override=False) loop made the FIRST
        file to set a key win, so this resolved to "base".
        """
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.dev.local").write_text("X=local\n")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="dev", env_dir=tmp_path).x == "local"

    def test_full_cascade_most_specific_file_wins(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=base\nONLY_BASE=y\n")
        (tmp_path / ".env.local").write_text("X=local_base\nONLY_LOCAL_BASE=z\n")
        (tmp_path / ".env.dev").write_text("X=dev\n")
        (tmp_path / ".env.dev.local").write_text("X=dev_local\n")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")
            only_base: str = Field(default="unset")
            only_local_base: str = Field(default="unset")

        config = Config.load(env="dev", env_dir=tmp_path)
        assert config.x == "dev_local"
        assert config.only_base == "y"
        assert config.only_local_base == "z"


class TestReadDotfilesFalse:
    """read_dotfiles=False skips the cascade entirely: no probing, no warning, no missing-dir error."""

    def test_missing_env_dir_does_not_raise(self, monkeypatch) -> None:
        monkeypatch.delenv("VALUE", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=Path("/nonexistent/hermetic"), read_dotfiles=False)
        assert config.value == "default"

    def test_no_env_files_found_warning_is_suppressed(self, tmp_path: Path, caplog) -> None:
        """An empty-but-existing dir would warn if dotfiles were read; read_dotfiles=False must not."""

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            config = Config.load(env_dir=tmp_path, read_dotfiles=False)

        assert config.value == "default"
        assert not any("No .env files found" in r.message for r in caplog.records)

    def test_values_come_from_env_and_defaults_only(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".env").write_text("VALUE=from_file\n")
        monkeypatch.delenv("VALUE", raising=False)

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path, read_dotfiles=False).value == "default"

        monkeypatch.setenv("VALUE", "from_env")
        assert Config.load(env_dir=tmp_path, read_dotfiles=False).value == "from_env"

    def test_override_is_moot_without_files(self, tmp_path: Path, monkeypatch) -> None:
        """With no file layer there is nothing for override to promote — the env var wins anyway."""
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=tmp_path, read_dotfiles=False, override=True)
        assert config.value == "from_env"


class TestEnvVarTier:
    """Behavior knobs: explicit argument > DOTENV_* env var > default."""

    def test_dotenv_override_flips_precedence(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DOTENV_OVERRIDE", "true")
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path).value == "from_file"

    def test_explicit_argument_beats_env_var(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DOTENV_OVERRIDE", "true")
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        assert Config.load(env_dir=tmp_path, override=False).value == "from_env"

    def test_invalid_boolean_env_var_warns_and_uses_default(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        monkeypatch.setenv("DOTENV_OVERRIDE", "banana")
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            config = Config.load(env_dir=tmp_path)

        assert config.value == "from_env"  # default override=False held
        assert any("DOTENV_OVERRIDE" in r.message and "banana" in r.message for r in caplog.records)

    def test_dotenv_read_dotfiles_false_skips_files(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        monkeypatch.setenv("DOTENV_READ_DOTFILES", "false")
        monkeypatch.delenv("VALUE", raising=False)
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            config = Config.load(env_dir=tmp_path)

        assert config.value == "default"
        assert not any("No .env files found" in r.message for r in caplog.records)


class TestLoadLocalRule:
    """.local files are skipped by default when env is "test".

    Extends the Next.js/dotenv-flow rule (which skips only .env.local in
    test) to all .local files — a gitignored .env.test.local must not
    decide test outcomes either.
    """

    @staticmethod
    def _write_test_cascade(tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.local").write_text("X=local_base\n")
        (tmp_path / ".env.test").write_text("X=test\n")
        (tmp_path / ".env.test.local").write_text("X=test_local\n")

    def test_test_env_skips_local_files_by_default(self, tmp_path: Path) -> None:
        self._write_test_cascade(tmp_path)

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="test", env_dir=tmp_path).x == "test"

    def test_dotenv_load_local_true_re_includes_local_files(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        self._write_test_cascade(tmp_path)
        monkeypatch.setenv("DOTENV_LOAD_LOCAL", "true")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="test", env_dir=tmp_path).x == "test_local"

    def test_load_local_true_re_includes_local_files(self, tmp_path: Path) -> None:
        self._write_test_cascade(tmp_path)

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="test", env_dir=tmp_path, load_local=True).x == "test_local"

    def test_dev_env_reads_local_files_by_default(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.local").write_text("X=local_base\n")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="dev", env_dir=tmp_path).x == "local_base"

    def test_load_local_false_excludes_local_files_in_dev(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.local").write_text("X=local_base\n")
        (tmp_path / ".env.dev").write_text("X=dev\n")
        (tmp_path / ".env.dev.local").write_text("X=dev_local\n")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="dev", env_dir=tmp_path, load_local=False).x == "dev"

    def test_invalid_dotenv_load_local_warns_and_uses_default(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.test.local").write_text("X=test_local\n")
        monkeypatch.setenv("DOTENV_LOAD_LOCAL", "banana")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            config = Config.load(env="test", env_dir=tmp_path)

        assert config.x == "base"  # the env="test" auto rule held
        assert any(
            "DOTENV_LOAD_LOCAL" in r.message and "banana" in r.message for r in caplog.records
        )


class TestLoadParamsRecording:
    """loaded_with() reports the resolved LoadParams; it raises when there is nothing to report."""

    def test_records_resolved_values_from_env_var_tier(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("ENV", "staging")
        monkeypatch.setenv("DOTENV_DIR", str(tmp_path))

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        config = Config.load()
        assert config.loaded_with() == LoadParams(
            env="staging",
            override=False,
            env_dir=tmp_path,
            read_dotfiles=True,
            load_local=True,
        )

    def test_records_test_env_auto_local_rule(self, tmp_path: Path) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="x")

        config = Config.load(env="test", env_dir=tmp_path)
        params = config.loaded_with()
        assert params.env == "test"
        assert params.load_local is False

    def test_params_equality(self, tmp_path: Path) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="x")

        first = Config.load(env="dev", env_dir=tmp_path).loaded_with()
        second = Config.load(env="dev", env_dir=tmp_path).loaded_with()
        assert first == second
        assert first != LoadParams(
            env="prod", override=False, env_dir=tmp_path, read_dotfiles=True, load_local=True
        )

    def test_loaded_with_raises_on_never_loaded_instance(self) -> None:
        class NeverLoaded(DotEnvConfig):
            value: str = Field(default="x")

        with pytest.raises(RuntimeError, match=r"NeverLoaded instance was never loaded"):
            NeverLoaded().loaded_with()

    def test_load_params_rejects_positional_construction(self) -> None:
        """Every field is keyword-only, locked in before 0.7.0 ships.

        Free while the API is unreleased: a future sixth knob cannot silently
        break positional constructions, because there are none.
        """
        signature = inspect.signature(LoadParams)
        kinds = {param.kind for param in signature.parameters.values()}
        assert kinds == {inspect.Parameter.KEYWORD_ONLY}


class TestNestedConfigLayer:
    """Nested DotEnvConfig fields resolve against the same dotfile layer as their parent."""

    def test_nested_config_resolves_from_dotenv_layer(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("PARENT_FLAG=parent_file\nNESTED_TOKEN=nested_file\n")

        class Nested(DotEnvConfig):
            env_prefix = "NESTED_"
            token: str = Field(default="unset")

        class Parent(DotEnvConfig):
            env_prefix = "PARENT_"
            flag: str = Field(default="unset")
            nested: Nested

        config = Parent.load(env_dir=tmp_path)
        assert config.flag == "parent_file"
        assert config.nested.token == "nested_file"
        assert "NESTED_TOKEN" not in os.environ  # resolved, never injected

    def test_override_policy_threads_into_nested_config(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("NESTED_TOKEN", "nested_env")
        (tmp_path / ".env").write_text("NESTED_TOKEN=nested_file\n")

        class Nested(DotEnvConfig):
            env_prefix = "NESTED_"
            token: str = Field(default="unset")

        class Parent(DotEnvConfig):
            nested: Nested

        assert Parent.load(env_dir=tmp_path).nested.token == "nested_env"
        assert Parent.load(env_dir=tmp_path, override=True).nested.token == "nested_file"

    def test_reload_resolves_nested_from_updated_files(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("NESTED_TOKEN=v1\n")

        class Nested(DotEnvConfig):
            env_prefix = "NESTED_"
            token: str = Field(default="unset")

        class Parent(DotEnvConfig):
            nested: Nested

        config = Parent.load(env_dir=tmp_path)
        assert config.nested.token == "v1"

        (tmp_path / ".env").write_text("NESTED_TOKEN=v2\n")
        config.reload()
        assert config.nested.token == "v2"


class TestCachedDisagreement:
    """cached()'s warm-path warning compares the resolved LoadParams, including the new knobs."""

    def test_read_dotfiles_disagreement_warns(self, caplog) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached(read_dotfiles=False)

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            Config.cached(read_dotfiles=True)

        assert any("arguments were ignored" in r.message for r in caplog.records)

    def test_load_local_disagreement_warns(self, tmp_path: Path, caplog) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached(env="test", env_dir=tmp_path)  # load_local auto-resolves to False

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            Config.cached(env="test", env_dir=tmp_path, load_local=True)

        assert any("arguments were ignored" in r.message for r in caplog.records)

    def test_disagreement_warning_presents_resolved_vs_recorded(
        self, tmp_path: Path, caplog
    ) -> None:
        """The warning compares the call's resolved configuration against the cache's
        recorded LoadParams — neither tuple is the caller's raw arguments."""

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached(env="test", env_dir=tmp_path)  # load_local auto-resolves to False

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            Config.cached(env="test", env_dir=tmp_path, load_local=True)

        warnings = [r for r in caplog.records if "cached() called" in r.message]
        assert len(warnings) == 1
        message = warnings[0].message
        assert "resolved configuration" in message
        assert "LoadParams recorded on the cached instance" in message
        assert "arguments were ignored" in message

    def test_matching_arguments_stay_silent(self, tmp_path: Path, caplog) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached(env="test", env_dir=tmp_path)

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            Config.cached(env="test", env_dir=tmp_path)
            Config.cached(env="test", env_dir=tmp_path, load_local=False)

        assert list(caplog.records) == []

    def test_override_installed_dict_instance_is_returned_without_judging(
        self, monkeypatch
    ) -> None:
        """cached() inside a cached_override() block must keep working with a dict-loaded instance.

        loaded_with() raises on instances that never went through an
        environment load; the warm path must not let that escape — an
        override-installed instance has no recorded params to disagree
        with, so it is returned as-is.
        """
        monkeypatch.setenv("VALUE", "env")

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        override = Config.load_from_dict({"VALUE": "override"})
        with Config.cached_override(override):
            assert Config.cached() is override


class TestReloadReuse:
    """A bare reload() repeats all five recorded load parameters."""

    def test_bare_reload_repeats_read_dotfiles_false(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=tmp_path, read_dotfiles=False)
        assert config.value == "default"
        config.reload()
        assert config.value == "default"  # files still not read

    def test_bare_reload_repeats_load_local_skip_for_test_env(self, tmp_path: Path) -> None:
        (tmp_path / ".env.test").write_text("VALUE=from_test\n")
        (tmp_path / ".env.test.local").write_text("VALUE=from_local\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env="test", env_dir=tmp_path)
        assert config.value == "from_test"
        config.reload()
        assert config.value == "from_test"  # .env.test.local still skipped

    def test_bare_reload_repeats_override(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=tmp_path, override=True)
        assert config.value == "from_file"
        config.reload()
        assert config.value == "from_file"  # override=True reused, env var loses again

    def test_bare_reload_repeats_recorded_override_over_env_var_channel(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Recorded params are what reload() repeats — the env-var tier is not re-consulted."""
        monkeypatch.setenv("VALUE", "from_env")
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=tmp_path)  # override=False recorded
        assert config.value == "from_env"

        monkeypatch.setenv("DOTENV_OVERRIDE", "true")
        config.reload()
        assert config.value == "from_env"

    def test_reload_picks_up_env_var_changes_over_files(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env_dir=tmp_path)
        assert config.value == "from_file"

        monkeypatch.setenv("VALUE", "new_env")
        config.reload()
        assert config.value == "new_env"

    def test_reload_updates_recorded_params(self, tmp_path: Path) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load(env="dev", env_dir=tmp_path, read_dotfiles=False)
        config.reload(
            env="prod",
            env_dir=tmp_path,
            override=True,
            read_dotfiles=True,
            load_local=False,
        )
        assert config.loaded_with() == LoadParams(
            env="prod",
            override=True,
            env_dir=tmp_path,
            read_dotfiles=True,
            load_local=False,
        )

    def test_reload_after_load_from_dict_uses_tier_defaults(self, monkeypatch) -> None:
        """A dict-loaded instance has no recorded params; reload() resolves from the tiers."""
        monkeypatch.setenv("VALUE", "env_value")

        class Config(DotEnvConfig):
            value: str = Field(default="default")

        config = Config.load_from_dict({"VALUE": "dict_value"})
        assert config.value == "dict_value"

        config.reload()
        assert config.value == "env_value"
        assert config.loaded_with().env == "dev"


class TestReadEnvFilesUnits:
    """read_env_files(): the pure merged-cascade reader replacing load_env_files()."""

    def test_later_files_win_within_the_layer(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("A=1\nB=base\n")
        (tmp_path / ".env.local").write_text("A=2\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values == {"A": "2", "B": "base"}
        assert layer.base_dir == tmp_path
        assert layer.files == (tmp_path / ".env", tmp_path / ".env.local")

    def test_bare_keys_are_left_unset(self, tmp_path: Path) -> None:
        """python-dotenv returns None for a bare `KEY`, and its load_dotenv() skips
        such keys entirely — the merged layer leaves them unset rather than "".

        Normalizing them to "" would silently satisfy required fields with an
        empty value python-dotenv itself would never set.
        """
        (tmp_path / ".env").write_text("BARE\nSET=x\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values == {"SET": "x"}
        assert "BARE" not in layer.values

    def test_missing_base_dir_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="does not exist"):
            read_env_files(env="dev", env_dir=Path("/nonexistent/hermetic"))

    def test_no_files_found_warns_and_returns_empty_layer(self, tmp_path: Path, caplog) -> None:
        with caplog.at_level("WARNING", logger="dotenvmodel"):
            layer = read_env_files(env="dev", env_dir=tmp_path)

        assert layer.values == {}
        assert layer.files == ()
        assert any("No .env files found" in r.message for r in caplog.records)

    def test_load_local_false_skips_local_probes(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("A=base\n")
        (tmp_path / ".env.local").write_text("A=local\nB=local_only\n")
        (tmp_path / ".env.dev.local").write_text("C=dev_local_only\n")

        layer = read_env_files(env="dev", env_dir=tmp_path, load_local=False)
        assert layer.values == {"A": "base"}
        assert tmp_path / ".env.local" not in layer.files
        assert tmp_path / ".env.dev.local" not in layer.files

    def test_env_name_resolved_from_env_var(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("ENV", "ci")
        (tmp_path / ".env.ci").write_text("VALUE=ci_file\n")

        layer = read_env_files(env_dir=tmp_path)
        assert layer.values == {"VALUE": "ci_file"}

    def test_env_dir_resolved_from_dotenv_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DOTENV_DIR", str(tmp_path))
        (tmp_path / ".env").write_text("VALUE=dir_file\n")

        layer = read_env_files(env="dev")
        assert layer.base_dir == tmp_path
        assert layer.values == {"VALUE": "dir_file"}

    def test_never_mutates_os_environ(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("VALUE=from_file\n")
        before = dict(os.environ)

        read_env_files(env="dev", env_dir=tmp_path)

        assert dict(os.environ) == before

    def test_invalid_env_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid environment name"):
            read_env_files(env="../etc", env_dir=Path("."))


class TestInterpolation:
    """${VAR} references resolve once against the merged layer, then os.environ."""

    def test_single_file_self_reference(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("HOST=localhost\nURL=http://${HOST}:5432\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values["URL"] == "http://localhost:5432"

    def test_cross_file_reference_reads_earlier_files_values(self, tmp_path: Path) -> None:
        """The regression: later cascade files used to interpolate against earlier files.

        The old sequential load_dotenv() loop had injected .env's HOST into
        os.environ before .env.local was read, so its ${HOST} resolved; the
        pure per-file read had lost that cross-file base.
        """
        (tmp_path / ".env").write_text("HOST=db.internal\n")
        (tmp_path / ".env.local").write_text("URL=postgres://${HOST}/app\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values["URL"] == "postgres://db.internal/app"

    def test_merged_layer_beats_process_env_in_the_interpolation_base(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("HOST", "from_env")
        (tmp_path / ".env").write_text("HOST=from_file\nURL=http://${HOST}\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values["URL"] == "http://from_file"

    def test_os_environ_is_the_fallback_base(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("EXTRA", "from_env")
        (tmp_path / ".env").write_text("X=prefixed-${EXTRA}\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values["X"] == "prefixed-from_env"

    def test_unresolved_reference_becomes_empty_string(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("MISSING", raising=False)
        (tmp_path / ".env").write_text("X=${MISSING}-suffix\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values["X"] == "-suffix"

    def test_interpolation_is_independent_of_override(self, tmp_path: Path, monkeypatch) -> None:
        """override flips per-field precedence, not the interpolation base.

        HOST resolves from the process env for the field lookup when
        override=False, but URL — read from the file — still interpolates
        against the file layer's HOST in both modes.
        """
        monkeypatch.setenv("HOST", "from_env")
        (tmp_path / ".env").write_text("HOST=from_file\nURL=http://${HOST}\n")

        class Config(DotEnvConfig):
            host: str = Field(default="unset")
            url: str = Field(default="unset")

        default_mode = Config.load(env_dir=tmp_path)
        assert default_mode.host == "from_env"
        assert default_mode.url == "http://from_file"

        override_mode = Config.load(env_dir=tmp_path, override=True)
        assert override_mode.host == "from_file"
        assert override_mode.url == "http://from_file"


class TestBareKeyParity:
    """A bare `KEY` line is unset in every layer, matching python-dotenv's load_dotenv()."""

    def test_required_field_with_a_bare_key_line_still_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("REQUIRED\n")

        class Config(DotEnvConfig):
            required: str = Field()

        with pytest.raises(MissingFieldError, match="REQUIRED"):
            Config.load(env_dir=tmp_path)

    def test_defaulted_field_with_a_bare_key_line_uses_its_default(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("FLAG\n")

        class Config(DotEnvConfig):
            flag: str = Field(default="fallback")

        assert Config.load(env_dir=tmp_path).flag == "fallback"


class TestLocalRuleCaseInsensitivity:
    """The test-env .local skip matches TEST/Test too, not just lowercase "test"."""

    @staticmethod
    def _write_cascade(tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.local").write_text("X=local_base\n")
        (tmp_path / ".env.TEST").write_text("X=test\n")
        (tmp_path / ".env.TEST.local").write_text("X=test_local\n")

    def test_uppercase_test_env_skips_local_files_in_load(self, tmp_path: Path) -> None:
        self._write_cascade(tmp_path)

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="TEST", env_dir=tmp_path).x == "test"

    def test_ambient_uppercase_env_env_var_skips_local_files_in_load(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("ENV", "TEST")
        self._write_cascade(tmp_path)

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env_dir=tmp_path).x == "test"

    def test_reader_skips_local_files_for_uppercase_test_env(self, tmp_path: Path) -> None:
        self._write_cascade(tmp_path)

        layer = read_env_files(env="TEST", env_dir=tmp_path)
        assert layer.values == {"X": "test"}
        assert layer.files == (tmp_path / ".env", tmp_path / ".env.TEST")

    def test_resolve_load_params_auto_rule_is_case_insensitive(self) -> None:
        assert resolve_load_params("Test").load_local is False
        assert resolve_load_params("dev").load_local is True


class TestReaderLoadLocalTier:
    """read_env_files() resolves load_local through the same tiers as load()."""

    @staticmethod
    def _write_test_cascade(tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=base\n")
        (tmp_path / ".env.local").write_text("X=local_base\n")
        (tmp_path / ".env.test").write_text("X=test\n")
        (tmp_path / ".env.test.local").write_text("X=test_local\n")

    def test_reader_default_matches_load_for_test_env(self, tmp_path: Path) -> None:
        """The previously-confirmed divergence: the reader included .local in test envs."""
        self._write_test_cascade(tmp_path)

        layer = read_env_files(env="test", env_dir=tmp_path)
        assert layer.values == {"X": "test"}
        assert layer.files == (tmp_path / ".env", tmp_path / ".env.test")

        class Config(DotEnvConfig):
            x: str = Field(default="unset")

        assert Config.load(env="test", env_dir=tmp_path).x == "test"

    def test_dotenv_load_local_env_var_steers_the_reader(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DOTENV_LOAD_LOCAL", "true")
        self._write_test_cascade(tmp_path)

        layer = read_env_files(env="test", env_dir=tmp_path)
        assert layer.values["X"] == "test_local"
        assert tmp_path / ".env.test.local" in layer.files

    def test_skipped_local_files_are_logged_with_restore_knobs(
        self, tmp_path: Path, caplog
    ) -> None:
        """A present-but-skipped .local file is named, with both ways to restore it."""
        self._write_test_cascade(tmp_path)

        with caplog.at_level("INFO", logger="dotenvmodel"):
            read_env_files(env="test", env_dir=tmp_path)

        skip_messages = [r.message for r in caplog.records if "Skipping" in r.message]
        assert len(skip_messages) == 2
        assert any(str(tmp_path / ".env.local") in m for m in skip_messages)
        assert any(str(tmp_path / ".env.test.local") in m for m in skip_messages)
        for message in skip_messages:
            assert "load_local=True" in message
            assert "DOTENV_LOAD_LOCAL=true" in message

    def test_no_skip_log_when_no_local_file_exists(self, tmp_path: Path, caplog) -> None:
        (tmp_path / ".env").write_text("X=base\n")

        with caplog.at_level("INFO", logger="dotenvmodel"):
            read_env_files(env="test", env_dir=tmp_path)

        assert not any("load_local=True" in r.message for r in caplog.records)

    def test_reading_a_file_logs_the_reading_wording(self, tmp_path: Path, caplog) -> None:
        """Nothing is injected into the environment anymore — the log says "Reading"."""
        (tmp_path / ".env").write_text("A=1\n")

        with caplog.at_level("INFO", logger="dotenvmodel"):
            read_env_files(env="dev", env_dir=tmp_path)

        assert any(f"Reading .env file: {tmp_path / '.env'}" in r.message for r in caplog.records)


class TestWarmPathRobustness:
    """A warm cached() never raises and never warns from unresolvable arguments."""

    def test_warm_cached_survives_a_deleted_process_cwd(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        """Path.cwd() failing (deleted cwd) must not break a call whose arguments are ignored anyway.

        The warm path resolves the caller's arguments only to compare them;
        when resolution itself fails there is nothing to judge — the cached
        instance is returned silently.
        """
        monkeypatch.chdir(tmp_path)

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        first = Config.cached(read_dotfiles=False)

        tmp_path.rmdir()  # the process cwd is now unlinked; Path.cwd() raises

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            second = Config.cached(read_dotfiles=False)

        assert second is first
        assert list(caplog.records) == []

    def test_warm_cached_survives_an_ambient_invalid_env(self, monkeypatch, caplog) -> None:
        monkeypatch.setenv("ENV", "valid-env")

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        first = Config.cached(read_dotfiles=False)

        monkeypatch.setenv("ENV", "../etc")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            second = Config.cached(read_dotfiles=False)

        assert second is first
        assert list(caplog.records) == []

    def test_warm_cached_with_invalid_env_argument_returns_cached_silently(self, caplog) -> None:
        class Config(DotEnvConfig):
            value: str = Field(default="x")

        first = Config.cached(read_dotfiles=False)

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            second = Config.cached(env="../etc", read_dotfiles=False)

        assert second is first
        assert list(caplog.records) == []


class TestEnvDirAbsolutization:
    """resolve_env_dir() returns absolute paths so recorded params stay cwd-stable."""

    def test_explicit_relative_env_dir_is_joined_onto_cwd(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert resolve_env_dir(Path("rel")) == tmp_path / "rel"

    def test_relative_dotenv_dir_is_joined_onto_cwd(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DOTENV_DIR", "rel")
        assert resolve_env_dir(None) == tmp_path / "rel"

    def test_absolutization_is_lexical_not_normalized(self, tmp_path: Path, monkeypatch) -> None:
        """No resolve(): .. segments and duplicate separators survive as written."""
        monkeypatch.chdir(tmp_path)
        assert resolve_env_dir(Path("rel/../rel2")) == tmp_path / "rel" / ".." / "rel2"

    def test_bare_reload_reads_the_original_directory_after_chdir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A relative env_dir is recorded absolute, so a bare reload() is cwd-stable.

        Recording "rel" unresolved would make the reload read the NEW cwd's
        rel/ directory instead of the one the load actually used.
        """
        base = tmp_path / "a"
        (base / "rel").mkdir(parents=True)
        (base / "rel" / ".env").write_text("VALUE=original\n")
        other = tmp_path / "b"
        (other / "rel").mkdir(parents=True)
        (other / "rel" / ".env").write_text("VALUE=moved\n")

        class Config(DotEnvConfig):
            value: str = Field(default="unset")

        monkeypatch.chdir(base)
        config = Config.load(env_dir=Path("rel"))
        assert config.value == "original"

        monkeypatch.chdir(other)
        config.reload()
        assert config.value == "original"

    def test_bare_reload_reads_original_directory_with_relative_dotenv_dir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        base = tmp_path / "a"
        (base / "rel").mkdir(parents=True)
        (base / "rel" / ".env").write_text("VALUE=original\n")
        other = tmp_path / "b"
        (other / "rel").mkdir(parents=True)
        (other / "rel" / ".env").write_text("VALUE=moved\n")

        class Config(DotEnvConfig):
            value: str = Field(default="unset")

        monkeypatch.chdir(base)
        monkeypatch.setenv("DOTENV_DIR", "rel")
        config = Config.load()
        assert config.value == "original"

        monkeypatch.chdir(other)
        config.reload()
        assert config.value == "original"

    def test_warm_cached_with_a_relative_dir_stays_silent(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        """A relative env_dir spelling of the recorded directory must not warn as a disagreement."""
        base = tmp_path / "a"
        (base / "rel").mkdir(parents=True)
        (base / "rel" / ".env").write_text("VALUE=from_file\n")

        class Config(DotEnvConfig):
            value: str = Field(default="unset")

        monkeypatch.chdir(base)
        first = Config.cached(env_dir=base / "rel")
        assert first.value == "from_file"

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            second = Config.cached(env_dir=Path("rel"))

        assert second is first
        assert list(caplog.records) == []


class TestEnvNameResolution:
    """resolve_env_name(): an empty ENV env var is treated as unset."""

    def test_empty_env_env_var_is_treated_as_unset(self, monkeypatch) -> None:
        monkeypatch.setenv("ENV", "")
        assert resolve_env_name(None) == "dev"

    def test_empty_env_env_var_resolves_to_dev_in_load(self, monkeypatch) -> None:
        monkeypatch.setenv("ENV", "")

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        assert Config.load(read_dotfiles=False).loaded_with().env == "dev"


class TestDotenvLayerRepr:
    """DotenvLayer's repr shows key names and counts, never values — merged values may be secrets."""

    def test_repr_masks_values_but_names_keys(self, tmp_path: Path) -> None:
        """The auto-generated dataclass repr would print every merged value in cleartext,
        including process-env values pulled in via ${VAR} interpolation."""
        (tmp_path / ".env").write_text("SECRET=hunter2\nPLAIN=visible\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        rendered = repr(layer)

        assert "SECRET" in rendered
        assert "PLAIN" in rendered
        assert "hunter2" not in rendered
        assert "visible" not in rendered
        assert "values=<2 keys: SECRET, PLAIN>" in rendered
        assert f"base_dir={tmp_path!r}" in rendered

    def test_values_attribute_remains_fully_accessible(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=hunter2\n")

        layer = read_env_files(env="dev", env_dir=tmp_path)
        assert layer.values["SECRET"] == "hunter2"


class TestGetEnvVarUnits:
    """get_env_var() keeps its os.getenv-only contract after the resolution rewrite.

    It no longer has an internal caller (_load_fields resolves through the
    layered lookup instead), but it is public API advertised for direct
    use, so its behavior is pinned here.
    """

    def test_reads_the_prefixed_upper_case_name(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_TOKEN", "value")
        assert get_env_var("token", prefix="APP_") == "value"

    def test_alias_is_absolute_and_ignores_prefix(self, monkeypatch) -> None:
        monkeypatch.setenv("ALIASED", "value")
        assert get_env_var("token", alias="ALIASED", prefix="APP_") == "value"

    def test_unset_variable_returns_none(self, monkeypatch) -> None:
        monkeypatch.delenv("APP_TOKEN", raising=False)
        assert get_env_var("token", prefix="APP_") is None


class TestResolveBool:
    """resolve_bool(): the shared boolean-knob resolver (argument > env var > default)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("true", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("Yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("OFF", False),
        ],
    )
    def test_parses_recognized_values_case_insensitively(
        self, monkeypatch, raw: str, expected: bool
    ) -> None:
        monkeypatch.setenv("DOTENV_TEST_FLAG", raw)
        assert resolve_bool(None, "DOTENV_TEST_FLAG", default=not expected) is expected

    def test_explicit_argument_beats_the_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("DOTENV_TEST_FLAG", "true")
        assert resolve_bool(False, "DOTENV_TEST_FLAG", default=True) is False

    def test_unset_env_var_yields_the_default(self, monkeypatch) -> None:
        monkeypatch.delenv("DOTENV_TEST_FLAG", raising=False)
        assert resolve_bool(None, "DOTENV_TEST_FLAG", default=True) is True

    def test_invalid_value_warns_and_returns_the_default(self, monkeypatch, caplog) -> None:
        monkeypatch.setenv("DOTENV_TEST_FLAG", "banana")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            assert resolve_bool(None, "DOTENV_TEST_FLAG", default=False) is False

        assert any(
            "DOTENV_TEST_FLAG" in r.message and "banana" in r.message for r in caplog.records
        )

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (" true ", True),
            ("\tfalse\n", False),
            ("  YES  ", True),
        ],
    )
    def test_strips_surrounding_whitespace(self, monkeypatch, raw: str, expected: bool) -> None:
        monkeypatch.setenv("DOTENV_TEST_FLAG", raw)
        assert resolve_bool(None, "DOTENV_TEST_FLAG", default=not expected) is expected

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_whitespace_only_value_is_treated_as_unset_silently(
        self, monkeypatch, caplog, raw: str
    ) -> None:
        """An empty value is ignored, not warned about — DOTENV_DIR's empty-value policy."""
        monkeypatch.setenv("DOTENV_TEST_FLAG", raw)

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            assert resolve_bool(None, "DOTENV_TEST_FLAG", default=True) is True

        assert list(caplog.records) == []
