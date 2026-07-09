"""Credential-redaction helpers shared across display paths.

Kept dependency-free (stdlib only) so both ``exceptions`` and ``types`` can
import it without creating an import cycle.
"""

import re
from urllib.parse import unquote_plus, urlparse

__all__ = ["redact_url_password"]

_MASK = "***"

# Unambiguous secret words. Matched as the whole (separator-stripped) key or as
# any separator-delimited token, so ``client_secret`` and ``X-Amz-Signature``
# match while ``secretary`` / ``author`` / ``oauth`` do not.
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
        "auth",
        "authorization",
        "signature",
        "sig",
        "hmac",
        "jwt",
        "bearer",
        "sessionid",
        "otp",
        "sas",
    }
)

# Long words distinctive enough to match as a substring of the stripped key
# (catches ``sslpassword`` / ``x-api-key`` without hitting benign lookalikes).
_SECRET_SUBSTRINGS = ("password", "passphrase", "passcode", "signature", "apikey")

# Qualifiers that make a trailing ``key`` token a secret (``api_key`` yes,
# ``sort_key`` / ``public_key`` no).
_KEY_QUALIFIERS = frozenset(
    {"api", "access", "secret", "private", "client", "encryption", "signing", "master", "session"}
)

_SEPARATORS = re.compile(r"[-_.]+")


def _is_sensitive_key(key: str) -> bool:
    """True if a query/fragment key names a credential.

    Uses token-boundary matching (not naive substring) so it catches
    ``passphrase``/``signature``/``X-Amz-Signature`` while leaving benign
    lookalikes like ``tokenizer``/``sort_key``/``secretary`` untouched.
    """
    raw = unquote_plus(key).strip()
    if not raw:
        return False

    # Split camelCase (clientSecret -> client, secret) then separators.
    k = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw).lower()
    tokens = _SEPARATORS.split(k)
    stripped = "".join(tokens)

    if stripped in _SECRET_WORDS or any(t in _SECRET_WORDS for t in tokens):
        return True
    if any(sub in stripped for sub in _SECRET_SUBSTRINGS):
        return True
    # ``token`` only as the whole key or a trailing token (access_token), never a
    # prefix (token_endpoint) or part of a word (tokenizer).
    if tokens[-1] == "token" and (len(tokens) > 1 or k == "token"):
        return True
    # ``key`` only when qualified as a credential (api_key), not sort_key.
    if len(tokens) > 1 and tokens[-1] == "key" and tokens[-2] in _KEY_QUALIFIERS:
        return True
    return False


def _redact_pairs(component: str) -> tuple[str, bool]:
    """Mask sensitive values in a ``&``/``;``-separated key=value string.

    Non-sensitive pairs are preserved byte-for-byte (no re-encoding) when
    nothing changes. If a secret is masked the component is re-joined with
    ``&`` (normalising any legacy ``;`` separator), which is display-only.
    Returns the (possibly rewritten) component and whether anything changed.
    """
    changed = False
    parts = re.split(r"[&;]", component)
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
