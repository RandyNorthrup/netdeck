# CI outcome for 503fd9a (resolves OP-CI-FIRST-RUN)

Run https://github.com/RandyNorthrup/netdeck/actions/runs/42567594775 — conclusion **success**.

| Job | Result |
| --- | --- |
| lint, build, install | passed |
| test (3.10, 3.11, 3.12, 3.13, 3.14) | passed |

The test jobs ran with `NETDECK_REQUIRE_E2E=1`; the 3.10 and 3.14 logs both report `131 passed` with no
skips, so the headless-Chrome browser tests and the ping-based process shutdown tests executed on the runner.
