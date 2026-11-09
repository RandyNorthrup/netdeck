"""UniFi tools: exact commands, elevation, validation, and the inform check against local fake servers."""

import http.server
import os
import socket
import threading

import pytest

from netdeck import probes, validators
from netdeck.catalog import SSH_FRESH_KEY, TOOLS_BY_ID
from test_fieldkit import build

EXPECTED = [
    ("unifi-discover", {"target": "10.0.0.0/24"},
     [["nmap", "-sU", "-p", "10001", "--script", "ubiquiti-discovery", "--open", "-T4", "--", "10.0.0.0/24"]]),
    ("unifi-adopt", {"device": "10.0.0.20", "controller": "10.0.0.1"},
     [["ssh", "-t", "-p", "22", "--", "ubnt@10.0.0.20", "mca-cli-op", "set-inform", "http://10.0.0.1:8080/inform"]]),
    ("unifi-adopt", {"device": "fd00::20", "controller": "fd00::1", "user": "admin", "fresh_key": True,
                     "inform_port": 8081, "port": 2222},
     [["ssh", "-t", "-p", "2222", *SSH_FRESH_KEY, "--", "admin@fd00::20", "mca-cli-op", "set-inform",
       "http://[fd00::1]:8081/inform"]]),
    ("unifi-info", {"device": "10.0.0.20"}, [["ssh", "-t", "-p", "22", "--", "ubnt@10.0.0.20", "mca-cli-op", "info"]]),
    ("unifi-controller", {"host": "10.0.0.1"}, [["xdg-open", "https://10.0.0.1"]]),
    ("unifi-controller", {"host": "unifi.lan", "kind": "legacy"}, [["xdg-open", "https://unifi.lan:8443"]]),
    ("unifi-controller", {"host": "fd00::1"}, [["xdg-open", "https://[fd00::1]"]]),
]


@pytest.fixture(autouse=True)
def lenient_devices(monkeypatch):
    monkeypatch.setattr(validators, "SYS_NET", "/nonexistent")


@pytest.mark.parametrize(("tool_id", "params", "argvs"), EXPECTED, ids=[f"{e[0]}-{i}" for i, e in enumerate(EXPECTED)])
def test_unifi_tool_commands(tool_id, params, argvs):
    tool, _, built = build(tool_id, **params)
    assert tool.category == "unifi"
    assert built == argvs


def test_unifi_modes_and_elevation():
    modes = {t: TOOLS_BY_ID[t].mode for t in ("unifi-discover", "unifi-inform", "unifi-adopt", "unifi-info",
                                                  "unifi-controller")}
    assert modes == {"unifi-discover": "stream", "unifi-inform": "stream", "unifi-adopt": "terminal",
                     "unifi-info": "terminal", "unifi-controller": "gui"}
    if os.geteuid() == 0:
        pytest.skip("everything runs unelevated as root")
    for tool_id, params, elevated in (("unifi-discover", {"target": "10.0.0.0/24"}, True),
                                      ("unifi-adopt", {"device": "10.0.0.2", "controller": "10.0.0.1"}, False),
                                      ("unifi-info", {"device": "10.0.0.2"}, False)):
        tool, clean, _ = build(tool_id, **params)
        assert tool.needs_root(clean) is elevated, tool_id


@pytest.mark.parametrize(("field", "bad"), [("device", "-oProxyCommand=x"), ("device", "10.0.0.2;reboot"),
                                            ("controller", "x y"), ("controller", "$(id)"), ("user", "-l")])
def test_unifi_adopt_rejects_unsafe_values(field, bad):
    params = {"device": "10.0.0.2", "controller": "10.0.0.1", field: bad}
    with pytest.raises(validators.ValidationError):
        build("unifi-adopt", **params)


# -- inform check ------------------------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    status, body = 400, b""

    def do_GET(self):
        self.server.paths.append((self.path, self.headers.get("Host")))
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


def _serve(status, body, family=socket.AF_INET, host="127.0.0.1"):
    handler = type("H", (_Handler,), {"status": status, "body": body})
    server_cls = type("S", (http.server.HTTPServer,), {"address_family": family})
    server = server_cls((host, 0), handler)
    server.paths = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def inform(host, port):
    lines = []
    code = probes.unifi_inform({"controller": host, "port": port}, lines.append, threading.Event())
    return code, "\n".join(lines)


def test_inform_check_recognises_the_unifi_endpoint():
    server = _serve(400, b"")
    try:
        code, out = inform("127.0.0.1", server.server_port)
    finally:
        server.shutdown()
    assert code == 0, out
    assert "UniFi inform endpoint answers" in out
    assert f"set-inform http://127.0.0.1:{server.server_port}/inform" in out
    assert server.paths == [("/inform", f"127.0.0.1:{server.server_port}")]


@pytest.mark.parametrize(("status", "body"), [(200, b"<html>router login</html>"), (400, b"<html>Bad Request</html>"),
                                              (404, b"")])
def test_inform_check_rejects_other_web_servers(status, body):
    server = _serve(status, body)
    try:
        code, out = inform("127.0.0.1", server.server_port)
    finally:
        server.shutdown()
    assert code == 1, out
    assert f"not like a UniFi inform endpoint (HTTP {status}" in out


def test_inform_check_reports_nothing_listening():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]  # bound but not listening: connections are refused
        code, out = inform("127.0.0.1", port)
    assert code == 1
    assert "refuses port" in out and "no UniFi controller is listening" in out


def test_inform_check_reports_a_non_http_service():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()

        def garbage():
            for _ in range(2):  # the TCP probe, then the HTTP request
                conn, _ = listener.accept()
                with conn:
                    conn.sendall(b"SSH-2.0-dropbear\r\n")

        threading.Thread(target=garbage, daemon=True).start()
        code, out = inform("127.0.0.1", listener.getsockname()[1])
    assert code == 1
    assert "does not speak HTTP" in out


def test_inform_check_over_ipv6():
    if not socket.has_ipv6:
        pytest.skip("no IPv6")
    try:
        server = _serve(400, b"", socket.AF_INET6, "::1")
    except OSError:
        pytest.skip("IPv6 loopback unavailable")
    try:
        code, out = inform("::1", server.server_port)
    finally:
        server.shutdown()
    assert code == 0, out
    assert f"http://[::1]:{server.server_port}/inform" in out
    assert server.paths == [("/inform", f"[::1]:{server.server_port}")]


def test_inform_check_unresolvable_name():
    code, out = inform("no-such-controller.invalid", 8080)
    assert code == 2 and "Could not resolve" in out
