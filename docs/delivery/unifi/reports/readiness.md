# Readiness review — WORK-UNIFI (scope revision 1)

Reviewed 2026-11-09 at 33d6e00. Requirements only; not evidence of behavior. Recorded after the first
implementation pass (the criteria come from the pre-implementation probes in the plan rationale); all behavior
evidence below is produced after this review.

- **Clarity:** every criterion names an observable: exact argv/category/mode/elevation, validator rejection,
  probe exit codes and messages against local fake servers, and live API outcomes on this laptop's network
  (UniFi console at 10.10.11.1, known unadopted and adopted devices on 10.10.11.0/24).
- **Failure behavior:** the inform check distinguishes refused, timed-out, non-HTTP, wrong-HTTP and
  unresolvable cases, each with its own message and a non-zero exit. Discovery on a network without UniFi
  completes with exit 0 and no devices; the live test only requires devices when a controller is named.
- **Scope / non-goals:** no destructive device commands, no stored credentials, no controller API. SSH tools
  are interactive (password typed by the user) and are verified to the exact command only; the user's
  unadopted bridge is not logged into.
- **Rules:** catalog entries on the argv/validator path, no shell strings; remote arguments after the SSH
  destination are built only from validated hosts and ports. Install hint added for `xdg-open`.
- **Safety:** discovery and inform traffic target only the user's own LAN during tests.

Result: ready.
