# Readiness review — WORK-INSTALLER-UPGRADE (scope revision 1)

Reviewed 2026-11-08 at 46866a0, clean tree. Requirements review only; not evidence of working behavior.

**Clarity.** Each criterion is observable from outside the installer: process liveness and start time
(`/proc`), the registered instance (`netdeck url` / instance file), the restarted process's argv, the
installer's exit code and output order, and the calls recorded by a `systemctl` stub.

**Conflicts / failure behavior.**
- If the owned instance does not stop within the wait, the installer must fail before replacing files
  (it would otherwise reproduce the defect). Recorded in the design; exercised indirectly because the
  restart criterion requires the old pid to be gone.
- If the restart fails, the installer warns and prints how to start NetDeck rather than failing the
  completed upgrade.
- Ownership is decided per installation: AC-UPG-3 prevents the fix from stopping a developer's source
  instance, which would be a surprising side effect of reinstalling.

**Scope.** In: installer stop/restart for the user and `--system` layouts, systemd user service. Out: pip/pipx
upgrades (no hook exists there), uninstall (already stops NetDeck).

**Rules (CONTRIBUTING.md).** Shell must pass shellcheck; no new runtime dependencies (none). The ownership
check runs the *installed* copy's Python and `netdeck.cli.read_instance` instead of duplicating the runtime
directory and instance-file logic in shell.

**Testability.** Real installs into an isolated `$HOME`, `XDG_RUNTIME_DIR` and port so the user's own NetDeck
on 8737 is untouched; servers are started with `setsid -f` (as real launches are) so they are reaped by init,
not left as zombies of the test. CI's install job runs the test with `NETDECK_TEST_INSTALL=1`; without it the
test skips locally because each install builds a virtualenv.

Result: ready.
