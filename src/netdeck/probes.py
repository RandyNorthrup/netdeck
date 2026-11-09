"""Pure-Python probes: run without external binaries, used as built-in tools."""

from __future__ import annotations

import concurrent.futures
import http.client
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from netdeck import sysinfo
from netdeck.hostenv import which

Emit = Callable[[str], None]


def _resolve(host: str, port: int, family: int = 0) -> List[tuple]:
    infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    seen, out = set(), []
    for fam, _, _, _, addr in infos:
        if addr[0] not in seen:
            seen.add(addr[0])
            out.append((fam, addr))
    return out


def tcp_check(p: Dict, emit: Emit, stop) -> int:
    """Measure TCP handshake time to host:port, like a 'ping' for services."""
    host, port, count, timeout = p["host"], p["port"], p["count"], p["timeout"]
    family = {"4": socket.AF_INET, "6": socket.AF_INET6}.get(p.get("ipver") or "", 0)
    try:
        addrs = _resolve(host, port, family)
    except socket.gaierror as exc:
        emit(f"✗ Could not resolve {host}: {exc.strerror}")
        return 2
    fam, addr = addrs[0]
    emit(f"TCP connect to {host} ({addr[0]}) port {port}, {count} attempt(s), timeout {timeout}s")
    emit("")
    ok_times: List[float] = []
    sent = 0
    for i in range(1, count + 1):
        if stop.is_set():
            break
        sent += 1
        start = time.monotonic()
        try:
            with socket.socket(fam, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(addr)
            ms = (time.monotonic() - start) * 1000
            ok_times.append(ms)
            emit(f"  #{i:<3} ✓ open      {ms:8.2f} ms")
        except TimeoutError:
            emit(f"  #{i:<3} ✗ timeout   (no answer in {timeout}s — filtered by a firewall?)")
        except ConnectionRefusedError:
            emit(f"  #{i:<3} ✗ refused   (host reachable, nothing listening on {port})")
        except OSError as exc:
            emit(f"  #{i:<3} ✗ error     {exc.strerror or exc}")
        if i < count and stop.wait(1.0):
            break
    emit("")
    emit(f"--- {host}:{port} statistics ---")
    emit(f"{sent} attempts, {len(ok_times)} succeeded, {sent - len(ok_times)} failed")
    if ok_times:
        emit(
            f"connect min/avg/max = {min(ok_times):.2f}/"
            f"{sum(ok_times) / len(ok_times):.2f}/{max(ok_times):.2f} ms"
        )
    return 0 if ok_times else 1


def _fmt_name(name) -> str:
    return ", ".join(f"{k}={v}" for rdn in name for (k, v) in rdn)


def tls_inspect(p: Dict, emit: Emit, stop) -> int:
    """Handshake with a TLS server, verify it and describe its certificate."""
    host, port = p["host"], p["port"]
    sni = p.get("sni") or host
    ctx = ssl.create_default_context()
    verified = True
    cert: Optional[dict] = None
    der: Optional[bytes] = None
    emit(f"Connecting to {host}:{port} (SNI {sni}) …")
    try:
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=10) as sock, \
                ctx.wrap_socket(sock, server_hostname=sni) as tls:
            ms = (time.monotonic() - start) * 1000
            emit(f"✓ Connected and verified in {ms:.0f} ms — {tls.version()}, cipher {tls.cipher()[0]}")
            cert = tls.getpeercert()
            der = tls.getpeercert(binary_form=True)
            chain = getattr(tls, "get_verified_chain", None)
            if chain:
                emit("")
                emit("Verified chain:")
                for depth, c in enumerate(chain()):
                    subject = c.get_info().get("subject") if hasattr(c, "get_info") else None
                    emit(f"  {depth}: {_fmt_name(subject) if subject else c}")
    except ssl.SSLCertVerificationError as exc:
        verified = False
        emit(f"✗ Certificate verification FAILED: {exc.verify_message}")
        der = _fetch_unverified(host, port, sni)
    except (OSError, ssl.SSLError) as exc:
        emit(f"✗ TLS connection failed: {exc}")
        return 2

    emit("")
    if cert:
        not_after = ssl.cert_time_to_seconds(cert["notAfter"])
        days = int((not_after - time.time()) // 86400)
        sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
        emit(f"Subject     : {_fmt_name(cert.get('subject', ()))}")
        emit(f"Issuer      : {_fmt_name(cert.get('issuer', ()))}")
        emit(f"Valid from  : {cert.get('notBefore')}")
        emit(f"Valid until : {cert.get('notAfter')}  ({days} days left)")
        emit(f"SANs        : {', '.join(sans[:20])}{' …' if len(sans) > 20 else ''}")
        emit(f"Serial      : {cert.get('serialNumber')}")
        if days < 14:
            emit("⚠ Certificate expires soon!")
    elif der and which("openssl"):
        out = subprocess.run(
            [which("openssl"), "x509", "-inform", "DER", "-noout", "-subject", "-issuer",
             "-dates", "-ext", "subjectAltName"],
            input=der, capture_output=True, timeout=10, check=False,
        )
        for line in out.stdout.decode(errors="replace").splitlines():
            emit(line)
    return 0 if verified else 1


def _fetch_unverified(host: str, port: int, sni: str) -> Optional[bytes]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=10) as sock, \
                ctx.wrap_socket(sock, server_hostname=sni) as tls:
            return tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError):
        return None


