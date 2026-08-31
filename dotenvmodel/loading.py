"""Environment variable and .env file reading, plus load-parameter resolution."""

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# Module-level logger
logger = logging.getLogger("dotenvmodel")

_TRUTHY = frozenset(("true", "1", "yes", "on"))
_FALSY = frozenset(("false", "0", "no", "off"))


@dataclass(frozen=True, kw_only=True)
class LoadParams:
    """Resolved load settings for one `load()` / `reload()` / `cached()` call.

    Every behavior knob follows the same three-tier model: an explicit
    (non-`None`) argument wins, then the well-known environment variable,
    then the documented default. Instances record the *resolved* values —
    booleans are never `None`, and `env_dir` is the resolved base
    directory (explicit argument > `DOTENV_DIR` > cwd at load time) — so a
    bare `reload()` repeats exactly what the previous load did, even across
    cwd changes.

    Construction is keyword-only: a future knob cannot silently break
    positional constructions, because there are none.

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


@dataclass(frozen=True, repr=False)
class DotenvLayer:
    """The merged `.env` cascade for one load — read, never injected.

    Attributes:
        values: Merged key/value pairs; a later (more specific) file wins,
            and bare keys (`KEY` with no `=`) are left unset — python-dotenv's
            `load_dotenv()` skips them too, so a bare key never satisfies a
            field with `""`.
        base_dir: The directory the cascade was read from.
        files: The files that existed and were read, in cascade order.

    Note:
        `repr()` is masked by design: it shows key names and counts, never
        values — merged values may be secrets, including process-env values
        pulled in via `${VAR}` interpolation. Access `values` directly when
        you need them.
    """

    values: dict[str, str]
    base_dir: Path
    files: tuple[Path, ...]

    def __repr__(self) -> str:
        """Key names and counts only — merged values may be secrets."""
        keys = ", ".join(self.values)
        return (
            f"DotenvLayer(values=<{len(self.values)} keys: {keys}>, "
            f"base_dir={self.base_dir!r}, files={self.files!r})"
        )


def resolve_env_name(env: str | None) -> str:
    """Resolve the environment name: explicit argument > `ENV` env var > "dev".

    When to use:
        - Called by `resolve_load_params()` and `read_env_files()` — call
          directly only if you need the same resolution without loading

    Args:
        env: Environment name, or None to read `ENV` (default "dev"; an
            empty `ENV` value is treated as unset — the same policy
            `DOTENV_DIR` applies to an empty value).

    Returns:
        The resolved environment name.

    Raises:
        ValueError: If the resolved name is empty or contains characters
            other than alphanumerics, hyphens, and underscores — the guard
            that prevents path traversal via `env="../etc"`.
    """
    if env is None:
        env = os.getenv("ENV") or "dev"

    if not env or not all(c.isalnum() or c in ("-", "_") for c in env):
        raise ValueError(
            f"Invalid environment name: {env!r}. "
            "Environment names must only contain alphanumeric characters, hyphens, and underscores."
        )
    return env


def resolve_env_dir(env_dir: Path | str | None) -> Path:
    """Resolve the `.env` base directory: explicit argument > `DOTENV_DIR` > cwd.

    The result is always absolute: a relative argument or `DOTENV_DIR`
    value is joined onto the current working directory. The join is
    lexical — no `resolve()`, no symlink following, no `..` normalization
    — so the recorded directory is exactly the path as spelled from the
    cwd at load time. Recording the absolute path is what keeps a bare
    `reload()` cwd-stable and `cached()`'s warm-path comparison from
    misjudging a relative spelling of the same directory.

    No existence check happens here. `read_env_files()` raises
    `FileNotFoundError` when it is about to read from a missing directory,
    or `NotADirectoryError` when the path exists but is not a directory;
    a `read_dotfiles=False` load must not raise for either.

    Args:
        env_dir: Explicit base directory — a `str` is accepted and converted
            to a `Path` here, the single conversion point for every
            `env_dir` acceptance site — or None to consult `DOTENV_DIR`
            (an empty value is ignored) and then the current working directory.

    Returns:
        The resolved base directory — always absolute.
    """
    if isinstance(env_dir, str):
        env_dir = Path(env_dir)
    if env_dir is not None:
        return env_dir if env_dir.is_absolute() else Path.cwd() / env_dir
    env_dir_str = os.getenv("DOTENV_DIR")
    if env_dir_str:
        from_env_var = Path(env_dir_str)
        return from_env_var if from_env_var.is_absolute() else Path.cwd() / from_env_var
    return Path.cwd()


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
        A stray env var never raises: values are stripped, then parsed
        case-insensitively against `true/1/yes/on` and `false/0/no/off`.
        A whitespace-only value is treated as unset (returning `default`
        silently — the same policy `DOTENV_DIR` applies to an empty value);
        anything else logs a warning naming the variable and value, then
        falls back to `default`.
    """
    if value is not None:
        return value
    raw = os.getenv(env_var)
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if not lowered:
        return default
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
    env_dir: Path | str | None = None,
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
    | Include `.local` files | `load_local` | `DOTENV_LOAD_LOCAL` | `False` iff resolved env is `"test"` (case-insensitive) |

    The `load_local` default skips `.env.local` / `.env.{env}.local` when
    the resolved environment is `"test"` (case-insensitive). This extends
    the Next.js / dotenv-flow rule — which skips only `.env.local` in test
    and still loads `.env.{env}.local` — to all `.local` files, because a
    gitignored `.env.test.local` must not decide test outcomes either;
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
        load_local=resolve_bool(
            load_local, "DOTENV_LOAD_LOCAL", default=resolved_env.lower() != "test"
        ),
    )


