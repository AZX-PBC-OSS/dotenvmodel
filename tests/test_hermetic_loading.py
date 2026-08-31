"""Tests for hermetic loading: environ isolation, layered resolution, pure .env reading.

Covers the resolution model behind ``DotEnvConfig.load()`` — layered lookup
across the process environment, the merged dotfile cascade, and field
defaults, with no ``os.environ`` mutation — plus the suite-wide
``os.environ`` isolation that makes the ``DOTENV_*`` env-var channel safe
to use between tests.
"""

import os

import pytest


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
