"""Credential-redaction helpers shared across display paths.

Kept dependency-free (stdlib only) so both ``exceptions`` and ``types`` can
import it without creating an import cycle.
"""

import re
from urllib.parse import unquote_plus, urlparse

__all__ = ["redact_url_password"]

_MASK = "***"

# Secret words: a key is sensitive when one of these is the WHOLE key or its
# LAST token. Keying on the last token means ``access_token``/``client_secret``
# match while ``token_endpoint``/``signature_method``/``auth_type`` (benign
# ``*_endpoint``/``*_method``/``*_type`` suffixes) do not.
_SECRET_WORDS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "passphrase",
        "passcode",
        "secret",
        "credential",
        "credentials",
        "apikey",
        "signature",
        "sig",
        "hmac",
        "jwt",
        "bearer",
        "sessionid",
        "otp",
        "totp",
        "sas",
        "assertion",
        "authorization",
        "token",
        "key",
    }
)

# Short/common words that are a credential only as the ENTIRE key, so
# ``pass``/``auth`` mask but ``pass_through``/``auth_type``/``auth_url`` do not.
_SECRET_WHOLE_ONLY = frozenset({"pass", "auth"})

# Glued (separator-less) suffixes, e.g. ``sslpassword`` / ``xapikey``.
_SECRET_SUFFIXES = ("password", "passphrase", "passcode", "signature", "apikey")

# Qualifiers that make a trailing ``key`` benign (``sort_key``), i.e. NOT a
# credential — everything else with a trailing ``key`` is masked.
_BENIGN_KEY_QUALIFIERS = frozenset(
    {
        "sort",
        "public",
        "partition",
        "cache",
        "routing",
        "foreign",
        "primary",
        "order",
        "group",
        "grouping",
        "unique",
        "composite",
        "natural",
        "shard",
        "sharding",
        "hash",
        "cluster",
        "dedup",
        "dedupe",
        "idempotency",
        # storage / DB object identifiers (the value is a name/path, not a secret)
        "object",
        "index",
        "row",
        "blob",
        "map",
        "bucket",
        "range",
        "lookup",
        "search",
        "query",
        "filter",
    }
)

# Qualifiers that make a trailing ``token`` benign (a pagination cursor).
_BENIGN_TOKEN_QUALIFIERS = frozenset(
    {
        "page",
        "next",
        "prev",
        "previous",
        "continuation",
        "continue",
        "cursor",
        "sync",
        "resume",
        "skip",
        "offset",
        "start",
        "before",
        "after",
        "pagination",
    }
)

# Prefixes that make a glued (separator-less) ``*key``/``*token``/``*secret``
# compound a credential: ``secretkey``, ``accesstoken``, ``clientsecret``.
_CREDENTIAL_PREFIXES = frozenset(
    {
        "secret",
        "access",
        "private",
        "api",
        "client",
        "signing",
        "encryption",
        "refresh",
        "session",
        "shared",
        "master",
        "auth",
        "bearer",
        "consumer",
        "sas",
    }
)
# The ambiguous words whose carve-outs must run even if the glued key is a
# whole secret word — so a bare ``key``/``token`` is not masked by the whole-word check.
_AMBIGUOUS = frozenset({"key", "token"})

# Split camelCase and ACRONYMBoundaries (HMACKey -> HMAC, Key).
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SEPARATORS = re.compile(r"[-_.]+")
# Fallback for unparseable URLs: mask the userinfo password (scheme://user:PW@).
_USERINFO_PW = re.compile(r"(://[^:/?#@\s]*:)[^@/?#\s]+(@)")


