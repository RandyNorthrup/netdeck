"""Read-only snapshot of the host's network state for the Overview page."""

from __future__ import annotations

import glob
import ipaddress
import json
import os
import re
import socket
import subprocess
import time
from typing import Dict, List, Optional

from netdeck.hostenv import os_release, which

SYS_NET = "/sys/class/net"
DEV_DIR = "/dev"


def _run_json(argv: List[str]):
    binary = which(argv[0])
    if not binary:
        return None
    try:
        out = subprocess.run([binary] + argv[1:], capture_output=True, text=True,
                             timeout=5, check=False)
        return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


# USB product names of links that are internal to the machine, not network ports.
INTERNAL_PRODUCTS = ("T2 Controller", "iBridge")  # Apple T2 Macs expose a cdc_ncm link to the T2 chip


def _iface_kind(name: str) -> str:
    base = os.path.join(SYS_NET, name)
    if name == "lo":
        return "loopback"
    product = _read(os.path.join(base, "device", "..", "product")) or ""
    if any(marker in product for marker in INTERNAL_PRODUCTS):
        return "internal"
    if os.path.isdir(os.path.join(base, "wireless")) or os.path.isdir(os.path.join(base, "phy80211")):
        return "wifi"
    if os.path.isdir(os.path.join(base, "bridge")):
        return "bridge"
    if os.path.exists(os.path.join(base, "tun_flags")) or name.startswith(("tun", "tap", "wg")):
        return "vpn"
    if not os.path.exists(os.path.join(base, "device")):
        return "virtual"
    return "ethernet"


def interfaces() -> List[Dict]:
    data = _run_json(["ip", "-j", "addr", "show"]) or []
    result = []
    for item in data:
        name = item.get("ifname", "")
        flags = item.get("flags", [])
        state = item.get("operstate", "UNKNOWN").lower()
        if state == "unknown" and "UP" in flags and "LOWER_UP" in flags:
            state = "up"
        speed = _read(os.path.join(SYS_NET, name, "speed"))
        result.append({
            "name": name,
            "kind": _iface_kind(name),
            "state": state,
            "loopback": "LOOPBACK" in flags,
            "mac": item.get("address") if item.get("link_type") == "ether" else None,
            "mtu": item.get("mtu"),
            "speed_mbps": int(speed) if speed and speed.lstrip("-").isdigit() and int(speed) > 0 else None,
            "addresses": [
                {"family": a.get("family"), "address": a.get("local"),
                 "prefix": a.get("prefixlen"), "scope": a.get("scope")}
                for a in item.get("addr_info", [])
                if a.get("local")
            ],
            "wifi": wifi_link(name) if _iface_kind(name) == "wifi" and state == "up" else None,
        })
    if not result:  # iproute2 without JSON support: minimal sysfs fallback
        for name in sorted(os.listdir(SYS_NET)) if os.path.isdir(SYS_NET) else []:
            result.append({"name": name, "kind": _iface_kind(name),
                           "state": (_read(os.path.join(SYS_NET, name, "operstate")) or "unknown"),
                           "loopback": name == "lo", "mac": _read(os.path.join(SYS_NET, name, "address")),
                           "mtu": None, "speed_mbps": None, "addresses": [], "wifi": None})
    return result


def wifi_link(name: str) -> Optional[Dict]:
    if not which("iw"):
        return None
    try:
        out = subprocess.run([which("iw"), "dev", name, "link"], capture_output=True,
                             text=True, timeout=3, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    info: Dict = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("SSID:"):
            info["ssid"] = line[5:].strip()
        elif line.startswith("signal:"):
            m = re.search(r"(-?\d+)", line)
            info["signal_dbm"] = int(m.group(1)) if m else None
        elif line.startswith("freq:"):
            info["freq_mhz"] = line.split(":", 1)[1].strip().split()[0]
        elif line.startswith("tx bitrate:"):
            info["tx_bitrate"] = line.split(":", 1)[1].strip().split(" MBit/s")[0] + " Mbit/s"
    return info or None


def serial_ports() -> List[str]:
    """USB and ACM serial adapters (console cables) currently plugged in."""
    return sorted(glob.glob(os.path.join(DEV_DIR, "ttyUSB*")) + glob.glob(os.path.join(DEV_DIR, "ttyACM*")))


def routes() -> List[Dict]:
    out = []
    for fam in ("-4", "-6"):
        for r in _run_json(["ip", "-j", fam, "route", "show"]) or []:
            out.append({"dst": r.get("dst"), "gateway": r.get("gateway"), "dev": r.get("dev"),
                        "protocol": r.get("protocol"), "metric": r.get("metric"),
                        "prefsrc": r.get("prefsrc"), "family": "inet6" if fam == "-6" else "inet"})
    return out


def default_gateway() -> Optional[Dict]:
    defaults = [r for r in routes() if r["dst"] == "default" and r["gateway"] and r["family"] == "inet"]
    if not defaults:
        return None
    defaults.sort(key=lambda r: r.get("metric") or 0)
    return defaults[0]


def dns_servers() -> Dict:
    servers: List[str] = []
    search: List[str] = []
    for line in (_read("/etc/resolv.conf") or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            servers.append(parts[1])
        elif parts and parts[0] in ("search", "domain"):
            search.extend(parts[1:])
    upstream: List[str] = []
    stub = any(s.startswith("127.0.0.53") or s == "127.0.0.54" for s in servers)
    if stub and which("resolvectl"):
        try:
            text = subprocess.run([which("resolvectl"), "dns"], capture_output=True,
                                  text=True, timeout=3, check=False).stdout
            for line in text.splitlines():
                _, _, addrs = line.partition(":")
                upstream.extend(a for a in addrs.split() if a not in upstream)
        except (OSError, subprocess.SubprocessError):
            pass
    return {"servers": servers, "search": search, "resolved_stub": stub, "upstream": upstream}


def primary() -> Dict:
    """Primary interface, IPv4 address and subnet — used to prefill forms."""
    gw = default_gateway()
    result: Dict = {"gateway": gw["gateway"] if gw else None, "iface": gw["dev"] if gw else None,
                    "ip": None, "subnet": None}
    if gw:
        for iface in interfaces():
            if iface["name"] == gw["dev"]:
                for a in iface["addresses"]:
                    if a["family"] == "inet":
                        net = ipaddress.ip_interface(f"{a['address']}/{a['prefix']}").network
                        result["ip"] = a["address"]
                        result["subnet"] = str(net) if net.prefixlen >= 16 else None
                        break
    return result


def counters() -> Dict[str, Dict[str, int]]:
    """Per-interface byte/packet counters from /proc/net/dev."""
    result = {}
    try:
        with open("/proc/net/dev", encoding="utf-8") as fh:
            lines = fh.readlines()[2:]
    except OSError:
        return result
    for line in lines:
        name, _, rest = line.partition(":")
        f = rest.split()
        if len(f) >= 16:
            result[name.strip()] = {"rx_bytes": int(f[0]), "rx_packets": int(f[1]),
                                    "rx_errors": int(f[2]), "rx_drop": int(f[3]),
                                    "tx_bytes": int(f[8]), "tx_packets": int(f[9]),
                                    "tx_errors": int(f[10]), "tx_drop": int(f[11])}
    return result


def snapshot() -> Dict:
    rel = os_release()
    return {
        "hostname": socket.gethostname(),
        "os": rel.get("PRETTY_NAME", "Linux"),
        "kernel": os.uname().release,
        "interfaces": interfaces(),
        "routes": routes(),
        "dns": dns_servers(),
        "primary": primary(),
        "serial_ports": serial_ports(),
        "time": time.time(),
    }
