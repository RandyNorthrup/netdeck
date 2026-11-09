.PHONY: dev run test lint check build clean install uninstall

PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

dev:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e '.[dev]'

run:
	PYTHONPATH=src $(PY) -m netdeck serve --port 8799 --log-level DEBUG

test:
	PYTHONPATH=src $(PY) -m pytest -q

lint:
	ruff check src tests
	shellcheck scripts/*.sh
	node --check src/netdeck/static/app.js
	node --check src/netdeck/static/theme.js

check: lint test

build:
	$(PY) -m build

install:
	./scripts/install.sh

uninstall:
	./scripts/uninstall.sh

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
