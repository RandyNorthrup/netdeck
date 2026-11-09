"""Process-level shutdown: a real `python -m netdeck serve` stopped by each supported path."""

import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

import pytest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")

pytestmark = pytest.mark.skipif(shutil.which("ping") is None, reason="needs ping for a long-running job")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def env(tmp_path):
    run = tmp_path / "run"
    run.mkdir(mode=0o700)
    return dict(os.environ, PYTHONPATH=SRC, XDG_RUNTIME_DIR=str(run), XDG_CONFIG_HOME=str(tmp_path / "cfg"),
                NETDECK_CAPTURES_DIR=str(tmp_path / "captures"), PYTHONUNBUFFERED="1")


def instance_path(env) -> str:
    return os.path.join(env["XDG_RUNTIME_DIR"], "netdeck", "instance.json")


def netdeck(env, *args, **kwargs):
    return subprocess.run([sys.executable, "-m", "netdeck", *args], env=env, capture_output=True, text=True,
                          timeout=60, **kwargs)


def start_server(env, tmp_path):
    port = free_port()
    log = open(tmp_path / "server.log", "w")  # noqa: SIM115 - closed by the caller via proc.log
    proc = subprocess.Popen([sys.executable, "-m", "netdeck", "serve", "--no-browser", "--port", str(port)],
                            env=env, stdout=log, stderr=subprocess.STDOUT)
    proc.log = log
    for _ in range(100):
        if os.path.exists(instance_path(env)):
            break
        time.sleep(0.1)
    with open(instance_path(env), encoding="utf-8") as fh:
        token = json.load(fh)["url"].split("token=")[1]
    return proc, port, token


def api(port, token, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": f"127.0.0.1:{port}", "Cookie": f"netdeck_{port}={token}"}
    if body is not None:
        headers.update({"Content-Type": "application/json", "X-NetDeck": "1"})
        body = json.dumps(body)
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, json.loads(data or b"{}")


def ping_pids(marker: int):
    """Pids of ping processes carrying our unique packet size."""
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as fh:
                argv = fh.read().split(b"\0")
        except OSError:
            continue
        if argv and os.path.basename(argv[0]) == b"ping" and str(marker).encode() in argv:
            pids.append(int(entry))
    return pids


@pytest.mark.parametrize("trigger", ["exit-button-api", "netdeck-stop", "ctrl-c"])
def test_every_shutdown_path_stops_jobs_and_cleans_up(env, tmp_path, trigger):
    proc, port, token = start_server(env, tmp_path)
    try:
        marker = 1000 + os.getpid() % 1000  # unusual packet size identifies our ping
        status, _ = api(port, token, "POST", "/api/run",
                        {"tool": "ping", "params": {"host": "127.0.0.1", "count": 0, "interval": "2",
                                                    "size": marker}})
        assert status == 200
        for _ in range(50):
            if ping_pids(marker):
                break
            time.sleep(0.1)
        assert ping_pids(marker), "precondition: the ping job never started"

        if trigger == "exit-button-api":
            status, data = api(port, token, "POST", "/api/shutdown", {})
            assert status == 202 and data["ok"] is True
        elif trigger == "netdeck-stop":
            result = netdeck(env, "stop")
            assert result.returncode == 0, result.stderr
            assert "Stopped NetDeck" in result.stdout
            assert proc.poll() is not None, "netdeck stop returned before the server exited"
        else:
            proc.send_signal(signal.SIGINT)

        assert proc.wait(timeout=15) == 0
        assert ping_pids(marker) == [], "the ping job outlived NetDeck"
        assert not os.path.exists(instance_path(env)), "instance.json was left behind"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.log.close()
    assert "NetDeck stopped." in (tmp_path / "server.log").read_text()


def test_stop_removes_a_stale_instance_file(env):
    dead = subprocess.Popen(["true"])
    dead.wait()
    os.makedirs(os.path.dirname(instance_path(env)), mode=0o700, exist_ok=True)
    with open(instance_path(env), "w", encoding="utf-8") as fh:
        json.dump({"pid": dead.pid, "port": free_port(), "url": "http://127.0.0.1:1/?token=x"}, fh)
    result = netdeck(env, "stop")
    assert result.returncode == 0
    assert "not running" in result.stdout
    assert not os.path.exists(instance_path(env)), "stale instance.json was not removed"


def test_stop_when_nothing_is_running(env):
    result = netdeck(env, "stop")
    assert result.returncode == 0
    assert "not running" in result.stdout
