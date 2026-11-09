"""Host platform helpers: binary lookup, distro detection, privilege strategy."""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
from typing import Dict, List, Optional

_EXTRA_PATH = ("/usr/local/sbin", "/usr/sbin", "/sbin")


def search_path() -> str:
    parts = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin").split(os.pathsep)
    parts += [p for p in _EXTRA_PATH if p not in parts]
    return os.pathsep.join(parts)


def which(binary: str) -> Optional[str]:
    """Locate ``binary``, also searching sbin directories (Debian keeps tcpdump there)."""
    return shutil.which(binary, path=search_path())


@functools.lru_cache(maxsize=1)
def os_release() -> Dict[str, str]:
    data: Dict[str, str] = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    key, sep, value = line.strip().partition("=")
                    if sep:
                        data[key] = value.strip().strip('"')
            break
        except OSError:
            continue
    return data


@functools.lru_cache(maxsize=1)
def distro_family() -> str:
    """One of: arch, debian, fedora, suse, unknown."""
    rel = os_release()
    ids = [rel.get("ID", "")] + rel.get("ID_LIKE", "").split()
    for ident in ids:
        if ident in ("arch", "manjaro", "endeavouros", "cachyos"):
            return "arch"
        if ident in ("debian", "ubuntu", "linuxmint", "pop", "raspbian"):
            return "debian"
        if ident in ("fedora", "rhel", "centos", "rocky", "almalinux"):
            return "fedora"
        if ident.startswith("opensuse") or ident in ("suse", "sles"):
            return "suse"
    return "unknown"


INSTALL_COMMANDS = {
    "arch": "sudo pacman -S --needed {pkg}",
    "debian": "sudo apt install {pkg}",
    "fedora": "sudo dnf install {pkg}",
    "suse": "sudo zypper install {pkg}",
}


def has_file_caps(path: Optional[str]) -> bool:
    """True if ``path`` carries file capabilities (e.g. cap_net_raw) and is executable by us."""
    if not path or not os.access(path, os.X_OK):
        return False
    try:
        return bool(os.getxattr(path, "security.capability"))
    except (OSError, AttributeError):
        return False


def is_root() -> bool:
    return os.geteuid() == 0


def capture_capable(binary: str) -> bool:
    """Can ``binary`` open raw sockets without elevation?"""
    if is_root():
        return True
    if binary in ("tshark", "termshark", "wireshark"):
        return has_file_caps(which("dumpcap"))
    return has_file_caps(which(binary))


def graphical_session() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


class Privilege:
    """How NetDeck elevates tools that need root.

    * ``root``    - NetDeck itself runs as root (not recommended).
    * ``sudo``    - ``sudo -n`` works without a password prompt (NOPASSWD rule).
    * ``pkexec``  - polkit shows a graphical authentication dialog per command.
    * ``none``    - no elevation available; privileged tools are disabled.
    """

    MODES = ("auto", "pkexec", "sudo", "none")

    def __init__(self, preference: str = "auto") -> None:
        self.preference = preference if preference in self.MODES else "auto"
        self.mode = self._detect()

    def _detect(self) -> str:
        if is_root():
            return "root"
        pref = self.preference
        if pref == "none":
            return "none"
        if pref in ("auto", "sudo") and which("sudo") and _sudo_passwordless():
            return "sudo"
        if pref in ("auto", "pkexec") and which("pkexec") and graphical_session():
            return "pkexec"
        return "none"

    @property
    def available(self) -> bool:
        return self.mode in ("root", "sudo", "pkexec")

    @property
    def killable(self) -> bool:
        """Can we signal an elevated child? (pkexec children run with root's real uid.)"""
        return self.mode in ("root", "sudo")

    def wrap(self, argv: List[str]) -> List[str]:
        if self.mode == "root":
            return argv
        if self.mode == "sudo":
            return ["sudo", "-n", "--"] + argv
        if self.mode == "pkexec":
            return ["pkexec", "--disable-internal-agent"] + argv
        raise PermissionError(
            "This tool needs administrator rights, but no elevation method is available. "
            "Start a polkit agent, configure sudo, or see docs/PRIVILEGES.md."
        )

    def describe(self) -> str:
        return {
            "root": "Running as root — privileged tools run directly.",
            "sudo": "Privileged tools run through passwordless sudo.",
            "pkexec": "Privileged tools ask for your password through polkit.",
            "none": "No elevation method found — privileged tools are disabled.",
        }[self.mode]


def _sudo_passwordless() -> bool:
    try:
        return (
            subprocess.run(
                ["sudo", "-n", "true"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False
