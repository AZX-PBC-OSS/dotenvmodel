"""Credential-redaction helpers shared across display paths.

Kept dependency-free (stdlib only) so both ``exceptions`` and ``types`` can
import it without creating an import cycle.
"""

from urllib.parse import parse_qsl, urlencode, urlparse

__all__ = ["redact_url_password"]

_MASK = "***"

# Query-string keys whose values are treated as secrets (case-insensitive).
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "token",
        "access_token",
        "secret",
        "api_key",
        "apikey",
        "auth",
        "authorization",
    }
)


def redact_url_password(value: str) -> str:
    """Return ``value`` with any URL password replaced by ``***``.

    Masks both the userinfo password (``user:pass@host`` → ``user:***@host``)
    and the value of any sensitive query-string key (e.g. ``?password=`` /
    ``?token=``). The original host, port, and other components are preserved
    verbatim. A string without a parseable ``scheme://...`` structure is
    returned unchanged, so this is safe to call on arbitrary values.
    """
    try:
        parsed = urlparse(value)
    except (ValueError, TypeError):
        return value

    netloc = parsed.netloc
    query = parsed.query
    changed = False

    if parsed.password:
        userinfo, _, hostpart = netloc.rpartition("@")
        username = userinfo.partition(":")[0]
        netloc = f"{username}:{_MASK}@{hostpart}"
        changed = True

    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        masked = [
            (key, _MASK if (key.lower() in _SENSITIVE_QUERY_KEYS and val) else val)
            for key, val in pairs
        ]
        if masked != pairs:
            query = urlencode(masked, safe="*")
            changed = True

    if not changed:
        return value

    return parsed._replace(netloc=netloc, query=query).geturl()
