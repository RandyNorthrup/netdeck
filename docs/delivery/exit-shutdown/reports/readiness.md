# Readiness review — WORK-EXIT-SHUTDOWN (scope revision 1)

Reviewed 2026-11-08 against `docs/delivery/exit-shutdown/PLAN.md` (plan sha256 `30f3fb55…`, scope sha256
`f1b0f2e8…`), source at `f5cac27` with a clean working tree. This reviews the requirements only; it is
not evidence that any behavior works.

## Clarity and measurability

| Criterion | Observable result | Finding |
| --- | --- | --- |
| AC-EXIT-1 | 202 from `/api/shutdown`, stopped screen element, process exit 0 ≤ 10 s | Measurable in a browser test against a real server process. |
| AC-EXIT-2 | dialog closed, no `/api/shutdown` request, `/api/ping` still 200 | Measurable; "no request sent" is observed through the server still running after cancel. |
| AC-EXIT-3 | 401/403 and `App.shutdown` unset | Measurable at the HTTP layer; three negative variants listed. |
| AC-STOP-1 | exit 0; no `ping` process carrying the job's unique argument | A unique packet size makes the job's process identifiable in `/proc`. Three trigger paths. |
| AC-STOP-2 | job status `stopped` ≤ 6 s, interrupt output captured | "Cannot signal" is simulated by making `os.killpg` raise `PermissionError` for the job, which is exactly what a root-owned child produces. 6 s covers the supervisor's INT → 2 s → TERM → 2 s → KILL ladder. |
| AC-STOP-3 | three SIGINT-ignoring jobs; shutdown < 4 s with a 2 s grace | Sequential termination would take ≥ 6 s, so the threshold discriminates. |
| AC-STREAM-1 | `event: bye` within 2 s | Measurable with a raw HTTP client. |
| AC-STREAM-2 | stopped screen ≤ 10 s after SIGINT | Measurable in the browser test. |
| AC-INST-1 | `instance.json` absent after each graceful path | Covered by the same subprocess tests as AC-STOP-1. |
| AC-INST-2 | `netdeck stop` exit/timing and stale-file removal | Measurable with isolated `XDG_RUNTIME_DIR`. |

## Conflicts and failure behavior

- No contradictions: the 10 s exit bound (AC-EXIT-1) exceeds the job deadline (~4 s) plus stream drain (2 s).
- Failure of the shutdown request itself (network error) keeps the existing behavior: the `api()` helper
  raises and the UI shows an error toast; the page stays usable. No new obligation needed.
- Repeated requests (double click, Ctrl+C twice, API + signal) must be idempotent: `request_shutdown`
  sets an event and starts the server shutdown once. Covered by design; exercised indirectly when the
  API test and the signal handler share the code path.
- `netdeck stop` when the process does not exit within its wait: report failure and exit non-zero rather
  than claim success (part of AC-INST-2's "returns 0 only after the process is gone").

## Scope and non-goals

- In scope: UI Exit, the API route, signal paths, `netdeck stop`, job termination (including polkit
  elevation), SSE streams, instance file.
- Out of scope (stated in the plan and to be stated in the dialog): detached terminal windows and desktop
  apps; cleanup after SIGKILL/power loss.
- sudo-mode elevation keeps its existing, working path (sudo relays signals to its child). It is not
  re-tested here because CI has no passwordless sudo policy for test tools; recorded as a limitation, not
  a gap in this change.

## Rules (CONTRIBUTING.md) and decisions

- "No new runtime dependencies": met. `websocket-client` is a dev/test extra only.
- "Never build shell strings": the polkit supervisor is a constant POSIX `sh` script; the tool argv is
  passed as positional parameters (`"$@"`), never interpolated, the same pattern `terminal.py` already uses
  for its hold wrapper. Consistent with the rule's intent; docs/ADDING_TOOLS.md's ban on `sh -c` applies
  to tool builders and is unaffected.
- Accepted trade-off: under polkit the authentication dialog names `/bin/sh` as the program (the details
  still show the full command line). Required because only a root-side process can signal the root-owned
  tool. To be documented in docs/PRIVILEGES.md.
- POSIX detail to honor: a non-interactive shell gives background lists `/dev/null` as stdin, so the
  supervisor must duplicate its stdin to another descriptor before backgrounding the watcher.

## Coverage

Every requirement has acceptance; every acceptance has an owning task; task dependencies form a chain
SUPERVISOR → RUNNER → SERVER → CLI → UI → DOCS with no cycles. Each criterion declares behavior and red
checks. Browser tests must not silently skip in CI: they will skip locally only when Chrome or
`websocket-client` is missing, and CI sets `NETDECK_REQUIRE_E2E=1` so a missing prerequisite fails.

Result: ready, with the limitations above recorded.
