"""Tests for the cached() / reset_cached() singleton accessor on DotEnvConfig."""

import contextlib
import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path
from typing import assert_type

import pytest

from dotenvmodel import DotEnvConfig, Field, MissingFieldError, ValidationError, ValidatorContext
from dotenvmodel.caching import has_cached

# A project-wide autouse fixture in tests/conftest.py snapshots and restores
# _cached_instance on every alive DotEnvConfig subclass after each test.
# For THIS file, the fixture is belt-and-suspenders: every test defines its
# own locally-scoped subclass, so when the test function returns, the class
# object becomes unreachable and both the class and its cached instance are
# collectible — isolation is a structural property, not something a fixture
# provides. The conftest fixture protects other test files that use
# module-scoped or imported config classes and call cached().


class TestCached:
    """Test cached() singleton accessor and reset_cached()."""

    def test_repeated_calls_return_same_instance(self, monkeypatch) -> None:
        """Repeated cached() calls return the exact same instance."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "first")

        first = Config.cached()
        second = Config.cached()

        assert first is second

    def test_env_read_only_once(self, monkeypatch) -> None:
        """cached() does not re-read the environment after the first call."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "original")

        first = Config.cached()
        assert first.value == "original"

        # Mutate the environment — cached should NOT pick this up.
        monkeypatch.setenv("VALUE", "changed")

        second = Config.cached()
        assert second is first
        assert second.value == "original"

    def test_load_called_exactly_once_across_repeated_calls(self, monkeypatch) -> None:
        """cached() calls the underlying load() exactly once across repeated calls."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "first")

        load_count = 0
        original_load = Config.load

        def counting_load(*args, **kwargs):
            nonlocal load_count
            load_count += 1
            return original_load(*args, **kwargs)

        monkeypatch.setattr(Config, "load", counting_load)

        for _ in range(4):
            Config.cached()

        assert load_count == 1

    def test_reset_cached_picks_up_changed_env(self, monkeypatch) -> None:
        """reset_cached() forces the next cached() call to re-read env."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "first")
        first = Config.cached()
        assert first.value == "first"

        monkeypatch.setenv("VALUE", "second")
        Config.reset_cached()
        second = Config.cached()
        assert second.value == "second"
        assert second is not first

    def test_reset_cached_safe_when_nothing_cached(self) -> None:
        """reset_cached() is a no-op when nothing is cached yet."""

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        # Should not raise.
        Config.reset_cached()

    def test_independent_subclasses_have_independent_caches(self, monkeypatch) -> None:
        """Two different DotEnvConfig subclasses cache independently."""

        class ConfigA(DotEnvConfig):
            value: str = Field()

        class ConfigB(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "from_a")
        a = ConfigA.cached()

        monkeypatch.setenv("VALUE", "from_b")
        b = ConfigB.cached()

        assert a.value == "from_a"
        assert b.value == "from_b"
        assert a is not b

        # Caching B must not have affected A's cache.
        monkeypatch.setenv("VALUE", "ignored")
        a_again = ConfigA.cached()
        assert a_again is a
        assert a_again.value == "from_a"

    def test_subclass_does_not_inherit_parent_cache(self, monkeypatch) -> None:
        """A subclass of a cached subclass gets its own cache entry."""

        class Parent(DotEnvConfig):
            value: str = Field()

        class Child(Parent):
            pass

        monkeypatch.setenv("VALUE", "parent")
        parent = Parent.cached()

        monkeypatch.setenv("VALUE", "child")
        child = Child.cached()

        assert parent is not child
        assert parent.value == "parent"
        assert child.value == "child"

    def test_cached_returns_concrete_subclass_type(self, monkeypatch) -> None:
        """cached() is typed to return the concrete subclass, not the base."""

        class MyConfig(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "typed")

        config = MyConfig.cached()
        assert_type(config, MyConfig)
        assert config.value == "typed"

    def test_warning_logged_when_args_disagree_with_the_warm_cache(
        self, monkeypatch, caplog
    ) -> None:
        """cached() warns when a caller's args differ from the ones that populated the cache."""

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached()

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            result = Config.cached(env="prod", override=False, env_dir=Path("/tmp"))

        assert result is Config.cached()
        assert any("arguments were ignored" in r.message for r in caplog.records)

    def test_repeating_the_arguments_the_cache_was_built_with_is_silent(
        self, monkeypatch, caplog
    ) -> None:
        """Asking for what you already got is not a mistake and must not be reported as one.

        The motivating case is an application accessor that must pass ``override=False`` (the
        process environment beats ``.env`` files, per 12-factor) on every call. Warning it every
        time emits a line per settings access for entirely correct usage — and a warning that
        fires on correct usage is one readers learn to filter out, costing it the job it exists
        for, which ``test_warning_logged_when_args_disagree_with_the_warm_cache`` still covers.

        Asserts on WHETHER anything was reported, never on the wording: the promise is silence,
        not a particular sentence, and a reworded message must not fail this test.
        """

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        args = {"env": "prod", "override": False, "env_dir": Path("/tmp")}
        first = Config.cached(**args)

        # Window opened AFTER the populating call, so only the repeats are observed.
        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            second = Config.cached(**args)
            third = Config.cached(**args)
            repeats_reported = list(caplog.records)

        assert second is first
        assert third is first
        assert repeats_reported == []

    def test_a_bare_reload_keeps_the_precedence_the_cache_was_loaded_with(
        self, monkeypatch, caplog
    ) -> None:
        """The SIGHUP shape: ``reload()`` with no arguments must not revert to ``override=True``.

        A hot-reload handler calls ``reload()`` bare. If that silently reset precedence to
        "``.env`` files beat the process environment", a running service would flip to the
        opposite configuration on a signal it was told was a no-op refresh — and an accessor
        passing ``override=False`` would then also start warning, having never changed.
        """

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        instance = Config.cached(override=False, env_dir=Path("/tmp"))
        assert instance.loaded_with() == (None, False, Path("/tmp"))

        instance.reload()

        assert instance.loaded_with() == (None, False, Path("/tmp"))
        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            assert Config.cached(override=False, env_dir=Path("/tmp")) is instance
            reported = list(caplog.records)
        assert reported == []

    def test_a_reset_cache_is_not_judged_against_the_arguments_it_dropped(
        self, monkeypatch, caplog
    ) -> None:
        """After ``reset_cached()`` the next call repopulates, so it cannot disagree with anything."""

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached(override=False)
        Config.reset_cached()
        # Repopulate OUTSIDE the window: a real load emits its own unrelated warnings (e.g. "no
        # .env files found"), and this test is about the warm path, not about loading.
        Config.cached(env="prod")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            Config.cached(env="prod")
            reported = list(caplog.records)

        assert reported == []

    def test_a_scoped_override_leaves_the_warm_cache_judged_as_before(
        self, monkeypatch, caplog
    ) -> None:
        """Exiting ``cached_override()`` restores the pre-override state, warnings included."""

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        Config.cached(override=False)
        with Config.cached_override(Config.load_from_dict({"VALUE": "y"})):
            pass

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            caplog.clear()
            Config.cached(override=False)
            agreeing = list(caplog.records)
            caplog.clear()
            Config.cached(env="prod")
            disagreeing = list(caplog.records)

        assert agreeing == []
        assert len(disagreeing) == 1

    def test_thread_safety_concurrent_first_access(self, monkeypatch) -> None:
        """Concurrent first callers all receive the same single instance."""
        import time

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "threaded")

        load_count = 0
        count_lock = threading.Lock()
        original_load = Config.load

        def slow_load(*args, **kwargs):
            nonlocal load_count
            time.sleep(0.05)  # Make the race window wide.
            with count_lock:
                load_count += 1
            return original_load(*args, **kwargs)

        monkeypatch.setattr(Config, "load", slow_load)

        results: list[DotEnvConfig] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()  # Line up all threads.
            instance = Config.cached()
            with results_lock:
                results.append(instance)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 8
        first_instance = results[0]
        assert all(r is first_instance for r in results)
        assert load_count == 1

    def test_failed_first_load_unwinds_and_retry_succeeds(self, monkeypatch) -> None:
        """A first cached() call whose load() raises leaves the cache cold and the lock usable.

        Covers the unwind path: the lock is released on failure, no instance is
        installed, a retry after fixing the environment succeeds, and an
        unrelated class can still cached() afterwards (the global lock is not
        wedged by the failure).
        """

        class Config(DotEnvConfig):
            value: str = Field()

        class Other(DotEnvConfig):
            other_value: str = Field()

        monkeypatch.setenv("OTHER_VALUE", "other")

        # No VALUE set — the first cached() call raises.
        with pytest.raises(MissingFieldError):
            Config.cached()

        # Nothing was installed; the cache is still cold.
        assert not has_cached(Config)

        # The global lock was released. Probed from a DIFFERENT thread: with
        # an RLock, a same-thread re-acquire would succeed even if the unwind
        # path leaked a lock count owned by this thread, so only a
        # cross-thread acquisition proves the lock is truly free.
        done: list[str] = []
        probe = threading.Thread(target=lambda: done.append(Other.cached().other_value))
        probe.start()
        probe.join(timeout=10)
        assert not probe.is_alive(), "cross-thread cached() hung — lock not released on failure"
        assert done == ["other"]

        # Retry succeeds once the missing value appears.
        monkeypatch.setenv("VALUE", "recovered")
        config = Config.cached()
        assert config.value == "recovered"
        assert Config.cached() is config

    def test_cached_override_replaces_inside_with(self, monkeypatch) -> None:
        """cached_override() makes cached() return the override inside the with block."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "env")
        override = Config.load_from_dict({"VALUE": "override"})

        with Config.cached_override(override) as ctx:
            assert ctx is override
            assert Config.cached() is override

    def test_cached_override_restores_nothing_after_with(self, monkeypatch) -> None:
        """After the with block (nothing cached before), cache is cleared."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "fresh")
        override = Config.load_from_dict({"VALUE": "override"})

        with Config.cached_override(override):
            assert Config.cached() is override

        fresh = Config.cached()
        assert fresh is not override
        assert fresh.value == "fresh"

    def test_cached_override_restores_previous_after_with(self, monkeypatch) -> None:
        """After the with block, the previously cached instance is restored."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "original")
        original = Config.cached()

        override = Config.load_from_dict({"VALUE": "override"})

        with Config.cached_override(override):
            assert Config.cached() is override

        restored = Config.cached()
        assert restored is original
        assert restored.value == "original"

    def test_cached_override_restores_on_exception(self, monkeypatch) -> None:
        """Restoration happens even if the with block raises."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "original")
        original = Config.cached()

        override = Config.load_from_dict({"VALUE": "override"})

        with pytest.raises(RuntimeError, match="boom"), Config.cached_override(override):
            assert Config.cached() is override
            raise RuntimeError("boom")

        restored = Config.cached()
        assert restored is original
        assert restored.value == "original"

    def test_cached_override_independent_classes(self, monkeypatch) -> None:
        """Overriding one class does not affect another's cache."""

        class ConfigA(DotEnvConfig):
            value: str = Field()

        class ConfigB(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "a")
        a = ConfigA.cached()
        monkeypatch.setenv("VALUE", "b")
        b = ConfigB.cached()

        override_a = ConfigA.load_from_dict({"VALUE": "override_a"})

        with ConfigA.cached_override(override_a):
            assert ConfigA.cached() is override_a
            assert ConfigB.cached() is b

        assert ConfigA.cached() is a
        assert ConfigB.cached() is b

    def test_nested_cached_override_restores_lifo(self, monkeypatch) -> None:
        """Nested cached_override() blocks unwind in LIFO order back to the original instance."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "original")
        original = Config.cached()

        override_a = Config.load_from_dict({"VALUE": "override_a"})
        override_b = Config.load_from_dict({"VALUE": "override_b"})

        with Config.cached_override(override_a):
            assert Config.cached() is override_a
            with Config.cached_override(override_b):
                assert Config.cached() is override_b
            # Exiting the inner override restores the outer one.
            assert Config.cached() is override_a
        # Exiting the outer override restores the pre-existing instance.
        assert Config.cached() is original

    def test_nested_cached_override_cold_start_leaves_cache_cold(self, monkeypatch) -> None:
        """Nested overrides on a cold cache leave it cold; the next cached() loads fresh."""

        class Config(DotEnvConfig):
            value: str = Field()

        monkeypatch.setenv("VALUE", "from_env")

        override_a = Config.load_from_dict({"VALUE": "override_a"})
        override_b = Config.load_from_dict({"VALUE": "override_b"})

        with Config.cached_override(override_a):
            assert Config.cached() is override_a
            with Config.cached_override(override_b):
                assert Config.cached() is override_b
            assert Config.cached() is override_a

        # Nothing was cached before either override, so the cache is cold
        # again and the next cached() call loads from the environment.
        assert not has_cached(Config)
        fresh = Config.cached()
        assert fresh.value == "from_env"
        assert fresh is not override_a
        assert fresh is not override_b


class TestCachedLifecycle:
    """Tests for cache storage lifecycle and reentrancy safety."""

    def test_dynamic_class_and_cache_are_garbage_collected(self, monkeypatch) -> None:
        """A dynamically-created config class and its cached instance are reclaimed once unreachable."""
        import gc
        import weakref

        def make_and_cache() -> weakref.ReferenceType[type[DotEnvConfig]]:
            class Ephemeral(DotEnvConfig):
                value: str = Field(default="x")

            Ephemeral.cached()
            return weakref.ref(Ephemeral)

        class_ref = make_and_cache()
        gc.collect()
        assert class_ref() is None

    def test_reentrant_cached_call_raises_instead_of_recursing(self, monkeypatch) -> None:
        """Calling cached() reentrantly from post_load() raises RuntimeError.

        The internal lock is reentrant, so the nested call would not hang —
        it would see a cold cache and recurse into load() without bound.
        """
        monkeypatch.setenv("VALUE", "x")

        class Config(DotEnvConfig):
            value: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                Config.cached()
                return None

        with pytest.raises(RuntimeError, match="Reentrant cached"):
            Config.cached()

    def test_cached_reflects_reload_on_instance(self, monkeypatch) -> None:
        """reload() on the cached instance is visible to subsequent cached() calls (shared reference)."""
        monkeypatch.setenv("VALUE", "first")

        class Config(DotEnvConfig):
            value: str = Field()

        config = Config.cached()
        assert config.value == "first"

        monkeypatch.setenv("VALUE", "second")
        config.reload()
        assert config.value == "second"

        again = Config.cached()
        assert again is config
        assert again.value == "second"

    def test_base_class_has_no_cached_instance_entry(self) -> None:
        """DotEnvConfig itself carries no ``_cached_instance`` entry in ``__dict__``.

        The class attribute is a bare annotation (no assignment), so the base
        class's ``__dict__`` has no entry: ``has_cached(DotEnvConfig)`` is
        False, and ``reset_cached()`` on the bare base class is a harmless
        no-op that neither raises nor creates/deletes anything.
        """
        assert "_cached_instance" not in DotEnvConfig.__dict__
        assert has_cached(DotEnvConfig) is False

        DotEnvConfig.reset_cached()  # must not raise

        assert "_cached_instance" not in DotEnvConfig.__dict__


class TestHookReentrancy:
    """Cache access from load() / post_load() / validator hooks.

    Cross-class cache operations from a hook are supported (the internal lock
    is reentrant); same-class operations from within that class's own
    in-flight load raise RuntimeError.
    """

    def test_cross_class_cached_from_post_load_completes(self, monkeypatch) -> None:
        """A post_load() hook calling cached() on a DIFFERENT cold class completes; both cache."""
        monkeypatch.setenv("A_VALUE", "from_a")
        monkeypatch.setenv("B_VALUE", "from_b")

        class ConfigB(DotEnvConfig):
            b_value: str = Field()

        seen: list[DotEnvConfig] = []

        class ConfigA(DotEnvConfig):
            a_value: str = Field()

            def post_load(self) -> list[ValidationError] | None:
                seen.append(ConfigB.cached())
                return None

        a = ConfigA.cached()
        assert a.a_value == "from_a"

        # Both classes are cached, and the instance the hook received is the
        # one B.cached() returns afterwards.
        assert len(seen) == 1
        assert seen[0] is ConfigB.cached()
        assert ConfigB.cached().b_value == "from_b"

    def test_cross_class_reset_and_override_from_post_load_work(self, monkeypatch) -> None:
        """A hook may reset_cached() / cached_override() a DIFFERENT class mid-load."""
        monkeypatch.setenv("A_VALUE", "from_a")
        monkeypatch.setenv("B_VALUE", "from_b_env")

        class ConfigB(DotEnvConfig):
            b_value: str = Field()

        b_env_instance = ConfigB.cached()
        assert b_env_instance.b_value == "from_b_env"
        b_override = ConfigB.load_from_dict({"B_VALUE": "b_override"})

        observations: list[DotEnvConfig] = []

        class ConfigA(DotEnvConfig):
            a_value: str = Field()

            def post_load(self) -> list[ValidationError] | None:
                ConfigB.reset_cached()
                with ConfigB.cached_override(b_override):
                    observations.append(ConfigB.cached())
                return None

        a = ConfigA.cached()
        assert a.a_value == "from_a"
        assert observations == [b_override]

        # The override exited inside the hook; B had no pre-override entry
        # (the hook reset it), so B is cold again and reloads from the env.
        monkeypatch.setenv("B_VALUE", "from_b_fresh")
        fresh_b = ConfigB.cached()
        assert fresh_b.b_value == "from_b_fresh"
        assert fresh_b is not b_env_instance
        assert fresh_b is not b_override

    def test_reset_cached_from_own_post_load_raises(self, monkeypatch) -> None:
        """reset_cached() for the SAME class from its own in-flight load raises RuntimeError."""
        monkeypatch.setenv("VALUE", "x")

        class Config(DotEnvConfig):
            value: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                Config.reset_cached()
                return None

        with pytest.raises(RuntimeError, match="silently undo this reset"):
            Config.cached()

    def test_cached_override_from_own_post_load_raises(self, monkeypatch) -> None:
        """cached_override() for the SAME class from its own in-flight load raises RuntimeError."""
        monkeypatch.setenv("VALUE", "x")

        class Config(DotEnvConfig):
            value: str = Field(default="x")

            def post_load(self) -> list[ValidationError] | None:
                # Bare construction: load_from_dict() would re-run post_load
                # and recurse; the override instance need not be loaded.
                with Config.cached_override(Config()):
                    pass
                return None

        with pytest.raises(RuntimeError, match="silently discard the override"):
            Config.cached()

    def test_same_class_cached_from_field_validator_raises(self, monkeypatch) -> None:
        """A field validator calling cached() on the SAME class raises RuntimeError."""
        monkeypatch.setenv("VALUE", "x")

        def reentrant_validator(value: str, context: ValidatorContext) -> str:
            Config.cached()
            return value

        class Config(DotEnvConfig):
            value: str = Field(default="x", validator=reentrant_validator)

        with pytest.raises(RuntimeError, match="Reentrant cached"):
            Config.cached()

    def test_circular_cross_class_chain_raises_and_unwinds(self, monkeypatch) -> None:
        """A circular hook chain (A loads B, B loads A) raises RuntimeError and unwinds cleanly.

        Documented behavior: the nested B.cached() runs on the same thread
        (the lock is reentrant), so B's hook calling A.cached() collapses back
        onto A — which is in this thread's loading set — and is reported as a
        same-class reentrancy error. The exception must propagate through both
        nested load frames with the loading set cleaned and the lock fully
        released: neither class is cached afterwards, and an unrelated class
        can still cached().
        """
        monkeypatch.setenv("A_VALUE", "from_a")
        monkeypatch.setenv("B_VALUE", "from_b")
        monkeypatch.setenv("C_VALUE", "from_c")

        class ConfigB(DotEnvConfig):
            b_value: str = Field()

            def post_load(self) -> list[ValidationError] | None:
                ConfigA.cached()
                return None

        class ConfigA(DotEnvConfig):
            a_value: str = Field()

            def post_load(self) -> list[ValidationError] | None:
                ConfigB.cached()
                return None

        class ConfigC(DotEnvConfig):
            c_value: str = Field()

        with pytest.raises(RuntimeError, match="Reentrant cached"):
            ConfigA.cached()

        # Both load frames unwound: nothing was cached for either class...
        assert not has_cached(ConfigA)
        assert not has_cached(ConfigB)

        # ...the loading set was cleaned (a retry raises the circularity
        # error again rather than a stale-set false positive)...
        with pytest.raises(RuntimeError, match="Reentrant cached"):
            ConfigA.cached()

        # ...and the global lock was fully released. Probed from a DIFFERENT
        # thread: with an RLock, a same-thread re-acquire would succeed even
        # if the unwind path leaked a lock count owned by this thread, so
        # only a cross-thread acquisition proves the lock is truly free.
        done: list[str] = []
        probe = threading.Thread(target=lambda: done.append(ConfigC.cached().c_value))
        probe.start()
        probe.join(timeout=10)
        assert not probe.is_alive(), "cross-thread cached() hung — lock not fully released"
        assert done == ["from_c"]

    def test_reset_cached_from_own_field_validator_raises(self, monkeypatch) -> None:
        """A field validator calling reset_cached() on the SAME class raises RuntimeError.

        Pins the validator-path guard: the RuntimeError must bubble through
        the validator wrapper (non-sensitive fields re-raise only
        ValueError/TypeError as ConstraintViolationError; other exceptions
        propagate unchanged).
        """
        monkeypatch.setenv("VALUE", "x")

        def resetting_validator(value: str, context: ValidatorContext) -> str:
            Config.reset_cached()
            return value

        class Config(DotEnvConfig):
            value: str = Field(default="x", validator=resetting_validator)

        with pytest.raises(RuntimeError, match="silently undo this reset"):
            Config.cached()

    def test_cached_override_from_own_field_validator_raises(self, monkeypatch) -> None:
        """A field validator entering cached_override() on the SAME class raises RuntimeError."""
        monkeypatch.setenv("VALUE", "x")

        def overriding_validator(value: str, context: ValidatorContext) -> str:
            # Bare construction: load_from_dict() would re-run the validator
            # and recurse; the override instance need not be loaded.
            with Config.cached_override(Config()):
                pass
            return value

        class Config(DotEnvConfig):
            value: str = Field(default="x", validator=overriding_validator)

        with pytest.raises(RuntimeError, match="silently discard the override"):
            Config.cached()

    def test_nested_config_field_hook_reentrancy_raises(self, monkeypatch) -> None:
        """A nested config field's own post_load() calling its own cached() raises RuntimeError.

        Nested DotEnvConfig fields load via _process_field -> nested
        ._load_fields(), which does NOT mark the nested class in the loading
        set, so the first B.cached() call from B's post_load() starts a fresh
        full load of B; that recursive load's hook calls B.cached() again and
        collapses onto the now-marked B, raising. The RuntimeError propagates
        through both load frames: neither class is cached afterwards.
        """
        monkeypatch.setenv("B_VALUE", "from_b")

        class ConfigB(DotEnvConfig):
            b_value: str = Field()

            def post_load(self) -> list[ValidationError] | None:
                ConfigB.cached()
                return None

        class ConfigA(DotEnvConfig):
            b: ConfigB

        with pytest.raises(RuntimeError, match="Reentrant cached"):
            ConfigA.cached()

        assert not has_cached(ConfigA)
        assert not has_cached(ConfigB)


class TestCachedStateFixture:
    """Tests proving the conftest.py autouse fixture correctly restores cached state.

    We drive the fixture's generator function manually (call it, advance past
    ``yield`` with ``next()``, mutate state, then trigger teardown with
    ``next()`` again) instead of using ``pytester``. This directly tests the
    actual fixture function from ``tests/conftest.py`` (not a duplicate in a
    nested conftest), is simpler with no plugin configuration, and faithfully
    simulates pytest's own behavior of calling ``next(gen)`` in a finally
    block to run teardown even when the test body raises.
    """

    def test_cached_instance_excluded_from_get_fields(self) -> None:
        """``_cached_instance`` is not swept into ``get_fields()`` by the metaclass."""

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        fields = Config.get_fields()
        assert "_cached_instance" not in fields
        assert "_loaded" not in fields
        assert "_load_env" not in fields

    def test_fixture_removes_new_cached_entry(self) -> None:
        """The fixture removes cached entries that did not exist before the test."""
        from tests.conftest import _snapshot_and_restore_cached_state

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        gen = _snapshot_and_restore_cached_state()
        next(gen)  # setup — snapshot taken (Config has no cached entry)

        Config.cached()
        assert "_cached_instance" in Config.__dict__

        with pytest.raises(StopIteration):
            next(gen)  # teardown

        assert "_cached_instance" not in Config.__dict__

    def test_fixture_restores_previous_cached_value(self) -> None:
        """The fixture restores a pre-existing cached value after the test."""
        from tests.conftest import _snapshot_and_restore_cached_state

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        original = Config.cached()

        gen = _snapshot_and_restore_cached_state()
        next(gen)  # setup — snapshot records Config._cached_instance = original

        override = Config.load_from_dict({"VALUE": "override"})
        Config._cached_instance = override
        assert Config.__dict__["_cached_instance"] is override

        with pytest.raises(StopIteration):
            next(gen)  # teardown

        assert Config.__dict__["_cached_instance"] is original

    def test_fixture_restores_even_when_test_raises(self) -> None:
        """The fixture's teardown runs and restores state even when the test body raises.

        We simulate pytest's behavior of calling ``next(gen)`` in a finally
        block: the teardown code after ``yield`` executes regardless of
        whether the test body raised an exception.
        """
        from tests.conftest import _snapshot_and_restore_cached_state

        class Config(DotEnvConfig):
            value: str = Field(default="x")

        gen = _snapshot_and_restore_cached_state()
        next(gen)  # setup

        Config.cached()
        assert "_cached_instance" in Config.__dict__

        try:
            try:
                raise RuntimeError("simulated test failure")
            finally:
                with contextlib.suppress(StopIteration):
                    next(gen)  # teardown runs despite the exception
        except RuntimeError:
            pass  # expected — the simulated test failure

        assert "_cached_instance" not in Config.__dict__

    def test_fixture_removes_base_class_entry_added_after_setup(self) -> None:
        """The fixture removes a ``_cached_instance`` entry added to DotEnvConfig itself mid-test."""
        from tests.conftest import _snapshot_and_restore_cached_state

        assert "_cached_instance" not in DotEnvConfig.__dict__  # precondition

        gen = _snapshot_and_restore_cached_state()
        next(gen)  # setup — base class has no entry in the snapshot

        try:
            sentinel = DotEnvConfig()
            DotEnvConfig._cached_instance = sentinel
            assert DotEnvConfig.__dict__["_cached_instance"] is sentinel

            with pytest.raises(StopIteration):
                next(gen)  # teardown

            assert "_cached_instance" not in DotEnvConfig.__dict__
        finally:
            # These tests mutate DotEnvConfig itself — never poison the base
            # class for later tests, even if this one fails.
            if "_cached_instance" in DotEnvConfig.__dict__:
                delattr(DotEnvConfig, "_cached_instance")

    def test_fixture_restores_base_class_entry_present_before_setup(self) -> None:
        """The fixture restores a pre-existing base-class entry that was changed mid-test."""
        from tests.conftest import _snapshot_and_restore_cached_state

        original = DotEnvConfig()
        replacement = DotEnvConfig()

        DotEnvConfig._cached_instance = original
        try:
            gen = _snapshot_and_restore_cached_state()
            next(gen)  # setup — snapshot records base entry = original

            DotEnvConfig._cached_instance = replacement
            assert DotEnvConfig.__dict__["_cached_instance"] is replacement

            with pytest.raises(StopIteration):
                next(gen)  # teardown

            assert DotEnvConfig.__dict__["_cached_instance"] is original
        finally:
            # The base class had no entry before this test — remove whatever
            # remains so later tests are not poisoned.
            if "_cached_instance" in DotEnvConfig.__dict__:
                delattr(DotEnvConfig, "_cached_instance")


# Child programs for the deadlock regression tests. Each is self-contained:
# it sets field values via os.environ, defines its config classes at module
# level, exercises one cross-class cache operation from a load hook, and
# prints the CHILD_OK sentinel on success. Pre-fix (non-reentrant lock) each
# of these self-deadlocked the only thread; post-fix they complete in ~1s.
_CHILD_CROSS_CLASS_CACHED = textwrap.dedent(
    """
    import os

    os.environ["A_VALUE"] = "from_a"
    os.environ["B_VALUE"] = "from_b"

    from dotenvmodel import DotEnvConfig, Field


    class ConfigB(DotEnvConfig):
        b_value: str = Field()


    class ConfigA(DotEnvConfig):
        a_value: str = Field()

        def post_load(self):
            ConfigB.cached()
            return None


    a = ConfigA.cached()
    assert a.a_value == "from_a"
    assert ConfigB.cached().b_value == "from_b"
    print("CHILD_OK")
    """
)

_CHILD_CROSS_CLASS_RESET = textwrap.dedent(
    """
    import os

    os.environ["A_VALUE"] = "from_a"
    os.environ["B_VALUE"] = "from_b"

    from dotenvmodel import DotEnvConfig, Field


    class ConfigB(DotEnvConfig):
        b_value: str = Field()


    b_cached = ConfigB.cached()


    class ConfigA(DotEnvConfig):
        a_value: str = Field()

        def post_load(self):
            ConfigB.reset_cached()
            return None


    ConfigA.cached()
    assert not ConfigB.__dict__.get("_cached_instance")
    print("CHILD_OK")
    """
)

_CHILD_CROSS_CLASS_OVERRIDE = textwrap.dedent(
    """
    import os

    os.environ["A_VALUE"] = "from_a"

    from dotenvmodel import DotEnvConfig, Field


    class ConfigB(DotEnvConfig):
        b_value: str = Field(default="b_default")


    b_override = ConfigB.load_from_dict({"B_VALUE": "b_override"})


    class ConfigA(DotEnvConfig):
        a_value: str = Field()

        def post_load(self):
            with ConfigB.cached_override(b_override):
                assert ConfigB.cached() is b_override
            return None


    ConfigA.cached()
    print("CHILD_OK")
    """
)


class TestCrossClassDeadlockRegression:
    """Regression tests for the pre-RLock cross-class deadlocks.

    Each scenario runs in its own subprocess (hermetic): if the fix regresses,
    the child hangs on the lock and is killed by the timeout, rather than
    wedging this pytest process's module-level cache lock for the rest of the
    session. cwd is a tmp dir so no project .env files interfere.
    """

    @pytest.mark.parametrize(
        "program",
        [
            _CHILD_CROSS_CLASS_CACHED,
            _CHILD_CROSS_CLASS_RESET,
            _CHILD_CROSS_CLASS_OVERRIDE,
        ],
        ids=["cross-class-cached", "cross-class-reset-cached", "cross-class-cached-override"],
    )
    def test_cross_class_hook_scenarios_complete(self, tmp_path, program: str) -> None:
        try:
            result = subprocess.run(
                [sys.executable, "-c", program],
                timeout=60,  # Generous so slow CI doesn't flake; healthy runs take ~1s.
                capture_output=True,
                text=True,
                cwd=tmp_path,
                # Point .env discovery at the empty tmp dir so a stray
                # DOTENV_DIR in the ambient environment cannot inject files.
                env={**os.environ, "DOTENV_DIR": str(tmp_path)},
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                "child process timed out after 60s — possible deadlock "
                "regression in cross-class cache access from a load hook"
            )
        assert result.returncode == 0, f"child failed:\n{result.stderr}"
        assert "CHILD_OK" in result.stdout
