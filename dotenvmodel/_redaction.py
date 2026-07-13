"""Credential-redaction helpers shared across display paths.

Kept dependency-free (stdlib only) so both ``exceptions`` and ``types`` can
import it without creating an import cycle.

Masking philosophy — deliberately asymmetric. These helpers run only on
error/describe/``repr`` display paths, where over-masking a benign value
(``sort_key=name`` shown as ``sort_key=***``) costs a little debug context,
while under-masking leaks a credential. So the classifier keeps NO benign
carve-out lists: any key with a secret-word token is masked, and the word
list is the single place to maintain.

Known, documented non-goals (use ``SecretStr`` for these):
- secrets embedded in a URL *path* segment (Slack webhooks, ``/bot<token>/``);
- plain non-URL secret values and secrets inside containers/JSON bodies;
- ``user:pw@host`` shapes buried mid-string (only a leading one is masked).
"""

import re
from urllib.parse import unquote_plus, urlparse

__all__ = ["redact_url_password"]

_MASK = "***"

# A key is sensitive when ANY of its separator/camelCase tokens is one of
# these words, or the separator-stripped whole key matches (``session_id`` ->
# ``sessionid``, ``connection_string`` -> ``connectionstring``). Exact token
# equality keeps lookalikes benign: ``keyword``/``monkey``/``authors``/
# ``oauth``/``bypass``/``passwordless`` never match.
_SECRET_WORDS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "pass",
        "passphrase",
        "passcode",
        "secret",
        "credential",
        "credentials",
        "apikey",
        "key",
        "token",
        "auth",
        "authorization",
        "assertion",
        "signature",
        "sig",
        "hmac",
        "jwt",
        "bearer",
        "sessionid",
        "jsessionid",
        "phpsessid",
        "sid",
        "session",
        "otp",
        "totp",
        "sas",
        "saml",
        "verifier",
        "challenge",
        "pin",
        "cvv",
        "cvc",
        "pat",
        "license",
        "dsn",
        "connectionstring",
        "connstr",
    }
)

# Credential only as the ENTIRE key: OAuth's bare ``?code=`` masks, while
# ``status_code``/``error_code`` (debug-critical) stay visible.
_SECRET_WHOLE_ONLY = frozenset({"code"})

# Glued (separator-less) suffixes, e.g. ``sslpassword`` / ``xapikey``.
_SECRET_SUFFIXES = (
    "password",
    "passphrase",
    "passcode",
    "signature",
    "apikey",
    "connectionstring",
    "connstr",
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
        "ssl",
        "account",
        "storage",
    }
)

# Split camelCase and ACRONYMBoundaries (HMACKey -> HMAC, Key).
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SEPARATORS = re.compile(r"[-_.]+")
# Fallback for unparseable URLs: mask the userinfo password (scheme://user:PW@).
# The password class allows '@'/':' and backtracks to the last '@' before the
# path, so an unescaped '@' in the password is still fully masked.
_USERINFO_PW = re.compile(r"(://[^:/?#@\s]*:)[^/?#\s]+(@)")
# Scheme-less userinfo (the forgot-the-scheme typo: ``dbuser:pw@host/db``).
# urlparse reads ``dbuser`` as the scheme there, so the netloc path never
# fires; anchored at the start so prose with colons is left alone.
_SCHEMELESS_PW = re.compile(r"^([^:/?#@\s]+:)[^/?#\s]+(@)(?=[^/?#\s@]*[/:])")


def _is_sensitive_key(key: str) -> bool:
    """True if a query/fragment/params key names a credential.

    Any secret-word token masks (``access_token``, ``db_pass``,
    ``api_key_v2beta`` — the qualifier tokens don't hide the match), plus a
    stripped-whole-key check for separator-spanning words and a suffix/prefix
    check for glued forms like ``sslpassword``/``secretkey``. No benign
    carve-outs: ``sort_key``/``page_token`` mask too, by design (see module
    docstring).
    """
    raw = unquote_plus(key).strip()
    if not raw:
        return False

    k = _CAMEL.sub("_", raw).lower()
    tokens = [t for t in _SEPARATORS.split(k) if t]
    if not tokens:
        return False
    stripped = "".join(tokens)

    if stripped in _SECRET_WHOLE_ONLY:
        return True
    # A secret-word token (or its plural: passwords/tokens/keys).
    if any(t in _SECRET_WORDS or (t.endswith("s") and t[:-1] in _SECRET_WORDS) for t in tokens):
        return True
    # A secret word spanning separators (session_id -> sessionid).
    if stripped in _SECRET_WORDS:
        return True
    if _is_glued_credential(stripped):
        return True
    return any(stripped.endswith(sfx) for sfx in _SECRET_SUFFIXES)


