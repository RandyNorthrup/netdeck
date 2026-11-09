# Readiness review addendum — WORK-EXIT-SHUTDOWN (scope revision 1)

Re-reviewed 2026-11-08 at closure because readiness inputs changed after the first review
(`readiness.md`, receipt EV-READY-1, now stale):

| Input | Change | Effect on requirements |
| --- | --- | --- |
| `README.md` (brief) | Usage section documents Exit, `netdeck stop` waiting, and that terminal/desktop windows stay open | Describes delivered behavior; no product decision changed. Matches AC-EXIT-1, AC-STOP-1, AC-INST-2 and the plan's non-goals. |
| `pyproject.toml` | `websocket-client` added to the `dev` extra | Test-only dependency for the browser tests; runtime `dependencies = []` unchanged, consistent with the CONTRIBUTING zero-dependency rule. |
| `CONTRIBUTING.md` (rules) | Unchanged | — |

Requirements, acceptance criteria, task mapping and non-goals are unchanged; no criterion was rewritten to fit
the implementation. Findings recorded during implementation that refined *tests*, not requirements:

- RD-STREAM-1a initially survived because the stream test's job printed every second, which woke the stream
  without the shutdown path; the fixture now uses a silent job, and the drill fails as intended.
- RD-STOP-3's first mutation crashed (`RuntimeError` from joining an unstarted thread) instead of exercising
  the timing assertion; it was replaced by a sequential-termination mutation that models the original defect.
- RD-INST-2a depends on the server needing time to exit after SIGTERM; it was repeated three times and failed
  as intended each time.

Open external outcome: the updated CI workflow (`NETDECK_REQUIRE_E2E=1`, browser tests in the runner's Chrome,
ping-based CLI tests) has not run on GitHub yet; it runs when these changes are pushed.

Result: still ready; scope and requirements unchanged.
