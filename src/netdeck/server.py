"""HTTP server: JSON API, Server-Sent Events and the static single-page UI.

Security model (see SECURITY.md):
* binds to 127.0.0.1 by default;
* every API call needs the per-instance session cookie (minted from a secret token);
* the Host header must be a loopback name (defeats DNS rebinding);
* state-changing requests need a custom header + same-origin (defeats CSRF);
* tools run as argv lists after strict validation — never through a shell.
"""

from __future__ import annotations

import contextlib
import hmac
import json
import logging
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

from netdeck import __version__, probes, sysinfo, terminal
from netdeck.catalog import CATEGORIES, PACKAGES, TOOLS, TOOLS_BY_ID, captures_dir
from netdeck.config import Config
from netdeck.hostenv import INSTALL_COMMANDS, Privilege, distro_family, which
from netdeck.runner import JobError, JobManager
from netdeck.validators import ValidationError, validate

log = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_BODY = 64 * 1024
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
       "frame-ancestors 'none'; form-action 'self'")

Route = Tuple[str, "re.Pattern[str]", Callable]


class App:
    """Shared state for all request handlers."""

    def __init__(self, config: Config, token: str, port: int, allow_remote: bool = False) -> None:
        self.config = config
        self.token = token
        self.allow_remote = allow_remote
        self.privilege = Privilege(config.privilege)
        self.jobs = JobManager(self.privilege, config.terminal)
        self.shutdown = threading.Event()
        # Called once when shutdown is requested; the owner of serve_forever sets it to stop the loop.
        self.on_shutdown: Optional[Callable[[], None]] = None
        self._shutdown_lock = threading.Lock()
        self._streams = 0
        self._streams_cond = threading.Condition()
        self.set_port(port)

    def set_port(self, port: int) -> None:
        self.port = port
        self.cookie_name = f"netdeck_{port}"
        self.allowed_hosts = {f"{h}:{port}" for h in ("127.0.0.1", "localhost", "[::1]")}

    def request_shutdown(self, reason: str) -> bool:
        """Begin shutting down (idempotent). Streams are woken so they can say goodbye."""
        with self._shutdown_lock:
            if self.shutdown.is_set():
                return False
            self.shutdown.set()
        log.info("shutting down: %s", reason)
        with self.jobs.lock:
            jobs = list(self.jobs.jobs.values())
        for job in jobs:
            job.wake()
        if self.on_shutdown:
            self.on_shutdown()
        return True

    def close(self, stream_drain: float = 2.0) -> None:
        """Stop every job and give open streams a moment to send their goodbye."""
        self.request_shutdown("server closing")
        self.jobs.shutdown()
        with self._streams_cond:
            self._streams_cond.wait_for(lambda: self._streams == 0, timeout=stream_drain)

    @contextlib.contextmanager
    def stream(self):
        """Count a live Server-Sent Events stream for the duration of the block."""
        with self._streams_cond:
            self._streams += 1
        try:
            yield
        finally:
            with self._streams_cond:
                self._streams -= 1
                self._streams_cond.notify_all()

    def reload_privilege(self) -> None:
        self.privilege = Privilege(self.config.privilege)
        self.jobs.privilege = self.privilege
        self.jobs.terminal_pref = self.config.terminal

    # -- payloads -------------------------------------------------------------
    def meta(self) -> Dict:
        return {
            "version": __version__,
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER") or str(os.getuid()),
            "distro": distro_family(),
            "privilege": {"mode": self.privilege.mode, "description": self.privilege.describe(),
                          "available": self.privilege.available},
            "terminal": terminal.detect(self.config.terminal),
            "captures_dir": captures_dir(),
        }

    def tools(self) -> Dict:
        family = distro_family()
        out = []
        for tool in TOOLS:
            installed = tool.binary is None or which(tool.binary) is not None
            hint = None
            if not installed:
                pkg = PACKAGES.get(tool.binary, {}).get(family)
                hint = INSTALL_COMMANDS[family].format(pkg=pkg) if pkg and family in INSTALL_COMMANDS else None
            priv = tool.privileged
            out.append({
                "id": tool.id, "name": tool.name, "category": tool.category, "summary": tool.summary,
                "binary": tool.binary, "mode": tool.mode, "popular": tool.popular,
                "long_running": tool.long_running, "notes": tool.notes, "keywords": list(tool.keywords),
                "privileged": "conditional" if callable(priv) else bool(priv),
                "params": [p.to_dict() for p in tool.params],
                "installed": installed, "install_hint": hint,
            })
        cats = [{"id": c.id, "name": c.name, "icon": c.icon, "summary": c.summary} for c in CATEGORIES]
        return {"categories": cats, "tools": out}

    def settings(self) -> Dict:
        return {
            "privilege": self.config.privilege, "terminal": self.config.terminal,
            "app_window": self.config.app_window, "captures_dir": self.config.captures_dir,
            "terminals": terminal.available(), "config_path": Config.path(),
        }


