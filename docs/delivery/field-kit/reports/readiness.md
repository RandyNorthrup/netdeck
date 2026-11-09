# Readiness review — WORK-FIELD-KIT (scope revision 1)

Reviewed 2026-11-08 at ffb643a (clean tree). Requirements only; not evidence of behavior.

- **Clarity:** each criterion names an observable: exact argv/category/elevation, validator accept/reject sets,
  interface classification from a fake sysfs, and live outcomes on this laptop's LAN (gateway 10.10.11.1 runs
  dnsmasq, so DHCP discovery has a known server to find; SNMP uses a temporary local agent because the gateway
  has none).
- **Failure behavior:** LLDP/CDP capture is bounded by `timeout` (frames arrive every 30–60 s only on wired
  switch ports; on Wi-Fi none arrive and the tool must still end cleanly). MTU test must report the
  fragmentation error, not hang. Duplicate-IP check exits non-zero when a reply arrives — that is the finding.
- **Scope / non-goals:** no live tests that need the USB Ethernet adapter, console cable or Alfa card; never
  toggle monitor mode on the built-in Broadcom card. Ookla speedtest and Kismet are not added (user decision
  pending). `lldpd` is not enabled: it would announce this laptop on client networks.
- **Rules:** catalog entries on the existing argv/validator path, no shell strings, `timeout` used as a
  plain argv prefix; install hints for every new binary (enforced by tests/test_catalog.py).
- **Safety:** scans and broadcasts target only the user's own LAN during tests; device-access tools only open
  a session the user drives.

Result: ready.