def _is_sensitive_key(key: str) -> bool:
    """True if a query/fragment key names a credential.

    Matches a secret word as the whole key or its last token (so
    ``access_token`` masks but ``token_endpoint`` does not), with benign-qualifier
    carve-outs for ``key``/``token`` and a suffix check for glued forms like
    ``sslpassword``.
    """
    raw = unquote_plus(key).strip()
    if not raw:
        return False

    k = _CAMEL.sub("_", raw).lower()
    tokens = [t for t in _SEPARATORS.split(k) if t]
    if not tokens:
        return False
    stripped = "".join(tokens)
    last = tokens[-1]
    prev = tokens[-2] if len(tokens) > 1 else None

    if stripped in _SECRET_WHOLE_ONLY:
        return True
    # A secret word spanning separators (session_id -> sessionid), but not the
    # ambiguous key/token, which still need their carve-outs below.
    if stripped in _SECRET_WORDS and stripped not in _AMBIGUOUS:
        return True
    if last in _SECRET_WORDS:
        # A secret-word last token is a credential unless it's a benign carve-out:
        # a bare/sort/public `key`, or a pagination-cursor `token`.
        benign = (last == "key" and (prev is None or prev in _BENIGN_KEY_QUALIFIERS)) or (
            last == "token" and prev in _BENIGN_TOKEN_QUALIFIERS
        )
        return not benign
    if _is_glued_credential(stripped):
        return True
    return any(stripped.endswith(sfx) for sfx in _SECRET_SUFFIXES)


def _is_glued_credential(stripped: str) -> bool:
    """True for separator-less compounds like ``secretkey`` / ``accesstoken``."""
    for suffix in ("key", "token", "secret", "password"):
        if (
            stripped.endswith(suffix)
            and len(stripped) > len(suffix)
            and stripped[: -len(suffix)] in _CREDENTIAL_PREFIXES
        ):
            return True
    return False


def _redact_pairs(component: str) -> tuple[str, bool]:
    """Mask sensitive values in an ``&``-separated key=value string.

    Per the WHATWG URL standard, ``&`` is the only separator; a ``;`` is data
    and stays inside its value. Non-sensitive pairs are preserved byte-for-byte.
    Returns the (possibly rewritten) component and whether anything changed.
    """
    changed = False
    parts = component.split("&")
    for i, part in enumerate(parts):
        key, sep, value = part.partition("=")
        if sep and value and _is_sensitive_key(key):
            parts[i] = f"{key}={_MASK}"
            changed = True
    return ("&".join(parts), changed) if changed else (component, False)


def redact_url_password(value: str) -> str:
    """Return ``value`` with any URL password replaced by ``***``.

    Masks the userinfo password (``user:pass@host`` -> ``user:***@host``) and
    the value of any sensitive key in the query string or fragment (e.g.
    ``?password=`` / ``?sslpassword=`` / ``#access_token=``). Host, port, and
    non-sensitive parameters are preserved verbatim. A string without a
    parseable ``scheme://...`` structure is returned unchanged, so this is safe
    to call on arbitrary values.
    """
    try:
        parsed = urlparse(value)
    except (ValueError, TypeError):
        # Malformed URL (e.g. bad IPv6). urlparse can't help, but neither the
        # userinfo password nor a query/fragment secret may leak, so mask the
        # userinfo by regex and redact the (splittable) query and fragment.
        masked = _USERINFO_PW.sub(rf"\1{_MASK}\2", value)
        head, hsep, frag = masked.partition("#")
        head, qsep, query = head.partition("?")
        if qsep:
            query = _redact_pairs(query)[0]
        if hsep:
            frag = _redact_pairs(frag)[0]
        return head + qsep + query + hsep + frag

    netloc = parsed.netloc
    changed = False

    if parsed.password:
        userinfo, _, hostpart = netloc.rpartition("@")
        username = userinfo.partition(":")[0]
        netloc = f"{username}:{_MASK}@{hostpart}"
        changed = True

    query, query_changed = _redact_pairs(parsed.query) if parsed.query else (parsed.query, False)
    fragment, frag_changed = (
        _redact_pairs(parsed.fragment) if parsed.fragment else (parsed.fragment, False)
    )
    changed = changed or query_changed or frag_changed

    if not changed:
        return value

    return parsed._replace(netloc=netloc, query=query, fragment=fragment).geturl()
