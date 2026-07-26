"""Tests for the cached() / reset_cached() singleton accessor on DotEnvConfig."""

import threading
from typing import assert_type

import pytest

from dotenvmodel import DotEnvConfig, Field


@pytest.fixture(autouse=True)
def _reset_cached_after_test():
    """Ensure no cached instances leak between tests."""
    yield
    DotEnvConfig.reset_cached()


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