def validate_params(tool_id: str, raw: Any) -> Tuple[Any, Dict]:
    tool = TOOLS_BY_ID.get(tool_id)
    if not tool:
        raise LookupError(f"unknown tool {tool_id!r}")
    raw = raw if isinstance(raw, dict) else {}
    clean, errors = {}, {}
    for param in tool.params:
        try:
            clean[param.name] = validate(param, raw.get(param.name))
        except ValidationError as exc:
            errors[param.name] = f"{param.label} {exc}"
    return tool, (errors or clean), bool(errors)


class Handler(BaseHTTPRequestHandler):
    server_version = f"NetDeck/{__version__}"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    server: NetDeckHTTPServer

    @property
    def app(self) -> App:
        return self.server.app

    def log_message(self, fmt: str, *args: Any) -> None:  # route through logging
        log.debug("%s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    # -- plumbing -------------------------------------------------------------
    def _dispatch(self, method: str) -> None:
        try:
            if not self._host_ok():
                return self._send_json({"error": "Host not allowed"}, HTTPStatus.MISDIRECTED_REQUEST)
            path, _, query = self.path.partition("?")
            self.query = {k: v[0] for k, v in parse_qs(query).items()}
            if method == "GET" and path == "/":
                return self._index()
            if method == "GET" and (path.startswith("/static/") or path == "/favicon.svg"):
                return self._static(path)
            if method == "GET" and path == "/api/ping":
                return self._send_json({"app": "netdeck", "version": __version__})
            if not self._authed():
                return self._send_json({"error": "Not authenticated. Open NetDeck with the `netdeck` command."},
                                       HTTPStatus.UNAUTHORIZED)
            if method != "GET" and not self._same_origin():
                return self._send_json({"error": "Cross-origin request rejected"}, HTTPStatus.FORBIDDEN)
            for verb, pattern, handler in ROUTES:
                match = pattern.fullmatch(path)
                if verb == method and match:
                    return handler(self, *match.groups())
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("unhandled error for %s %s", method, self.path)
            with contextlib.suppress(OSError):
                self._send_json({"error": "Internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _host_ok(self) -> bool:
        return self.app.allow_remote or self.headers.get("Host", "") in self.app.allowed_hosts

    def _authed(self) -> bool:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:  # noqa: BLE001 — malformed cookie header
            return False
        morsel = cookie.get(self.app.cookie_name)
        return bool(morsel) and hmac.compare_digest(morsel.value, self.app.token)

    def _same_origin(self) -> bool:
        if self.headers.get("X-NetDeck") != "1":
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.split("://", 1)[-1] == self.headers.get("Host")

    def _security_headers(self) -> None:
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def _send(self, body: bytes, status: int = 200, ctype: str = "application/json",
              headers: Optional[Dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, data: Any, status: int = 200) -> None:
        self._send(json.dumps(data).encode(), status)

    def _body(self) -> Dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("Request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw or b"{}")
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data

    # -- pages ----------------------------------------------------------------
    def _index(self) -> None:
        token = self.query.get("token")
        if token is not None:
            if hmac.compare_digest(token, self.app.token):
                cookie = (f"{self.app.cookie_name}={self.app.token}; Path=/; HttpOnly; "
                          "SameSite=Strict; Max-Age=31536000")
                return self._send(b"", HTTPStatus.FOUND, "text/plain", {"Location": "/", "Set-Cookie": cookie})
            return self._static("/static/locked.html", HTTPStatus.UNAUTHORIZED)
        if not self._authed():
            return self._static("/static/locked.html", HTTPStatus.UNAUTHORIZED)
        self._static("/static/index.html")

    def _static(self, path: str, status: int = 200) -> None:
        name = "icon.svg" if path == "/favicon.svg" else path[len("/static/"):]
        full = os.path.realpath(os.path.join(STATIC_DIR, name))
        if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
            return self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            self._send(fh.read(), status, ctype)

    # -- SSE --------------------------------------------------------------------
    def _sse_open(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self._security_headers()
        self.end_headers()
        self.close_connection = True

    def _sse(self, event: str, data: Any, event_id: Optional[str] = None) -> None:
        msg = f"event: {event}\n"
        if event_id:
            msg += f"id: {event_id}\n"
        msg += f"data: {json.dumps(data)}\n\n"
        self.wfile.write(msg.encode())
        self.wfile.flush()

    # -- API handlers ---------------------------------------------------------
    def api_meta(self) -> None:
        self._send_json(self.app.meta())

    def api_tools(self) -> None:
        self._send_json(self.app.tools())

    def api_system(self) -> None:
        self._send_json(sysinfo.snapshot())

    def api_health(self) -> None:
        self._send_json({"steps": probes.health_check(), "time": probes.now_iso()})

    def api_preview(self) -> None:
        body = self._body()
        try:
            tool, result, failed = validate_params(body.get("tool", ""), body.get("params"))
        except LookupError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        if failed:
            return self._send_json({"errors": result})
        self._send_json(self.app.jobs.preview(tool, result))

    def api_run(self) -> None:
        body = self._body()
        try:
            tool, result, failed = validate_params(body.get("tool", ""), body.get("params"))
        except LookupError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        if failed:
            return self._send_json({"errors": result}, HTTPStatus.UNPROCESSABLE_ENTITY)
        try:
            self._send_json(self.app.jobs.start(tool, result))
        except (JobError, PermissionError, RuntimeError, OSError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.CONFLICT)

    def api_jobs(self) -> None:
        self._send_json({"jobs": self.app.jobs.list()})

    def _job(self, job_id: str):
        try:
            return self.app.jobs.get(job_id)
        except KeyError:
            self._send_json({"error": "No such job"}, HTTPStatus.NOT_FOUND)
            return None

    def api_job(self, job_id: str) -> None:
        job = self._job(job_id)
        if job:
            self._send_json(job.summary())

    def api_job_stop(self, job_id: str) -> None:
        if self._job(job_id):
            self.app.jobs.stop(job_id)
            self._send_json({"ok": True})

    def api_job_delete(self, job_id: str) -> None:
        if self._job(job_id):
            try:
                self.app.jobs.remove(job_id)
                self._send_json({"ok": True})
            except JobError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.CONFLICT)

    def api_job_output(self, job_id: str) -> None:
        job = self._job(job_id)
        if job:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(job.started))
            header = f"# NetDeck {__version__} — {job.tool.name}\n# " + "\n# ".join(job.display) + "\n\n"
            self._send((header + job.text()).encode(), 200, "text/plain; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="netdeck-{job.tool.id}-{stamp}.txt"'})

    def api_job_open(self, job_id: str) -> None:
        job = self._job(job_id)
        if not job:
            return
        action = self._body().get("action", "wireshark")
        if not job.artifact or not os.path.isfile(job.artifact):
            return self._send_json({"error": "This job produced no file"}, HTTPStatus.NOT_FOUND)
        if action == "wireshark" and which("wireshark"):
            argv = [which("wireshark"), "-r", job.artifact]
        elif which("xdg-open"):
            argv = [which("xdg-open"), os.path.dirname(job.artifact)]
        else:
            return self._send_json({"error": "No application available to open the file"}, HTTPStatus.CONFLICT)
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        self._send_json({"ok": True})

    def api_job_stream(self, job_id: str) -> None:
        job = self._job(job_id)
        if not job:
            return
        cursor, rev = 0, 0
        last_id = self.headers.get("Last-Event-ID") or self.query.get("resume")
        if last_id and re.fullmatch(r"\d+:\d+", last_id):
            cursor, rev = (int(x) for x in last_id.split(":"))
        with self.app.stream():
            self._sse_open()
            self._sse("meta", job.summary())
            while not self.app.shutdown.is_set():
                was_running = job.running
                lines, cursor, rev = job.changes_since(cursor, rev)
                if lines:
                    self._sse("lines", {"lines": lines, "open": job.open_line}, f"{cursor}:{rev}")
                if not was_running:
                    self._sse("end", job.summary())
                    return
                with job.cond:
                    changed = job.cond.wait_for(
                        lambda seen=rev: job.rev != seen or self.app.shutdown.is_set(), timeout=15)
                if not changed:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            self._sse("bye", {"reason": "shutdown"})

    def api_stats_stream(self) -> None:
        with self.app.stream():
            self._sse_open()
            self._stats_loop()
            self._sse("bye", {"reason": "shutdown"})

    def _stats_loop(self) -> None:
        prev, prev_t = sysinfo.counters(), time.monotonic()
        while not self.app.shutdown.wait(1.0):
            cur, now = sysinfo.counters(), time.monotonic()
            dt = max(now - prev_t, 1e-3)
            rates = {}
            for name, c in cur.items():
                p = prev.get(name)
                if p:
                    rates[name] = {
                        "rx": max(0, c["rx_bytes"] - p["rx_bytes"]) / dt,
                        "tx": max(0, c["tx_bytes"] - p["tx_bytes"]) / dt,
                        "rx_total": c["rx_bytes"], "tx_total": c["tx_bytes"],
                        "errors": c["rx_errors"] + c["tx_errors"], "drops": c["rx_drop"] + c["tx_drop"],
                    }
            self._sse("stats", {"t": time.time(), "rates": rates})
            prev, prev_t = cur, now

    def api_shutdown(self) -> None:
        running = len(self.app.jobs.running_jobs())
        self.close_connection = True
        self._send_json({"ok": True, "stopping_jobs": running}, HTTPStatus.ACCEPTED)
        self.app.request_shutdown("exit requested from the dashboard")

    def api_settings(self) -> None:
        self._send_json(self.app.settings())

    def api_settings_update(self) -> None:
        body = self._body()
        try:
            self.app.config.update({k: v for k, v in body.items() if k in Config.EDITABLE})
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.app.config.save()
        self.app.config.apply_env()
        self.app.reload_privilege()
        self._send_json({"settings": self.app.settings(), "meta": self.app.meta()})


def _r(method: str, pattern: str, fn: Callable) -> Route:
    return (method, re.compile(pattern), fn)


JOB = r"([0-9a-f]{12})"
ROUTES: List[Route] = [
    _r("GET", r"/api/meta", Handler.api_meta),
    _r("GET", r"/api/tools", Handler.api_tools),
    _r("GET", r"/api/system", Handler.api_system),
    _r("POST", r"/api/health", Handler.api_health),
    _r("POST", r"/api/preview", Handler.api_preview),
    _r("POST", r"/api/run", Handler.api_run),
    _r("GET", r"/api/jobs", Handler.api_jobs),
    _r("GET", rf"/api/jobs/{JOB}", Handler.api_job),
    _r("DELETE", rf"/api/jobs/{JOB}", Handler.api_job_delete),
    _r("POST", rf"/api/jobs/{JOB}/stop", Handler.api_job_stop),
    _r("POST", rf"/api/jobs/{JOB}/open", Handler.api_job_open),
    _r("GET", rf"/api/jobs/{JOB}/output", Handler.api_job_output),
    _r("GET", rf"/api/jobs/{JOB}/stream", Handler.api_job_stream),
    _r("GET", r"/api/stats/stream", Handler.api_stats_stream),
    _r("GET", r"/api/settings", Handler.api_settings),
    _r("POST", r"/api/settings", Handler.api_settings_update),
    _r("POST", r"/api/shutdown", Handler.api_shutdown),
]


class NetDeckHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Tuple[str, int], app: App) -> None:
        self.address_family = socket.AF_INET6 if ":" in address[0] else socket.AF_INET
        super().__init__(address, Handler)
        self.app = app

    def handle_error(self, request, client_address) -> None:
        """Clients closing connections early (port probes, closed tabs) is routine, not an error."""
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)):
            log.debug("client %s disconnected: %s", client_address, exc)
            return
        log.exception("error while handling request from %s", client_address)


def make_server(host: str, port: int, app: App) -> NetDeckHTTPServer:
    """Bind to ``port``, falling back to the next free ports if it is taken."""
    last_error: Optional[OSError] = None
    for candidate in range(port, port + 20):
        try:
            app.set_port(candidate)
            srv = NetDeckHTTPServer((host, candidate), app)
            app.set_port(srv.server_address[1])
            return srv
        except OSError as exc:
            last_error = exc
    raise OSError(f"no free port in {port}-{port + 19}: {last_error}")

