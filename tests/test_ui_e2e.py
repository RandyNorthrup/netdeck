"""Browser tests: the Exit control and the stopped screen, in headless Chrome against a real server.

Skipped when Chrome or websocket-client is unavailable, unless NETDECK_REQUIRE_E2E=1 (set in CI), in
which case a missing prerequisite fails instead of silently skipping.
"""

import contextlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.request

import pytest

from test_cli import api, env, start_server  # noqa: F401 - `env` is a fixture used by these tests

CHROME = next((shutil.which(n) for n in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser")
               if shutil.which(n)), None)
try:
    import websocket
except ImportError:  # pragma: no cover - depends on the environment
    websocket = None

REQUIRED = os.environ.get("NETDECK_REQUIRE_E2E") == "1"
MISSING = [name for name, ok in (("Chrome", CHROME), ("websocket-client", websocket)) if not ok]
if MISSING and REQUIRED:
    raise RuntimeError(f"NETDECK_REQUIRE_E2E=1 but missing: {', '.join(MISSING)}")
pytestmark = pytest.mark.skipif(bool(MISSING), reason=f"needs {', '.join(MISSING)}")


class Browser:
    """Just enough of the Chrome DevTools Protocol to drive one page."""

    def __init__(self) -> None:
        self.ws = None
        self.profile = tempfile.mkdtemp(prefix="netdeck-e2e-")
        # Chrome gets its own process group so close() can end its helper processes too.
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--remote-debugging-port=0", f"--user-data-dir={self.profile}", "--window-size=1280,900",
             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            self._connect()
        except BaseException:
            self.close()  # a failed setup must not leave Chrome running
            raise

    def _connect(self) -> None:
        port_file = pathlib.Path(self.profile, "DevToolsActivePort")
        for _ in range(100):
            if port_file.exists() and port_file.read_text().strip():
                break
            time.sleep(0.1)
        port = int(port_file.read_text().split()[0])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json") as resp:
            page = next(t for t in json.load(resp) if t["type"] == "page")
        # No Origin header: Chrome accepts DevTools clients that send none, so no allow-list is needed.
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
        self.msg_id = 0
        self.exceptions = []
        self.call("Runtime.enable")

    def call(self, method, **params):
        self.msg_id += 1
        my_id = self.msg_id
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                details = msg["params"]["exceptionDetails"]
                self.exceptions.append(details.get("exception", {}).get("description", details.get("text")))
            if msg.get("id") == my_id:
                return msg.get("result", {})

    def js(self, expression):
        result = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        return result.get("result", {}).get("value")

    def wait_for(self, expression, timeout=10.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.js(expression):
                return True
            time.sleep(0.1)
        return False

    def press_escape(self):
        for kind in ("keyDown", "keyUp"):
            self.call("Input.dispatchKeyEvent", type=kind, key="Escape", code="Escape", windowsVirtualKeyCode=27)

    def close(self):
        if self.ws is not None:
            with contextlib.suppress(Exception):
                self.ws.close()
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.proc.pid, signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):  # SIGKILL below handles a hung Chrome
            self.proc.wait(10)
        # Helpers (network service, GPU, renderers) outlive the main process briefly and would keep writing
        # into the profile; end the whole group before deleting it.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc.wait(10)
        shutil.rmtree(self.profile, ignore_errors=True)


@pytest.fixture
def browser():
    b = Browser()
    yield b
    b.close()


@pytest.fixture
def server(env, tmp_path):  # noqa: F811 - pytest fixture injection
    proc, port, token = start_server(env, tmp_path)
    yield proc, port, token, env
    if proc.poll() is None:
        proc.kill()
        proc.wait()
    proc.log.close()


DIALOG_OPEN = "document.querySelector('#exit-dialog').open"
STOPPED_SHOWN = "!document.querySelector('#stopped').hidden"


def exit_code_within(proc, seconds, what):
    try:
        return proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        pytest.fail(f"server still running {seconds} s after {what}")


def assert_still_running(proc, port, after):
    time.sleep(1.0)
    assert proc.poll() is None, f"server exited after {after}"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=5) as resp:
        assert resp.status == 200


def open_dashboard(browser, port, token):
    browser.call("Page.navigate", url=f"http://127.0.0.1:{port}/?token={token}")
    assert browser.wait_for("!!document.querySelector('.page')"), "dashboard did not render"


def test_exit_dialog_cancel_keeps_running_then_confirm_stops(browser, server):
    proc, port, token, _ = server
    open_dashboard(browser, port, token)
    api(port, token, "POST", "/api/run", {"tool": "ping", "params": {"host": "127.0.0.1", "count": 0}})

    # Cancel with the button, then with Escape: nothing is shut down.
    browser.js("document.querySelector('#exit-btn').click()")
    assert browser.wait_for(DIALOG_OPEN), "exit dialog did not open"
    assert "Exit NetDeck?" in browser.js("document.querySelector('#exit-dialog').innerText")
    assert browser.wait_for("document.querySelector('#exit-jobs-list').innerText.includes('Ping')"), \
        "running tool not listed"
    browser.js("document.querySelector('#exit-cancel').click()")
    assert browser.wait_for(f"!{DIALOG_OPEN}"), "cancel did not close the dialog"
    assert_still_running(proc, port, "Cancel")
    browser.js("document.querySelector('#exit-btn').click()")
    assert browser.wait_for(DIALOG_OPEN), "exit dialog did not reopen"
    browser.press_escape()
    assert browser.wait_for(f"!{DIALOG_OPEN}"), "Escape did not close the dialog"
    assert_still_running(proc, port, "Escape")
    assert not browser.js(STOPPED_SHOWN)

    # Confirm: the page shows the stopped screen and the server exits cleanly.
    browser.js("document.querySelector('#exit-btn').click()")
    assert browser.wait_for(DIALOG_OPEN)
    browser.js("document.querySelector('#exit-confirm').click()")
    assert browser.wait_for(STOPPED_SHOWN), "stopped screen not shown after Exit"
    assert browser.js("document.querySelector('#stopped-title').innerText") == "NetDeck has stopped"
    assert exit_code_within(proc, 10, "Exit") == 0
    assert browser.exceptions == []


def test_stopped_screen_when_server_is_stopped_from_terminal(browser, server):
    proc, port, token, _ = server
    open_dashboard(browser, port, token)
    assert browser.wait_for("!!document.querySelector('.iface')"), "overview with live stats did not render"
    proc.send_signal(signal.SIGINT)
    assert exit_code_within(proc, 10, "SIGINT") == 0
    assert browser.wait_for(STOPPED_SHOWN, timeout=10), "stopped screen not shown after Ctrl+C"
    assert browser.js("document.querySelector('#stopped-title').innerText") == "NetDeck was stopped"
    assert browser.exceptions == []
