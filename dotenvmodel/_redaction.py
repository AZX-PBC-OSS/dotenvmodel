"""Credential-redaction helpers shared across display paths.

Kept dependency-free (stdlib only) so both ``exceptions`` and ``types`` can
import it without creating an import cycle.
"""

from urllib.parse import urlparse

__all__ = ["redact_url_password"]

_MASK = "***"


def redact_url_password(value: str) -> str:
    """Return ``value`` with any URL userinfo password replaced by ``***``.

    A string without a parseable ``scheme://user:password@host`` structure is
    returned unchanged, so this is safe to call on arbitrary values.
    """
    try:
        parsed = urlparse(value)
    except (ValueError, TypeError):
        return value

    if not parsed.password:
        return value

    userinfo, _, hostpart = parsed.netloc.rpartition("@")
    username = userinfo.partition(":")[0]
    new_netloc = f"{username}:{_MASK}@{hostpart}"
    return parsed._replace(netloc=new_netloc).geturl()
