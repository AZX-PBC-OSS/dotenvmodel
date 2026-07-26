"""Shared pytest fixtures and configuration for dotenvmodel tests."""

from collections.abc import Iterator

import pytest

from dotenvmodel import DotEnvConfig

_CACHED_ATTR = "_cached_instance"


def _all_dotenv_subclasses() -> Iterator[type[DotEnvConfig]]:
    """Yield every currently-alive DotEnvConfig subclass, recursively.

    ``type.__subclasses__()`` returns only direct subclasses and uses weak
    references internally — it does not prevent garbage collection of classes
    with no other referents (verified empirically). We walk the tree
    depth-first, deduplicating by identity to handle diamond hierarchies.
    """
    seen: set[type] = set()
    stack: list[type] = list(DotEnvConfig.__subclasses__())
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
        yield cls


@pytest.fixture(autouse=True)
def _restore_cached_state() -> Iterator[None]:
    """Snapshot and restore ``_cached_instance`` on every DotEnvConfig subclass.

    Function-scoped (autouse) because cached state must be restored after
    every single test — a session-scoped fixture would allow one test's
    cached instance to leak into the next.

    At setup, walks every alive ``DotEnvConfig`` subclass and records which
    ones have their *own* ``_cached_instance`` entry in ``cls.__dict__``
    (not inherited) and what the value is. At teardown, restores the exact
    pre-test state: classes that had an entry get it restored; classes
    discovered after the test that have an entry but did not have one before
    get it removed. Classes that had no entry before and still have none
    are untouched.

    This is a belt-and-suspenders safety net. For test files where every
    test defines its own locally-scoped subclass, isolation is already
    structural — the class goes out of scope when the test returns, and
    both the class and its cached instance become collectible together.
    This fixture protects against leaks from tests that use module-scoped
    or imported config classes and call ``cached()``.
    """
    yield from _snapshot_and_restore_cached_state()


def _snapshot_and_restore_cached_state() -> Iterator[None]:
    """Generator that snapshots and restores ``_cached_instance`` on all subclasses.

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
