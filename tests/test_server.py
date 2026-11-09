"""HTTP-level tests: authentication, DNS-rebinding and CSRF protection, job lifecycle."""

import http.client
import json
import socket
import sys
import threading
import time

import pytest

from netdeck.catalog import Step, Tool
from netdeck.config import Config
from netdeck.server import App, make_server

TOKEN = "test-token-123"


@pytest.fixture(scope="module")
def server():
    app = App(Config(), TOKEN, 0)
    srv = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    app.shutdown.set()
    app.jobs.shutdown()
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, body=None, headers=None, cookie=True, host=None):
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    hdrs = {"Host": host or f"127.0.0.1:{port}"}
    if cookie:
        hdrs["Cookie"] = f"netdeck_{port}={TOKEN}"
    if body is not None:
        hdrs["Content-Type"] = "application/json"
        hdrs["X-NetDeck"] = "1"
        body = json.dumps(body)
    hdrs.update(headers or {})
    conn.request(method, path, body=body, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp, data


def test_requires_auth(server):
    resp, _ = request(server, "GET", "/api/meta", cookie=False)
    assert resp.status == 401


def test_rejects_foreign_host(server):
    resp, _ = request(server, "GET", "/api/meta", host="evil.example:80")
    assert resp.status == 421


def test_post_requires_custom_header(server):
    resp, _ = request(server, "POST", "/api/run", headers={"Content-Type": "application/json"})
    assert resp.status == 403


def test_post_rejects_cross_origin(server):
    resp, _ = request(server, "POST", "/api/preview", body={"tool": "ping"}, headers={"Origin": "http://evil.example"})
    assert resp.status == 403


def test_token_login_sets_cookie(server):
    resp, _ = request(server, "GET", f"/?token={TOKEN}", cookie=False)
    assert resp.status == 302
    cookie = resp.getheader("Set-Cookie")
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    resp, _ = request(server, "GET", "/?token=wrong", cookie=False)
    assert resp.status == 401


def test_security_headers(server):
    resp, _ = request(server, "GET", "/api/meta")
    assert "default-src 'self'" in resp.getheader("Content-Security-Policy")
    assert resp.getheader("X-Frame-Options") == "DENY"


def test_static_no_traversal(server):
    resp, _ = request(server, "GET", "/static/../server.py")
    assert resp.status == 404


def test_tools_catalog(server):
    resp, data = request(server, "GET", "/api/tools")
    payload = json.loads(data)
    assert resp.status == 200
    assert {"categories", "tools"} <= payload.keys()
    assert any(t["id"] == "tcp-check" and t["installed"] for t in payload["tools"])


def test_preview_validation(server):
    _, data = request(server, "POST", "/api/preview", body={"tool": "ping", "params": {"host": "-oBad"}})
    assert "host" in json.loads(data)["errors"]
    body = {"tool": "ping", "params": {"host": "127.0.0.1", "count": 2}}
    _, data = request(server, "POST", "/api/preview", body=body)
    assert json.loads(data)["commands"][0].startswith("ping -c 2")


def test_run_unknown_tool(server):
    resp, _ = request(server, "POST", "/api/run", body={"tool": "rm-rf"})
    assert resp.status == 404


def test_builtin_job_lifecycle(server):
    """Run the pure-Python TCP probe against our own listening port and read its output."""
    port = server.server_address[1]
    resp, data = request(server, "POST", "/api/run",
                         body={"tool": "tcp-check", "params": {"host": "127.0.0.1", "port": port, "count": 1}})
    assert resp.status == 200, data
    job_id = json.loads(data)["job"]["id"]
    for _ in range(50):
        _, data = request(server, "GET", f"/api/jobs/{job_id}")
        if json.loads(data)["status"] != "running":
            break
        time.sleep(0.1)
    assert json.loads(data)["status"] == "done"
    resp, text = request(server, "GET", f"/api/jobs/{job_id}/output")
    assert "✓ open" in text.decode()
    assert "attachment" in resp.getheader("Content-Disposition")
    resp, _ = request(server, "DELETE", f"/api/jobs/{job_id}", body={})
    assert resp.status == 200


# -- shutdown -----------------------------------------------------------------------------------

@pytest.fixture
def stoppable():
    """A server owned by one test, wired like `netdeck serve` so it can really stop."""
    app = App(Config(), TOKEN, 0)
    srv = make_server("127.0.0.1", 0, app)
    app.on_shutdown = lambda: threading.Thread(target=srv.shutdown, daemon=True).start()
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    thread.start()
    yield srv, thread
    app.request_shutdown("test teardown")
    app.close()
    thread.join(5)
    srv.server_close()


@pytest.mark.parametrize("variant", ["no-cookie", "no-header", "foreign-origin"])
def test_shutdown_refuses_unauthenticated_or_cross_origin(stoppable, variant):
    srv, thread = stoppable
    kwargs = {
        "no-cookie": {"cookie": False, "body": {}},
        "no-header": {"headers": {"Content-Type": "application/json"}},
        "foreign-origin": {"body": {}, "headers": {"Origin": "http://evil.example"}},
    }[variant]
    resp, _ = request(srv, "POST", "/api/shutdown", **kwargs)
    assert resp.status in (401, 403)
    assert not srv.app.shutdown.is_set()
    resp, _ = request(srv, "GET", "/api/ping")
    assert resp.status == 200
    assert thread.is_alive()


def test_shutdown_endpoint_stops_the_server(stoppable):
    srv, thread = stoppable
    resp, data = request(srv, "POST", "/api/shutdown", body={})
    assert resp.status == 202
    assert json.loads(data)["ok"] is True
    thread.join(3)
    assert not thread.is_alive(), "serve_forever is still running"
    assert srv.app.shutdown.is_set()


def open_stream(srv, path):
    port = srv.server_address[1]
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall((f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                  f"Cookie: netdeck_{port}={TOKEN}\r\nAccept: text/event-stream\r\n\r\n").encode())
    sock.settimeout(0.2)
    return sock


def read_stream(sock, until=None, timeout=5.0):
    """Read until `until` appears or the server closes the stream. Returns (data, closed)."""
    data, end = b"", time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            chunk = sock.recv(65536)
        except TimeoutError:
            continue
        if not chunk:
            return data, True
        data += chunk
        if until and until in data:
            return data, False
    return data, False


def test_streams_say_bye_and_close_on_shutdown(stoppable):
    """A job that goes silent: only the shutdown wake-up can end the stream's 15 s wait early."""
    srv, _ = stoppable
    quiet = Tool("quiet", "Quiet", "connectivity", "Prints once, then waits.", None,
                 lambda p: [Step([sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"])])
    job_id = srv.app.jobs.start(quiet, {})["job"]["id"]
    job_stream = open_stream(srv, f"/api/jobs/{job_id}/stream")
    stats_stream = open_stream(srv, "/api/stats/stream")
    assert b'"up"' in read_stream(job_stream, until=b'"up"')[0]
    assert b"event: stats" in read_stream(stats_stream, until=b"event: stats")[0]

    start = time.monotonic()
    request(srv, "POST", "/api/shutdown", body={})
    for sock in (job_stream, stats_stream):
        data, closed = read_stream(sock, timeout=2.0)
        assert b"event: bye" in data, data[-300:]
        assert closed, "stream was not closed"
        sock.close()
    assert time.monotonic() - start < 2.0
