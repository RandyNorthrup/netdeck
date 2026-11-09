# Readiness addendum — WORK-FIELD-KIT

`README.md` (brief) changed after EV-FK-READY-1: tool table, counts and a *Field kit* section (hardware and the
field self-test) now describe the delivered tools. Requirements and acceptance are unchanged.

Implementation findings that changed the design, not the requirements:
- A drill baseline showed the DHCP check can miss on Wi-Fi (one lost broadcast; 8/8 direct retries answered).
  The tool now sends two independent requests, which also helps catch a rogue server that answers only
  sometimes. Live DHCP test then passed 3/3 and in the full live run.
- Two drills first failed for the right reason but with unmatched diagnostics (pytest's `assert (2 == 1)`
  formatting; an unlabelled MTU assertion). The patterns/messages were corrected, not the expectations.

Result: still ready.
