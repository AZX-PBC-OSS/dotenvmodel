# Security Policy

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability in dotenvmodel, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please use [GitHub Security Advisories](https://github.com/AZX-PBC-OSS/dotenvmodel/security/advisories/new) to report vulnerabilities privately.

## Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial Assessment:** Within 5 business days
- **Fix or Mitigation:** Depends on severity, typically within 30 days for high-severity issues

## Scope

This policy covers the dotenvmodel Python package and its CI/CD pipeline. Vulnerabilities in third-party dependencies should be reported to their respective maintainers.

## Disclosure

We follow coordinated disclosure. Once a fix is released, we will publish a GitHub Security Advisory with credit to the reporter (unless they prefer to remain anonymous).

## Residual Secret-Exposure Channels

dotenvmodel masks secrets in the common display paths (`repr`, error messages, and exception chains for `SecretStr` and DSN-typed fields). Two residual channels remain by design and are the caller's responsibility to mitigate:

- **Traceback frame locals.** When a load-time error is raised, library internals hold the raw env value in local variables (e.g. `raw_value` in `_process_field`); validator-hook errors additionally hold the coerced value in `_run_field_validator`/`_run_sensitive_validator` frame locals. Error-reporting tools that capture locals will record these — Sentry with `include_locals=True`, `pytest --showlocals`, or rich tracebacks. Do not enable local capture for processes that load configs containing secrets.
- **`FieldInfo.__repr__`.** `FieldInfo.__repr__` prints `default` values verbatim (the raw default stored on the descriptor, before load-time coercion). A `str` default supplied for a `SecretStr` field is visible in `repr(field_info)` and in `describe()`/`generate_env_example()` introspection. Do not log `FieldInfo` reprs, or pass secret defaults as `SecretStr(...)` instances (which mask themselves) rather than plain strings.
