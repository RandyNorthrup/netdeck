# Delivery plan: UniFi tools

## Rationale

The user troubleshoots networks that often run Ubiquiti UniFi. The most common UniFi failure in the field is
adoption: devices that never appear in the controller or sit in "Adopting". On the user's own network
(2026-11-09) `nmap --script ubiquiti-discovery` on UDP 10001 returned model, firmware, hostname and
`config_status` (one bridge `default/unmanaged`, the Cloud Key `managed/adopted`), and a plain `GET /inform`
on the UniFi console's port 8080 returned HTTP 400 with an empty body, while a non-controller host refused the
port. Those two observations make discovery and the inform check reliable without credentials.

**Tools (new *UniFi* category).**
- *UniFi Device Discovery*: `nmap -sU -p 10001 --script ubiquiti-discovery --open -T4 -- <subnet>` (UDP scan,
  so elevated).
- *UniFi Inform Check*: built-in probe: TCP connect, then `GET /inform`; 400 + empty body = UniFi endpoint.
- *UniFi Adopt*: `ssh -t ... -- user@device mca-cli-op set-inform http://<controller>:8080/inform` in a
  terminal (the user types the password; factory default `ubnt`). `mca-cli-op` is the non-interactive form of
  the device CLI's `set-inform`/`info`. Opt-in "factory-reset" switch skips host-key checking, because a
  reset device presents a new key.
- *UniFi Device Info*: same SSH path with `mca-cli-op info`.
- *Open UniFi Controller*: `xdg-open https://<host>` (UniFi OS consoles) or `:8443` (self-hosted servers).

**Non-goals.** No factory reset or other destructive device commands, no stored controller credentials or
controller API calls, no automated "Adopt" click. The unadopted bridge on the user's network is not touched:
Adopt and Device Info are verified to the exact command, not run against a device.

