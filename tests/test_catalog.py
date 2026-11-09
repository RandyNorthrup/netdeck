"""Every tool must build a safe argv from its defaults — no shell strings, no stray options."""

import pytest

from netdeck import validators
from netdeck.catalog import CATEGORIES, GUI, PACKAGES, STREAM, TERMINAL, TOOLS, TOOLS_BY_ID, Internal, Step

SAMPLE = {
    "host": "example.com", "hosts": "1.1.1.1 8.8.8.8", "target": "192.168.1.0/24", "ip": "192.168.1.1",
    "cidr": "10.0.0.0/24", "url": "https://example.com", "iface": "lo", "ports": "22,80", "port": "443",
    "rate": "10M", "expr": "port 53",
}


def sample_params(tool):
    raw = {}
    for p in tool.params:
        if p.required or p.default is None:
            raw[p.name] = SAMPLE.get(p.kind) if p.kind not in ("bool", "choice", "int") else p.default
    clean = {p.name: validators.validate(p, raw.get(p.name)) for p in tool.params}
    clean.update(_elevated=False, _user="tester")
    return clean


def test_ids_unique_and_categories_valid():
    assert len(TOOLS_BY_ID) == len(TOOLS)
    cats = {c.id for c in CATEGORIES}
    for tool in TOOLS:
        assert tool.category in cats, tool.id
        assert tool.mode in (STREAM, TERMINAL, GUI)
        assert tool.summary.endswith("."), f"{tool.id}: summary should be a sentence"


def test_every_category_has_tools():
    used = {t.category for t in TOOLS}
    assert used == {c.id for c in CATEGORIES}


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.id)
def test_builds_argv_lists(tool, monkeypatch, tmp_path):
    monkeypatch.setenv("NETDECK_CAPTURES_DIR", str(tmp_path))
    monkeypatch.setattr(validators, "SYS_NET", "/nonexistent")  # accept any interface name
    params = sample_params(tool)
    plan = tool.plan(params)
    assert plan.steps
    for step in plan.steps:
        if isinstance(step, Internal):
            assert tool.binary is None
            continue
        assert isinstance(step, Step)
        assert all(isinstance(a, str) for a in step.argv), step.argv
        assert step.argv[0] == tool.binary or step.argv[0] in ("ip", "ss", "nmcli", "dig", "curl"), step.argv
        assert not any(a == "" for a in step.argv), step.argv


def test_user_values_never_parsed_as_options(monkeypatch):
    """Host-like values must come after '--' or be validated against a leading dash."""
    tool = TOOLS_BY_ID["ping"]
    argv = tool.plan(sample_params(tool)).steps[0].argv
    assert argv[-2:] == ["--", "example.com"]


def test_conditional_privilege():
    scan = TOOLS_BY_ID["nmap-scan"]
    base = sample_params(scan)
    assert scan.needs_root(dict(base, scan="syn")) or __import__("os").geteuid() == 0
    assert not scan.needs_root(dict(base, scan="connect"))


def test_capture_file_artifact(monkeypatch, tmp_path):
    monkeypatch.setenv("NETDECK_CAPTURES_DIR", str(tmp_path))
    monkeypatch.setattr(validators, "SYS_NET", "/nonexistent")
    tool = TOOLS_BY_ID["tcpdump-file"]
    plan = tool.plan(dict(sample_params(tool), _elevated=True, _user="alice"))
    assert plan.artifact and plan.artifact.startswith(str(tmp_path))
    argv = plan.steps[0].argv
    assert argv[argv.index("-Z"):argv.index("-Z") + 2] == ["-Z", "alice"]


def test_package_hints_cover_binaries():
    missing = {t.binary for t in TOOLS if t.binary and t.binary not in PACKAGES and t.binary not in ("ipscan",)}
    assert not missing, f"add install hints for: {sorted(missing)}"
