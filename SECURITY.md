# Security Policy

NetDeck launches powerful network tools, some with administrator rights, so we take security reports seriously.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |

## Reporting a vulnerability

**Please do not open a public issue.** Use GitHub's
[private vulnerability reporting](https://github.com/randynorthrup/netdeck/security/advisories/new)
and include:

- the NetDeck version (`netdeck --version`) and your distribution,
- steps to reproduce, and the impact you believe it has.

You can expect an acknowledgement within 3 working days and a fix or mitigation plan within 14 days for
confirmed issues. We are happy to credit reporters in the release notes.

## Threat model

NetDeck is a **single-user, local** application. It defends against:

| Threat | Mitigation |
| --- | --- |
| Other websites in your browser (CSRF) | `SameSite=Strict` cookie, mandatory `X-NetDeck` header (forces CORS preflight, which is never granted), `Origin` check |
| DNS rebinding | `Host` header must be `127.0.0.1`, `localhost` or `[::1]` with the instance port |
| Other machines on the network | Binds to `127.0.0.1`; `--allow-remote` must be passed explicitly and prints a warning |
| Unauthenticated local clients | Per-instance 256-bit random token, compared in constant time |
| Remote shutdown (`POST /api/shutdown`) | Same token, CSRF header and Origin checks as every other state-changing request |
| Command / option injection | No shell; argv lists only; typed validators reject leading `-`, control characters and malformed values; free-form filters are passed as a single argument after `--` |
| XSS via tool output | Output inserted as text nodes only; strict CSP (`script-src 'self'`), no inline scripts |
| Path traversal | Static files are served from a fixed directory with `realpath` containment |

**Out of scope:** processes running as your own user can already read NetDeck's token file
(`$XDG_RUNTIME_DIR/netdeck/instance.json`, mode `0600`) and act as you. Granting passwordless sudo or file
capabilities to tools is a decision you make for your whole system, not just for NetDeck.

## Hardening tips

- Prefer `pkexec` (default) over passwordless sudo.
- Keep `--allow-remote` off; use an SSH tunnel (`ssh -L 8737:127.0.0.1:8737 host`) for remote access.
