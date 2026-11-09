# Outcome for b7caf17 (resolves OP-UPG-CI)

**CI:** run https://github.com/RandyNorthrup/netdeck/actions/runs/42571314761 — success. The install job ran
`tests/test_install.py` with `NETDECK_TEST_INSTALL=1`: 4 collected, 4 passed (no skips).

**Real upgrade on the development machine (Arch, Hyprland session):** NetDeck from the user install was
running (pid 72333). Re-running `scripts/install.sh` printed "Stopping the running NetDeck (pid 72333) for
the upgrade" before "Installing NetDeck into …", then "Restarted NetDeck with the new version". Afterwards pid
72333 was gone and the registered instance (pid 72414) had started after the new `server.py` was written; with
a graphical session present it was started without `--no-browser` and opened its window.
