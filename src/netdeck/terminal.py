"""Open interactive (TUI) tools in the user's terminal emulator."""

from __future__ import annotations

import os
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

from netdeck.hostenv import which

# Keeps the window open after the tool exits so errors stay readable.
# The tool's argv is passed as positional parameters — never interpolated.
_HOLD = (
    'printf "\\033]0;%s\\007" "$NETDECK_TITLE"; "$@"; rc=$?; '
    'printf "\\n\\033[2m[NetDeck] exited with status %s — press Enter to close\\033[0m" "$rc"; read -r _'
)

Builder = Callable[[str, List[str]], List[str]]

TERMINALS: Tuple[Tuple[str, Builder], ...] = (
    ("kitty", lambda t, a: ["kitty", "--title", t] + a),
    ("ghostty", lambda t, a: ["ghostty", f"--title={t}", "-e"] + a),
    ("alacritty", lambda t, a: ["alacritty", "--title", t, "-e"] + a),
    ("wezterm", lambda t, a: ["wezterm", "start", "--"] + a),
    ("foot", lambda t, a: ["foot", "--title", t] + a),
    ("gnome-terminal", lambda t, a: ["gnome-terminal", "--title", t, "--"] + a),
    ("ptyxis", lambda t, a: ["ptyxis", "--new-window", "--"] + a),
    ("konsole", lambda t, a: ["konsole", "-e"] + a),
    ("xfce4-terminal", lambda t, a: ["xfce4-terminal", "--title", t, "-x"] + a),
    ("mate-terminal", lambda t, a: ["mate-terminal", "--title", t, "-x"] + a),
    ("lxterminal", lambda t, a: ["lxterminal", "-t", t, "-e"] + a),
    ("terminator", lambda t, a: ["terminator", "-T", t, "-x"] + a),
    ("xterm", lambda t, a: ["xterm", "-T", t, "-e"] + a),
    ("x-terminal-emulator", lambda t, a: ["x-terminal-emulator", "-e"] + a),
)
_BY_NAME: Dict[str, Builder] = dict(TERMINALS)


def detect(preference: str = "auto") -> Optional[str]:
    """Return the terminal emulator to use, honouring config, then $TERMINAL, then a known list."""
    candidates: List[str] = []
    if preference and preference != "auto":
        candidates.append(preference)
    env = os.environ.get("TERMINAL", "").strip()
    if env:
        candidates.append(os.path.basename(env.split()[0]))
    candidates += [name for name, _ in TERMINALS]
    for name in candidates:
        if which(name):
            return name
    return None


def available() -> List[str]:
    return [name for name, _ in TERMINALS if which(name)]


def launch_in_terminal(argv: List[str], title: str, sudo: bool = False, preference: str = "auto") -> str:
    name = detect(preference)
    if not name:
        raise RuntimeError("No terminal emulator found. Set one in Settings or export $TERMINAL.")
    if sudo and os.geteuid() != 0:
        argv = ["sudo", "--"] + argv
    inner = ["sh", "-c", _HOLD, "netdeck"] + argv
    builder = _BY_NAME.get(name, lambda t, a: [name, "-e"] + a)
    cmd = builder(title, inner)
    cmd[0] = which(cmd[0]) or cmd[0]
    env = dict(os.environ, NETDECK_TITLE=title)
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, env=env)
    return name
