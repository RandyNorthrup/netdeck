"""User configuration (~/.config/netdeck/config.json) and runtime state paths."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict

log = logging.getLogger(__name__)

DEFAULT_PORT = 8737


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "netdeck")


def runtime_dir() -> str:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base or not os.path.isdir(base):
        base = os.path.join(tempfile.gettempdir(), f"netdeck-{os.getuid()}")
    path = os.path.join(base, "netdeck")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


@dataclass
class Config:
    port: int = DEFAULT_PORT
    privilege: str = "auto"  # auto | pkexec | sudo | none
    terminal: str = "auto"
    app_window: bool = True  # open in a chromeless browser window when a Chromium browser exists
    captures_dir: str = "~/netdeck-captures"

    EDITABLE = ("privilege", "terminal", "app_window", "captures_dir")

    @classmethod
    def path(cls) -> str:
        return os.path.join(config_dir(), "config.json")

    @classmethod
    def load(cls) -> Config:
        cfg = cls()
        try:
            with open(cls.path(), encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return cfg
        except (OSError, ValueError) as exc:
            log.warning("ignoring unreadable config %s: %s", cls.path(), exc)
            return cfg
        cfg.update(data, strict=False)
        return cfg

    def update(self, data: Dict[str, Any], strict: bool = True) -> None:
        known = {f.name: f for f in fields(self)}
        for key, value in data.items():
            if key not in known:
                if strict:
                    raise ValueError(f"unknown setting {key!r}")
                continue
            expected = type(getattr(self, key))
            if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
                if strict:
                    raise ValueError(f"setting {key!r} must be {expected.__name__}")
                continue
            if key == "privilege" and value not in ("auto", "pkexec", "sudo", "none"):
                raise ValueError("privilege must be auto, pkexec, sudo or none")
            if key == "port" and not 1024 <= value <= 65535:
                raise ValueError("port must be between 1024 and 65535")
            if key == "terminal" and (not value or "/" in value or len(value) > 64):
                raise ValueError("terminal must be a program name such as 'kitty' or 'auto'")
            setattr(self, key, value)

    def save(self) -> None:
        os.makedirs(config_dir(), exist_ok=True)
        tmp = self.path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
            fh.write("\n")
        os.replace(tmp, self.path())

    def apply_env(self) -> None:
        os.environ["NETDECK_CAPTURES_DIR"] = os.path.expanduser(self.captures_dir)
