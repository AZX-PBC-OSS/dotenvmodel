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
    A module-level ``threading.Lock`` guards the double-checked-locking
    initialization path and the save/restore operations in
    ``begin_override`` / ``end_override``.  A ``threading.local`` set tracks
    same-thread reentrant ``cached()`` calls to detect and raise on
    self-deadlock scenarios.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dotenvmodel._constants import LOGGER_NAME

if TYPE_CHECKING:
    from dotenvmodel.config import DotEnvConfig

logger = logging.getLogger(LOGGER_NAME)

_CACHED_ATTR = "_cached_instance"
_cache_lock = threading.Lock()
_loading_local = threading.local()


def _get_loading_set() -> set[type[DotEnvConfig]]:
    """Get or create this thread's set of classes currently loading via ``cached()``.

    Used for reentrant-``cached()`` deadlock detection. Each thread gets its
    own independent set, so only same-thread reentrancy is detected (the actual
    deadlock scenario). Cross-thread contention is handled by ``_cache_lock``.
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
    """
    with _cache_lock:
        if has_cached(cls):
            delattr(cls, _CACHED_ATTR)


def acquire_cached(
    cls: type[DotEnvConfig],
    env: str | None,
    override: bool,
    env_dir: Path | None,
) -> DotEnvConfig:
    """Return the cached instance for *cls*, loading on first call.

    Implements double-checked locking: a lock-free fast path checks
    ``cls.__dict__``; if the cache is warm, the existing instance is returned
    immediately (with a warning if non-default arguments were passed against
    an already-warm cache). If the cache is cold, a module-level lock is
    acquired and the check is repeated before calling ``cls.load()``.

    Reentrant calls for the same class from within that class's own
    ``load()`` / ``post_load()`` / field ``validator`` hooks are detected
    via a thread-local loading set and raise ``RuntimeError`` instead of
    deadlocking on the non-reentrant lock.

    Args:
        cls: The config class to cache for.
        env: Environment name (only used on first call).
        override: Whether .env files override env vars (only used on first call).
        env_dir: Custom .env directory (only used on first call).

    Returns:
        The cached ``DotEnvConfig`` instance.

    Raises:
        RuntimeError: If ``cached()`` is called reentrantly for *cls* from
            within that class's own load path.
    """
    cached = get_cached(cls)
    if cached is not None:
        if env is not None or override is not True or env_dir is not None:
            logger.warning(
                "cached() called on %s with arguments (env=%r, override=%r, "
                "env_dir=%r) but the cache is already populated; "
                "arguments were ignored.",
                cls.__name__,
                env,
                override,
                env_dir,
            )
        return cached

    loading = _get_loading_set()
    if cls in loading:
        raise RuntimeError(
            f"Reentrant cached() call detected for {cls.__name__}: "
            f"cached() was called for this class while its first "
            f"cached() call is still loading (inside load() / "
            f"post_load() / validator). This would deadlock. "
            f"If a hook needs the instance mid-load, call cls.load() "
            f"directly or use 'self' instead."
        )

    loading.add(cls)
    try:
        with _cache_lock:
            cached = get_cached(cls)
            if cached is not None:
                return cached

            instance = cls.load(env=env, override=override, env_dir=env_dir)
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
    """
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
    """
    with _cache_lock:
        if had_cached:
            set_cached(cls, cast("DotEnvConfig", previous))
        elif has_cached(cls):
            delattr(cls, _CACHED_ATTR)
