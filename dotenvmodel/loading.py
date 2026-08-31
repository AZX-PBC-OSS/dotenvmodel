"""Environment variable and .env file reading, plus load-parameter resolution."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from dotenv import dotenv_values
from dotenv.main import resolve_variables

# Module-level logger
logger = logging.getLogger("dotenvmodel")

_TRUTHY = frozenset(("true", "1", "yes", "on"))
_FALSY = frozenset(("false", "0", "no", "off"))


@dataclass(frozen=True)
class LoadParams:
    """Resolved load settings for one `load()` / `reload()` / `cached()` call.

    Every behavior knob follows the same three-tier model: an explicit
    (non-`None`) argument wins, then the well-known environment variable,
    then the documented default. Instances record the *resolved* values —
    booleans are never `None`, and `env_dir` is the resolved base
    directory (explicit argument > `DOTENV_DIR` > cwd at load time) — so a
    bare `reload()` repeats exactly what the previous load did, even across
    cwd changes.

    Attributes:
        env: Environment name selecting the `.env.{env}` files.
        override: Whether the merged dotfile layer beats the process
            environment (default `False` — the process environment wins).
        env_dir: Resolved base directory for `.env` files.
        read_dotfiles: Whether `.env` files are read at all.
        load_local: Whether `.local` files are included (default skips
            them when `env` is `"test"`).
    """

    env: str
    override: bool
    env_dir: Path
    read_dotfiles: bool
    load_local: bool


@dataclass(frozen=True)
class DotenvLayer:
    """The merged `.env` cascade for one load — read, never injected.

    Attributes:
        values: Merged key/value pairs; a later (more specific) file wins,
            and bare keys (`KEY` with no `=`) are left unset — python-dotenv's
            `load_dotenv()` skips them too, so a bare key never satisfies a
            field with `""`.
        base_dir: The directory the cascade was read from.
        files: The files that existed and were read, in cascade order.
    """

    values: dict[str, str]
    base_dir: Path
    files: tuple[Path, ...]


def resolve_env_name(env: str | None) -> str:
    """Resolve the environment name: explicit argument > `ENV` env var > "dev".

    When to use:
        - Called by `resolve_load_params()` and `read_env_files()` — call
          directly only if you need the same resolution without loading

    Args:
        env: Environment name, or None to read `ENV` (default "dev").

    Returns:
        The resolved environment name.

    Raises:
        ValueError: If the resolved name is empty or contains characters
            other than alphanumerics, hyphens, and underscores — the guard
            that prevents path traversal via `env="../etc"`.
    """
    if env is None:
        env = os.getenv("ENV", "dev")

    if not env or not all(c.isalnum() or c in ("-", "_") for c in env):
        raise ValueError(
            f"Invalid environment name: {env!r}. "
            "Environment names must only contain alphanumeric characters, hyphens, and underscores."
        )
    return env


def resolve_env_dir(env_dir: Path | None) -> Path:
    """Resolve the `.env` base directory: explicit argument > `DOTENV_DIR` > cwd.

    No existence check happens here. `read_env_files()` raises
    `FileNotFoundError` when it is about to read from a missing directory;
    a `read_dotfiles=False` load must not raise for one.

    Args:
        env_dir: Explicit base directory, or None to consult `DOTENV_DIR`
            (an empty value is ignored) and then the current working directory.

    Returns:
        The resolved base directory.
    """
    if env_dir is not None:
        return env_dir
    env_dir_str = os.getenv("DOTENV_DIR")
    return Path(env_dir_str) if env_dir_str else Path.cwd()


def resolve_bool(value: bool | None, env_var: str, default: bool) -> bool:
    """Resolve a boolean knob: explicit argument > env var > default.

    When to use:
        - Called by `resolve_load_params()` for every boolean parameter

    Args:
        value: Explicit argument; anything but None wins immediately.
        env_var: Environment variable consulted when `value` is None.
        default: Value used when the env var is unset — or unparseable.

    Returns:
        The resolved boolean.

    Note:
        A stray env var never raises: unrecognized values are parsed
        case-insensitively against `true/1/yes/on` and `false/0/no/off`,
        and anything else logs a warning naming the variable and value,
        then falls back to `default`.
    """
    if value is not None:
        return value
    raw = os.getenv(env_var)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSY:
        return False
    logger.warning(
        f"Invalid boolean value {raw!r} for {env_var}; expected one of "
        f"true/1/yes/on or false/0/no/off (case-insensitive). Using default {default!r}."
    )
    return default


def resolve_load_params(
    env: str | None = None,
    *,
    override: bool | None = None,
    env_dir: Path | None = None,
    read_dotfiles: bool | None = None,
    load_local: bool | None = None,
) -> LoadParams:
    """Resolve every `load()` behavior knob into a `LoadParams` record.

    Each knob follows the tier model documented on `LoadParams` — explicit
    argument > environment variable > default:

    | Knob | Argument | Env var | Default |
    |---|---|---|---|
    | Environment name | `env` | `ENV` | `"dev"` |
    | Base directory | `env_dir` | `DOTENV_DIR` | cwd |
    | Dotfiles beat process env | `override` | `DOTENV_OVERRIDE` | `False` |
    | Read dotfiles at all | `read_dotfiles` | `DOTENV_READ_DOTFILES` | `True` |
    | Include `.local` files | `load_local` | `DOTENV_LOAD_LOCAL` | `False` iff resolved env is `"test"` |

    The `load_local` default skips `.env.local` / `.env.{env}.local` when
    the resolved environment is `"test"` (the Next.js / dotenv-flow
    convention: tests should produce the same results for everyone);
    `.env.{env}` itself is still read in every environment.

    Args:
        env: Environment name, or None for the `ENV` tier.
        override: Whether dotfiles beat the process env, or None for the tier.
        env_dir: Base directory, or None for the tier.
        read_dotfiles: Whether to read dotfiles at all, or None for the tier.
        load_local: Whether to include `.local` files, or None for the tier.

    Returns:
        The fully resolved `LoadParams`.

    Raises:
        ValueError: If the resolved environment name is invalid (see
            `resolve_env_name`).

    See Also:
        - [`DotEnvConfig.load`][dotenvmodel.config.DotEnvConfig.load]: Consumes these params.
        - [`LoadParams`][dotenvmodel.loading.LoadParams]: The record type.
    """
    resolved_env = resolve_env_name(env)
    return LoadParams(
        env=resolved_env,
        override=resolve_bool(override, "DOTENV_OVERRIDE", default=False),
        env_dir=resolve_env_dir(env_dir),
        read_dotfiles=resolve_bool(read_dotfiles, "DOTENV_READ_DOTFILES", default=True),
        load_local=resolve_bool(load_local, "DOTENV_LOAD_LOCAL", default=resolved_env != "test"),
    )


def read_env_files(
    env: str | None = None,
    *,
    env_dir: Path | None = None,
    load_local: bool = True,
) -> DotenvLayer:
    """Read the cascading .env files and merge them — purely, without touching os.environ.

    This is the pure replacement for the removed `load_env_files()`: it
    never writes to the process environment, returning the merged values
    instead. Files are probed in Node.js-style cascade order and merged
    with later (more specific) files winning, regardless of any override
    policy — the override policy is applied later, once, against the whole
    merged layer (see `DotEnvConfig.load()`).

    Interpolation happens once, after the merge: a `${VAR}` reference in
    any file resolves against the merged cascade first, then `os.environ`
    — the base the old sequential `load_dotenv(override=True)` cascade
    effectively used — and is independent of the `override` knob, which
    only governs per-field precedence afterwards. python-dotenv's own
    semantics apply (`${VAR}` / `${VAR:-default}`; no `$VAR` shorthand;
    an unresolved reference becomes `""`). Bare keys (`KEY` with no `=`)
    are left unset, matching `load_dotenv()`, which skips them.

    Probing order:
        1. `.env` (base configuration)
        2. `.env.local` (local base overrides — only when `load_local`)
        3. `.env.{env}` (environment-specific)
        4. `.env.{env}.local` (local environment overrides — only when `load_local`)

    When to use:
        - Called automatically by `DotEnvConfig.load()` — you rarely call this directly
        - Call directly if you need the merged dotfile layer without creating a config

    Args:
        env: Environment name (e.g., "dev", "prod", "test"). If None, reads from
            the `ENV` environment variable, defaults to "dev"
        env_dir: Custom base directory for .env files. If None, uses
            the `DOTENV_DIR` environment variable or current working directory
        load_local: If False, `.env.local` and `.env.{env}.local` are not
            probed at all (default True — `DotEnvConfig.load()` passes the
            resolved auto rule, which skips them in the "test" environment)

    Returns:
        A `DotenvLayer` with the merged values, the base directory, and
        the files that were read

    Raises:
        ValueError: If `env` contains invalid characters (only alphanumeric,
            hyphens, and underscores allowed — prevents path traversal)
        FileNotFoundError: If the resolved base directory doesn't exist

    Example:
        ```python
        # Merge the .env cascade for the dev environment
        layer = read_env_files(env="dev")

        # Custom directory, skipping .local files
        from pathlib import Path
        layer = read_env_files(env="prod", env_dir=Path("/app/config"), load_local=False)
        ```

    See Also:
        - [`DotEnvConfig.load`][dotenvmodel.config.DotEnvConfig.load]: Loads config, applying its override policy against this layer.
        - [`get_env_var`][dotenvmodel.loading.get_env_var]: Get a single env var by field name.
    """
    resolved_env = resolve_env_name(env)
    logger.info(f"Loading configuration for environment: {resolved_env}")

    base_dir = resolve_env_dir(env_dir)
    logger.debug(f"Base directory for .env files: {base_dir}")

    if not base_dir.exists():
        logger.error(f"Environment file directory does not exist: {base_dir}")
        raise FileNotFoundError(f"Environment file directory does not exist: {base_dir}")

    env_files = [base_dir / ".env"]  # Base shared configuration
    if load_local:
        env_files.append(base_dir / ".env.local")  # Local base overrides
    env_files.append(base_dir / f".env.{resolved_env}")  # Environment-specific config
    if load_local:
        env_files.append(base_dir / f".env.{resolved_env}.local")  # Local environment overrides

    logger.debug(f"Searching for .env files in order: {[str(f) for f in env_files]}")

    values: dict[str, str] = {}
    loaded_files: list[Path] = []
    for file_path in env_files:
        if file_path.exists():
            logger.info(f"Loading environment variables from {file_path}")
            # dotenv_values() is pure (no os.environ writes). Reading with
            # interpolate=False defers ${VAR} resolution to one pass over
            # the whole merged layer below, so a later file's references
            # can see an earlier file's values without any injection.
            file_values = dotenv_values(file_path, interpolate=False)
            # A bare key (`KEY` with no `=`) comes back as None and is
            # dropped, matching load_dotenv(), which never sets such keys.
            values.update({k: v for k, v in file_values.items() if v is not None})
            loaded_files.append(file_path)
        else:
            logger.debug(f"{file_path} not found (skipping)")

    # Interpolate once, against the whole merged layer: a ${VAR} reference
    # resolves against the merged cascade first, then os.environ — the base
    # the old sequential load_dotenv(override=True) cascade effectively used
    # (earlier files' values were already in os.environ when later files were
    # interpolated). That base is deliberately independent of load()'s
    # override knob, which only governs per-field precedence afterwards.
    # resolve_variables' own override=True selects exactly that base order,
    # and unresolved references become "" (python-dotenv semantics: ${VAR} /
    # ${VAR:-default} only; $VAR shorthand is not interpolated). No None
    # values entered, so none leave — every output is a str.
    values = cast("dict[str, str]", dict(resolve_variables(values.items(), override=True)))

    if loaded_files:
        logger.info(
            f"Successfully loaded {len(loaded_files)} file(s): "
            f"{', '.join(str(f) for f in loaded_files)}"
        )
    else:
        logger.warning(f"No .env files found in {base_dir}")

    return DotenvLayer(values=values, base_dir=base_dir, files=tuple(loaded_files))


def get_env_var(field_name: str, alias: str | None = None, prefix: str | None = None) -> str | None:
    """Get environment variable value by field name or alias.

    Reads `os.environ` only — dotfile values are not consulted; use
    `read_env_files()` for the file layer.

    When to use:
        - Use directly if you need to check a config env var without loading the full config

    Args:
        field_name: Name of the field (converted to UPPER_CASE for env var lookup)
        alias: Optional alias that overrides the field name for env var lookup.
            When provided, `prefix` is NOT applied.
        prefix: Optional class-level prefix to prepend to the env var name.
            Not applied when `alias` is provided.

    Returns:
        Environment variable value as string, or None if not set

    See Also:
        - [`get_env_var_name`][dotenvmodel.loading.get_env_var_name]: Get just the name, not the value.
    """
    # Use alias if provided, otherwise convert field_name to UPPER_CASE
    env_var_name = alias if alias else field_name.upper()

    # Prepend prefix if provided (and alias is not used, since alias is absolute)
    if prefix and not alias:
        env_var_name = f"{prefix}{env_var_name}"

    return os.getenv(env_var_name)


def get_env_var_name(field_name: str, alias: str | None = None, prefix: str | None = None) -> str:
    """Get the environment variable name for a field.

    When to use:
        - For generating documentation or .env.example files
        - For error messages that reference the env var name
        - Called internally during config loading

    Args:
        field_name: Name of the field (converted to UPPER_CASE for env var lookup)
        alias: Optional alias that overrides the field name. When provided,
            `prefix` is NOT applied.
        prefix: Optional class-level prefix to prepend. Not applied when
            `alias` is provided.

    Returns:
        The environment variable name string

    Example:
        ```python
        get_env_var_name("database_url")           # "DATABASE_URL"
        get_env_var_name("host", prefix="DB_")     # "DB_HOST"
        get_env_var_name("dsn", alias="DATABASE")  # "DATABASE" (no prefix)
        ```

    See Also:
        - [`get_env_var`][dotenvmodel.loading.get_env_var]: Get the value, not just the name.
    """
    # Use alias if provided, otherwise convert field_name to UPPER_CASE
    env_var_name = alias if alias else field_name.upper()

    # Prepend prefix if provided (and alias is not used, since alias is absolute)
    if prefix and not alias:
        env_var_name = f"{prefix}{env_var_name}"

    return env_var_name