def _is_glued_credential(stripped: str) -> bool:
    """True for separator-less compounds like ``secretkey`` / ``accesstoken``."""
    for suffix in ("key", "token", "secret", "password"):
        if stripped.endswith(suffix) and len(stripped) > len(suffix):
            prefix = stripped[: -len(suffix)]
            # ``secretaccesskey`` -> prefix ``secretaccess`` starts with ``secret``.
            if any(prefix.startswith(p) for p in _CREDENTIAL_PREFIXES):
                return True
    return False


def _redact_pairs(component: str) -> tuple[str, bool]:
    """Mask sensitive values in an ``&``-separated key=value string.

    Per the WHATWG URL standard, ``&`` is the only separator; a ``;`` is data
    and stays inside its value. A sensitive key masks its whole value
    (including any ``;`` tail). Defensively, a legacy ``;``-glued sub-pair
    inside a *benign* key's value (``db=0;password=x``) is also masked, pair
    by pair. Non-sensitive pairs are preserved byte-for-byte. Returns the
    (possibly rewritten) component and whether anything changed.
    """
    changed = False
    parts = component.split("&")
    for i, part in enumerate(parts):
        key, sep, value = part.partition("=")
        if sep and value and _is_sensitive_key(key):
            parts[i] = f"{key}={_MASK}"
            changed = True
            continue
        if ";" in part:
            subs = part.split(";")
            sub_changed = False
            for j, sub in enumerate(subs):
                skey, ssep, svalue = sub.partition("=")
                if ssep and svalue and _is_sensitive_key(skey):
                    subs[j] = f"{skey}={_MASK}"
                    sub_changed = True
            if sub_changed:
                parts[i] = ";".join(subs)
                changed = True
    return ("&".join(parts), changed) if changed else (component, False)


def redact_url_password(value: str) -> str:
    """Return ``value`` with any URL credential replaced by ``***``.

    Masks the userinfo password (``user:pass@host`` -> ``user:***@host``,
    including the scheme-less typo form ``user:pass@host`` with no ``//``)
    and the value of any sensitive key in the query string, fragment, or
    ``;``-params component (e.g. ``?password=`` / ``#access_token=`` /
    ``/path;password=``). Host, port, and non-sensitive parameters are
    preserved verbatim. A string without any credential-shaped part is
    returned unchanged, so this is safe to call on arbitrary values.
    """
    # Scheme-less userinfo: urlparse would read the username as the scheme, so
    # mask a leading `user:pw@host/…` up front (anchored + a path/port lookahead
    # so `https://…` and email-shaped `cc:john@example.com` are left alone). Done
    # unconditionally so a later `://` (e.g. in a redirect param) can't skip it.
    prefix_masked = _SCHEMELESS_PW.sub(rf"\1{_MASK}\2", value)

    try:
        parsed = urlparse(prefix_masked)
    except ValueError:
        # Malformed URL (e.g. bad IPv6). urlparse can't help, but neither the
        # userinfo password nor a query/fragment secret may leak, so mask the
        # userinfo by regex and redact the (splittable) query and fragment.
        masked = _USERINFO_PW.sub(rf"\1{_MASK}\2", prefix_masked)
        head, hsep, frag = masked.partition("#")
        head, qsep, query = head.partition("?")
        head, psep, params = head.partition(";")
        if psep:
            params = _redact_pairs(params)[0]
        if qsep:
            query = _redact_pairs(query)[0]
        if hsep:
            frag = _redact_pairs(frag)[0]
        return head + psep + params + qsep + query + hsep + frag

    netloc = parsed.netloc
    changed = prefix_masked != value

    if parsed.password:
        userinfo, _, hostpart = netloc.rpartition("@")
        username = userinfo.partition(":")[0]
        netloc = f"{username}:{_MASK}@{hostpart}"
        changed = True

    params, params_changed = (
        _redact_pairs(parsed.params) if parsed.params else (parsed.params, False)
    )
    query, query_changed = _redact_pairs(parsed.query) if parsed.query else (parsed.query, False)
    fragment, frag_changed = (
        _redact_pairs(parsed.fragment) if parsed.fragment else (parsed.fragment, False)
    )
    changed = changed or params_changed or query_changed or frag_changed

    if not changed:
        return value

    return parsed._replace(netloc=netloc, params=params, query=query, fragment=fragment).geturl()
