# Contributing to NetDeck

Thanks for helping! Bug reports, new tools, UI polish and documentation are all welcome.

## Getting started

```bash
git clone https://github.com/randynorthrup/netdeck.git && cd netdeck
make dev     # .venv with pytest + ruff
make run     # starts NetDeck from source on port 8799 with debug logging
```

Edit files under `src/netdeck/` — the UI (`static/`) is plain HTML/CSS/JS with no build step; reload the
browser to see changes. Python changes need a restart of `make run`.

## Before opening a pull request

```bash
make lint    # ruff, shellcheck, node --check
make test    # pytest
```

- Keep the **zero-dependency** promise: standard library only at runtime, no CDN assets.
- **Never** build shell strings. Tools are argv lists, and every new parameter kind needs a validator and tests.
- New tools need a summary sentence, sensible defaults and install hints in `PACKAGES` (see
  [docs/ADDING_TOOLS.md](docs/ADDING_TOOLS.md)). `tests/test_catalog.py` checks every tool automatically.
- UI changes: check dark and light themes and a narrow (phone) window; attach before/after screenshots.
- Write commit messages in the imperative mood ("Add vnStat view") and keep PRs focused.

## Reporting bugs

Open an issue with your distribution, `netdeck --version`, the output of `netdeck doctor`, and what you
expected vs. what happened. Security issues: see [SECURITY.md](SECURITY.md) — please report privately.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE) and to follow
our [Code of Conduct](CODE_OF_CONDUCT.md).
