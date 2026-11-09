# Delivery plan: Exit button and clean shutdown

## Rationale

The user asked for an Exit button and for NetDeck to shut down and clean up properly. A scan of the
canonical shutdown paths (`cli.cmd_serve`, `cli.cmd_stop`, `server.Handler.api_job_stream` /
`api_stats_stream`, `runner.JobManager.shutdown` / `_terminate` / `_pump` / `_exec`) found these gaps:

1. There is no way to exit from the UI.
2. Elevated jobs started through polkit (`pkexec`) run with root's real uid, so `os.killpg` raises
   `PermissionError`; `_pump`/`_exec` then abandon the child, which keeps running until its next write.
   Neither Stop nor shutdown can end it.
3. `JobManager.shutdown` stops jobs one after another (up to ~3 s each).
4. Job output streams wait up to 15 s on the job condition and never learn that the server is stopping;
   open pages get no signal and just see network errors.
5. `netdeck stop` sends SIGTERM and prints "Stopped" without confirming the process exited, and a stale
   `instance.json` left by a crash is never removed.

**Approach (reuse first).** Shutdown stays owned by `cmd_serve`; the existing `App.shutdown` event becomes
the single signal, set through a new `App.request_shutdown` used by the signal handlers and the new
`POST /api/shutdown` route (same auth/CSRF dispatcher as every other POST). `JobManager` keeps owning
process termination: it now stops all jobs concurrently under one deadline. For polkit elevation,
`Privilege.wrap` (the canonical elevation point) runs the tool under a small root-side POSIX `sh`
supervisor that interrupts the tool when NetDeck closes the supervisor's stdin; closing a pipe needs no
privileges, and the pipe also closes if NetDeck dies. The tool's argv is passed as positional parameters,
never interpolated. SSE handlers send a `bye` event and are counted so shutdown can let them flush.
The UI adds an Exit control with a native `<dialog>` confirmation and a stopped screen shown after Exit,
on `bye`, or when the server stops answering.

**Non-goals.** Terminal windows and desktop apps launched from NetDeck are detached, user-owned windows
and stay open (the dialog says so). SIGKILL/power loss cannot run cleanup; non-elevated children then end
via SIGPIPE as before, and supervised elevated children end because their stdin pipe closes.

