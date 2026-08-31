"""Shared pytest fixtures and configuration for dotenvmodel tests."""

import os
from collections.abc import Iterator

import pytest

from dotenvmodel import DotEnvConfig
from dotenvmodel.caching import _CACHED_ATTR

# Environment variables that steer load() behavior (explicit argument >
# env var > default). Scrubbed at setup so an ambient value in the
# developer's or CI's shell cannot silently flip behavior for one test
# and not the next.
_KNOB_ENV_VARS = (
    "ENV",
    "DOTENV_DIR",
    "DOTENV_OVERRIDE",
    "DOTENV_READ_DOTFILES",
    "DOTENV_LOAD_LOCAL",
)


def _all_dotenv_subclasses() -> Iterator[type[DotEnvConfig]]:
    """Yield DotEnvConfig itself and every currently-alive subclass, recursively.

    The stack is seeded with the base class so its own cached state (if any)
    is snapshotted/restored too — the caching module stores instances as
    per-class ``__dict__`` entries, and the base class is itself a valid
    ``cached()`` target.

    ``type.__subclasses__()`` returns only direct subclasses and uses weak
    references internally — it does not prevent garbage collection of classes
    with no other referents (verified empirically). We walk the tree
    depth-first, deduplicating by identity to handle diamond hierarchies.
    """
    seen: set[type[DotEnvConfig]] = set()
    stack: list[type[DotEnvConfig]] = [DotEnvConfig]
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
        yield cls


@pytest.fixture(autouse=True)
def _isolate_environ() -> Iterator[None]:
    """Snapshot ``os.environ`` around every test and scrub the ``DOTENV_*`` knobs.

    The load() behavior channel (explicit argument > environment variable >
    default) means a stray ``ENV`` / ``DOTENV_DIR`` / ``DOTENV_OVERRIDE`` /
    ``DOTENV_READ_DOTFILES`` / ``DOTENV_LOAD_LOCAL`` in the ambient
    environment — a developer's shell, a CI runner, or a previous test that
    forgot to clean up — would silently flip precedence or file discovery
    for every test after it. Popping the knobs at setup makes each test
    start from the documented defaults; restoring the exact pre-test
    snapshot at teardown keeps any mid-test mutation (raw ``os.environ``
    writes, subprocess helpers) from leaking onward.

    ``monkeypatch`` users are unaffected: its own undo runs against the
    same snapshot semantics, and this fixture never re-adds anything the
    test did not leave behind.
    """
    yield from _snapshot_and_restore_environ()


def _snapshot_and_restore_environ() -> Iterator[None]:
    """Generator that snapshots/restores ``os.environ`` around a test.

    This is the underlying logic for :func:`_isolate_environ`, extracted as
    a plain (non-fixture) generator so it can be driven manually in unit
    tests that verify the scrub/restore behavior — the same pattern as
    ``_snapshot_and_restore_cached_state``.

    Drive with ``next(gen)`` to run setup (snapshot + scrub), then
    ``next(gen)`` again to run teardown (restore); the second call raises
    ``StopIteration``.
    """
    before = dict(os.environ)
    for var in _KNOB_ENV_VARS:
        os.environ.pop(var, None)
    yield
    os.environ.clear()
    os.environ.update(before)


@pytest.fixture(autouse=True)
def _restore_cached_state() -> Iterator[None]:
    """Snapshot and restore ``_cached_instance`` on DotEnvConfig and every subclass.

    Function-scoped (autouse) because cached state must be restored after
    every single test — a session-scoped fixture would allow one test's
    cached instance to leak into the next.

    At setup, walks ``DotEnvConfig`` itself and every alive subclass and
    records which ones have their *own* ``_cached_instance`` entry in
    ``cls.__dict__`` (not inherited) and what the value is. At teardown,
    restores the exact pre-test state: classes that had an entry get it
    restored; classes discovered after the test that have an entry but did
    not have one before get it removed. Classes that had no entry before
    and still have none are untouched.

    This is a belt-and-suspenders safety net. For test files where every
    test defines its own locally-scoped subclass, isolation is already
    structural — the class goes out of scope when the test returns, and
    both the class and its cached instance become collectible together.
    This fixture protects against leaks from tests that use module-scoped
    or imported config classes and call ``cached()``.
    """
    yield from _snapshot_and_restore_cached_state()


def _snapshot_and_restore_cached_state() -> Iterator[None]:
    """Generator that snapshots/restores ``_cached_instance`` on the base class and all subclasses.

    This is the underlying logic for :func:`_restore_cached_state`, extracted
    as a plain (non-fixture) generator so it can also be driven manually in
    unit tests that verify the restore behavior — pytest 9+ disallows calling
    ``@pytest.fixture``-decorated functions directly.

    Drive with ``next(gen)`` to run setup (snapshot), then ``next(gen)``
    again to run teardown (restore); the second call raises ``StopIteration``.
    """
    before: dict[type, object] = {}
    for cls in _all_dotenv_subclasses():
        if _CACHED_ATTR in cls.__dict__:
            before[cls] = cls.__dict__[_CACHED_ATTR]

    yield

    for cls in _all_dotenv_subclasses():
        if cls in before:
            setattr(cls, _CACHED_ATTR, before[cls])
        elif _CACHED_ATTR in cls.__dict__:
            delattr(cls, _CACHED_ATTR)
