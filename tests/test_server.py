"""HTTP-level tests: authentication, DNS-rebinding and CSRF protection, job lifecycle."""

import http.client
import json
import threading
import time

import pytest

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