# ---------------------------------------------------------------------------
# UniFi
# ---------------------------------------------------------------------------

def _netloc(host: str, port: int) -> str:
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def unifi_inform_url(host: str, port: int) -> str:
    """The inform URL UniFi devices are given with set-inform."""
    return f"http://{_netloc(host, port)}/inform"


def unifi_inform(p: Dict, emit: Emit, stop) -> int:
    """Check that a UniFi Network controller's inform endpoint answers.

    Devices POST encrypted informs to /inform. A plain GET gets "400 Bad Request" with an empty body from the
    controller; anything else on that port (a web page, an HTTPS-only server's error page) is not the endpoint.
    """
    host, port = p["controller"], p["port"]
    url = unifi_inform_url(host, port)
    emit(f"Checking {url}")
    emit("")
    try:
        addrs = _resolve(host, port)
    except socket.gaierror as exc:
        emit(f"✗ Could not resolve {host}: {exc.strerror}")
        return 2
    fam, addr = addrs[0]
    start = time.monotonic()
    try:
        with socket.socket(fam, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(addr)
    except TimeoutError:
        emit(f"✗ No answer from {addr[0]} port {port} in 5 s: a firewall drops it, or the address is wrong.")
        return 1
    except ConnectionRefusedError:
        emit(f"✗ {addr[0]} refuses port {port}: no UniFi controller is listening there.")
        emit("  Check the controller's address, or that UniFi Network is running on it.")
        return 1
    except OSError as exc:
        emit(f"✗ Cannot reach {addr[0]} port {port}: {exc.strerror or exc}")
        return 1
    emit(f"✓ TCP port {port} open on {addr[0]} ({(time.monotonic() - start) * 1000:.1f} ms)")

    conn = http.client.HTTPConnection(_netloc(addr[0], port), timeout=5)
    try:
        conn.request("GET", "/inform", headers={"Host": _netloc(host, port), "User-Agent": "NetDeck"})
        resp = conn.getresponse()
        body = resp.read(4096)
    except (OSError, http.client.HTTPException) as exc:
        emit(f"✗ Port {port} is open but does not speak HTTP: {exc}")
        return 1
    finally:
        conn.close()
    if resp.status == 400 and not body:
        emit("✓ UniFi inform endpoint answers (HTTP 400 to a plain request is normal: devices send informs).")
        emit("")
        emit(f"Devices that can reach this address can be adopted with: set-inform {url}")
        return 0
    emit(f"⚠ A web server answers on port {port}, but not like a UniFi inform endpoint "
         f"(HTTP {resp.status}, {len(body)} bytes).")
    emit("  Another service may be using this port, or the controller uses a different inform port.")
    return 1


# ---------------------------------------------------------------------------
# One-click health check
# ---------------------------------------------------------------------------

def _timed(fn, timeout: float):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        start = time.monotonic()
        result = pool.submit(fn).result(timeout=timeout)
        return result, (time.monotonic() - start) * 1000


def health_check() -> List[Dict]:
    """Layer-by-layer connectivity diagnosis: link → gateway → DNS → internet → HTTPS."""
    steps: List[Dict] = []

    def add(step_id, label, status, detail, ms=None):
        steps.append({"id": step_id, "label": label, "status": status, "detail": detail,
                      "ms": round(ms, 1) if ms is not None else None})

    ifaces = [i for i in sysinfo.interfaces()
              if i["state"] == "up" and not i["loopback"] and i["kind"] != "internal"]
    with_ip = [i for i in ifaces if any(a["family"] == "inet" for a in i["addresses"])]
    if with_ip:
        names = ", ".join(i["name"] for i in with_ip)
        add("link", "Network link", "ok", f"Connected via {names}")
    elif ifaces:
        add("link", "Network link", "warn", "Interface is up but has no IPv4 address (DHCP?)")
    else:
        add("link", "Network link", "fail", "No active network interface")

    gw = sysinfo.default_gateway()
    if not gw:
        add("gateway", "Default gateway", "fail", "No default route configured")
    elif not which("ping"):
        add("gateway", "Default gateway", "skip", f"{gw['gateway']} (ping not installed)")
    else:
        res = subprocess.run([which("ping"), "-c", "2", "-i", "0.2", "-W", "1", "-q", gw["gateway"]],
                             capture_output=True, text=True, timeout=8, check=False)
        if res.returncode == 0:
            rtt = _parse_ping_avg(res.stdout)
            add("gateway", "Default gateway", "ok", f"{gw['gateway']} via {gw['dev']} answers",
                float(rtt) if rtt else None)
        else:
            add("gateway", "Default gateway", "warn",
                f"{gw['gateway']} does not answer ping (some routers block ICMP)")

    try:
        addrs, ms = _timed(lambda: socket.getaddrinfo("example.com", 443), 6)
        add("dns", "DNS resolution", "ok" if ms < 1000 else "warn",
            f"example.com → {addrs[0][4][0]}" + (" (slow resolver)" if ms >= 1000 else ""), ms)
        dns_ok = True
    except Exception as exc:  # noqa: BLE001 — any failure is a diagnosis
        add("dns", "DNS resolution", "fail", f"Cannot resolve names: {exc}")
        dns_ok = False

    internet_ms = None
    for addr in ("1.1.1.1", "9.9.9.9", "8.8.8.8"):
        try:
            start = time.monotonic()
            with socket.create_connection((addr, 443), timeout=3):
                internet_ms = (time.monotonic() - start) * 1000
            add("internet", "Internet reachability", "ok", f"TCP 443 to {addr} succeeded", internet_ms)
            break
        except OSError:
            continue
    if internet_ms is None:
        add("internet", "Internet reachability", "fail", "Cannot reach public resolvers on TCP 443")

    if dns_ok and internet_ms is not None:
        try:
            def handshake():
                ctx = ssl.create_default_context()
                with socket.create_connection(("example.com", 443), timeout=5) as sock, \
                        ctx.wrap_socket(sock, server_hostname="example.com") as tls:
                    return tls.version()
            version, ms = _timed(handshake, 8)
            add("https", "Secure web (HTTPS)", "ok", f"Verified TLS ({version}) to example.com", ms)
        except Exception as exc:  # noqa: BLE001
            add("https", "Secure web (HTTPS)", "fail",
                f"TLS failed — captive portal, proxy or wrong system clock? ({exc})")
    else:
        add("https", "Secure web (HTTPS)", "skip", "Skipped: earlier step failed")

    return steps


def _parse_ping_avg(output: str) -> Optional[str]:
    for line in output.splitlines():
        if "min/avg/max" in line and "=" in line:
            try:
                return line.split("=")[1].split("/")[1].strip()
            except IndexError:
                return None
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