# python-dotenv's ${VAR} resolver (dotenv.main.resolve_variables) is internal
# API — not in dotenv.__all__ — and pyproject.toml pins python-dotenv>=1.2.3
# with no upper bound, so importing it can break at module load time on a
# future release. The helpers below replicate the 1.2.3 resolver's surface
# locally: ${VAR} and ${VAR:-default} only (no $VAR shorthand; unclosed ${ and
# a bare $ stay literal), with the default applying only when the name is
# absent from the base — a present-but-empty value wins, matching 1.2.3's
# dict.get lookup.
_POSIX_VARIABLE = re.compile(
    r"""
    \$\{
        (?P<name>[^\}:]*)
        (?::-
            (?P<default>[^\}]*)
        )?
    \}
    """,
    re.VERBOSE,
)


def _resolve_reference(match: re.Match[str], base: Mapping[str, str]) -> str:
    """Resolve one ${VAR} / ${VAR:-default} match with python-dotenv 1.2.3 semantics."""
    default = match["default"]
    return base.get(match["name"], default if default is not None else "")


def interpolate_value(text: str, base: Mapping[str, str]) -> str:
    """Resolve the ``${VAR}`` / ``${VAR:-default}`` references in one string.

    The single interpolation entry point: ``.env`` file values (via
    `read_env_files`) and literal string field defaults (via
    `DotEnvConfig.load`) both resolve through this function, so every
    template-bearing value shares one reference syntax and one semantics
    table. ``base`` supplies the names in lookup order (e.g. merged dotfile
    values over ``os.environ``); a name absent from it resolves to the
    ``:-`` default when one is given, else ``""`` — a present-but-empty
    value beats the ``:-`` default, plain ``dict.get`` semantics. Nothing
    else is a reference: a bare ``$``, ``$VAR`` shorthand, and an unclosed
    ``${`` stay literal.

    When to use:
        - Resolving a template-bearing string against the same base a load
          already interpolates against (``os.environ`` overlaid with the
          merged dotfile values)

    Args:
        text: The string to resolve.
        base: Names to resolve references against, in lookup order.

    Returns:
        The resolved string — *text* itself, the same object, when it
        contains no ``${``, so template-free values never enter the regex
        path.

    Example:
        ```python
        interpolate_value("postgres://${HOST}/app", {"HOST": "db.internal"})
        # 'postgres://db.internal/app'
        ```
    """
    # The membership guard keeps ordinary values off the regex path: most
    # strings — and nearly every field default — contain no "${" at all.
    if "${" not in text:
        return text
    parts: list[str] = []
    cursor = 0
    for match in _POSIX_VARIABLE.finditer(text):
        start, end = match.span()
        if start > cursor:
            parts.append(text[cursor:start])
        parts.append(_resolve_reference(match, base))
        cursor = end
    if cursor < len(text):
        parts.append(text[cursor:])
    return "".join(parts)


def _interpolate(values: dict[str, str]) -> dict[str, str]:
    """Resolve ${VAR} / ${VAR:-default} references, python-dotenv 1.2.3 semantics.

    The base is built exactly like 1.2.3's resolve_variables(override=True):
    the process environment overlaid, in key order, with each key's
    already-resolved value — so an earlier key's value wins over os.environ
    for later references, while a later or self reference sees only
    os.environ. Unresolved references become "". Nothing between ${ and its
    closing } other than the two supported forms is a reference at all, so
    it stays literal. Each value resolves through `interpolate_value`, the
    same single-string entry point the field-default path uses.
    """
    resolved: dict[str, str] = {}
    base: dict[str, str] = dict(os.environ)
    for name, value in values.items():
        resolved[name] = interpolate_value(value, base)
        base[name] = resolved[name]
    return resolved


