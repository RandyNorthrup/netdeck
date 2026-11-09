"""Command-line entry point: ``netdeck [serve|doctor|url|stop]``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from typing import List, Optional

from netdeck import __version__
from netdeck.catalog import CATEGORIES, PACKAGES, TOOLS
from netdeck.config import Config, runtime_dir
from netdeck.hostenv import INSTALL_COMMANDS, Privilege, distro_family, which

log = logging.getLogger("netdeck")

APP_BROWSERS = ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "brave-browser",
                "brave", "microsoft-edge-stable", "vivaldi-stable")


# ---------------------------------------------------------------------------
# instance bookkeeping
# ---------------------------------------------------------------------------

def instance_file() -> str:
    return os.path.join(runtime_dir(), "instance.json")


def read_instance() -> Optional[dict]:
    try:
        with open(instance_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        os.kill(int(data["pid"]), 0)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:  # pid may have been recycled: confirm it is really NetDeck answering
        with urllib.request.urlopen(f"http://127.0.0.1:{data['port']}/api/ping", timeout=2) as resp:
            if json.load(resp).get("app") == "netdeck":
                return data
    except (OSError, ValueError):
        pass
    return None


def write_instance(port: int, url: str) -> None:
    path = instance_file()
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(), "port": port, "url": url, "started": time.time()}, fh)
    os.replace(path + ".tmp", path)


def remove_instance() -> None:
    try:
        with open(instance_file(), encoding="utf-8") as fh:
            if json.load(fh).get("pid") == os.getpid():
                os.unlink(instance_file())
    except (OSError, ValueError):
        pass


def open_ui(url: str, app_window: bool) -> None:
    if app_window:
        for name in APP_BROWSERS:
            binary = which(name)
            if binary:
                subprocess.Popen([binary, f"--app={url}", "--window-size=1440,920"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return
    if not webbrowser.open(url):
        print(f"Open this URL in your browser: {url}")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_serve(args: argparse.Namespace) -> int:
    from netdeck.server import App, make_server  # deferred: keeps `netdeck doctor` fast

    existing = read_instance()
    if existing and not args.port:
        print(f"NetDeck is already running: {existing['url']}")
        if not args.no_browser:
            open_ui(existing["url"], Config.load().app_window and not args.no_app_window)
        return 0

    config = Config.load()
    config.apply_env()
    host = args.host
    if host not in ("127.0.0.1", "::1", "localhost") and not args.allow_remote:
        print("Refusing to listen on a non-loopback address without --allow-remote.", file=sys.stderr)
        return 2
    if args.allow_remote:
        log.warning("Remote access enabled: anyone who obtains the URL token can run network tools as %s. "
                    "Traffic is NOT encrypted — use an SSH tunnel instead whenever possible.",
                    os.environ.get("USER", "this user"))

    token = secrets.token_urlsafe(32)
    app = App(config, token, args.port or config.port, allow_remote=args.allow_remote)
    server = make_server(host, args.port or config.port, app)
    port = server.server_address[1]
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::", "localhost") else host
    url = f"http://{display_host if ':' not in display_host else f'[{display_host}]'}:{port}/?token={token}"
    write_instance(port, url)

    def stop(signum, _frame):
        log.info("received signal %s, shutting down", signum)
        app.shutdown.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    print(f"NetDeck {__version__} is running at:\n\n    {url}\n", flush=True)
    print(f"Privileges: {app.privilege.describe()}")
    print("Press Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        threading.Timer(0.4, open_ui, args=(url, config.app_window and not args.no_app_window)).start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        app.shutdown.set()
        app.jobs.shutdown()
        server.server_close()
        remove_instance()
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    family = distro_family()
    priv = Privilege(Config.load().privilege)
    from netdeck import terminal

    print(f"NetDeck {__version__}  ·  Python {sys.version.split()[0]}  ·  distro family: {family}")
    print(f"Privileges : {priv.describe()}")
    print(f"Terminal   : {terminal.detect(Config.load().terminal) or 'none found'}")
    print()
    missing: List[str] = []
    color = sys.stdout.isatty()
    ok, bad = ("\033[32m✓\033[0m", "\033[31m✗\033[0m") if color else ("✓", "✗")
    for cat in CATEGORIES:
        print(cat.name)
        for tool in (t for t in TOOLS if t.category == cat.id):
            found = tool.binary is None or which(tool.binary)
            if not found:
                pkg = PACKAGES.get(tool.binary, {}).get(family)
                if pkg and pkg not in missing:
                    missing.append(pkg)
            print(f"  {ok if found else bad} {tool.name:<28} {tool.binary or '(built-in)'}")
        print()
    if missing and family in INSTALL_COMMANDS:
        print("Install the missing tools with:")
        print("  " + INSTALL_COMMANDS[family].format(pkg=" ".join(missing)))
    return 0


def cmd_url(_args: argparse.Namespace) -> int:
    inst = read_instance()
    if not inst:
        print("NetDeck is not running.", file=sys.stderr)
        return 1
    print(inst["url"])
    return 0


def cmd_stop(_args: argparse.Namespace) -> int:
    inst = read_instance()
    if not inst:
        print("NetDeck is not running.")
        return 0
    os.kill(int(inst["pid"]), signal.SIGTERM)
    print(f"Stopped NetDeck (pid {inst['pid']}).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netdeck",
                                     description="A local web dashboard for network troubleshooting tools.")
    parser.add_argument("--version", action="version", version=f"netdeck {__version__}")
    parser.add_argument("--log-level", default=os.environ.get("NETDECK_LOG_LEVEL", "INFO"),
                        choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="start the dashboard (default)")
    for p in (parser, serve):
        # On the subcommand, SUPPRESS keeps values given before `serve` from being reset.
        dflt = (lambda v: v) if p is parser else (lambda v: argparse.SUPPRESS)
        p.add_argument("--host", default=dflt("127.0.0.1"), help="address to bind (default 127.0.0.1)")
        p.add_argument("--port", type=int, default=dflt(0), help="port (default from config, 8737)")
        p.add_argument("--no-browser", action="store_true", default=dflt(False),
                       help="don't open a browser window")
        p.add_argument("--no-app-window", action="store_true", default=dflt(False),
                       help="open a normal browser tab")
        p.add_argument("--allow-remote", action="store_true", default=dflt(False),
                       help="allow binding to non-loopback addresses")
    serve.set_defaults(func=cmd_serve)
    sub.add_parser("doctor", help="check which tools are installed").set_defaults(func=cmd_doctor)
    sub.add_parser("url", help="print the URL of the running instance").set_defaults(func=cmd_url)
    sub.add_parser("stop", help="stop the running instance").set_defaults(func=cmd_stop)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    func = getattr(args, "func", cmd_serve)
    try:
        return func(args)
    except KeyboardInterrupt:
        return 130
