"""Credential-redaction helpers shared across display paths.

Kept dependency-free (stdlib only) so both ``exceptions`` and ``types`` can
import it without creating an import cycle.
"""

import re
from urllib.parse import unquote, urlparse

__all__ = ["redact_url_password"]

_MASK = "***"

# Distinctive substrings: masking any key containing one of these avoids
# false positives like ``author`` (which merely contains ``auth``).
_SENSITIVE_SUBSTRINGS = ("password", "passwd", "secret", "token", "apikey")

# Short/ambiguous keys matched exactly or as a separator-delimited token,
# so ``x-api-key`` masks but ``author`` / ``keyboard`` do not.
_SENSITIVE_TOKENS = frozenset(
    {
        "pwd",
        "auth",
        "authorization",
        "api_key",
        "api-key",
        "apikey",
        "key",
        "credential",
        "credentials",
    }
)


def _is_sensitive_key(key: str) -> bool:
    """True if a query/fragment key names a credential."""
    k = unquote(key).lower()
    if k in _SENSITIVE_TOKENS:
        return True
    if any(sub in k for sub in _SENSITIVE_SUBSTRINGS):
        return True
    return any(part in _SENSITIVE_TOKENS for part in re.split(r"[-_]", k))


def _redact_pairs(component: str) -> tuple[str, bool]:
    """Mask sensitive values in an ``&``-separated key=value string.

    Non-sensitive pairs are preserved byte-for-byte (no re-encoding), so a
    benign ``note=a%20b`` is not normalised to ``note=a+b``. Returns the
    (possibly rewritten) component and whether anything changed.
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
        return value

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
