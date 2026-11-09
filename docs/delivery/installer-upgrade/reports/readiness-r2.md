# Readiness addendum — WORK-INSTALLER-UPGRADE

The brief (`README.md`) changed after EV-UPG-READY-1: its Install section now documents upgrading (stop owned
NetDeck, restart afterwards, service restarted through systemd, source-checkout instances left alone). This
describes the planned behavior exactly; requirements and acceptance are unchanged. Implementation refined one
test only: the systemd test treats a missing stub log as "no calls" (RD-UPG-4 first failed with
FileNotFoundError instead of the named assertion). Result: still ready.
