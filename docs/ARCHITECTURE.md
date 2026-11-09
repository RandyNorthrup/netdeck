# Architecture

```
 Browser (vanilla JS SPA)                     NetDeck server (Python stdlib)
 ┌────────────────────────────┐   fetch    ┌──────────────────────────────────────────────┐
 │ Overview · Categories ·    │ ─────────▶ │ server.py   routes, auth, CSRF/Host checks,  │
 │ Tool forms · Console ·     │            │             static files, SSE                │
 │ Activity · Settings ·      │ ◀───────── │ catalog.py  Tool/Param definitions → argv    │
 │ Command palette            │    SSE     │ validators  typed input validation           │
 └────────────────────────────┘            │ runner.py   jobs, process groups, streaming  │
                                           │ hostenv.py  which(), distro, privileges      │
                                           │ sysinfo.py  interfaces, routes, DNS, counters│
                                           │ probes.py   built-in TCP/TLS/health probes   │
                                           │ terminal.py open TUIs in a terminal emulator │
                                           └───────────────┬──────────────────────────────┘
                                                           │ argv (no shell)
                                                           ▼
                                    ping · mtr · dig · nmap · tcpdump · iperf3 · ss · …
```

## Request flow for a tool run

1. The form posts `{tool, params}` to `/api/preview` (debounced) — the server validates and returns the
   exact command line, shown under *Command*.
2. *Run* posts to `/api/run`. The server validates again, builds a `Plan`, decides on elevation and starts a
   `Job` thread. Terminal and GUI tools are launched detached and return immediately.
3. The browser opens `/api/jobs/<id>/stream` (Server-Sent Events). Lines are addressed by absolute index and
   revision, so carriage-return progress updates replace lines in place and reconnects resume without gaps.
4. *Stop* sends `SIGINT` to the process group (so tools print their summaries), then `SIGTERM`, then `SIGKILL`.

## Why no framework?

Zero runtime dependencies means NetDeck installs on any distribution with Python 3.10+, works offline, and has
a tiny supply-chain surface for a tool that can run privileged commands. `ThreadingHTTPServer` + SSE is ample
for a single local user.

## State

- Jobs live in memory (last 100 kept; output capped at 50k lines per job, downloadable in full until trimmed).
- Server settings: `~/.config/netdeck/config.json`. Instance info (pid, port, token): `$XDG_RUNTIME_DIR/netdeck/instance.json` (0600).
- Browser-only preferences (theme, accent, last parameters per tool, recent hosts) use `localStorage`.
