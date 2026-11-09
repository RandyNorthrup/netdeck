"""Upgrading with scripts/install.sh while NetDeck runs: stop what belongs to the install, restart it after.

Each install builds a virtualenv, so these tests are opt-in: NETDECK_TEST_INSTALL=1 (set in CI's install job).
Everything happens in an isolated $HOME, runtime directory and port; `systemctl` is a stub that records calls.
"""

import glob
import json
import os
import pathlib
import socket
import subprocess
import sys
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.environ.get("NETDECK_TEST_INSTALL") != "1",
                                reason="builds virtualenvs; set NETDECK_TEST_INSTALL=1")

SYSTEMCTL_STUB = """#!/bin/sh
echo "$*" >> "$STUB_LOG"
case "$*" in
  *is-active*) [ -f "$STUB_ACTIVE" ] && exit 0; exit 3 ;;
  *stop*) rm -f "$STUB_ACTIVE" ;;
  *start*) touch "$STUB_ACTIVE" ;;
esac
exit 0
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    run = home / "run"
    run.mkdir(mode=0o700)
    stub_dir = home / "stub-bin"
    stub_dir.mkdir()
    (stub_dir / "systemctl").write_text(SYSTEMCTL_STUB)
    (stub_dir / "systemctl").chmod(0o755)
    (home / ".config" / "netdeck").mkdir(parents=True)
    (home / ".config" / "netdeck" / "config.json").write_text(json.dumps({"port": free_port()}))
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "PYTHONPATH")}
    environment.update(
        HOME=str(home), XDG_RUNTIME_DIR=str(run),
        PATH=f"{stub_dir}:{home}/.local/bin:{os.environ['PATH']}",
        PIP_CACHE_DIR=os.path.expanduser("~/.cache/pip"),  # reuse the real cache: installs stay fast
        STUB_LOG=str(home / "systemctl.log"), STUB_ACTIVE=str(home / "service-active"),
    )
    first = install(environment)
    assert first.returncode == 0, first.stdout + first.stderr
    yield environment
    stop_everything(environment)


def install(env):
    return subprocess.run(["bash", str(REPO / "scripts" / "install.sh")], env=env, capture_output=True,
                          text=True, timeout=900)


def netdeck_bin(env) -> str:
    return os.path.join(env["HOME"], ".local", "bin", "netdeck")


def alive(pid) -> bool:
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def registered_pid(env):
    """Pid of the NetDeck the runtime directory points at, if it is alive and answering."""
    result = subprocess.run([netdeck_bin(env), "url"], env=env, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return None
    with open(os.path.join(env["XDG_RUNTIME_DIR"], "netdeck", "instance.json"), encoding="utf-8") as fh:
        return int(json.load(fh)["pid"])


def wait_registered(env, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pid = registered_pid(env)
        if pid:
            return pid
        time.sleep(0.2)
    raise AssertionError("NetDeck never came up")


def start_detached(env, argv, extra_env=None):
    # setsid -f, as real launches: the server is reaped by init, not left as a zombie of this test.
    subprocess.run(["setsid", "-f", *argv], env=dict(env, **(extra_env or {})), check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wait_registered(env)


def stop_everything(env):
    for _ in range(3):
        pid = registered_pid(env)
        if not pid:
            return
        subprocess.run([netdeck_bin(env), "stop"], env=env, capture_output=True, timeout=60)


def installed_server_mtime(env) -> float:
    pattern = os.path.join(env["HOME"], ".local/share/netdeck/venv/lib/python*/site-packages/netdeck/server.py")
    return os.stat(glob.glob(pattern)[0]).st_mtime


def cmdline(pid):
    with open(f"/proc/{pid}/cmdline", "rb") as fh:
        return [a.decode() for a in fh.read().split(b"\0") if a]


@pytest.fixture
def clean(env):
    stop_everything(env)
    pathlib.Path(env["STUB_ACTIVE"]).unlink(missing_ok=True)
    pathlib.Path(env["STUB_LOG"]).unlink(missing_ok=True)
    yield env
    stop_everything(env)
    pathlib.Path(env["STUB_ACTIVE"]).unlink(missing_ok=True)


def test_upgrade_restarts_a_running_installed_netdeck(clean):
    env = clean
    old = start_detached(env, [netdeck_bin(env), "serve", "--no-browser"])
    result = install(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not alive(old), "old NetDeck still running after upgrade"
    new = registered_pid(env)
    assert new is not None, "no NetDeck running after upgrade"
    assert new != old
    assert os.stat(f"/proc/{new}").st_mtime > installed_server_mtime(env), "restarted NetDeck runs the old code"
    assert "--no-browser" in cmdline(new), "restart without a display must not open a browser"
    assert "Restarted NetDeck" in result.stdout


def test_upgrade_with_nothing_running_starts_nothing(clean):
    env = clean
    assert registered_pid(env) is None
    result = install(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert registered_pid(env) is None, "installer started NetDeck although none was running"


def test_upgrade_leaves_a_netdeck_from_elsewhere_alone(clean):
    env = clean
    source = start_detached(env, [sys.executable, "-m", "netdeck", "serve", "--no-browser"],
                            {"PYTHONPATH": str(REPO / "src")})
    result = install(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert alive(source), "foreign NetDeck was stopped"
    assert registered_pid(env) == source, "foreign NetDeck was replaced"


def test_upgrade_restarts_the_user_service_through_systemd(clean):
    env = clean
    pathlib.Path(env["STUB_ACTIVE"]).touch()
    result = install(env)
    assert result.returncode == 0, result.stdout + result.stderr
    log = pathlib.Path(env["STUB_LOG"])
    calls = log.read_text().splitlines() if log.exists() else []  # no log: systemctl was never called
    assert "--user stop netdeck.service" in calls, "service was not stopped"
    assert "--user start netdeck.service" in calls, "service was not started again"
    assert calls.index("--user stop netdeck.service") < calls.index("--user start netdeck.service")
    out = result.stdout
    assert out.index("Stopping the NetDeck service") < out.index("Installing NetDeck into"), \
        "service was not stopped before installing"
    assert registered_pid(env) is None, "a separate NetDeck was started next to the service"
