# Delivery plan: field kit

## Rationale

The user will use this laptop to troubleshoot other people's networks. A smoke run of every live-output tool
through NetDeck's API (2026-11-08) found real defects, and the deck lacked the tools a field technician
reaches for first, most of which were already installed.

**Defects to fix.**
- *OS Fingerprint* printed nothing for 143 s against the gateway (it also re-ran service detection, which
  *Port Scan* already offers), so it looked frozen.
- *Public IP* reported failure on IPv4-only networks because the IPv6 check ran by default.
- The overview labelled the Apple T2 controller link (`cdc_ncm`, MAC `ac:de:48:00:11:22`) as Ethernet and the
  health check counted it as a network link; this MacBook has no Ethernet port.
- *Usage History* failed because the vnStat service was not enabled (machine setup, now done).

**Additions (organized into categories).**
- *LAN Services* (new): DHCP server check (nmap `broadcast-dhcp-discover`; finds missing or rogue servers),
  Switch Port via passive LLDP/CDP capture (transmits nothing, unlike running `lldpd`), SNMP query, LAN device
  discovery (mDNS/UPnP/NetBIOS broadcast scripts), NetBIOS name scan (`nbtscan`), IPv6 router advertisements
  (`rdisc6`).
- *Device Access* (new): serial console (`picocom`; elevates only when the device is not accessible), SSH, Telnet.
- *Wi-Fi* (new; Wi-Fi Scan and Wi-Fi Link move here): signal meter (`wavemon`), channel chart (`linssid`),
  monitor mode on/off and site survey (`airmon-ng`, `airodump-ng`) for monitor-capable adapters.
- *Connectivity*: MTU test (`ping -M do`), duplicate-IP check (`arping -D`). *Traffic*: `bandwhich`.
  *Web & TLS*: TLS configuration audit (`testssl`). *Interfaces*: Ethernet cable test (`ethtool --cable-test`).

**Reuse.** Every addition is a catalog entry on the existing builder/validator/runner path. New parameter
kinds (serial device, SNMP community, SSH username) extend `validators.validate`.

**Not testable here.** The USB Ethernet adapter, console cable and Alfa adapter are not connected: serial,
cable test, monitor mode and survey are covered by exact-argv tests and installed binaries, not live runs.
Monitor mode is never toggled on the built-in Broadcom card (it cannot do it, and trying could drop Wi-Fi).

