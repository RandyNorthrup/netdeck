# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Exit** button (top-right power icon) with a confirmation dialog that lists the tools it will stop, and a
  "NetDeck has stopped" screen. Open pages also switch to that screen when NetDeck is stopped elsewhere.
- `POST /api/shutdown`, protected like every other state-changing request.

### Fixed
- Tools elevated through polkit can now be stopped: they run under a root-side supervisor that interrupts them
  when NetDeck closes its stdin. Previously Stop and shutdown could leave them running as root.
- Shutdown stops all running jobs in parallel under one deadline instead of one after another.
- Live output streams end promptly on shutdown with a goodbye event instead of waiting up to 15 s.
- `netdeck stop` waits for the server to exit and reports failure if it does not, and a stale `instance.json`
  left by a crash is removed.

### Changed
- Minimum Python is now 3.10 (3.9 is end-of-life and unavailable on current CI runners); CI tests 3.10–3.14.
- CI actions updated to their Node 24 releases.

## [1.0.0] - 2026-11-08

### Added
- Local web dashboard with Overview, 10 tool categories, Activity history and Settings.
- 62 tool workflows: connectivity, DNS, discovery, throughput, traffic, capture, interfaces, sockets, web/TLS, firewall.
- One-click layered connection health check (link → gateway → DNS → internet → HTTPS).
- Live per-interface throughput graphs, Wi-Fi signal and link details.
- Streaming output with highlighting, filtering, copy, download and stop; `\r` progress handling.
- Built-in TCP port probe and TLS certificate inspector (no external binaries needed).
- Capture-to-file with "Open in Wireshark".
- Interactive TUI tools open in the user's terminal; GUI tools launch directly.
- Command palette, keyboard shortcuts, dark/light themes, accent colours, responsive layout.
- Privilege elevation per command via polkit or sudo, with file-capability detection.
- Security: loopback binding, session token, Host/Origin/CSRF checks, strict CSP, argv-only execution.
- `netdeck doctor`, `url` and `stop` commands; single-instance re-open.
- Installer (user/system, optional tools and systemd user service), uninstaller, desktop entry.