**Reuse.** Catalog entries on the existing argv/validator/runner path; the inform check reuses the probe
helpers (`_resolve`) used by TCP Check. IPv6 literals are bracketed in every URL.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "WORK-UNIFI",
    "title": "UniFi tools: discovery, inform check, adoption, device info, controller",
    "scope_revision": 1,
    "brief": "README.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "CONTRIBUTING.md",
        "revision": "33d6e00"
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
        "nmap": "7.993",
        "node": "26.13.0"
      }
    }
  },
  "requirements": [
    {
      "id": "REQ-UF-TOOLS",
      "statement": "A UniFi category lets a field technician find Ubiquiti devices and their adoption state, verify the controller's inform endpoint, point a device at a controller (set-inform), read a device's status, and open the controller UI, with validated inputs.",
      "priority": "critical",
      "acceptance": [
        "AC-UF-ARGV",
        "AC-UF-VAL",
        "AC-UF-INFORM",
        "AC-UF-LIVE"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-UF-ARGV",
      "requirement": "REQ-UF-TOOLS",
      "given": "Each UniFi tool with representative parameters, including IPv6 addresses",
      "when": "Its command is built",
      "then": "It equals the expected argv (nmap ubiquiti-discovery on UDP 10001; ssh -t ... mca-cli-op set-inform/info; xdg-open of the controller URL), lives in the UniFi category with the expected mode, and only discovery requests elevation",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-UF-VAL",
      "requirement": "REQ-UF-TOOLS",
      "given": "Option-like or shell-metacharacter device, controller or user values",
      "when": "UniFi Adopt validates them",
      "then": "They are rejected before any command is built",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-UF-INFORM",
      "requirement": "REQ-UF-TOOLS",
      "given": "The UniFi Inform Check pointed at local fake servers",
      "when": "It runs",
      "then": "An HTTP 400 with an empty body to GET /inform passes and prints the set-inform URL; other web responses, a refused port, a non-HTTP service and an unresolvable name fail with a specific diagnosis; IPv6 addresses are bracketed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-UF-LIVE",
      "requirement": "REQ-UF-TOOLS",
      "given": "A real NetDeck server on this laptop's UniFi network (controller 10.10.11.1)",
      "when": "Discovery and the inform check run through its API",
      "then": "Discovery finishes within 90 s and reports at least one device with its config_status; the inform check confirms the controller's endpoint",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "TASK-UF-DECK",
      "purpose": "Add the UniFi category, five tools, the inform probe, icons, install hint and tests",
      "acceptance": [
        "AC-UF-ARGV",
        "AC-UF-VAL",
        "AC-UF-INFORM",
        "AC-UF-LIVE"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "src/netdeck/catalog.py",
          "action": "modify"
        },
        {
          "path": "src/netdeck/probes.py",
          "action": "modify"
        },
        {
          "path": "src/netdeck/static/app.js",
          "action": "modify"
        },
        {
          "path": "tests/test_unifi.py",
          "action": "create"
        },
        {
          "path": "tests/test_field_live.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-UF-BEH-UNIT",
        "EV-UF-BEH-LIVE",
        "EV-RD-UF-ARGVb",
        "EV-RD-UF-PRIV",
        "EV-RD-UF-VAL",
        "EV-RD-UF-INFORM",
        "EV-RD-UF-INFORM2b",
        "EV-RD-UF-LIVEb",
        "EV-RD-UF-LIVE2"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-UF-DOCS",
      "purpose": "Document the UniFi tools and adoption workflow from shipped behavior",
      "acceptance": [
        "AC-UF-ARGV",
        "AC-UF-LIVE"
      ],
      "depends_on": [
        "TASK-UF-DECK"
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
        "EV-UF-BEH-UNIT",
        "EV-UF-BEH-LIVE",
        "EV-RD-UF-ARGVb",
        "EV-RD-UF-LIVEb",
        "EV-RD-UF-LIVE2"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-UF-READY-1",
      "acceptance": [
        "AC-UF-ARGV",
        "AC-UF-VAL",
        "AC-UF-INFORM",
        "AC-UF-LIVE"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Manual requirements review for observability, failure behavior, scope, rules and safety; recorded in the artifact.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/unifi/reports/readiness.md",
        "sha256": "fa8685f37263a0f37b45d8e571b564344daf3384b26f2437c0b0109bfb2815a2"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-UF-BEH-UNIT",
      "acceptance": [
        "AC-UF-ARGV",
        "AC-UF-VAL",
        "AC-UF-INFORM"
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
        "tests/test_unifi.py",
        "tests/test_catalog.py"
      ],
      "method": "PYTHONPATH=src: exact argv/category/mode/elevation for all five UniFi tools incl. IPv6, unsafe-value rejection, inform probe against local fake HTTP servers (400 empty, 200/400-HTML/404, refused, non-HTTP, IPv6, unresolvable); generic build/hint checks for all 86 tools. 113 passed; full suite with NETDECK_REQUIRE_E2E=1: 232 passed, 15 opt-in skipped (reports/final/full-suite.log); make lint clean (reports/final/lint.log).",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/final/unit.log",
        "sha256": "4381413c211b464d7283a135eb67093e4d7373fc0edcc9d4202f66567f266078"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-UF-BEH-LIVE",
      "acceptance": [
        "AC-UF-LIVE"
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
        "tests/test_field_live.py",
        "-k",
        "unifi"
      ],
      "method": "NETDECK_TEST_LIVE=1 NETDECK_TEST_UNIFI_CONTROLLER=10.10.11.1 PYTHONPATH=src: real NetDeck server, tools run through /api/run with sudo elevation; discovery on 10.10.11.0/24 reported config_status within 90 s and the inform check confirmed the UniFi console's endpoint. 2 passed.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/final/live.log",
        "sha256": "7e3231e398ed7483b943fad96dad4cd3d3646a75434652c5a673d9d4a9dd9440"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-RD-UF-ARGV",
      "acceptance": [
        "AC-UF-ARGV"
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
        "tests/test_unifi.py::test_unifi_tool_commands"
      ],
      "method": "Dropping ssh -t from the UniFi SSH builder fails the exact-argv test. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-ARGV.log",
        "sha256": "0bf3b778a00f1d356b4a70ac44213165ee8021b5dcb9551a300ed2ab1b791f14"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": {
        "mutation": "src/netdeck/catalog.py: 'return ([\"ssh\", \"-t\", \"-p\", str(p[\"port\"])]' -> 'return ([\"ssh\", \"-p\", str(p[\"port\"])]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert \\[\\['ssh', '-p'",
        "observed_diagnostic": "AssertionError: assert [['ssh', '-p'",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "d30a5defa8212d5826b9c7b10b55026e25e2a8e94a573be3e4d72be671eda560"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ]
      },
      "reason": "expected_diagnostic was recorded as a regular expression, but the ledger compares it literally; superseded by the same-artifact receipt with suffix b. Next action: none."
    },
    {
      "id": "EV-RD-UF-PRIV",
      "acceptance": [
        "AC-UF-ARGV"
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
        "tests/test_unifi.py::test_unifi_modes_and_elevation"
      ],
      "method": "Discovery without elevation fails the elevation test (UDP scans need root). Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-PRIV.log",
        "sha256": "2b4207e805f1a22849d0d62f630bfb728d95737f80bb0c48bd8fd1865176a418"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": {
        "mutation": "src/netdeck/catalog.py: '\"-T4\", \"--\", p[\"target\"]], privileged=True, popular=True,' -> '\"-T4\", \"--\", p[\"target\"]], privileged=False, popular=True,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: unifi-discover",
        "observed_diagnostic": "AssertionError: unifi-discover",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "41e7b5d232042fefca28ce47c6048b1809f17e3b234f1b7adf044ff86f8427af"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UF-VAL",
      "acceptance": [
        "AC-UF-VAL"
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
        "tests/test_unifi.py::test_unifi_adopt_rejects_unsafe_values"
      ],
      "method": "Validating the Adopt device as a free-form expression lets a shell-metacharacter value through and the rejection test fails. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-VAL.log",
        "sha256": "d90580e00963a82cf8bb33000dc2069e8db95a09db65339fba9f97052ce61874"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "fae72c734488136ee7ebda86bfac4d84c729e333ac3a67b96b226a38f3cfdb5b",
      "red": {
        "mutation": "src/netdeck/catalog.py: 'Param(\"device\", \"Device\", \"host\", required=True, placeholder=\"192.168.1.20\"),\\n             Param(\"controller\"' -> 'Param(\"device\", \"Device\", \"expr\", required=True, placeholder=\"192.168.1.20\"),\\n             Param(\"controller\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Failed: DID NOT RAISE",
        "observed_diagnostic": "Failed: DID NOT RAISE",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "b26d9188be8dba8bb4697152fa7ca017e300a51a8bd18f840753ae82cd8d9e4b"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UF-INFORM",
      "acceptance": [
        "AC-UF-INFORM"
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
        "tests/test_unifi.py::test_inform_check_rejects_other_web_servers"
      ],
      "method": "Accepting any HTTP 400 as the inform endpoint makes an HTML 400 page pass and the rejection test fails. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-INFORM.log",
        "sha256": "fbbb486021518ea8297ad012a0cb829ea106425a5a62fcffc34906c80bbea5e8"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "fae72c734488136ee7ebda86bfac4d84c729e333ac3a67b96b226a38f3cfdb5b",
      "red": {
        "mutation": "src/netdeck/probes.py: 'if resp.status == 400 and not body:' -> 'if resp.status == 400:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 0 == 1",
        "observed_diagnostic": "assert 0 == 1",
        "before": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "fe100da0b9f63ab0e0d1737ff850e438106ee1609f93abd41e1bb6a8d131f81c"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UF-INFORM2",
      "acceptance": [
        "AC-UF-INFORM"
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
        "tests/test_unifi.py::test_inform_check_over_ipv6"
      ],
      "method": "Not bracketing IPv6 literals yields http://::1:port/inform and the IPv6 test fails. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-INFORM2.log",
        "sha256": "2caa45f1604f9eca3f608563bba779c9b36ba543afc4681f0abe0f421b9cd305"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "fae72c734488136ee7ebda86bfac4d84c729e333ac3a67b96b226a38f3cfdb5b",
      "red": {
        "mutation": "src/netdeck/probes.py: 'return f\"[{host}]:{port}\" if \":\" in host else f\"{host}:{port}\"' -> 'return f\"{host}:{port}\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert 'http://\\[::1\\]:\\d+/inform' in 'Checking http://::1:",
        "observed_diagnostic": "AssertionError: assert 'http://[::1]:45903/inform' in 'Checking http://::1:",
        "before": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ff6443e472992eff020b8c82f938b8f86b570a28f047923b2513400093351504"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ]
      },
      "reason": "expected_diagnostic was recorded as a regular expression, but the ledger compares it literally; superseded by the same-artifact receipt with suffix b. Next action: none."
    },
    {
      "id": "EV-RD-UF-LIVE",
      "acceptance": [
        "AC-UF-LIVE"
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
        "tests/test_field_live.py::test_unifi_inform_check"
      ],
      "method": "Probing / instead of /inform on the real controller gets a 400 HTML page; the live inform test fails with the not-an-inform-endpoint diagnosis. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-LIVE.log",
        "sha256": "762bb7b2d850d1987d9cb7e5b71e4cbdbd4ce56537bef60ce3e72d08fad74e4e"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": {
        "mutation": "src/netdeck/probes.py: 'conn.request(\"GET\", \"/inform\",' -> 'conn.request(\"GET\", \"/\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "not like a UniFi inform endpoint \\(HTTP 400, \\d+ bytes\\)",
        "observed_diagnostic": "not like a UniFi inform endpoint (HTTP 400, 435 bytes)",
        "before": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "2615a21517de35ea3b019bef49f6cad26eaf75ad6704add4d29ad2dfc9fa9a98"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ]
      },
      "reason": "expected_diagnostic was recorded as a regular expression, but the ledger compares it literally; superseded by the same-artifact receipt with suffix b. Next action: none."
    },
    {
      "id": "EV-RD-UF-LIVE2",
      "acceptance": [
        "AC-UF-LIVE"
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
        "tests/test_field_live.py::test_unifi_discovery_completes_and_finds_devices_on_unifi_networks"
      ],
      "method": "Discovery on UDP 10002 instead of 10001 finds no UniFi device and the live discovery test fails. Log scrubbed of MACs and hostnames before recording. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-LIVE2.log",
        "sha256": "453c74bcd320c2d2de391c643dc9d535e8f30515ee5c624f1f04c493c118729c"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": {
        "mutation": "src/netdeck/catalog.py: 'UNIFI_DISCOVERY_PORT = \"10001\"' -> 'UNIFI_DISCOVERY_PORT = \"10002\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "no UniFi device answered",
        "observed_diagnostic": "no UniFi device answered",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "383759b00958188936d7ccc2a0bd9c52634c7cd59f9d2ea6f5348d8b86d0573c"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UF-ARGVb",
      "acceptance": [
        "AC-UF-ARGV"
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
        "tests/test_unifi.py::test_unifi_tool_commands"
      ],
      "method": "Dropping ssh -t from the UniFi SSH builder fails the exact-argv test. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-ARGV.log",
        "sha256": "0bf3b778a00f1d356b4a70ac44213165ee8021b5dcb9551a300ed2ab1b791f14"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": {
        "mutation": "src/netdeck/catalog.py: 'return ([\"ssh\", \"-t\", \"-p\", str(p[\"port\"])]' -> 'return ([\"ssh\", \"-p\", str(p[\"port\"])]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert [['ssh', '-p'",
        "observed_diagnostic": "AssertionError: assert [['ssh', '-p'",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "d30a5defa8212d5826b9c7b10b55026e25e2a8e94a573be3e4d72be671eda560"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UF-INFORM2b",
      "acceptance": [
        "AC-UF-INFORM"
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
        "tests/test_unifi.py::test_inform_check_over_ipv6"
      ],
      "method": "Not bracketing IPv6 literals yields http://::1:port/inform and the IPv6 test fails. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-INFORM2.log",
        "sha256": "2caa45f1604f9eca3f608563bba779c9b36ba543afc4681f0abe0f421b9cd305"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "fae72c734488136ee7ebda86bfac4d84c729e333ac3a67b96b226a38f3cfdb5b",
      "red": {
        "mutation": "src/netdeck/probes.py: 'return f\"[{host}]:{port}\" if \":\" in host else f\"{host}:{port}\"' -> 'return f\"{host}:{port}\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert 'http://[::1]:",
        "observed_diagnostic": "AssertionError: assert 'http://[::1]:45903/inform' in 'Checking http://::1:",
        "before": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ff6443e472992eff020b8c82f938b8f86b570a28f047923b2513400093351504"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-UF-LIVEb",
      "acceptance": [
        "AC-UF-LIVE"
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
        "tests/test_field_live.py::test_unifi_inform_check"
      ],
      "method": "Probing / instead of /inform on the real controller gets a 400 HTML page; the live inform test fails with the not-an-inform-endpoint diagnosis. Mutation applied in a disposable copy; original byte-identical and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "nmap": "7.993",
          "node": "26.13.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/unifi/reports/drills/RD-UF-LIVE.log",
        "sha256": "762bb7b2d850d1987d9cb7e5b71e4cbdbd4ce56537bef60ce3e72d08fad74e4e"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
        },
        {
          "path": "tests/test_unifi.py",
          "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
        }
      ],
      "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
      "red": {
        "mutation": "src/netdeck/probes.py: 'conn.request(\"GET\", \"/inform\",' -> 'conn.request(\"GET\", \"/\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "not like a UniFi inform endpoint (HTTP 400,",
        "observed_diagnostic": "not like a UniFi inform endpoint (HTTP 400, 435 bytes)",
        "before": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "2615a21517de35ea3b019bef49f6cad26eaf75ad6704add4d29ad2dfc9fa9a98"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "0ba4b89a42e17358769290833ac28c1cc2f3471bd3ff148529421eb0d38edecd",
    "inputs": [
      {
        "path": "CHANGELOG.md",
        "sha256": "3354dc19992980f479224d4a29c6c7b5ad8438832f0b28bd425fca9d7f85237c"
      },
      {
        "path": "CONTRIBUTING.md",
        "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
      },
      {
        "path": "README.md",
        "sha256": "fcced46c1a12ce25ef01cfe699efbf2e6111c7d48a72141c6e609ad37dadb205"
      },
      {
        "path": "pyproject.toml",
        "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
      },
      {
        "path": "src/netdeck/catalog.py",
        "sha256": "a1a04b97845e2cd259a1b93de585d4abd23e9d3615ae5e9807ccfca7e62ec750"
      },
      {
        "path": "src/netdeck/probes.py",
        "sha256": "ee6bfbc83764965a54cda09e29a63cf7c28d4712bcbd594a00719e8ad08bb1f6"
      },
      {
        "path": "src/netdeck/static/app.js",
        "sha256": "ccd8c3e785d4e8cb7625881954178a60de67d812b2371ccfbbe1af43314f57e1"
      },
      {
        "path": "tests/test_field_live.py",
        "sha256": "2e1e6f76978bd55a43978cf3c7c08c3094f218e5c7807382018d8e8106a7a372"
      },
      {
        "path": "tests/test_unifi.py",
        "sha256": "310d26da2cfefdeb0d5957d4c6714610fe4bb758a605db81131a885e13e6b005"
      }
    ],
    "environment": {
      "platform": "linux",
      "tools": {
        "nmap": "7.993",
        "node": "26.13.0",
        "pytest": "9.2.0",
        "python": "3.14.9",
        "ruff": "0.17.4"
      }
    },
    "verified_tasks": [
      "TASK-UF-DECK",
      "TASK-UF-DOCS"
    ],
    "pending_operations": [],
    "next_action": "None: delivery closed; see reports/ci-4e03749.md.",
    "source_revision": "4e03749"
  }
}
```
