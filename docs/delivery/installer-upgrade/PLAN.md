# Delivery plan: upgrade-safe installer

## Rationale

Re-running `scripts/install.sh` replaces the virtualenv while a NetDeck started from that installation may still
be running. The running server keeps its old Python code in memory but reads the web UI from disk on every
request, so it serves a page that does not match it. This happened in practice: after the Exit-button release
the reinstalled UI showed Exit, the old server had no `/api/shutdown`, and Exit failed with "Not found".

**Approach.** The installer, which owns upgrades, detects a running NetDeck that belongs to *this* installation
before touching files, stops it, and starts the upgraded version afterwards. Ownership is decided from the
instance file through the installed copy's own `read_instance` and the process's `argv[0]` lying inside this
installation's virtualenv, so a NetDeck run from a source tree or another install is left alone. A
systemd user service (`--service` installs) is stopped and started through `systemctl --user` instead, so it
stays managed by systemd. The restart opens the app window only when a graphical session exists
(`--no-browser` otherwise), so headless upgrades never launch a console browser.

**Non-goals.** Upgrades through pip/pipx outside the installer are not intercepted. Stopping uses the installed
copy's `netdeck stop` and then waits for the process itself, because 1.0.0's `stop` did not wait.

**Test strategy.** `tests/test_install.py` runs the real installer twice into an isolated `$HOME` with its own
runtime directory and port, and a `systemctl` stub on `PATH` that records calls (CI runners have no user
systemd manager, and the user's own must not be touched by tests). It is opt-in through
`NETDECK_TEST_INSTALL=1` because each install builds a virtualenv; CI's install job runs it with that set.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "WORK-INSTALLER-UPGRADE",
    "title": "Upgrade-safe installer",
    "scope_revision": 1,
    "brief": "README.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "CONTRIBUTING.md",
        "revision": "46866a0"
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
        "shellcheck": "0.11.0",
        "bash": "5.3.20"
      }
    }
  },
  "requirements": [
    {
      "id": "REQ-UPG",
      "statement": "Re-running the installer while NetDeck from that installation is running stops it before replacing files and starts the upgraded version afterwards; other NetDeck processes are left alone and a systemd-managed NetDeck stays managed by systemd.",
      "priority": "critical",
      "acceptance": [
        "AC-UPG-1",
        "AC-UPG-2",
        "AC-UPG-3",
        "AC-UPG-4"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-UPG-1",
      "requirement": "REQ-UPG",
      "given": "NetDeck started from the installed copy is running and no graphical session is present",
      "when": "install.sh runs again",
      "then": "It exits 0, the old process is gone, and a new instance answers whose process started after the new files were written and was started with --no-browser",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-UPG-2",
      "requirement": "REQ-UPG",
      "given": "No NetDeck is running",
      "when": "install.sh runs again",
      "then": "No NetDeck instance is started",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-UPG-3",
      "requirement": "REQ-UPG",
      "given": "A NetDeck started from a source tree (not this installation) is running with the same runtime directory",
      "when": "install.sh runs",
      "then": "That process keeps running and remains the registered instance",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-UPG-4",
      "requirement": "REQ-UPG",
      "given": "The netdeck user service is active",
      "when": "install.sh runs",
      "then": "systemctl --user stops the service before files are replaced and starts it afterwards, and no separate instance is started",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "TASK-UPG-INSTALLER",
      "purpose": "Stop an owned running NetDeck (or the user service) before installing and restart it afterwards; cover it with an opt-in installer test run in CI",
      "acceptance": [
        "AC-UPG-1",
        "AC-UPG-2",
        "AC-UPG-3",
        "AC-UPG-4"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "scripts/install.sh",
          "action": "modify"
        },
        {
          "path": "tests/test_install.py",
          "action": "create"
        },
        {
          "path": ".github/workflows/ci.yml",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-UPG-BEH-1",
        "EV-RD-UPG-1",
        "EV-RD-UPG-1b",
        "EV-RD-UPG-2",
        "EV-RD-UPG-3",
        "EV-RD-UPG-4"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-UPG-DOCS",
      "purpose": "Document upgrade behavior from shipped behavior",
      "acceptance": [
        "AC-UPG-1",
        "AC-UPG-4"
      ],
      "depends_on": [
        "TASK-UPG-INSTALLER"
      ],
      "changes": [
        {
          "path": "README.md",
          "action": "modify"
        },
        {
          "path": "CHANGELOG.md",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-UPG-BEH-1",
        "EV-RD-UPG-1",
        "EV-RD-UPG-1b",
        "EV-RD-UPG-4"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-UPG-READY-1",
      "acceptance": [
        "AC-UPG-1",
        "AC-UPG-2",
        "AC-UPG-3",
        "AC-UPG-4"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Manual requirements review for observability, failure behavior, ownership scope, CONTRIBUTING rules and test isolation; recorded in the artifact.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/readiness.md",
        "sha256": "3d356c4f368d7deaddc333e3c81c06b68250d95cc1d8d5e1968f13df6c6c0a91"
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
      "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
      "red": null,
      "reason": "README.md (brief) changed by TASK-UPG-DOCS; superseded by EV-UPG-READY-2. Next action: none."
    },
    {
      "id": "EV-UPG-READY-2",
      "acceptance": [
        "AC-UPG-1",
        "AC-UPG-2",
        "AC-UPG-3",
        "AC-UPG-4"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Re-reviewed the changed brief against the requirements; unchanged scope recorded in the artifact.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/readiness-r2.md",
        "sha256": "93536aa2c8f24fab0d0450619ed0019531fa4921205836b6241b2158e4327539"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        }
      ],
      "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-UPG-BEH-1",
      "acceptance": [
        "AC-UPG-1",
        "AC-UPG-2",
        "AC-UPG-3",
        "AC-UPG-4"
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
        "tests/test_install.py"
      ],
      "method": "Ran with NETDECK_TEST_INSTALL=1: real installs into an isolated HOME/runtime dir/port with a recording systemctl stub. Upgrade stopped the running installed NetDeck and restarted one running the new code with --no-browser; with nothing running none was started; a source-tree NetDeck kept running as the registered instance; an active user service was stopped before installing and started after via systemctl with no separate instance. 4 tests collected and passed; shellcheck and ruff clean.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/behavior/install.log",
        "sha256": "a64813524ccc830082620c8e8bc38399ed8c5bd0952cb4189511d2639141d613"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "4d5e4e7fcdbaf3e5007c3a331d6d13f36f2483011934bbdd4e1e967b8bac696c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
        },
        {
          "path": "tests/test_install.py",
          "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
        }
      ],
      "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-RD-UPG-1",
      "acceptance": [
        "AC-UPG-1"
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
        "tests/test_install.py::test_upgrade_restarts_a_running_installed_netdeck"
      ],
      "method": "Disabled detection of the running installed NetDeck (the original defect) in scripts/install.sh of a disposable copy; the named installer test failed with the expected diagnostic; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/drills/RD-UPG-1.log",
        "sha256": "31ca0c18d54f342bccee42be4723be4c66ca228a4e8389b92e2e59a1126d53e1"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "4d5e4e7fcdbaf3e5007c3a331d6d13f36f2483011934bbdd4e1e967b8bac696c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
        },
        {
          "path": "tests/test_install.py",
          "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
        }
      ],
      "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
      "red": {
        "mutation": "scripts/install.sh: 'elif OLD_PID=\"$(installed_pid)\"; then\\n' -> 'elif false; then\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "old NetDeck still running after upgrade",
        "observed_diagnostic": "old NetDeck still running after upgrade",
        "before": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ],
        "mutated": [
          {
            "path": "scripts/install.sh",
            "sha256": "cf8bd3976fa7644a59c3cf82d7a0212ff2c00c6262dbb7cf9c2f5ab5c7531c31"
          }
        ],
        "after": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UPG-1b",
      "acceptance": [
        "AC-UPG-1"
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
        "tests/test_install.py::test_upgrade_restarts_a_running_installed_netdeck"
      ],
      "method": "Disabled the restart of a stopped instance in scripts/install.sh of a disposable copy; the named installer test failed with the expected diagnostic; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/drills/RD-UPG-1b.log",
        "sha256": "cecb55e778dcaf06553038bfded9b6881b49ad15dd9d2de4f93e386cdb51484d"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "4d5e4e7fcdbaf3e5007c3a331d6d13f36f2483011934bbdd4e1e967b8bac696c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
        },
        {
          "path": "tests/test_install.py",
          "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
        }
      ],
      "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
      "red": {
        "mutation": "scripts/install.sh: 'elif [ \"$RESTART\" = instance ]; then\\n' -> 'elif [ \"$RESTART\" = never ]; then\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "no NetDeck running after upgrade",
        "observed_diagnostic": "no NetDeck running after upgrade",
        "before": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ],
        "mutated": [
          {
            "path": "scripts/install.sh",
            "sha256": "c249c1a3706046cb7c768f90eb46330607cf56dafacf6fdbe169a7a078088c1c"
          }
        ],
        "after": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UPG-2",
      "acceptance": [
        "AC-UPG-2"
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
        "tests/test_install.py::test_upgrade_with_nothing_running_starts_nothing"
      ],
      "method": "Restarted NetDeck whenever the service was not involved in scripts/install.sh of a disposable copy; the named installer test failed with the expected diagnostic; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/drills/RD-UPG-2.log",
        "sha256": "37d92895872f9aed8d5bb62684fe3590869d7d624913aebf49c823828875430c"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
        },
        {
          "path": "tests/test_install.py",
          "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
        }
      ],
      "scope_sha256": "b53a43f9b11395816bde4d8374c6f67725faf697f348d476c1cc1b16844f9641",
      "red": {
        "mutation": "scripts/install.sh: 'elif [ \"$RESTART\" = instance ]; then\\n' -> 'elif [ \"$RESTART\" != service ]; then\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "installer started NetDeck although none was running",
        "observed_diagnostic": "installer started NetDeck although none was running",
        "before": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ],
        "mutated": [
          {
            "path": "scripts/install.sh",
            "sha256": "8bcdec03b37e2c5b93d8ef0ab9bc73996df1365118bf427ce715c4da0e94c099"
          }
        ],
        "after": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UPG-3",
      "acceptance": [
        "AC-UPG-3"
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
        "tests/test_install.py::test_upgrade_leaves_a_netdeck_from_elsewhere_alone"
      ],
      "method": "Removed the installation-ownership check in scripts/install.sh of a disposable copy; the named installer test failed with the expected diagnostic; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/drills/RD-UPG-3.log",
        "sha256": "a33f7a68ef34545a47239039054fde2e9c02a9a4886efd53706c393a50bcf4e2"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
        },
        {
          "path": "tests/test_install.py",
          "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
        }
      ],
      "scope_sha256": "b53a43f9b11395816bde4d8374c6f67725faf697f348d476c1cc1b16844f9641",
      "red": {
        "mutation": "scripts/install.sh: 'if not exe.startswith(sys.argv[1]):\\n' -> 'if False:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "foreign NetDeck was stopped",
        "observed_diagnostic": "foreign NetDeck was stopped",
        "before": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ],
        "mutated": [
          {
            "path": "scripts/install.sh",
            "sha256": "5ff7e5499ae8fbbc6b59f8f00baaace8afd8d24133a17477ed91eaff941b5237"
          }
        ],
        "after": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UPG-4",
      "acceptance": [
        "AC-UPG-4"
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
        "tests/test_install.py::test_upgrade_restarts_the_user_service_through_systemd"
      ],
      "method": "Removed the systemd user-service branch in scripts/install.sh of a disposable copy; the named installer test failed with the expected diagnostic; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "shellcheck": "0.11.0",
          "bash": "5.3.20"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/installer-upgrade/reports/drills/RD-UPG-4.log",
        "sha256": "e7f719dff5692e3e2a0eda788c7f6f877f14b8972b5061c2c3fa224aff628ca8"
      },
      "inputs": [
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
        },
        {
          "path": "CHANGELOG.md",
          "sha256": "4d5e4e7fcdbaf3e5007c3a331d6d13f36f2483011934bbdd4e1e967b8bac696c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
        },
        {
          "path": "tests/test_install.py",
          "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
        }
      ],
      "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
      "red": {
        "mutation": "scripts/install.sh: 'if command -v systemctl >/dev/null && systemctl --user is-active --quiet netdeck.service 2>/dev/null; then\\n' -> 'if false; then\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "service was not stopped",
        "observed_diagnostic": "service was not stopped",
        "before": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ],
        "mutated": [
          {
            "path": "scripts/install.sh",
            "sha256": "fb648fe0a88278ce36b0a104d31347406ee47e81c00c6de5d133091d9f083589"
          }
        ],
        "after": [
          {
            "path": "scripts/install.sh",
            "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "d03483008ef6a75e4f3d337b222a57f21dd42647839ef8ae2eb016cd49ea77d9",
    "inputs": [
      {
        "path": ".github/workflows/ci.yml",
        "sha256": "a739931232654683e0442520fcfdbf4b67aba81eb4ce6f2ccabfe6befda0f690"
      },
      {
        "path": "CHANGELOG.md",
        "sha256": "4d5e4e7fcdbaf3e5007c3a331d6d13f36f2483011934bbdd4e1e967b8bac696c"
      },
      {
        "path": "CONTRIBUTING.md",
        "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
      },
      {
        "path": "README.md",
        "sha256": "2d91eb6d59ea0084ac9fff684a40dcb3751917f615e79d9d71992b64b0094dec"
      },
      {
        "path": "pyproject.toml",
        "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
      },
      {
        "path": "scripts/install.sh",
        "sha256": "3cf8910ff271db4f798ca1d47b3434f6750a4c685697c90f9c6837cb4a3c5725"
      },
      {
        "path": "tests/test_install.py",
        "sha256": "7d5d3cc050f318b23038a1aa5267fc0db92932304e7be7db21b31caf5caca205"
      }
    ],
    "environment": {
      "platform": "linux",
      "tools": {
        "bash": "5.3.20",
        "pytest": "9.2.0",
        "python": "3.14.9",
        "ruff": "0.17.4",
        "shellcheck": "0.11.0"
      }
    },
    "verified_tasks": [
      "TASK-UPG-INSTALLER",
      "TASK-UPG-DOCS"
    ],
    "pending_operations": [
      {
        "id": "OP-UPG-CI",
        "description": "CI install job now runs tests/test_install.py with NETDECK_TEST_INSTALL=1; not yet run on GitHub.",
        "next_action": "Push, watch the install job, confirm the 4 upgrade tests ran, and record the outcome."
      }
    ],
    "next_action": "Push and observe OP-UPG-CI; then upgrade this machine's real install with the new installer.",
    "source_revision": "46866a0 + uncommitted WORK-INSTALLER-UPGRADE changes"
  }
}
```