def read_env_files(
    env: str | None = None,
    *,
    env_dir: Path | str | None = None,
    load_local: bool | None = None,
) -> DotenvLayer:
    """Read the cascading .env files and merge them — purely, without touching os.environ.

    The process environment is never written; the merged values are
    returned instead. Files are probed in Node.js-style cascade order and merged
    with later (more specific) files winning, regardless of any override
    policy — the override policy is applied later, once, against the whole
    merged layer (see `DotEnvConfig.load()`).

    Interpolation happens once, after the merge, and progressively in
    merged-key order: a `${VAR}` reference in a file value sees the keys
    defined earlier in the merged cascade — with their already-resolved
    values — over `os.environ`, so a later file can build on an earlier
    file's value, while a forward or self reference (to a key defined
    later in the merged order, or after it in the same file) sees only
    `os.environ`. A reference to a variable defined only in the process
    environment still resolves, and interpolation is independent of the
    `override` knob, which only governs per-field precedence afterwards.
    python-dotenv 1.2.3's semantics apply, replicated locally (`${VAR}`
    / `${VAR:-default}`; no `$VAR` shorthand; an unresolved reference
    becomes `""`; the `:-` default applies only when the name is absent
    from the base — a present-but-empty value wins over it). Bare keys
    (`KEY` with no `=`) are left unset, matching `load_dotenv()`, which
    skips them.

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
        env_dir: Custom base directory for .env files — a `str` is accepted
            and converted to a `Path`. If None, uses the `DOTENV_DIR`
            environment variable or current working directory
        load_local: Whether to include `.local` files. If None (the
            default), resolves through `DOTENV_LOAD_LOCAL` with the same
            auto rule as `load()`: skip `.local` files when the resolved
            environment is `"test"` (case-insensitive), else include them.
            When False, a present-but-skipped `.local` file is logged at
            INFO with the two restore knobs (`load_local=True` /
            `DOTENV_LOAD_LOCAL=true`)

    Returns:
        A `DotenvLayer` with the merged values, the base directory, and
        the files that were read

    Raises:
        ValueError: If `env` contains invalid characters (only alphanumeric,
            hyphens, and underscores allowed — prevents path traversal)
        FileNotFoundError: If the resolved base directory doesn't exist
        NotADirectoryError: If the resolved base directory exists but is not
            a directory — typically `DOTENV_DIR` or `env_dir` pointed at a
            `.env` file itself rather than the directory containing it

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

    # is_dir(), not exists(): a regular file passes an existence check but
    # yields an empty cascade and a "No .env files found" warning that names
    # the file itself — a misconfigured env_dir indistinguishable from a
    # correctly-configured empty one. Pointing DOTENV_DIR at .env rather than
    # its parent is the common spelling of that mistake.
    if not base_dir.is_dir():
        if base_dir.exists():
            logger.error(f"Environment file directory is not a directory: {base_dir}")
            raise NotADirectoryError(f"Environment file directory is not a directory: {base_dir}")
        logger.error(f"Environment file directory does not exist: {base_dir}")
        raise FileNotFoundError(f"Environment file directory does not exist: {base_dir}")

    # Same tier resolution as load(): explicit argument > DOTENV_LOAD_LOCAL
    # > the auto rule (skip .local files when the resolved env is "test",
    # matched case-insensitively).
    resolved_load_local = resolve_bool(
        load_local, "DOTENV_LOAD_LOCAL", default=resolved_env.lower() != "test"
    )

    env_files = [base_dir / ".env"]  # Base shared configuration
    if resolved_load_local:
        env_files.append(base_dir / ".env.local")  # Local base overrides
    env_files.append(base_dir / f".env.{resolved_env}")  # Environment-specific config
    if resolved_load_local:
        env_files.append(base_dir / f".env.{resolved_env}.local")  # Local environment overrides
    else:
        # Make the skip observable: a present-but-skipped .local file is
        # exactly what a developer debugging "why isn't my local override
        # picked up in test?" needs to see, with both ways to restore it.
        for local_file in (base_dir / ".env.local", base_dir / f".env.{resolved_env}.local"):
            if local_file.exists():
                logger.info(
                    f"Skipping {local_file}: local files are excluded for this load. "
                    "Pass load_local=True or set DOTENV_LOAD_LOCAL=true to include them."
                )

    logger.debug(f"Searching for .env files in order: {[str(f) for f in env_files]}")

    values: dict[str, str] = {}
    loaded_files: list[Path] = []
    for file_path in env_files:
        if file_path.exists():
            logger.info(f"Reading .env file: {file_path}")
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

    # Interpolate in one pass over the merged layer, progressively in
    # merged-key order: a ${VAR} reference sees the keys defined earlier
    # in the merge (with their already-resolved values) over os.environ,
    # so a later file can build on an earlier file's value, while a
    # forward or self reference sees only os.environ. That base is
    # deliberately independent of load()'s override knob, which only
    # governs per-field precedence afterwards.
    # Unresolved references become "" (python-dotenv 1.2.3 semantics: ${VAR}
    # / ${VAR:-default} only; $VAR shorthand is not interpolated), and no
    # None values entered the merge, so none leave — every output is a str.
    values = _interpolate(values)

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