**Test strategy.** Python behavior tests extend the canonical `tests/test_runner.py` and
`tests/test_server.py`; process-level shutdown paths get `tests/test_cli.py` (real `python -m netdeck`
subprocesses in isolated runtime/config dirs); UI behavior gets `tests/test_ui_e2e.py`, driving headless
Chrome over the DevTools protocol against a real server. Red drills mutate disposable copies.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "WORK-EXIT-SHUTDOWN",
    "title": "Exit button and clean shutdown",
    "scope_revision": 1,
    "brief": "README.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "CONTRIBUTING.md",
        "revision": "f5cac27"
      }
    ],
    "inputs": [
      "pyproject.toml"
    ],
    "environment": {
      "platform": "linux",
      "tools": {
        "python": "3.14.9",
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "node": "26.13.0",
        "shellcheck": "0.11.0",
        "google-chrome": "154.0.8037.97",
        "websocket-client": "1.9.2"
      }
    }
  },
  "requirements": [
    {
      "id": "REQ-EXIT",
      "statement": "The dashboard offers an Exit control that, after confirmation, shuts NetDeck down; unauthenticated or cross-origin shutdown requests are refused.",
      "priority": "critical",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-EXIT-3"
      ],
      "superseded_by": null
    },
    {
      "id": "REQ-STOP",
      "statement": "Every graceful shutdown path (Exit, Ctrl+C/SIGINT, SIGTERM/netdeck stop) stops all running jobs, including polkit-elevated ones, within a bounded time and leaves no tool process behind.",
      "priority": "critical",
      "acceptance": [
        "AC-STOP-1",
        "AC-STOP-2",
        "AC-STOP-3"
      ],
      "superseded_by": null
    },
    {
      "id": "REQ-STREAM",
      "statement": "Open pages are told the server is stopping, and live streams do not delay exit.",
      "priority": "normal",
      "acceptance": [
        "AC-STREAM-1",
        "AC-STREAM-2"
      ],
      "superseded_by": null
    },
    {
      "id": "REQ-INST",
      "statement": "Instance bookkeeping is cleaned up and netdeck stop reports the real outcome.",
      "priority": "normal",
      "acceptance": [
        "AC-INST-1",
        "AC-INST-2"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-EXIT-1",
      "requirement": "REQ-EXIT",
      "given": "The dashboard is open with a valid session and the server is running",
      "when": "The user activates the Exit control and confirms in the dialog",
      "then": "POST /api/shutdown returns 202, the page shows the 'NetDeck has stopped' screen, and the server process exits with status 0 within 10 s",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-EXIT-2",
      "requirement": "REQ-EXIT",
      "given": "The Exit dialog is open",
      "when": "The user cancels it",
      "then": "The dialog closes, no shutdown request is sent, and the server still answers /api/ping",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-EXIT-3",
      "requirement": "REQ-EXIT",
      "given": "A running server",
      "when": "POST /api/shutdown arrives without the session cookie, without the X-NetDeck header, or with a foreign Origin",
      "then": "It is refused with 401/403 and the shutdown event stays unset",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-STOP-1",
      "requirement": "REQ-STOP",
      "given": "A server started with python -m netdeck running a continuous ping job",
      "when": "Shutdown is triggered via POST /api/shutdown, via netdeck stop (SIGTERM), or via SIGINT",
      "then": "The server exits with status 0 and no ping process from that job remains",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-STOP-2",
      "requirement": "REQ-STOP",
      "given": "A running elevated job in polkit mode whose process NetDeck cannot signal",
      "when": "The job is stopped or the job manager shuts down",
      "then": "The tool receives SIGINT through the supervisor, its interrupt output is captured, and the job ends as 'stopped' within 6 s",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-STOP-3",
      "requirement": "REQ-STOP",
      "given": "Three running jobs that each need their full SIGINT grace period to exit",
      "when": "JobManager.shutdown runs",
      "then": "All processes are gone and shutdown returns within one grace period plus margin, not three",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-STREAM-1",
      "requirement": "REQ-STREAM",
      "given": "An open job output stream for a running job",
      "when": "Shutdown is requested",
      "then": "The stream receives a 'bye' event and closes within 2 s",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-STREAM-2",
      "requirement": "REQ-STREAM",
      "given": "The dashboard is open",
      "when": "The server is stopped from the terminal with SIGINT",
      "then": "Within 10 s the page shows the stopped screen",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-INST-1",
      "requirement": "REQ-INST",
      "given": "A running instance with its instance.json",
      "when": "It stops through any graceful path",
      "then": "instance.json is removed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-INST-2",
      "requirement": "REQ-INST",
      "given": "A running instance, or an instance.json whose pid is dead",
      "when": "netdeck stop runs",
      "then": "It returns 0 only after the server process is gone and prints that it stopped; for a dead pid it reports not running and removes the stale file",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "TASK-SUPERVISOR",
      "purpose": "Run polkit-elevated tools under a root-side sh supervisor that interrupts the tool when its stdin closes",
      "acceptance": [
        "AC-STOP-2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "src/netdeck/hostenv.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-BEH-RUNNER-G",
        "EV-RED-STOP-2a-G",
        "EV-RED-STOP-2b-G"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-RUNNER",
      "purpose": "Stop supervised jobs by closing stdin, drop the abandon-on-PermissionError paths, stop all jobs concurrently under one deadline, and wake waiting streams",
      "acceptance": [
        "AC-STOP-2",
        "AC-STOP-3"
      ],
      "depends_on": [
        "TASK-SUPERVISOR"
      ],
      "changes": [
        {
          "path": "src/netdeck/runner.py",
          "action": "modify"
        },
        {
          "path": "tests/test_runner.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-BEH-RUNNER-G",
        "EV-RED-STOP-2a-G",
        "EV-RED-STOP-2b-G",
        "EV-RED-STOP-3-G"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-SERVER",
      "purpose": "Add POST /api/shutdown, App.request_shutdown/close, SSE bye events and live-stream tracking",
      "acceptance": [
        "AC-EXIT-3",
        "AC-STREAM-1"
      ],
      "depends_on": [
        "TASK-RUNNER"
      ],
      "changes": [
        {
          "path": "src/netdeck/server.py",
          "action": "modify"
        },
        {
          "path": "tests/test_server.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-BEH-SERVER-G",
        "EV-RED-EXIT-3-G",
        "EV-RED-STREAM-1a-G",
        "EV-RED-STREAM-1b-G"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-CLI",
      "purpose": "Wire one shutdown sequence for signals and the API, make netdeck stop wait for exit, and remove stale instance files",
      "acceptance": [
        "AC-STOP-1",
        "AC-INST-1",
        "AC-INST-2"
      ],
      "depends_on": [
        "TASK-SERVER"
      ],
      "changes": [
        {
          "path": "src/netdeck/cli.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-BEH-CLI-G",
        "EV-RED-STOP-1-G",
        "EV-RED-INST-1-G",
        "EV-RED-INST-2a-G",
        "EV-RED-INST-2b-G"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-UI",
      "purpose": "Add the Exit control, confirmation dialog and stopped screen, detect server shutdown, and cover it with a browser test wired into CI",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-STREAM-2"
      ],
      "depends_on": [
        "TASK-CLI"
      ],
      "changes": [
        {
          "path": "src/netdeck/static/index.html",
          "action": "modify"
        },
        {
          "path": "src/netdeck/static/app.js",
          "action": "modify"
        },
        {
          "path": "src/netdeck/static/app.css",
          "action": "modify"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "action": "create"
        },
        {
          "path": ".github/workflows/ci.yml",
          "action": "modify"
        },
        {
          "path": "pyproject.toml",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-BEH-UI-G",
        "EV-RED-EXIT-1-G",
        "EV-RED-EXIT-1api-G",
        "EV-RED-EXIT-2-G",
        "EV-RED-STREAM-2-G"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-DOCS",
      "purpose": "Document Exit, shutdown guarantees and the polkit supervisor from shipped behavior",
      "acceptance": [
        "AC-EXIT-1",
        "AC-STOP-2"
      ],
      "depends_on": [
        "TASK-UI"
      ],
      "changes": [
        {
          "path": "README.md",
          "action": "modify"
        },
        {
          "path": "CHANGELOG.md",
          "action": "modify"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "action": "modify"
        },
        {
          "path": "SECURITY.md",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-BEH-UI-G",
        "EV-BEH-RUNNER-G",
        "EV-RED-EXIT-1-G",
        "EV-RED-STOP-2a-G",
        "EV-RED-STOP-2b-G"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-READY-1",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-EXIT-3",
        "AC-STOP-1",
        "AC-STOP-2",
        "AC-STOP-3",
        "AC-STREAM-1",
        "AC-STREAM-2",
        "AC-INST-1",
        "AC-INST-2"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Manual requirements review of every criterion for measurability, conflicts, failure behavior, scope, CONTRIBUTING rules and task coverage; findings and accepted trade-offs recorded in the artifact.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/readiness.md",
        "sha256": "87c9b841ebd27a7c117ace1e1f91c9f237e265d0b5c9d6284fee2cd8f376b243"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-RUNNER-1",
      "acceptance": [
        "AC-STOP-2",
        "AC-STOP-3"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py"
      ],
      "method": "Ran the runner suite with PYTHONPATH=src: elevated polkit-mode job stopped via supervisor with os.killpg forced to raise PermissionError (stop and shutdown variants), and three SIGINT-ignoring jobs stopped concurrently; 9 tests collected and passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/behavior/runner.log",
        "sha256": "04f00802c35ad463411e47e3d89b9754cf5cc69d661e4515d28cd617e09cd7a2"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "e3ca0ac7594d150e230a1c251d76f4a278f76be54d86146626959c8ee05bf3a9"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "c869230bde79f54f370c5ed902665d3080f41954b8550d9b2018a179273221f3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "SECURITY.md",
          "sha256": "da4a8aef76bf94ad294a71fa0d8e5d39f6c36d3e7fa004896d22e1efa857c379"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "a57e00740086039a86d0256526560c0614dcaa287c59fb71ccd4185418d38482"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "a8191db677ae2881c4b67b9c1e262a9dcab22c993ce5e2cdb0365551da406832"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "04189509f1dbac287e370ab88a53ad8757a915799fd1ba5e5008d7ed92870a69"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "3726ae67eb0a1b6f0eeb2903dd9823a8cc7196cd85504fb65c0f8510d79445aa"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "b96e9f57b216eeaea2cb7e51de680eca42331820bd9942bdd6118b7a6cb61fdc"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "a6a9060c3db24793c1f75fc6a6e04cfa9f74249b5655868bda9c6cd220a77631"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": null
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "055d8d8888c9038f7525ebda9cab29f1c710ad0f8eeb83a5d78c9b4474133ee9"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": null
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-2a",
      "acceptance": [
        "AC-STOP-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_unsignalable_elevated_job_is_stopped_through_supervisor"
      ],
      "method": "Removed the stdin close from the supervised branch of JobManager._terminate in a disposable copy; the stop test failed because the job stayed running; original restored byte-identical and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-2a.log",
        "sha256": "50f80db3d6c2d24e49d654dd7387356bd4b5d216da6513a4d6de3b2c11011d3d"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "e3ca0ac7594d150e230a1c251d76f4a278f76be54d86146626959c8ee05bf3a9"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "c869230bde79f54f370c5ed902665d3080f41954b8550d9b2018a179273221f3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "SECURITY.md",
          "sha256": "da4a8aef76bf94ad294a71fa0d8e5d39f6c36d3e7fa004896d22e1efa857c379"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "a57e00740086039a86d0256526560c0614dcaa287c59fb71ccd4185418d38482"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "a8191db677ae2881c4b67b9c1e262a9dcab22c993ce5e2cdb0365551da406832"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "04189509f1dbac287e370ab88a53ad8757a915799fd1ba5e5008d7ed92870a69"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "3726ae67eb0a1b6f0eeb2903dd9823a8cc7196cd85504fb65c0f8510d79445aa"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "b96e9f57b216eeaea2cb7e51de680eca42331820bd9942bdd6118b7a6cb61fdc"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "a6a9060c3db24793c1f75fc6a6e04cfa9f74249b5655868bda9c6cd220a77631"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": null
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "055d8d8888c9038f7525ebda9cab29f1c710ad0f8eeb83a5d78c9b4474133ee9"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": null
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/runner.py: '            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.\\n            _close_quietly(proc.stdin)\\n' -> '            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'running' == 'stopped'",
        "observed_diagnostic": "assert 'running' == 'stopped'",
        "before": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "bbe7557f11d9ab7cf5df5060bdf5e1cadabf6226bc65b244ed59571bf875a67c"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-2b",
      "acceptance": [
        "AC-STOP-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_unsignalable_elevated_job_is_stopped_through_supervisor"
      ],
      "method": "Made the supervisor watcher read the background /dev/null stdin instead of fd 3 in a disposable copy; the tool was never interrupted and the test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-2b.log",
        "sha256": "752bf9192a308b2f05690f32702ab6768b6dc9213034c40492e4e79a42ef2984"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "e3ca0ac7594d150e230a1c251d76f4a278f76be54d86146626959c8ee05bf3a9"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "c869230bde79f54f370c5ed902665d3080f41954b8550d9b2018a179273221f3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "SECURITY.md",
          "sha256": "da4a8aef76bf94ad294a71fa0d8e5d39f6c36d3e7fa004896d22e1efa857c379"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "a57e00740086039a86d0256526560c0614dcaa287c59fb71ccd4185418d38482"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "a8191db677ae2881c4b67b9c1e262a9dcab22c993ce5e2cdb0365551da406832"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "04189509f1dbac287e370ab88a53ad8757a915799fd1ba5e5008d7ed92870a69"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "3726ae67eb0a1b6f0eeb2903dd9823a8cc7196cd85504fb65c0f8510d79445aa"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "b96e9f57b216eeaea2cb7e51de680eca42331820bd9942bdd6118b7a6cb61fdc"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "a6a9060c3db24793c1f75fc6a6e04cfa9f74249b5655868bda9c6cd220a77631"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": null
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "055d8d8888c9038f7525ebda9cab29f1c710ad0f8eeb83a5d78c9b4474133ee9"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": null
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/hostenv.py: '( read -r _ <&3; kill -INT' -> '( read -r _; kill -INT'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'interrupted' in",
        "observed_diagnostic": "assert 'interrupted' in",
        "before": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "0f4e850f15e4d911a3a68688828b37b21b32f98834b046abd2f6bedd0aa322b8"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-3",
      "acceptance": [
        "AC-STOP-3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_shutdown_stops_jobs_concurrently"
      ],
      "method": "Replaced concurrent stopper threads with sequential _terminate calls in a disposable copy; shutdown took 6.0s and the bound assertion failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-3.log",
        "sha256": "395daa39a8a2ec62b5383b4a1a114b1ef575d4b0350915be1ffb5ca3eaf7899b"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        }
      ],
      "scope_sha256": "8bbfb291c6b62adb8fda96bb9c4c9a7e196f5b61ac25b787f6424ffd310a286f",
      "red": {
        "mutation": "src/netdeck/runner.py: '        for thread in stoppers:\\n            thread.start()\\n' -> '        for job in running:\\n            self._terminate(job, grace)\\n        stoppers = []\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "shutdown took",
        "observed_diagnostic": "shutdown took 6.0s",
        "before": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "d671dd5738157251d4eaf25cc24b9411e01b2e8184995ae946713bd426690061"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-SERVER-1",
      "acceptance": [
        "AC-EXIT-3",
        "AC-STREAM-1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py"
      ],
      "method": "Ran the server suite with PYTHONPATH=src against real in-process servers: /api/shutdown refused without cookie (401), without X-NetDeck (403) and with a foreign Origin (403) while the server kept serving; a silent job stream and the stats stream each received event: bye and closed within 2 s of shutdown; 16 tests collected and passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/behavior/server.log",
        "sha256": "39cf8c38e616a6111a5a45842ef640b29dfb6e5381b5ba431cd030e884857be8"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": null,
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-3",
      "acceptance": [
        "AC-EXIT-3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_shutdown_refuses_unauthenticated_or_cross_origin"
      ],
      "method": "Removed the X-NetDeck header guard from _same_origin in a disposable copy; the header-less shutdown was accepted (202) and the refusal test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-3.log",
        "sha256": "62d97b83c49e76fff9945298449bc39ee9112ae3d705677caaa444daa45d5bb1"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: '        if self.headers.get(\"X-NetDeck\") != \"1\":\\n            return False\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 202 in (401, 403)",
        "observed_diagnostic": "assert 202 in (401, 403)",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "e3758272d8d8f0c174d251123943d4910ae2b03c95d76c4622b671ee21b6da0b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STREAM-1a",
      "acceptance": [
        "AC-STREAM-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_streams_say_bye_and_close_on_shutdown"
      ],
      "method": "Removed the shutdown condition from the job-stream wait predicate in a disposable copy; the silent job stream missed the 2 s bye and the test failed; original restored and green. (An earlier version of this test survived this mutation because its job printed every second; the fixture was changed to a silent job.)",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-1a.log",
        "sha256": "3c94a554ffc00877102b0c6b793af00360ae7d0d822da5e16a577a0fbc7a36a0"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: 'lambda seen=rev: job.rev != seen or self.app.shutdown.is_set(), timeout=15)' -> 'lambda seen=rev: job.rev != seen, timeout=15)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert b'event: bye' in",
        "observed_diagnostic": "assert b'event: bye' in",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "28eb92a30ccee0ce2ef7df252a4894a5b25e806424d38ac3b281d744d683ab8b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STREAM-1b",
      "acceptance": [
        "AC-STREAM-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_streams_say_bye_and_close_on_shutdown"
      ],
      "method": "Removed the stats-stream bye event in a disposable copy; the stats stream closed without bye and the test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-1b.log",
        "sha256": "f6171ebb60d7d31e4c9ead67330a0a516f28bdfdd4daf39bcc0a09cb058148ec"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: '            self._stats_loop()\\n            self._sse(\"bye\", {\"reason\": \"shutdown\"})\\n' -> '            self._stats_loop()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert b'event: bye' in",
        "observed_diagnostic": "assert b'event: bye' in",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "285ccbd0aeb5b3e82fb24f98adfce78ca2521c11c8aed4e1106c2ee1e3c97a32"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-CLI-1",
      "acceptance": [
        "AC-STOP-1",
        "AC-INST-1",
        "AC-INST-2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py"
      ],
      "method": "Ran real python -m netdeck serve processes in isolated XDG runtime/config dirs with a continuous ping job (unique packet size, asserted running first) and stopped each via POST /api/shutdown, netdeck stop and SIGINT: exit 0, no ping process left, instance.json removed, netdeck stop returned only after exit; stale instance.json with a dead pid was removed; 5 tests collected and passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/behavior/cli.log",
        "sha256": "e667e10f1adfa9cf89909c966b443c763eca0e506662f9f4ac3d278875fff0bd"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": null,
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-1",
      "acceptance": [
        "AC-STOP-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up"
      ],
      "method": "Removed jobs.shutdown() from App.close in a disposable copy; the ping process outlived the server on every path and the test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-1.log",
        "sha256": "685c6a0d91659ff6ab3988ebbbd31db59dbd074cba5eeb83a7c6ce8c5d20b023"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/server.py: '        self.request_shutdown(\"server closing\")\\n        self.jobs.shutdown()\\n' -> '        self.request_shutdown(\"server closing\")\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "the ping job outlived NetDeck",
        "observed_diagnostic": "the ping job outlived NetDeck",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "ace5d9ab10a3913532952235078143f965698be0c3b133100fe2c230e42b307d"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-INST-1",
      "acceptance": [
        "AC-INST-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up"
      ],
      "method": "Removed remove_instance() from the serve cleanup in a disposable copy; instance.json remained and the test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-1.log",
        "sha256": "73670fb347df314f4750cfb4c1ff9f4e8339f42008e42d586a31e4d42a316bd8"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '        server.server_close()\\n        remove_instance()\\n' -> '        server.server_close()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "instance.json was left behind",
        "observed_diagnostic": "instance.json was left behind",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "67afa10ff3af2d6f5af447aecad38ad68041ce7da0b2f9e084b55787ec52f04b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-INST-2a",
      "acceptance": [
        "AC-INST-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up[netdeck-stop]"
      ],
      "method": "Made netdeck stop report success without waiting for the process in a disposable copy (the original defect); the test failed because the server was still running; repeated 3 times, failed each time; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-2a.log",
        "sha256": "bad465d1462983281720827f0de7fc3a3798df1a11daf38da718e51e1d1ef6cc"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '    while time.monotonic() < deadline:\\n        if not process_alive(pid):\\n' -> '    while time.monotonic() < deadline:\\n        if True:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "netdeck stop returned before the server exited",
        "observed_diagnostic": "netdeck stop returned before the server exited",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "d9462d768fe7c995cb538febccdc24a4d11b29c1522280e4037a1fa9fc1c321b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-INST-2b",
      "acceptance": [
        "AC-INST-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_stop_removes_a_stale_instance_file"
      ],
      "method": "Removed stale instance-file deletion from read_instance in a disposable copy; the stale-file test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-2b.log",
        "sha256": "2c846603b55f3e6b9efc37f918dbc23f5e0d97b8459c8ae114f08158334acdc3"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "83d1ae89911993b8c28dde769f96d9b443bd1df362d372df605bb75c6047dad6"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '        with contextlib.suppress(OSError):\\n            os.unlink(instance_file())\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "stale instance.json was not removed",
        "observed_diagnostic": "stale instance.json was not removed",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "26e7624f5e84f525c78e4a914924ddb1d9875dd79ab55e7c619aba8c02970099"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-UI-1",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-STREAM-2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py"
      ],
      "method": "Ran with NETDECK_REQUIRE_E2E=1 and PYTHONPATH=src: headless Chrome 154 over CDP against a real python -m netdeck serve process. Exit dialog opened and listed the running Ping; Cancel and Escape closed it with the server still answering /api/ping; Confirm showed the stopped screen and the server exited 0 within 10 s; SIGINT from outside showed the NetDeck was stopped screen; no page exceptions. 2 tests collected and passed, none skipped.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/behavior/ui.log",
        "sha256": "97dc2ee29b9a997cb79b299d751d21343c8a9cdc62935cf90bc1be936834f65e"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "c869230bde79f54f370c5ed902665d3080f41954b8550d9b2018a179273221f3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "SECURITY.md",
          "sha256": "da4a8aef76bf94ad294a71fa0d8e5d39f6c36d3e7fa004896d22e1efa857c379"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "a57e00740086039a86d0256526560c0614dcaa287c59fb71ccd4185418d38482"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-1",
      "acceptance": [
        "AC-EXIT-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_exit_dialog_cancel_keeps_running_then_confirm_stops"
      ],
      "method": "Removed the POST /api/shutdown call from exitNetDeck in a disposable copy; the page claimed it stopped but the server kept running and the browser test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-1.log",
        "sha256": "1b48c59da3d5b2a6cd8cec9a2293125113e3988978bbd43afa579f1183d0d1f4"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "c869230bde79f54f370c5ed902665d3080f41954b8550d9b2018a179273221f3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "SECURITY.md",
          "sha256": "da4a8aef76bf94ad294a71fa0d8e5d39f6c36d3e7fa004896d22e1efa857c379"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "a57e00740086039a86d0256526560c0614dcaa287c59fb71ccd4185418d38482"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/static/app.js: '      await api(\"/api/shutdown\", { method: \"POST\" });\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "server still running 10 s after Exit",
        "observed_diagnostic": "server still running 10 s after Exit",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "cd708cdb59d44a4daefe57cff743d2210c8e2c9075211bea1c3ef8896459cd9a"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-1api",
      "acceptance": [
        "AC-EXIT-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_shutdown_endpoint_stops_the_server"
      ],
      "method": "Made the shutdown endpoint answer 202 without requesting shutdown in a disposable copy; the API-level test failed because the serve loop kept running; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-1api.log",
        "sha256": "544f537d51823a61c3751d8307d771ba5d84e9865a347951172257e64f22b56c"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "c869230bde79f54f370c5ed902665d3080f41954b8550d9b2018a179273221f3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "SECURITY.md",
          "sha256": "da4a8aef76bf94ad294a71fa0d8e5d39f6c36d3e7fa004896d22e1efa857c379"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "a57e00740086039a86d0256526560c0614dcaa287c59fb71ccd4185418d38482"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/server.py: '        self.app.request_shutdown(\"exit requested from the dashboard\")\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "serve_forever is still running",
        "observed_diagnostic": "serve_forever is still running",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "8e38fe0cfd13ef802d7a2e19ce63cf40782b4214ffb0fd1184709461526ff112"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-2",
      "acceptance": [
        "AC-EXIT-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_exit_dialog_cancel_keeps_running_then_confirm_stops"
      ],
      "method": "Made the dialog close handler exit regardless of the chosen button in a disposable copy; Cancel shut the server down and the browser test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-2.log",
        "sha256": "3756248624c5e0652a5dbe966544f156c399ef165a34ac6c700e55d2b833d49d"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "036677321ce32a61f6baf556c1aafaec79ead552991537da8ff2c465c081be46",
      "red": {
        "mutation": "src/netdeck/static/app.js: '      if ($(\"#exit-dialog\").returnValue === \"exit\") exitNetDeck();\\n' -> '      exitNetDeck();\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "server exited after Cancel",
        "observed_diagnostic": "server exited after Cancel",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "86c769d101a186f18ef223718a9e10a11c66b28ad503a4a355d057af522a8c48"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STREAM-2",
      "acceptance": [
        "AC-STREAM-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_stopped_screen_when_server_is_stopped_from_terminal"
      ],
      "method": "Made showStopped ignore server-initiated stops in a disposable copy; after SIGINT the page never showed the stopped screen and the browser test failed; original restored and green.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-2.log",
        "sha256": "eeddfd44a0f3a6241f97ecd70fb417d54e5528118348979000fe9b77255dd13b"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "b5b7d5522ffbee99baefddeb3e52f311dd0ae1dc7abcd12ffc88dff311a7dd88"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "036677321ce32a61f6baf556c1aafaec79ead552991537da8ff2c465c081be46",
      "red": {
        "mutation": "src/netdeck/static/app.js: '    if (S.stopped) return;\\n    S.stopped = true;\\n' -> '    if (S.stopped || reason === \"server\") return;\\n    S.stopped = true;\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "stopped screen not shown after Ctrl+C",
        "observed_diagnostic": "stopped screen not shown after Ctrl+C",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "a0431ae894c9f1c64faecf4461f6433342c59b67847f4102fecdedb2d95cef9a"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": "Bound inputs changed later in this work unit (subsequent task edits and docs); superseded by the closure re-run receipts ending in -F. Next action: none; kept as history."
    },
    {
      "id": "EV-READY-2",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-EXIT-3",
        "AC-STOP-1",
        "AC-STOP-2",
        "AC-STOP-3",
        "AC-STREAM-1",
        "AC-STREAM-2",
        "AC-INST-1",
        "AC-INST-2"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Closure re-review of changed readiness inputs (README brief usage section, pyproject dev extra); requirements, acceptance and non-goals unchanged; implementation-time test refinements and the open CI outcome recorded.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/readiness-r2.md",
        "sha256": "497d478a830e0571d2812f9b79bd597a45d54521eb1cfaa83ed604a93d43b297"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-BEH-RUNNER-F",
      "acceptance": [
        "AC-STOP-2",
        "AC-STOP-3"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py"
      ],
      "method": "Closure re-run against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 9 tests: unsignalable polkit-mode job stopped via supervisor (stop and shutdown), three SIGINT-ignoring jobs stopped concurrently. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_runner.log",
        "sha256": "04f00802c35ad463411e47e3d89b9754cf5cc69d661e4515d28cd617e09cd7a2"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-SERVER-F",
      "acceptance": [
        "AC-EXIT-3",
        "AC-STREAM-1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py"
      ],
      "method": "Closure re-run against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 16 tests: shutdown refused without cookie/header/same origin while serving continued; silent job stream and stats stream got bye and closed within 2 s. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_server.log",
        "sha256": "1249db952cc5d5bd4d879793c3476bc2771c596a27bc029987f99f0975d005ff"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": null,
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-CLI-F",
      "acceptance": [
        "AC-STOP-1",
        "AC-INST-1",
        "AC-INST-2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py"
      ],
      "method": "Closure re-run against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 5 tests: real servers stopped via API, netdeck stop and SIGINT with a running ping: exit 0, no ping left, instance.json removed, stop waited for exit; stale instance file removed. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_cli.log",
        "sha256": "f469fd1ba5ea38e8a6ff9c2dfd9295db42112899fc4659d9ab4452740744bd72"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": null,
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-UI-F",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-STREAM-2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py"
      ],
      "method": "Closure re-run against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 2 tests in headless Chrome 154 with NETDECK_REQUIRE_E2E=1: Cancel/Escape kept the server running, Confirm showed the stopped screen and the server exited 0; SIGINT showed the stopped screen; no page exceptions. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_ui_e2e.log",
        "sha256": "f122366a7c85eb4af2baf75f1eea1132dd372512bfeea35c9d435e4bef006416"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-1-F",
      "acceptance": [
        "AC-EXIT-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_exit_dialog_cancel_keeps_running_then_confirm_stops"
      ],
      "method": "Closure re-run: Removed the POST /api/shutdown call from exitNetDeck in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-1.log",
        "sha256": "0f6a21015dec9cfec0be71aa761cc2493a1fdfdb1fc576c8ec8cea9a01026c80"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/static/app.js: '      await api(\"/api/shutdown\", { method: \"POST\" });\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "server still running 10 s after Exit",
        "observed_diagnostic": "server still running 10 s after Exit",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "cd708cdb59d44a4daefe57cff743d2210c8e2c9075211bea1c3ef8896459cd9a"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-1api-F",
      "acceptance": [
        "AC-EXIT-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_shutdown_endpoint_stops_the_server"
      ],
      "method": "Closure re-run: Made the shutdown endpoint answer 202 without requesting shutdown in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-1api.log",
        "sha256": "5de3343d3128aab12ee6c4721ebf5aa2431124b9c73ae2fe391bdbb48cdd46b8"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/server.py: '        self.app.request_shutdown(\"exit requested from the dashboard\")\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "serve_forever is still running",
        "observed_diagnostic": "serve_forever is still running",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "8e38fe0cfd13ef802d7a2e19ce63cf40782b4214ffb0fd1184709461526ff112"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-2-F",
      "acceptance": [
        "AC-EXIT-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_exit_dialog_cancel_keeps_running_then_confirm_stops"
      ],
      "method": "Closure re-run: Made the dialog close handler exit regardless of the chosen button in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-2.log",
        "sha256": "26136e2ada0c1e69b6650757f5ae2fc6802594e8fcf239c61d158d3fddd03288"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "036677321ce32a61f6baf556c1aafaec79ead552991537da8ff2c465c081be46",
      "red": {
        "mutation": "src/netdeck/static/app.js: '      if ($(\"#exit-dialog\").returnValue === \"exit\") exitNetDeck();\\n' -> '      exitNetDeck();\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "server exited after Cancel",
        "observed_diagnostic": "server exited after Cancel",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "86c769d101a186f18ef223718a9e10a11c66b28ad503a4a355d057af522a8c48"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-EXIT-3-F",
      "acceptance": [
        "AC-EXIT-3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_shutdown_refuses_unauthenticated_or_cross_origin"
      ],
      "method": "Closure re-run: Removed the X-NetDeck header guard from _same_origin in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-3.log",
        "sha256": "0dced1eb6efb1db96d373d01729a8fa93fed6b7d9572c3bb5c2747796163df68"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: '        if self.headers.get(\"X-NetDeck\") != \"1\":\\n            return False\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 202 in (401, 403)",
        "observed_diagnostic": "assert 202 in (401, 403)",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "e3758272d8d8f0c174d251123943d4910ae2b03c95d76c4622b671ee21b6da0b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-INST-1-F",
      "acceptance": [
        "AC-INST-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up"
      ],
      "method": "Closure re-run: Removed remove_instance() from the serve cleanup in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-1.log",
        "sha256": "dd3595ce70f4e9295d61067d6335935c92e80001c6b96c29d4be0116427d6b97"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '        server.server_close()\\n        remove_instance()\\n' -> '        server.server_close()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "instance.json was left behind",
        "observed_diagnostic": "instance.json was left behind",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "67afa10ff3af2d6f5af447aecad38ad68041ce7da0b2f9e084b55787ec52f04b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-INST-2a-F",
      "acceptance": [
        "AC-INST-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up[netdeck-stop]"
      ],
      "method": "Closure re-run: Made netdeck stop report success without waiting (the original defect) in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-2a.log",
        "sha256": "2e6efa38970855f453b92dd01976cf88da5eabc4fbaccbc73079d8d5392fc7f3"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '    while time.monotonic() < deadline:\\n        if not process_alive(pid):\\n' -> '    while time.monotonic() < deadline:\\n        if True:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "netdeck stop returned before the server exited",
        "observed_diagnostic": "netdeck stop returned before the server exited",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "d9462d768fe7c995cb538febccdc24a4d11b29c1522280e4037a1fa9fc1c321b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-INST-2b-F",
      "acceptance": [
        "AC-INST-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_stop_removes_a_stale_instance_file"
      ],
      "method": "Closure re-run: Removed stale instance-file deletion from read_instance in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-2b.log",
        "sha256": "bc591c570298a60459bb290ce816d6ff1220fac0e0718599f731addde47114cc"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '        with contextlib.suppress(OSError):\\n            os.unlink(instance_file())\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "stale instance.json was not removed",
        "observed_diagnostic": "stale instance.json was not removed",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "26e7624f5e84f525c78e4a914924ddb1d9875dd79ab55e7c619aba8c02970099"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-1-F",
      "acceptance": [
        "AC-STOP-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up"
      ],
      "method": "Closure re-run: Removed jobs.shutdown() from App.close in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-1.log",
        "sha256": "eaa8310d31db9da18e40a8d040c8f822fe6b57001a2297d8dcd3a8528cb0ccbc"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/server.py: '        self.request_shutdown(\"server closing\")\\n        self.jobs.shutdown()\\n' -> '        self.request_shutdown(\"server closing\")\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "the ping job outlived NetDeck",
        "observed_diagnostic": "the ping job outlived NetDeck",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "ace5d9ab10a3913532952235078143f965698be0c3b133100fe2c230e42b307d"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-2a-F",
      "acceptance": [
        "AC-STOP-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_unsignalable_elevated_job_is_stopped_through_supervisor"
      ],
      "method": "Closure re-run: Removed the stdin close from the supervised branch of _terminate in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-2a.log",
        "sha256": "52b4c8430cef57bee75bd9bf212048ae806dfba30be7597bcaa3c13380a8af02"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/runner.py: '            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.\\n            _close_quietly(proc.stdin)\\n' -> '            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'running' == 'stopped'",
        "observed_diagnostic": "assert 'running' == 'stopped'",
        "before": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "bbe7557f11d9ab7cf5df5060bdf5e1cadabf6226bc65b244ed59571bf875a67c"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-2b-F",
      "acceptance": [
        "AC-STOP-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_unsignalable_elevated_job_is_stopped_through_supervisor"
      ],
      "method": "Closure re-run: Made the supervisor watcher read the background /dev/null stdin instead of fd 3 in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-2b.log",
        "sha256": "49127a20edcac803ef66ffa5c676af1c42aca4b6173c4952a7f5f4fe15a7fc7f"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/hostenv.py: '( read -r _ <&3; kill -INT' -> '( read -r _; kill -INT'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'interrupted' in",
        "observed_diagnostic": "assert 'interrupted' in",
        "before": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "0f4e850f15e4d911a3a68688828b37b21b32f98834b046abd2f6bedd0aa322b8"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STOP-3-F",
      "acceptance": [
        "AC-STOP-3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_shutdown_stops_jobs_concurrently"
      ],
      "method": "Closure re-run: Replaced concurrent stoppers with sequential _terminate calls in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-3.log",
        "sha256": "fe86340aa28f1819df5713c8fcb0904832f21fee3a9db6b6451c298bd5da7f93"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        }
      ],
      "scope_sha256": "8bbfb291c6b62adb8fda96bb9c4c9a7e196f5b61ac25b787f6424ffd310a286f",
      "red": {
        "mutation": "src/netdeck/runner.py: '        for thread in stoppers:\\n            thread.start()\\n' -> '        for job in running:\\n            self._terminate(job, grace)\\n        stoppers = []\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "shutdown took",
        "observed_diagnostic": "shutdown took 6.0s",
        "before": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "d671dd5738157251d4eaf25cc24b9411e01b2e8184995ae946713bd426690061"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STREAM-1a-F",
      "acceptance": [
        "AC-STREAM-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_streams_say_bye_and_close_on_shutdown"
      ],
      "method": "Closure re-run: Removed the shutdown condition from the job-stream wait predicate in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-1a.log",
        "sha256": "5bde9feea5fcf27d4bd22cd054786dd57b52889f3b1fa6f6b68abc0b7e90d879"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: 'lambda seen=rev: job.rev != seen or self.app.shutdown.is_set(), timeout=15)' -> 'lambda seen=rev: job.rev != seen, timeout=15)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert b'event: bye' in",
        "observed_diagnostic": "assert b'event: bye' in",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "28eb92a30ccee0ce2ef7df252a4894a5b25e806424d38ac3b281d744d683ab8b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STREAM-1b-F",
      "acceptance": [
        "AC-STREAM-1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_streams_say_bye_and_close_on_shutdown"
      ],
      "method": "Closure re-run: Removed the stats-stream bye event in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-1b.log",
        "sha256": "f632d366e2b449f824d9605493c28a7fc093582ef8c9ed4a2a24059723a38813"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: '            self._stats_loop()\\n            self._sse(\"bye\", {\"reason\": \"shutdown\"})\\n' -> '            self._stats_loop()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert b'event: bye' in",
        "observed_diagnostic": "assert b'event: bye' in",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "285ccbd0aeb5b3e82fb24f98adfce78ca2521c11c8aed4e1106c2ee1e3c97a32"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-RED-STREAM-2-F",
      "acceptance": [
        "AC-STREAM-2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_stopped_screen_when_server_is_stopped_from_terminal"
      ],
      "method": "Closure re-run: Made showStopped ignore server-initiated stops in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-2.log",
        "sha256": "9e8b9feb8e5e0a8ccfd86f2badac2222ba77abe22828adac5a1adaf5be981246"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "62b79c5fdf93d84e2761adb041fbd93252ce73492574f71bef0946e17843c68c"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "4e2f4c3c636a24e4f2c44dadaf76ed339f14f7c37ac176e9cd3c571324d94bda"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "036677321ce32a61f6baf556c1aafaec79ead552991537da8ff2c465c081be46",
      "red": {
        "mutation": "src/netdeck/static/app.js: '    if (S.stopped) return;\\n    S.stopped = true;\\n' -> '    if (S.stopped || reason === \"server\") return;\\n    S.stopped = true;\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "stopped screen not shown after Ctrl+C",
        "observed_diagnostic": "stopped screen not shown after Ctrl+C",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "a0431ae894c9f1c64faecf4461f6433342c59b67847f4102fecdedb2d95cef9a"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": "runner.py and server.py changed by the job-snapshot race fix found in semantic review; superseded by the -G receipts. Next action: none; kept as history."
    },
    {
      "id": "EV-BEH-RUNNER-G",
      "acceptance": [
        "AC-STOP-2",
        "AC-STOP-3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py"
      ],
      "method": "Final re-run after the job-snapshot race fix against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 9 tests: unsignalable polkit-mode job stopped via supervisor (stop and shutdown), three SIGINT-ignoring jobs stopped concurrently. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_runner.log",
        "sha256": "6a4dbd8082508da9b397e4f6db9b0474da71caf065983738d2edef865573edb7"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-BEH-SERVER-G",
      "acceptance": [
        "AC-EXIT-3",
        "AC-STREAM-1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py"
      ],
      "method": "Final re-run after the job-snapshot race fix against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 16 tests: shutdown refused without cookie/header/same origin while serving continued; silent job stream and stats stream got bye and closed within 2 s. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_server.log",
        "sha256": "1249db952cc5d5bd4d879793c3476bc2771c596a27bc029987f99f0975d005ff"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-BEH-CLI-G",
      "acceptance": [
        "AC-STOP-1",
        "AC-INST-1",
        "AC-INST-2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py"
      ],
      "method": "Final re-run after the job-snapshot race fix against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 5 tests: real servers stopped via API, netdeck stop and SIGINT with a running ping: exit 0, no ping left, instance.json removed, stop waited for exit; stale instance file removed. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_cli.log",
        "sha256": "ac89e204f2b23fec900364bf0b45676bdc603b85e436bc99f534d3f2e331a98d"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-BEH-UI-G",
      "acceptance": [
        "AC-EXIT-1",
        "AC-EXIT-2",
        "AC-STREAM-2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python3",
        "-m",
        "pytest",
        "-v",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py"
      ],
      "method": "Final re-run after the job-snapshot race fix against the final source with PYTHONPATH=src and NETDECK_REQUIRE_E2E=1: 2 tests in headless Chrome 154 with NETDECK_REQUIRE_E2E=1: Cancel/Escape kept the server running, Confirm showed the stopped screen and the server exited 0; SIGINT showed the stopped screen; no page exceptions. All collected tests passed; full suite 131 passed and make lint passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/final/test_ui_e2e.log",
        "sha256": "480caac87d396f5dfcfe6615f68e9d9739f913ad5b9a332af2ce2b934fc1e9bd"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-RED-EXIT-1-G",
      "acceptance": [
        "AC-EXIT-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_exit_dialog_cancel_keeps_running_then_confirm_stops"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed the POST /api/shutdown call from exitNetDeck in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-1.log",
        "sha256": "8205921dc30f7a49e8549f6905956a19108a9e0f59acb03b40d0d140c3d131c6"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/static/app.js: '      await api(\"/api/shutdown\", { method: \"POST\" });\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "server still running 10 s after Exit",
        "observed_diagnostic": "server still running 10 s after Exit",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "cd708cdb59d44a4daefe57cff743d2210c8e2c9075211bea1c3ef8896459cd9a"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-EXIT-1api-G",
      "acceptance": [
        "AC-EXIT-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_shutdown_endpoint_stops_the_server"
      ],
      "method": "Final re-run after the job-snapshot race fix: Made the shutdown endpoint answer 202 without requesting shutdown in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-1api.log",
        "sha256": "0a63ca5cdea5a8803512daaf92a874ace79bdd06865d7b0bc0c4b757232dda3e"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/server.py: '        self.app.request_shutdown(\"exit requested from the dashboard\")\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "serve_forever is still running",
        "observed_diagnostic": "serve_forever is still running",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "0489f9632ddde7e3d65f22c14133d536a33198430da508a13919244346fb72f7"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-EXIT-2-G",
      "acceptance": [
        "AC-EXIT-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_exit_dialog_cancel_keeps_running_then_confirm_stops"
      ],
      "method": "Final re-run after the job-snapshot race fix: Made the dialog close handler exit regardless of the chosen button in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-2.log",
        "sha256": "c2cb606c4f45c95124b701f1f44331cca7230877be1d536d8d90aad5a17e1247"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "036677321ce32a61f6baf556c1aafaec79ead552991537da8ff2c465c081be46",
      "red": {
        "mutation": "src/netdeck/static/app.js: '      if ($(\"#exit-dialog\").returnValue === \"exit\") exitNetDeck();\\n' -> '      exitNetDeck();\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "server exited after Cancel",
        "observed_diagnostic": "server exited after Cancel",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "86c769d101a186f18ef223718a9e10a11c66b28ad503a4a355d057af522a8c48"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-EXIT-3-G",
      "acceptance": [
        "AC-EXIT-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_shutdown_refuses_unauthenticated_or_cross_origin"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed the X-NetDeck header guard from _same_origin in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-EXIT-3.log",
        "sha256": "7c5fdad805b9fdcb1ae6afdacfa6fbedffbf5b4485f225e396f7864c13131fcb"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: '        if self.headers.get(\"X-NetDeck\") != \"1\":\\n            return False\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 202 in (401, 403)",
        "observed_diagnostic": "assert 202 in (401, 403)",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "e3178b845edb51a7990c6577474b876509c0de7144f98ad2a1ae9fe04f1c2e19"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-INST-1-G",
      "acceptance": [
        "AC-INST-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed remove_instance() from the serve cleanup in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-1.log",
        "sha256": "578da883e491d0f1563fc63cd56f4a75c11fb4dc71ca58340beceb99e1eb55f6"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '        server.server_close()\\n        remove_instance()\\n' -> '        server.server_close()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "instance.json was left behind",
        "observed_diagnostic": "instance.json was left behind",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "67afa10ff3af2d6f5af447aecad38ad68041ce7da0b2f9e084b55787ec52f04b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-INST-2a-G",
      "acceptance": [
        "AC-INST-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up[netdeck-stop]"
      ],
      "method": "Final re-run after the job-snapshot race fix: Made netdeck stop report success without waiting (the original defect) in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-2a.log",
        "sha256": "6909db6ae17afe071d3261ca8a2d563076781ee75ffb0db224e53986f6dc8b28"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '    while time.monotonic() < deadline:\\n        if not process_alive(pid):\\n' -> '    while time.monotonic() < deadline:\\n        if True:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "netdeck stop returned before the server exited",
        "observed_diagnostic": "netdeck stop returned before the server exited",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "d9462d768fe7c995cb538febccdc24a4d11b29c1522280e4037a1fa9fc1c321b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-INST-2b-G",
      "acceptance": [
        "AC-INST-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_stop_removes_a_stale_instance_file"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed stale instance-file deletion from read_instance in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-INST-2b.log",
        "sha256": "82e3be5cb9f20f59b10fbc41f347dc4248153043d8224072da09117ff7a93771"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/cli.py: '        with contextlib.suppress(OSError):\\n            os.unlink(instance_file())\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "stale instance.json was not removed",
        "observed_diagnostic": "stale instance.json was not removed",
        "before": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "26e7624f5e84f525c78e4a914924ddb1d9875dd79ab55e7c619aba8c02970099"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/cli.py",
            "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STOP-1-G",
      "acceptance": [
        "AC-STOP-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_every_shutdown_path_stops_jobs_and_cleans_up"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed jobs.shutdown() from App.close in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-1.log",
        "sha256": "7513fa070afe9d523c889bd2de3f76680551f42382d759b9644113fc79c653bb"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "1c5215964fd8b5ec6fea16cfb51864ba95578e38dc48e8b914a6910e0b8864ff",
      "red": {
        "mutation": "src/netdeck/server.py: '        self.request_shutdown(\"server closing\")\\n        self.jobs.shutdown()\\n' -> '        self.request_shutdown(\"server closing\")\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "the ping job outlived NetDeck",
        "observed_diagnostic": "the ping job outlived NetDeck",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "1146053da0afa354aea8ed0123ebb4262a01456abf9e51eb1e34440b09a42682"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STOP-2a-G",
      "acceptance": [
        "AC-STOP-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_unsignalable_elevated_job_is_stopped_through_supervisor"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed the stdin close from the supervised branch of _terminate in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-2a.log",
        "sha256": "06d804a9e53e9400e025fbf40d7c8bdce1b440f0a9c5801e40afc1d04c13211b"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/runner.py: '            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.\\n            _close_quietly(proc.stdin)\\n' -> '            # Supervised elevated child: the root-side supervisor runs the INT/TERM/KILL ladder.\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'running' == 'stopped'",
        "observed_diagnostic": "assert 'running' == 'stopped'",
        "before": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "23b7e2913cd7d52620492241536ad39ed56f88012fc4d6ea1391c0ba831e5899"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STOP-2b-G",
      "acceptance": [
        "AC-STOP-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_unsignalable_elevated_job_is_stopped_through_supervisor"
      ],
      "method": "Final re-run after the job-snapshot race fix: Made the supervisor watcher read the background /dev/null stdin instead of fd 3 in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-2b.log",
        "sha256": "356eaf467c2563ee06153936fb81c7224321eb9b5ac090c78f4e9a1978a9d884"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "SECURITY.md",
          "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
        },
        {
          "path": "docs/PRIVILEGES.md",
          "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
      "red": {
        "mutation": "src/netdeck/hostenv.py: '( read -r _ <&3; kill -INT' -> '( read -r _; kill -INT'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'interrupted' in",
        "observed_diagnostic": "assert 'interrupted' in",
        "before": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "0f4e850f15e4d911a3a68688828b37b21b32f98834b046abd2f6bedd0aa322b8"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/hostenv.py",
            "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STOP-3-G",
      "acceptance": [
        "AC-STOP-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_runner.py::test_shutdown_stops_jobs_concurrently"
      ],
      "method": "Final re-run after the job-snapshot race fix: Replaced concurrent stoppers with sequential _terminate calls in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STOP-3.log",
        "sha256": "bc170a651a7dd4a4a3e3dd014c3e9656e237491e4db3146611f7a8fd2443b4f2"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        }
      ],
      "scope_sha256": "8bbfb291c6b62adb8fda96bb9c4c9a7e196f5b61ac25b787f6424ffd310a286f",
      "red": {
        "mutation": "src/netdeck/runner.py: '        for thread in stoppers:\\n            thread.start()\\n' -> '        for job in running:\\n            self._terminate(job, grace)\\n        stoppers = []\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "shutdown took",
        "observed_diagnostic": "shutdown took 6.0s",
        "before": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "5662c914e5c458348c4ad31655bf36abe91afdf45eb746fff63127482ad99473"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/runner.py",
            "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STREAM-1a-G",
      "acceptance": [
        "AC-STREAM-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_streams_say_bye_and_close_on_shutdown"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed the shutdown condition from the job-stream wait predicate in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-1a.log",
        "sha256": "66564bd1442b0f1175ebb8d76a8ebf37ec6ad53437e937a68b217155c1171ac2"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: 'lambda seen=rev: job.rev != seen or self.app.shutdown.is_set(), timeout=15)' -> 'lambda seen=rev: job.rev != seen, timeout=15)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert b'event: bye' in",
        "observed_diagnostic": "assert b'event: bye' in",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "e4769b430aa77b2440e51155e8356d3a1029fac676f09b248ace73e7067c3624"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STREAM-1b-G",
      "acceptance": [
        "AC-STREAM-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_server.py::test_streams_say_bye_and_close_on_shutdown"
      ],
      "method": "Final re-run after the job-snapshot race fix: Removed the stats-stream bye event in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-1b.log",
        "sha256": "76beea238a16225670a474192a689415aa2f4790bb6d1dd2810e87773c6fee35"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        }
      ],
      "scope_sha256": "dd2ad2c029a2e22528ea249572b8e6fbec3e4afa6a4fd286a22b2a98133bad42",
      "red": {
        "mutation": "src/netdeck/server.py: '            self._stats_loop()\\n            self._sse(\"bye\", {\"reason\": \"shutdown\"})\\n' -> '            self._stats_loop()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert b'event: bye' in",
        "observed_diagnostic": "assert b'event: bye' in",
        "before": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "5614528f6ce0f06c0a9929088a9c63c22b436cc23b177de7164f7780a375c153"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/server.py",
            "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-STREAM-2-G",
      "acceptance": [
        "AC-STREAM-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/usr/bin/python3",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_ui_e2e.py::test_stopped_screen_when_server_is_stopped_from_terminal"
      ],
      "method": "Final re-run after the job-snapshot race fix: Made showStopped ignore server-initiated stops in a disposable copy; the named test failed with the expected diagnostic; the original was byte-identical before/after and the test passed again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "node": "26.13.0",
          "shellcheck": "0.11.0",
          "google-chrome": "154.0.8037.97",
          "websocket-client": "1.9.2"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/exit-shutdown/reports/drills/RD-STREAM-2.log",
        "sha256": "01816462dd5eb6a95173ae8495149063e2b6289d5e91e35b943defbf9fbd0f2d"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/cli.py",
          "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
        },
        {
          "path": "src/netdeck/hostenv.py",
          "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
        },
        {
          "path": "src/netdeck/runner.py",
          "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
        },
        {
          "path": "src/netdeck/server.py",
          "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
        },
        {
          "path": "src/netdeck/static/app.css",
          "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
        },
        {
          "path": "src/netdeck/static/index.html",
          "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
        },
        {
          "path": "tests/test_runner.py",
          "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
        },
        {
          "path": "tests/test_server.py",
          "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
        },
        {
          "path": "tests/test_ui_e2e.py",
          "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
        }
      ],
      "scope_sha256": "036677321ce32a61f6baf556c1aafaec79ead552991537da8ff2c465c081be46",
      "red": {
        "mutation": "src/netdeck/static/app.js: '    if (S.stopped) return;\\n    S.stopped = true;\\n' -> '    if (S.stopped || reason === \"server\") return;\\n    S.stopped = true;\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "stopped screen not shown after Ctrl+C",
        "observed_diagnostic": "stopped screen not shown after Ctrl+C",
        "before": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "a0431ae894c9f1c64faecf4461f6433342c59b67847f4102fecdedb2d95cef9a"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/static/app.js",
            "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "f1b0f2e82815400d7c893357e369b3da22b033d6fb5b10799b3177184136e067",
    "inputs": [
      {
        "path": ".github/workflows/ci.yml",
        "sha256": "99023084a0e40d11e070a7617ac17f5f56f2cd612fce851b853a315043cdd4e3"
      },
      {
        "path": "CHANGELOG.md",
        "sha256": "01dc37ee908aaa0845d8090a0cb8c74e30e3d6653a7045ecccb6067b12a51628"
      },
      {
        "path": "CONTRIBUTING.md",
        "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
      },
      {
        "path": "README.md",
        "sha256": "7e2fd58a304625b18c2ced61788158b9d19ee72ccca488b92bf703213635019d"
      },
      {
        "path": "SECURITY.md",
        "sha256": "be35a91c802b6d8ccea50d4c2c2c013fa7885af44b99f5e99c3f1fdb20e7dc14"
      },
      {
        "path": "docs/PRIVILEGES.md",
        "sha256": "9b7d0177eaf74b6030ea9bc4e4ae6571a0cab7abd734b3e8e187cc0835196a2e"
      },
      {
        "path": "pyproject.toml",
        "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
      },
      {
        "path": "src/netdeck/cli.py",
        "sha256": "9143e494df07f31aabc1eb3a53f0e73cccb0a42eff01b7a864e8c3110f3f8135"
      },
      {
        "path": "src/netdeck/hostenv.py",
        "sha256": "afd1c5aa4f7c09afc74283c0fc32fcd78fe5070497c5b8d5f591442091018d00"
      },
      {
        "path": "src/netdeck/runner.py",
        "sha256": "c81b8f1d97f0d97777ff37e6c5a9d0f0cbd062533d2d51a6c6afe9114d0fe508"
      },
      {
        "path": "src/netdeck/server.py",
        "sha256": "2525de82950e2a85259c4e6396c0cf01995341bf31c49123633d140d32519452"
      },
      {
        "path": "src/netdeck/static/app.css",
        "sha256": "ae2ec03b7f5ed7851e53f24ae5da4f6df54d485849bc5fc542ff9be751940926"
      },
      {
        "path": "src/netdeck/static/app.js",
        "sha256": "43a476598ab2b1d7e18d52f163e42bac41c4f1d0a22227b12c2d657253eecdbb"
      },
      {
        "path": "src/netdeck/static/index.html",
        "sha256": "98d7a649019787078b1bf5bb84340a6307d2cef2ed6ad7ee28bef3855c434952"
      },
      {
        "path": "tests/test_cli.py",
        "sha256": "5460dcd8371cea7997ee04268533643cb0c86dbae3d7e7b2bdbb3bd55a9f4f4d"
      },
      {
        "path": "tests/test_runner.py",
        "sha256": "1f5f262cceea35928b9cd923d8c51d5a1ea2b09e8e789e913163702ea3f6f5ad"
      },
      {
        "path": "tests/test_server.py",
        "sha256": "0fbb1d65e4ce2999f1b00c1d5d3f7b5a48b2728c12c207a1e48746a6af6d6dca"
      },
      {
        "path": "tests/test_ui_e2e.py",
        "sha256": "26fd75808875f09fdb8a7213a755b66163620e2aa322e2b78148861db3123835"
      }
    ],
    "environment": {
      "platform": "linux",
      "tools": {
        "google-chrome": "154.0.8037.97",
        "node": "26.13.0",
        "pytest": "9.2.0",
        "python": "3.14.9",
        "ruff": "0.17.4",
        "shellcheck": "0.11.0",
        "websocket-client": "1.9.2"
      }
    },
    "verified_tasks": [
      "TASK-SUPERVISOR",
      "TASK-RUNNER",
      "TASK-SERVER",
      "TASK-CLI",
      "TASK-UI",
      "TASK-DOCS"
    ],
    "pending_operations": [
      {
        "id": "OP-CI-FIRST-RUN",
        "description": "The updated CI workflow (browser tests with NETDECK_REQUIRE_E2E=1 in the runner's Chrome, ping-based CLI tests) has not run on GitHub; the changes are not committed or pushed yet.",
        "next_action": "After the user approves commit and push, watch the CI run and record its outcome; if Chrome or ping is unavailable on the runner, fix the workflow rather than skipping the tests."
      }
    ],
    "next_action": "Ask the user to approve committing and pushing; then observe OP-CI-FIRST-RUN.",
    "source_revision": "f5cac27 + uncommitted WORK-EXIT-SHUTDOWN changes"
  }
}
```