**Test strategy.** `tests/test_fieldkit.py` asserts exact argv, privilege decisions, validators and the T2
classification against a fake sysfs. `tests/test_field_live.py` (opt-in, `NETDECK_TEST_LIVE=1`) runs the
hardware-free tools through a real NetDeck server on the local network, including SNMP against a temporary
local `snmpd`; it doubles as a field self-test the user can run on site.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "WORK-FIELD-KIT",
    "title": "Field kit: fixes and field troubleshooting tools",
    "scope_revision": 1,
    "brief": "README.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "CONTRIBUTING.md",
        "revision": "ffb643a"
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
      "id": "REQ-FK-FIX",
      "statement": "Defects found by the field smoke run are fixed: OS fingerprinting shows progress and is quick by default, Public IP does not fail on IPv4-only networks, the Apple T2 internal link is not presented as Ethernet or as a network link, and usage history works on this machine.",
      "priority": "critical",
      "acceptance": [
        "AC-FK-OS",
        "AC-FK-IP",
        "AC-FK-T2",
        "AC-FK-VNSTAT"
      ],
      "superseded_by": null
    },
    {
      "id": "REQ-FK-NEW",
      "statement": "Field troubleshooting tools are available in the deck, organized by category, with validated parameters, and the ones that need no extra hardware work on this machine.",
      "priority": "critical",
      "acceptance": [
        "AC-FK-ARGV",
        "AC-FK-VAL",
        "AC-FK-LIVE"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-FK-OS",
      "requirement": "REQ-FK-FIX",
      "given": "The OS Fingerprint tool with default options",
      "when": "Its command is built and run against the gateway",
      "then": "The command includes --stats-every and omits -sV unless service detection is chosen, and the live run finishes within 60 s with an OS guess",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-FK-IP",
      "requirement": "REQ-FK-FIX",
      "given": "The Public IP tool with default options",
      "when": "It runs on an IPv4-only network",
      "then": "Only the IPv4 check runs and the job completes successfully; IPv6 is opt-in",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-FK-T2",
      "requirement": "REQ-FK-FIX",
      "given": "A network interface whose USB product is the Apple T2 Controller",
      "when": "Interfaces are classified and the health check evaluates links",
      "then": "It is classified as internal (labelled Apple T2 link), never as Ethernet, and does not count as a network link",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-FK-VNSTAT",
      "requirement": "REQ-FK-FIX",
      "given": "This laptop with the vnStat service enabled",
      "when": "Usage History runs",
      "then": "It exits 0 and shows the interface database",
      "checks": [
        "manual"
      ],
      "manual_reason": "Machine configuration rather than code: the fix is enabling the vnstat service, observed by running the tool afterwards."
    },
    {
      "id": "AC-FK-ARGV",
      "requirement": "REQ-FK-NEW",
      "given": "Each new or moved tool with representative parameters",
      "when": "Its command is built",
      "then": "It equals the expected argv, lives in the expected category, and elevation is requested exactly when required",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-FK-VAL",
      "requirement": "REQ-FK-NEW",
      "given": "Serial device, SNMP community and SSH username inputs",
      "when": "They are validated",
      "then": "Well-formed values pass; option-like, path-traversing, shell-metacharacter and nonexistent-device values are rejected",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-FK-LIVE",
      "requirement": "REQ-FK-NEW",
      "given": "A real NetDeck server on this laptop's network",
      "when": "The hardware-free field tools run through its API",
      "then": "DHCP check finds the DHCP server, device discovery and NetBIOS scan complete, SNMP reads sysDescr from a local test agent, MTU test passes at 1472 and reports fragmentation at 1500, duplicate-IP check flags the gateway's address as in use, IPv6 RA and TLS audit complete, and the switch-port capture ends cleanly within its time limit",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "TASK-FK-DECK",
      "purpose": "Fix the defects and add the field tools, validators, categories, install hints and tests",
      "acceptance": [
        "AC-FK-OS",
        "AC-FK-IP",
        "AC-FK-T2",
        "AC-FK-VNSTAT",
        "AC-FK-ARGV",
        "AC-FK-VAL",
        "AC-FK-LIVE"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "src/netdeck/catalog.py",
          "action": "modify"
        },
        {
          "path": "src/netdeck/validators.py",
          "action": "modify"
        },
        {
          "path": "src/netdeck/sysinfo.py",
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
          "path": "scripts/install.sh",
          "action": "modify"
        },
        {
          "path": "tests/test_catalog.py",
          "action": "modify"
        },
        {
          "path": "tests/test_fieldkit.py",
          "action": "create"
        },
        {
          "path": "tests/test_field_live.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-FK-BEH-UNIT",
        "EV-FK-BEH-LIVE",
        "EV-FK-VNSTAT",
        "EV-RD-FK-OS",
        "EV-RD-FK-IP",
        "EV-RD-FK-T2",
        "EV-RD-FK-T2b",
        "EV-RD-FK-ARGV",
        "EV-RD-FK-PRIV",
        "EV-RD-FK-VAL",
        "EV-RD-FK-VAL2",
        "EV-RD-FK-LIVE",
        "EV-RD-FK-LIVE2"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-FK-DOCS",
      "purpose": "Document the field kit, required hardware and the field self-test from shipped behavior",
      "acceptance": [
        "AC-FK-ARGV",
        "AC-FK-LIVE"
      ],
      "depends_on": [
        "TASK-FK-DECK"
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
        "EV-FK-BEH-UNIT",
        "EV-FK-BEH-LIVE",
        "EV-RD-FK-ARGV",
        "EV-RD-FK-PRIV",
        "EV-RD-FK-LIVE",
        "EV-RD-FK-LIVE2"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-FK-READY-1",
      "acceptance": [
        "AC-FK-OS",
        "AC-FK-IP",
        "AC-FK-T2",
        "AC-FK-VNSTAT",
        "AC-FK-ARGV",
        "AC-FK-VAL",
        "AC-FK-LIVE"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Manual requirements review for observability, failure behavior, scope, rules and test safety; recorded in the artifact.",
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
        "path": "docs/delivery/field-kit/reports/readiness.md",
        "sha256": "e0eb8355605b0c6f42cfaf00f5bf44bb4a03cf2e90d15af5e73e051133fde342"
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
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": null,
      "reason": "README.md (brief) changed by TASK-FK-DOCS; superseded by EV-FK-READY-2. Next action: none."
    },
    {
      "id": "EV-FK-READY-2",
      "acceptance": [
        "AC-FK-OS",
        "AC-FK-IP",
        "AC-FK-T2",
        "AC-FK-VNSTAT",
        "AC-FK-ARGV",
        "AC-FK-VAL",
        "AC-FK-LIVE"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Re-reviewed the changed brief and the implementation-time design findings; requirements unchanged.",
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
        "path": "docs/delivery/field-kit/reports/readiness-r2.md",
        "sha256": "f8f0a0fd42577b8317d4794710a397c5e503d595763dcb19ff0597d2b7cbc844"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-FK-BEH-UNIT",
      "acceptance": [
        "AC-FK-OS",
        "AC-FK-IP",
        "AC-FK-T2",
        "AC-FK-ARGV",
        "AC-FK-VAL"
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
        "tests/test_fieldkit.py",
        "tests/test_catalog.py"
      ],
      "method": "PYTHONPATH=src: exact argv, categories and elevation for every new/moved tool, OS-fingerprint and Public IP defaults, T2 classification and health-check exclusion against fake sysfs/probes, serial/community/username validators; generic build/hint checks for all 80 tools. 140 collected and passed; full suite 203 passed (12 opt-in skipped), make lint clean.",
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
        "path": "docs/delivery/field-kit/reports/final/unit.log",
        "sha256": "77cfc23f5aacfd85e59cc42ca5191792d00677f84f7269c29b0b1ba0eae2ef56"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-FK-BEH-LIVE",
      "acceptance": [
        "AC-FK-LIVE",
        "AC-FK-OS"
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
        "tests/test_field_live.py"
      ],
      "method": "NETDECK_TEST_LIVE=1 on this laptop's Wi-Fi LAN through a real NetDeck server: DHCP check found the gateway's server, discovery and NetBIOS scan completed, SNMP read sysDescr from a temporary local snmpd, MTU 1472 passed and 1500 reported fragmentation, the gateway's IP was flagged as in use, OS fingerprint finished under 60 s, switch-port capture ended within its limit, IPv6 RA, TLS audit, Public IP (IPv4 only) and usage history completed. 8 collected and passed.",
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
        "path": "docs/delivery/field-kit/reports/final/live.log",
        "sha256": "44d93dfdbd2efd74c0a2b648029d5a633c404c22a044718850f4db841419a660"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-FK-VNSTAT",
      "acceptance": [
        "AC-FK-VNSTAT"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "Enabled the vnstat service on this laptop, then observed the service active and vnstat printing its interface database with exit status 0 (also exercised through NetDeck in the live test).",
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
        "path": "docs/delivery/field-kit/reports/final/vnstat-manual.log",
        "sha256": "911744da9191dddc953ed2b20ce3f0eb1c7635257201f9db4db181ca750dcb03"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-RD-FK-OS",
      "acceptance": [
        "AC-FK-OS"
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
        "tests/test_fieldkit.py::test_os_fingerprint_shows_progress_and_skips_service_detection_by_default"
      ],
      "method": "Mutated src/netdeck/catalog.py in a disposable copy ('\"-T4\", \"--stats-every\", \"10s\"]' -> '\"-T4\"]'); test_os_fingerprint_shows_progress_and_skips_service_detection_by_default failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-OS.log",
        "sha256": "1369d91715f1aca5479bb9e4b6897ece2e9b9f615987f1edefbc6c5544d83d8c"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": {
        "mutation": "src/netdeck/catalog.py: '\"-T4\", \"--stats-every\", \"10s\"]' -> '\"-T4\"]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert [['nmap'",
        "observed_diagnostic": "assert [['nmap'",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "3b30dd1716d744ba11402429319b033966b1b9efb59ac0f14778f375f4833d2c"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-IP",
      "acceptance": [
        "AC-FK-IP"
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
        "tests/test_fieldkit.py::test_public_ip_checks_ipv4_only_by_default"
      ],
      "method": "Mutated src/netdeck/catalog.py in a disposable copy ('            Param(\"v6\", \"Also check IPv6\", \"bool\", False,' -> '            Param(\"v6\", \"Also check IPv6\", \"bool\", True,'); test_public_ip_checks_ipv4_only_by_default failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-IP.log",
        "sha256": "190d2fae2fa51e4a28012bfb8ce5de68d4e9af7caa2645b2abdcf1045edba3ce"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": {
        "mutation": "src/netdeck/catalog.py: '            Param(\"v6\", \"Also check IPv6\", \"bool\", False,' -> '            Param(\"v6\", \"Also check IPv6\", \"bool\", True,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert (2 == 1)",
        "observed_diagnostic": "assert (2 == 1)",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "238a0217e9d7f59ba211633fe62b7bcb1cb0c4fe158835ead38ea68670c562c5"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-T2",
      "acceptance": [
        "AC-FK-T2"
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
        "tests/test_fieldkit.py::test_apple_t2_link_is_internal_not_ethernet"
      ],
      "method": "Mutated src/netdeck/sysinfo.py in a disposable copy ('    if any(marker in product for marker in INTERNAL_PRODUCTS' -> ''); test_apple_t2_link_is_internal_not_ethernet failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-T2.log",
        "sha256": "66372feb58ff460bf5f5710280a68a9bcdf2ffe6670319c13f20ef45c845dc8e"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": {
        "mutation": "src/netdeck/sysinfo.py: '    if any(marker in product for marker in INTERNAL_PRODUCTS):\\n        return \"internal\"\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'ethernet' == 'internal'",
        "observed_diagnostic": "assert 'ethernet' == 'internal'",
        "before": [
          {
            "path": "src/netdeck/sysinfo.py",
            "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/sysinfo.py",
            "sha256": "bae90bde8071f82c5dbabaa2c7295c9d51889837a7b38505e7f9cc505d4ed069"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/sysinfo.py",
            "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-T2b",
      "acceptance": [
        "AC-FK-T2"
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
        "tests/test_fieldkit.py::test_health_check_does_not_count_the_t2_link_as_a_network_link"
      ],
      "method": "Mutated src/netdeck/probes.py in a disposable copy (' and i[\"kind\"] != \"internal\"]' -> ']'); test_health_check_does_not_count_the_t2_link_as_a_network_link failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-T2b.log",
        "sha256": "d48373050f9975788ea6a9c90dd49c6bac4b59234b911a3069e30d7777ade0c1"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": {
        "mutation": "src/netdeck/probes.py: ' and i[\"kind\"] != \"internal\"]' -> ']'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'ok' == 'fail'",
        "observed_diagnostic": "assert 'ok' == 'fail'",
        "before": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "1830e8f20503c87ffda121290504ee08b9c82eede3b6706a2c3792d1eaa37545"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/probes.py",
            "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-ARGV",
      "acceptance": [
        "AC-FK-ARGV"
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
        "tests/test_fieldkit.py::test_field_tool_commands"
      ],
      "method": "Mutated src/netdeck/catalog.py in a disposable copy ('\"-s\", \"1500\",\\n                               \"-c\", \"1\", \"--\"' -> '\"-s\", \"1500\",\\n                               \"--\", LLDP_CDP_'); test_field_tool_commands failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-ARGV.log",
        "sha256": "4b2955e2a558283e70d8c8f9a33e9ca36281cb39a72f12a2ce1dde814bf61dc7"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": {
        "mutation": "src/netdeck/catalog.py: '\"-s\", \"1500\",\\n                               \"-c\", \"1\", \"--\", LLDP_CDP_FILTER]' -> '\"-s\", \"1500\",\\n                               \"--\", LLDP_CDP_FILTER]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert [['timeout'",
        "observed_diagnostic": "AssertionError: assert [['timeout'",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "c99ff0b109938ca35306fc8a745b2218494b725cb42059621beb49ad11bbbc59"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-PRIV",
      "acceptance": [
        "AC-FK-ARGV"
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
        "tests/test_fieldkit.py::test_field_tool_elevation"
      ],
      "method": "Mutated src/netdeck/catalog.py in a disposable copy ('         privileged=True, popular=True, keywords=(\"rogue dhc' -> '         privileged=False, popular=True, keywords=(\"rogue dh'); test_field_tool_elevation failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-PRIV.log",
        "sha256": "6a67948d20cd95aaaabf463bcab4be9758adc45b1555d64a254e0ba56f940e6d"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": {
        "mutation": "src/netdeck/catalog.py: '         privileged=True, popular=True, keywords=(\"rogue dhcp\"' -> '         privileged=False, popular=True, keywords=(\"rogue dhcp\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert False is True",
        "observed_diagnostic": "assert False is True",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "6bce4a23008cb59236c60991b594adbe3268fd51412b0c0982b6636a2640ee32"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-VAL",
      "acceptance": [
        "AC-FK-VAL"
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
        "tests/test_fieldkit.py::test_serial_device_validation"
      ],
      "method": "Mutated src/netdeck/validators.py in a disposable copy ('    if os.path.isdir(DEV_DIR) and not os.path.exists(os.path' -> '    if False:'); test_serial_device_validation failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-VAL.log",
        "sha256": "71e302bd4dc248eef45a371120a4d9798512c13b18dba73c6fa4ee000cb77db0"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": {
        "mutation": "src/netdeck/validators.py: '    if os.path.isdir(DEV_DIR) and not os.path.exists(os.path.join(DEV_DIR, name)):' -> '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "DID NOT RAISE",
        "before": [
          {
            "path": "src/netdeck/validators.py",
            "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/validators.py",
            "sha256": "72d2902387fd6938d9c47f39c65f6ae90057b6a06f0eeb540d93fffd1d6bd222"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/validators.py",
            "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-VAL2",
      "acceptance": [
        "AC-FK-VAL"
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
        "tests/test_fieldkit.py::test_community_rejects"
      ],
      "method": "Mutated src/netdeck/validators.py in a disposable copy ('_COMMUNITY = re.compile(r\"^[A-Za-z0-9._@#%+=:~^*!-]{1,64}$\")' -> '_COMMUNITY = re.compile(r\"^[^-].{0,63}$\")'); test_community_rejects failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-VAL2.log",
        "sha256": "48028543a5113e1cf0e191ebe350ecad3353803a079d4acf373d81883e979dab"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "82786f26a1a93d87347a4638158a25ae0f0cf3f56ae294acc69446ad7dc5db00",
      "red": {
        "mutation": "src/netdeck/validators.py: '_COMMUNITY = re.compile(r\"^[A-Za-z0-9._@#%+=:~^*!-]{1,64}$\")' -> '_COMMUNITY = re.compile(r\"^[^-].{0,63}$\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DID NOT RAISE",
        "observed_diagnostic": "DID NOT RAISE",
        "before": [
          {
            "path": "src/netdeck/validators.py",
            "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/validators.py",
            "sha256": "da77e5f6856548f37c86a75608a66e8553c686e13698a7e3fe5bd3f574edd756"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/validators.py",
            "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-LIVE",
      "acceptance": [
        "AC-FK-LIVE"
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
        "tests/test_field_live.py::test_dhcp_check_finds_the_dhcp_server"
      ],
      "method": "Mutated src/netdeck/catalog.py in a disposable copy ('[Step([\"nmap\", \"--script\", \"broadcast-dhcp-discover\", \"-e\", ' -> '[Step([\"nmap\", \"--script\", \"broadcast-dns-service-discovery\"'); test_dhcp_check_finds_the_dhcp_server failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-LIVE.log",
        "sha256": "d9d1503d7668845e6fdb3b4fc1dd3c26a37160a610e67042b77a5c5089125276"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": {
        "mutation": "src/netdeck/catalog.py: '[Step([\"nmap\", \"--script\", \"broadcast-dhcp-discover\", \"-e\", p[\"iface\"]],' -> '[Step([\"nmap\", \"--script\", \"broadcast-dns-service-discovery\", \"-e\", p[\"iface\"]],'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "no DHCP server answered",
        "observed_diagnostic": "no DHCP server answered",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "c5f92db28614c2f80719509f161931f8dcc5718b054dab7da543b8d71e786f58"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RD-FK-LIVE2",
      "acceptance": [
        "AC-FK-LIVE"
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
        "tests/test_field_live.py::test_mtu_test_passes_at_1472_and_reports_fragmentation_at_1500"
      ],
      "method": "Mutated src/netdeck/catalog.py in a disposable copy ('[\"ping\", \"-M\", \"do\", \"-s\",' -> '[\"ping\", \"-s\",'); test_mtu_test_passes_at_1472_and_reports_fragmentation_at_1500 failed with the expected diagnostic; original byte-identical and green again.",
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
        "path": "docs/delivery/field-kit/reports/drills/RD-FK-LIVE2.log",
        "sha256": "f2dd73539714c47c803401816bc32b4bda539c6ae7a423c94115124ac2a355ef"
      },
      "inputs": [
        {
          "path": "CHANGELOG.md",
          "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
        },
        {
          "path": "README.md",
          "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
        },
        {
          "path": "pyproject.toml",
          "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
        },
        {
          "path": "scripts/install.sh",
          "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
        },
        {
          "path": "src/netdeck/catalog.py",
          "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
        },
        {
          "path": "src/netdeck/probes.py",
          "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
        },
        {
          "path": "src/netdeck/static/app.js",
          "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
        },
        {
          "path": "src/netdeck/sysinfo.py",
          "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
        },
        {
          "path": "src/netdeck/validators.py",
          "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
        },
        {
          "path": "tests/test_catalog.py",
          "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
        },
        {
          "path": "tests/test_field_live.py",
          "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
        },
        {
          "path": "tests/test_fieldkit.py",
          "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
        }
      ],
      "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
      "red": {
        "mutation": "src/netdeck/catalog.py: '[\"ping\", \"-M\", \"do\", \"-s\",' -> '[\"ping\", \"-s\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "a 1528-byte packet passed with fragmentation forbidden",
        "observed_diagnostic": "a 1528-byte packet passed with fragmentation forbidden",
        "before": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ],
        "mutated": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "e2797cf7a002e5c3789955ce190ade99f1a7b71c1aeddb13331192252a895b5d"
          }
        ],
        "after": [
          {
            "path": "src/netdeck/catalog.py",
            "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "389a221ceb64e79f0369a25f444c2919d8e0d4863d4eb702ee77e110e9bf06dc",
    "inputs": [
      {
        "path": "CHANGELOG.md",
        "sha256": "bc84c671806c488e20f4c4d230cd06c0b9f080e5895bfdfed98049f244948e50"
      },
      {
        "path": "CONTRIBUTING.md",
        "sha256": "0460467256f328b75238576f5b76b5c16bdc1780393abf6ecb66df6195af8108"
      },
      {
        "path": "README.md",
        "sha256": "bdf2fbb8430e7cafa22e78216a7ea7c849c91af2d4393fe37aac4059e553f712"
      },
      {
        "path": "pyproject.toml",
        "sha256": "24d2759b7889d789609aae1822a2e3bb67baec046e7c7f92460b693d2081f745"
      },
      {
        "path": "scripts/install.sh",
        "sha256": "f9f62914b8f0c1d85a2a61be2a2d86e4080567442d58c378356887248562c2c8"
      },
      {
        "path": "src/netdeck/catalog.py",
        "sha256": "ac64d87b2f64b53e9aa6fd87e5f79329558b30931d69f7d4eff7a90e08f7becf"
      },
      {
        "path": "src/netdeck/probes.py",
        "sha256": "ff4de18002f73f8c75de3e327603f65cf4a3cc455df5fe7978a32114f06b3e49"
      },
      {
        "path": "src/netdeck/static/app.js",
        "sha256": "4ce670fa725d55538bc4c4455fa10b1a8c3fe643efe5045dfdd2b6974892eccb"
      },
      {
        "path": "src/netdeck/sysinfo.py",
        "sha256": "2f7a08414c900ce249cfde81c4eeb8e08f83f6ccd9a816248f856d3d736cbc34"
      },
      {
        "path": "src/netdeck/validators.py",
        "sha256": "cceded1d744225a783cd94a6613868c3e15cec750377d8b82b09511881f42721"
      },
      {
        "path": "tests/test_catalog.py",
        "sha256": "414c519e8c8bca04e378a41fea85ad70ed87ff42944f09995697dd68deaa48a1"
      },
      {
        "path": "tests/test_field_live.py",
        "sha256": "debe2e34cafc28f5abb46c21738999dda96da23a254634277918a8c341322835"
      },
      {
        "path": "tests/test_fieldkit.py",
        "sha256": "40e15d910e94af899118b7d0a56faa4f808a52885e1cc763e8f3d08858577c42"
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
      "TASK-FK-DECK",
      "TASK-FK-DOCS"
    ],
    "pending_operations": [
      {
        "id": "OP-FK-CI",
        "description": "CI has not run the field-kit changes yet.",
        "next_action": "Push and confirm CI passes; record the outcome."
      }
    ],
    "next_action": "Push, observe OP-FK-CI, then upgrade the installed NetDeck with the installer.",
    "source_revision": "ffb643a + uncommitted WORK-FIELD-KIT changes"
  }
}
```
