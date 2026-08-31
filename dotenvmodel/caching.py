"""Cached singleton-instance machinery for DotEnvConfig subclasses.

Provides the internal implementation behind ``DotEnvConfig.cached()``,
``DotEnvConfig.reset_cached()``, and ``DotEnvConfig.cached_override()``.
The public API lives on ``DotEnvConfig`` itself as thin classmethod wrappers
that preserve concrete-subclass typing (``Self``); this module operates on
plain ``type[DotEnvConfig]`` / ``DotEnvConfig`` and is not part of the
package's public API.

The cached instance is stored as a private class attribute
(``_cached_instance``) on each config subclass's own ``__dict__`` rather than
in a module-level registry.  This ties the cache lifetime to the class object:
when nothing else references the class, both the class and its cached instance
become collectible together.

Thread safety:
    A module-level ``threading.RLock`` guards the double-checked-locking
    initialization path and the save/restore operations in
    ``begin_override`` / ``end_override``. A reentrant lock (not a plain
    ``Lock``) is required because the lock is held across ``cls.load()``:
    ``post_load()`` and field ``validator`` hooks may legitimately touch
    the cache for *other* classes, and a non-reentrant lock would
    self-deadlock that thread. With a single module-level lock no
    cross-thread circular wait is possible — only one thread holds the
    lock and the holder always proceeds — so same-thread nesting is the
    only reentrancy case, and the RLock permits it.

    Same-class operations from within that class's own in-flight load
    remain invalid: ``cached()`` cannot return an instance that does not
    exist yet (the nested call would see a cold cache and recurse into
    ``load()`` without bound), and ``reset_cached()`` /
    ``cached_override()`` would be silently overwritten when the
    in-flight load installs its instance. A ``threading.local`` set
    tracks classes currently loading on each thread; all three entry
    points raise ``RuntimeError`` in that case. A circular cross-class
    chain (A's hook loads B, B's hook loads A) collapses back onto the
    first class and is likewise reported as a same-class
    ``RuntimeError``.

    One residual hazard sits outside this design: the lock is held for
    the duration of a load, so a hook must not block on another thread
    (e.g. ``thread.join()``) that touches the cache — the joining thread
    holds the lock while the joined thread waits for it, deadlocking
    both.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dotenvmodel._constants import LOGGER_NAME

# resolve_load_params deliberately lives in loading (not config): config.py
# imports caching at runtime, so importing it from config here would be
# circular.
from dotenvmodel.loading import resolve_load_params

if TYPE_CHECKING:
    from dotenvmodel.config import DotEnvConfig

logger = logging.getLogger(LOGGER_NAME)

_CACHED_ATTR = "_cached_instance"
_cache_lock = threading.RLock()
_loading_local = threading.local()


def _get_loading_set() -> set[type[DotEnvConfig]]:
    """Get or create this thread's set of classes currently loading via ``cached()``.

    Used to reject same-class cache operations issued from within that
    class's own in-flight load (see the module docstring's "Thread safety"
    section). Each thread gets its own independent set, so only same-thread
    reentrancy is detected (the only possible nesting case with a single
    module-level reentrant lock). Cross-thread contention is handled by
    ``_cache_lock``.
    """
    loading = cast("set[type[DotEnvConfig]] | None", getattr(_loading_local, "loading", None))
    if loading is None:
        loading = set()
        _loading_local.__dict__["loading"] = loading
    return loading


def get_cached(cls: type[DotEnvConfig]) -> DotEnvConfig | None:
    """Return the cached instance stored in *cls*'s own ``__dict__``, or ``None``.

    Reads ``cls.__dict__`` (not ``getattr``) so that only an entry set
    directly on *cls* — not one inherited from a parent class via the MRO —
    is considered a cache hit.
    """
    return cls.__dict__.get(_CACHED_ATTR)


def has_cached(cls: type[DotEnvConfig]) -> bool:
    """Return ``True`` if *cls* has its own ``_cached_instance`` entry in ``__dict__``."""
    return _CACHED_ATTR in cls.__dict__


def set_cached(cls: type[DotEnvConfig], instance: DotEnvConfig) -> None:
    """Store *instance* as the cached singleton on *cls*.

    This is an unlocked primitive — callers are responsible for acquiring
    ``_cache_lock`` when thread-safety is required.
    """
    setattr(cls, _CACHED_ATTR, instance)


def clear_cached(cls: type[DotEnvConfig]) -> None:
    """Remove *cls*'s own cached instance entry if one exists.

    Safe to call when no entry is present (no-op). Acquires ``_cache_lock``
    internally.

    Raises:
        RuntimeError: If called for *cls* from within that class's own
            in-flight load (``load()`` / ``post_load()`` / field
            ``validator`` on this thread): the load installs its instance
            when it completes, which would silently undo this reset.
            Cross-class calls (e.g. one class's hook resetting another
            class) are permitted.
    """
    if cls in _get_loading_set():
        raise RuntimeError(
            f"reset_cached() called for {cls.__name__} from within that "
            f"class's own in-flight load (load() / post_load() / "
            f"validator): the load installs its instance when it "
            f"completes, which would silently undo this reset. Call "
            f"reset_cached() after the load finishes instead."
        )
    with _cache_lock:
        if has_cached(cls):
            delattr(cls, _CACHED_ATTR)


def acquire_cached(
    cls: type[DotEnvConfig],
    env: str | None,
    override: bool | None,
    env_dir: Path | str | None,
    read_dotfiles: bool | None,
    load_local: bool | None,
) -> DotEnvConfig:
    """Return the cached instance for *cls*, loading on first call.

    Implements double-checked locking: a lock-free fast path checks
    ``cls.__dict__``; if the cache is warm, the existing instance is returned
    immediately (with a warning if the caller's arguments resolve differently
    from the parameters the cached instance holds). If the cache is cold, a
    module-level lock is acquired and the check is repeated before calling
    ``cls.load()``.

    Reentrant calls for the same class from within that class's own
    ``load()`` / ``post_load()`` / field ``validator`` hooks are detected
    via a thread-local loading set and raise ``RuntimeError``: the internal
    lock is reentrant, so the nested call would not deadlock — it would see
    a cold cache and recurse into ``load()`` without bound. Nested calls
    for *other* classes from those hooks proceed normally.

    Args:
        cls: The config class to cache for.
        env: Environment name (only used on first call).
        override: Whether dotfiles beat the process env (only used on first call).
        env_dir: Custom .env directory (only used on first call).
        read_dotfiles: Whether to read dotfiles at all (only used on first call).
        load_local: Whether to include ``.local`` files (only used on first call).

    Returns:
        The cached ``DotEnvConfig`` instance.

    Raises:
        RuntimeError: If ``cached()`` is called reentrantly for *cls* from
            within that class's own load path (including via a circular
            cross-class hook chain that collapses back onto *cls*).
    """
    cached = get_cached(cls)
    if cached is not None:
        # An instance installed via cached_override() that never went through
        # an environment load (load_from_dict(), bare construction) has no
        # recorded parameters to disagree with — loaded_with() would raise,
        # and there is nothing to compare, so it is returned unjudged.
        if cached._load_params is not None:
            # Warn on DISAGREEMENT, not on non-default arguments. The caller's
            # arguments are resolved through the same tier model the cache was
            # built with first, so an accessor that consistently asks for what
            # it already got (however it spells it) stays silent; a warning
            # that fires on correct usage is one readers learn to filter out.
            # A caller whose *resolved* request differs from what the cache
            # holds is the real bug this catches, and it still fires.
            #
            # Compared against the INSTANCE's own record of how it was loaded —
            # the same fields `reload()` reuses — rather than a second copy
            # kept beside the cache. One source of truth, and self-correcting:
            # `reload(env="prod")` updates them, so a later `cached()` is
            # judged against what the cached object actually holds now, not
            # against whatever populated it originally.
            #
            # Both tuples in the message are tier-RESOLVED configuration —
            # this call's resolved request vs. the cache's recorded
            # LoadParams — never the caller's raw arguments, which are not
            # observable here (the same resolved request can be spelled many
            # ways: explicit argument, env var, or default).
            #
            # Resolution failure is swallowed, not raised: the warm path
            # ignores arguments by contract (see the docstring), so when
            # they cannot even be resolved — the process cwd was deleted, a
            # stray ambient ENV is invalid — there is nothing to judge and
            # the cached instance is returned silently.
            #
            # The handler wraps ONLY the resolution. Extending it over the
            # comparison and the logger.warning() call below would swallow a
            # failure in the reporting itself, erasing the diagnostic at the
            # one moment it was about to be emitted.
            try:
                requested = resolve_load_params(
                    env,
                    override=override,
                    env_dir=env_dir,
                    read_dotfiles=read_dotfiles,
                    load_local=load_local,
                )
            except (OSError, ValueError):
                logger.debug(
                    "cached() called on %s: arguments could not be resolved for the "
                    "disagreement check; they are ignored on the warm path either way.",
                    cls.__name__,
                    exc_info=True,
                )
                return cached

            loaded = cached.loaded_with()
            if requested != loaded:
                logger.warning(
                    "cached() called on %s: this call's resolved configuration "
                    "(env=%r, override=%r, env_dir=%r, read_dotfiles=%r, "
                    "load_local=%r) differs from the LoadParams recorded on "
                    "the cached instance (env=%r, override=%r, env_dir=%r, "
                    "read_dotfiles=%r, load_local=%r); arguments were ignored "
                    "and the cached instance was returned.",
                    cls.__name__,
                    requested.env,
                    requested.override,
                    requested.env_dir,
                    requested.read_dotfiles,
                    requested.load_local,
                    loaded.env,
                    loaded.override,
                    loaded.env_dir,
                    loaded.read_dotfiles,
                    loaded.load_local,
                )
        return cached

    loading = _get_loading_set()
    if cls in loading:
        raise RuntimeError(
            f"Reentrant cached() call detected for {cls.__name__}: "
            f"cached() was called for this class while its first "
            f"cached() call is still loading (inside load() / "
            f"post_load() / validator). The instance cannot exist until "
            f"that first load completes, and the internal lock is "
            f"reentrant, so the nested call would recurse into load() "
            f"without bound. If a hook needs the instance mid-load, call "
            f"cls.load() directly or use 'self' instead."
        )

    try:
        # add() lives inside the try so a (vanishingly unlikely) async
        # exception between add and try-entry cannot strand cls in this
        # thread's loading set; discard() on a never-added class is a no-op.
        loading.add(cls)
        with _cache_lock:
            cached = get_cached(cls)
            if cached is not None:
                return cached

            instance = cls.load(
                env=env,
                override=override,
                env_dir=env_dir,
                read_dotfiles=read_dotfiles,
                load_local=load_local,
            )
            set_cached(cls, instance)
            return instance
    finally:
        loading.discard(cls)


def begin_override(
    cls: type[DotEnvConfig],
    instance: DotEnvConfig,
) -> tuple[bool, DotEnvConfig | None]:
    """Save the current cached state on *cls* and install *instance* as the override.

    Returns ``(had_cached, previous)`` so the caller can restore the exact
    pre-override state via :func:`end_override`. Acquires ``_cache_lock``
    internally.

    Raises:
        RuntimeError: If called for *cls* from within that class's own
            in-flight load (``load()`` / ``post_load()`` / field
            ``validator`` on this thread): the load installs its instance
            when it completes, which would silently discard the override.
            Cross-class calls (e.g. one class's hook overriding another
            class) are permitted.
    """
    if cls in _get_loading_set():
        raise RuntimeError(
            f"cached_override() entered for {cls.__name__} from within "
            f"that class's own in-flight load (load() / post_load() / "
            f"validator): the load installs its instance when it "
            f"completes, which would silently discard the override. "
            f"Enter the override after the load finishes instead."
        )
    with _cache_lock:
        had_cached = has_cached(cls)
        previous = get_cached(cls)
        set_cached(cls, instance)
    return had_cached, previous


def end_override(
    cls: type[DotEnvConfig],
    had_cached: bool,
    previous: DotEnvConfig | None,
) -> None:
    """Restore the cached state saved by :func:`begin_override`.

    If *had_cached* is ``True``, *previous* is restored. If *had_cached* is
    ``False`` and *cls* now has its own entry (e.g. a concurrent ``cached()``
    call set one), the entry is removed. Acquires ``_cache_lock`` internally.

    No same-class loading guard here by design: via ``cached_override()`` this
    only runs after a successful :func:`begin_override`, which already
    rejected entry while *cls* was loading on this thread.
    """
    with _cache_lock:
        if had_cached:
            set_cached(cls, cast("DotEnvConfig", previous))
        elif has_cached(cls):
            delattr(cls, _CACHED_ATTR)
