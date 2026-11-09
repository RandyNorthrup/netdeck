"""The tool catalog: every tool NetDeck can drive, its parameters and its argv builder.

Adding a tool is a single :class:`Tool` entry — see docs/ADDING_TOOLS.md.
Builders receive *validated* parameters and return an argv list, a list of
:class:`Step` objects, a :class:`Plan` or an :class:`Internal` probe. They never
build shell strings.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from netdeck import probes
from netdeck.hostenv import capture_capable, is_root

STREAM, TERMINAL, GUI = "stream", "terminal", "gui"


@dataclass(frozen=True)
class Param:
    name: str
    label: str
    kind: str  # see validators.validate
    default: Any = None
    required: bool = False
    help: str = ""
    placeholder: str = ""
    min: Optional[int] = None
    max: Optional[int] = None
    choices: Tuple[Tuple[str, str], ...] = ()
    allow_any: bool = False
    prefill: str = ""  # gateway | subnet | iface | ip — filled from live system info
    advanced: bool = False

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", (), False) or k == "default"}


@dataclass(frozen=True)
class Step:
    argv: List[str]
    label: Optional[str] = None


@dataclass(frozen=True)
class Internal:
    fn: Callable
    label: str


@dataclass
class Plan:
    steps: List[Union[Step, Internal]]
    artifact: Optional[str] = None  # file produced by the job (e.g. a .pcap)


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    icon: str
    summary: str


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    category: str
    summary: str
    binary: Optional[str]
    build: Callable[[Dict], Any]
    params: Tuple[Param, ...] = ()
    mode: str = STREAM
    privileged: Union[bool, Callable[[Dict], bool]] = False
    popular: bool = False
    long_running: bool = False
    notes: str = ""
    keywords: Tuple[str, ...] = field(default_factory=tuple)

    def needs_root(self, params: Dict) -> bool:
        if is_root():
            return False
        if callable(self.privileged):
            return bool(self.privileged(params))
        return bool(self.privileged)

    def plan(self, params: Dict) -> Plan:
        built = self.build(params)
        if isinstance(built, Plan):
            return built
        if isinstance(built, Internal):
            return Plan([built])
        if built and isinstance(built[0], Step):
            return Plan(list(built))
        return Plan([Step(list(built))])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _if(cond: Any, *args: str) -> List[str]:
    return list(args) if cond else []


def _ipver(p: Dict) -> List[str]:
    return {"4": ["-4"], "6": ["-6"]}.get(p.get("ipver") or "", [])


def captures_dir() -> str:
    path = os.environ.get("NETDECK_CAPTURES_DIR") or os.path.expanduser("~/netdeck-captures")
    os.makedirs(path, mode=0o750, exist_ok=True)
    return path


IPVER = Param("ipver", "IP version", "choice", "", choices=(("", "Automatic"), ("4", "IPv4 only"), ("6", "IPv6 only")),
              advanced=True)
HOST = Param("host", "Host", "host", required=True, placeholder="example.com or 1.1.1.1",
             help="Hostname or IP address")
TARGET = Param("target", "Target", "target", required=True, placeholder="192.168.1.0/24", prefill="subnet",
               help="Host, IP, CIDR network or range (e.g. 10.0.0.1-50)")
IFACE = Param("iface", "Interface", "iface", required=True, prefill="iface",
              help="Network interface, e.g. eth0 or wlan0")
IFACE_ANY = Param("iface", "Interface", "iface", "any", allow_any=True, prefill="iface",
                  help="Interface to capture on, or 'any'")
IFACE_OPT = Param("iface", "Interface", "iface", help="Leave empty for all interfaces", placeholder="all")

RECORD_TYPES = tuple((t, t) for t in ("A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "SRV", "CAA", "PTR", "ANY"))

PUBLIC_RESOLVERS = (("1.1.1.1", "Cloudflare"), ("8.8.8.8", "Google"), ("9.9.9.9", "Quad9"),
                    ("208.67.222.222", "OpenDNS"))

CATEGORIES: Tuple[Category, ...] = (
    Category("connectivity", "Connectivity", "activity", "Reachability, latency and path tracing"),
    Category("dns", "DNS & Lookup", "globe", "Name resolution, records and ownership"),
    Category("discovery", "Discovery & Scanning", "radar", "Find hosts, open ports and services"),
    Category("performance", "Speed & Throughput", "gauge", "Bandwidth tests and speed tests"),
    Category("traffic", "Traffic Monitor", "chart", "Who is using the network right now"),
    Category("capture", "Packet Capture", "layers", "Capture and inspect packets"),
    Category("interfaces", "Interfaces & Routing", "network", "Adapters, addresses, routes and Wi-Fi"),
    Category("connections", "Connections & Ports", "plug", "Sockets, listeners and owning processes"),
    Category("web", "Web & TLS", "lock", "HTTP, certificates and public IP"),
    Category("firewall", "Firewall", "shield", "Packet filter rules"),
)


# ---------------------------------------------------------------------------
# builders that need more than one line
# ---------------------------------------------------------------------------

def _ping(p: Dict) -> List[str]:
    return (["ping"] + _ipver(p) + _if(p["count"], "-c", str(p["count"])) +
            ["-i", p["interval"], "-s", str(p["size"])] + _if(p["numeric"], "-n") + ["-O", "--", p["host"]])


def _traceroute(p: Dict) -> List[str]:
    method = {"icmp": ["-I"], "tcp": ["-T", "-p", str(p["port"] or 443)]}.get(p["method"], [])
    return (["traceroute"] + _ipver(p) + method + ["-m", str(p["max_hops"]), "-q", str(p["queries"]),
            "-w", str(p["wait"])] + _if(p["numeric"], "-n") + ["--", p["host"]])


def _mtr(p: Dict) -> List[str]:
    proto = {"udp": ["--udp"], "tcp": ["--tcp", "-P", str(p["port"] or 443)]}.get(p["protocol"], [])
    return (["mtr", "--report-wide", "-c", str(p["cycles"])] + _ipver(p) + proto +
            _if(p["numeric"], "-n") + _if(p["asn"], "-z") + ["--", p["host"]])


def _dig(p: Dict) -> List[str]:
    return (["dig"] + _if(p["server"], "@" + str(p["server"])) + [p["name"], p["rtype"]] +
            _if(p["short"], "+short") + _if(p["trace"], "+trace") + _if(p["tcp"], "+tcp") +
            _if(p["dnssec"], "+dnssec"))


def _dns_compare(p: Dict) -> List[Step]:
    steps = [Step(["dig", "+short", "+time=3", "+tries=1", p["name"], p["rtype"]], "System resolver")]
    for addr, name in PUBLIC_RESOLVERS:
        steps.append(Step(["dig", "+short", "+time=3", "+tries=1", "@" + addr, p["name"], p["rtype"]],
                          f"{name} ({addr})"))
    return steps


def _nmap_scan(p: Dict) -> List[str]:
    scan = {"connect": "-sT", "syn": "-sS", "udp": "-sU"}[p["scan"]]
    presets = {"fast": ["-F"], "top1000": [], "all": ["-p-"]}
    port_args = ["-p", p["ports"]] if p["ports"] else presets[p["preset"]]
    return (["nmap", scan] + port_args + ["-T" + p["timing"], "--stats-every", "10s", "--reason"] +
            _if(p["service"], "-sV") + _if(p["scripts"], "-sC") + _if(p["skip_ping"], "-Pn") +
            _if(p["open_only"], "--open") + ["--", p["target"]])


def _tcpdump(p: Dict) -> List[str]:
    return (["tcpdump", "-l", "-i", p["iface"], "-c", str(p["count"])] +
            _if(p["numeric"], "-nn") + {"1": [], "2": ["-v"], "3": ["-vv"]}[p["verbosity"]] +
            _if(p["ascii"], "-A") + _if(p["link"], "-e") +
            _if(p["filter"], "--", str(p["filter"])))


def _tcpdump_file(p: Dict) -> Plan:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(captures_dir(), f"capture-{p['iface']}-{stamp}.pcap")
    argv = (["tcpdump", "-i", p["iface"], "-w", path, "-c", str(p["count"]),
             "-G", str(p["duration"]), "-W", "1", "--print", "-nn", "-q"] +
            _if(p.get("_elevated") or is_root(), "-Z", p.get("_user", "root")) +
            _if(p["filter"], "--", str(p["filter"])))
    return Plan([Step(argv)], artifact=path)


def _tshark(p: Dict) -> List[str]:
    return (["tshark", "-l", "-i", p["iface"], "-c", str(p["count"]), "-a", f"duration:{p['duration']}"] +
            _if(p["numeric"], "-n") + _if(p["capture_filter"], "-f", str(p["capture_filter"])) +
            _if(p["display_filter"], "-Y", str(p["display_filter"])))


def _iperf_client(p: Dict) -> List[str]:
    return (["iperf3", "-c", p["host"], "-p", str(p["port"]), "-t", str(p["duration"]),
             "-P", str(p["parallel"]), "--forceflush"] + _ipver(p) + _if(p["reverse"], "-R") +
            _if(p["bidir"], "--bidir") + _if(p["udp"], "-u", "-b", str(p["bitrate"] or "100M")))


CURL_TIMING = (
    "\\n"
    "  HTTP status ........ %{http_code}\\n"
    "  Remote address ..... %{remote_ip}:%{remote_port}\\n"
    "  HTTP version ....... %{http_version}\\n"
    "\\n"
    "  DNS lookup ......... %{time_namelookup}s\\n"
    "  TCP connect ........ %{time_connect}s\\n"
    "  TLS handshake ...... %{time_appconnect}s\\n"
    "  Time to first byte . %{time_starttransfer}s\\n"
    "  Total .............. %{time_total}s\\n"
    "\\n"
    "  Downloaded ......... %{size_download} bytes  (%{speed_download} bytes/s)\\n"
    "  Redirects .......... %{num_redirects}\\n"
)


# ---------------------------------------------------------------------------
# the catalog
# ---------------------------------------------------------------------------

TOOLS: Tuple[Tool, ...] = (
    # ── Connectivity ─────────────────────────────────────────────────────────
    Tool("ping", "Ping", "connectivity", "Check if a host is reachable and measure round-trip latency.",
         "ping", _ping, popular=True, keywords=("icmp", "latency", "echo"), params=(
             HOST,
             Param("count", "Count", "int", 10, min=0, max=10000, help="Number of pings; 0 = until stopped"),
             Param("interval", "Interval", "choice", "1", choices=(("0.2", "0.2 s"), ("0.5", "0.5 s"),
                   ("1", "1 s"), ("2", "2 s"), ("5", "5 s"))),
             Param("size", "Packet size (bytes)", "int", 56, min=16, max=65000, advanced=True),
             Param("numeric", "Don't resolve names", "bool", False, advanced=True),
             IPVER)),
    Tool("tcp-check", "TCP Port Check", "connectivity",
         "Test whether a TCP service accepts connections and time the handshake.",
         None, lambda p: Internal(probes.tcp_check, "TCP connect probe"), popular=True,
         keywords=("port", "telnet", "nc", "netcat", "service"), params=(
             HOST,
             Param("port", "Port", "port", 443, required=True),
             Param("count", "Attempts", "int", 4, min=1, max=100),
             Param("timeout", "Timeout (s)", "int", 3, min=1, max=30),
             IPVER)),
    Tool("traceroute", "Traceroute", "connectivity", "Show every router hop between you and a host.",
         "traceroute", _traceroute, privileged=lambda p: p["method"] == "tcp",
         keywords=("hops", "path", "route"), params=(
             HOST,
             Param("method", "Probe method", "choice", "udp", choices=(("udp", "UDP (default)"),
                   ("icmp", "ICMP echo"), ("tcp", "TCP SYN — passes most firewalls (admin)"))),
             Param("port", "TCP port", "port", 443, help="Only for TCP SYN method"),
             Param("max_hops", "Max hops", "int", 30, min=1, max=64),
             Param("queries", "Probes per hop", "int", 3, min=1, max=10, advanced=True),
             Param("wait", "Wait per probe (s)", "int", 3, min=1, max=10, advanced=True),
             Param("numeric", "Don't resolve names", "bool", False),
             IPVER)),
    Tool("tracepath", "Tracepath", "connectivity", "Trace the path and discover the path MTU, no privileges needed.",
         "tracepath", lambda p: ["tracepath"] + _if(p["numeric"], "-n") + _if(p["both"], "-b") +
         ["-m", str(p["max_hops"]), "--", p["host"]], keywords=("mtu", "path"), params=(
             HOST,
             Param("max_hops", "Max hops", "int", 30, min=1, max=64),
             Param("numeric", "Don't resolve names", "bool", False),
             Param("both", "Show names and IPs", "bool", False, advanced=True))),
    Tool("mtr-report", "MTR Report", "connectivity",
         "Combined ping + traceroute: per-hop packet loss and latency statistics.",
         "mtr", _mtr, popular=True, keywords=("loss", "jitter", "hops"),
         notes="Results appear when all cycles have finished.", params=(
             HOST,
             Param("cycles", "Cycles", "int", 10, min=1, max=500),
             Param("protocol", "Protocol", "choice", "icmp", choices=(("icmp", "ICMP"), ("udp", "UDP"),
                   ("tcp", "TCP"))),
             Param("port", "Port (TCP)", "port", 443, advanced=True),
             Param("numeric", "Don't resolve names", "bool", False),
             Param("asn", "Show AS numbers", "bool", False, advanced=True),
             IPVER)),
    Tool("mtr-live", "MTR Live", "connectivity", "Interactive, continuously updating MTR in a terminal window.",
         "mtr", lambda p: ["mtr", "--", p["host"]], mode=TERMINAL, params=(HOST,)),
    Tool("gping", "Graph Ping", "connectivity", "Ping several hosts at once with a live latency graph.",
         "gping", lambda p: ["gping", "--"] + p["hosts"], mode=TERMINAL, keywords=("graph", "compare"),
         params=(Param("hosts", "Hosts", "hosts", "1.1.1.1 8.8.8.8", required=True,
                       help="Up to 6 hosts separated by spaces", prefill=""),)),
    Tool("trippy", "Trippy", "connectivity", "Modern traceroute + ping TUI with charts and world map.",
         "trip", lambda p: ["trip", "--", p["host"]], mode=TERMINAL,
         privileged=lambda p: not capture_capable("trip"), params=(HOST,)),
    Tool("arping", "ARP Ping", "connectivity",
         "Ping a host on the local network at layer 2 (works when ICMP is blocked).",
         "arping", lambda p: ["arping", "-c", str(p["count"]), "-I", p["iface"], "--", p["ip"]],
         privileged=lambda p: not capture_capable("arping"), keywords=("layer2", "mac", "duplicate"), params=(
             Param("ip", "IP address", "ip", required=True, prefill="gateway"),
             IFACE,
             Param("count", "Count", "int", 5, min=1, max=1000))),

    # ── DNS ──────────────────────────────────────────────────────────────────
    Tool("dig", "DNS Query (dig)", "dns", "Query any DNS record type, optionally against a specific server.",
         "dig", _dig, popular=True, keywords=("record", "mx", "txt", "nslookup"), params=(
             Param("name", "Name", "host", required=True, placeholder="example.com"),
             Param("rtype", "Record type", "choice", "A", choices=RECORD_TYPES),
             Param("server", "DNS server", "host", placeholder="system default",
                   help="Optional resolver, e.g. 1.1.1.1"),
             Param("short", "Short answer only", "bool", False),
             Param("trace", "Trace from root servers", "bool", False, advanced=True),
             Param("tcp", "Use TCP", "bool", False, advanced=True),
             Param("dnssec", "Request DNSSEC records", "bool", False, advanced=True))),
    Tool("dns-compare", "Resolver Comparison", "dns",
         "Ask your resolver and four public resolvers the same question — spot stale or hijacked DNS.",
         "dig", _dns_compare, keywords=("propagation", "cloudflare", "google"), params=(
             Param("name", "Name", "host", required=True, placeholder="example.com"),
             Param("rtype", "Record type", "choice", "A", choices=RECORD_TYPES))),
    Tool("reverse-dns", "Reverse Lookup", "dns", "Find the hostname (PTR record) for an IP address.",
         "dig", lambda p: ["dig", "-x", p["ip"]] + _if(p["short"], "+short"), params=(
             Param("ip", "IP address", "ip", required=True),
             Param("short", "Short answer only", "bool", True))),
    Tool("host", "Host Lookup", "dns", "Quick, human-friendly lookup of all common records for a name.",
         "host", lambda p: ["host"] + _if(p["all"], "-a") + ["--", p["name"]], params=(
             Param("name", "Name or IP", "host", required=True, placeholder="example.com"),
             Param("all", "All records (verbose)", "bool", False))),
    Tool("whois", "WHOIS", "dns", "Registration and ownership details for a domain or IP block.",
         "whois", lambda p: ["whois", p["query"]], keywords=("registrar", "owner", "abuse"), params=(
             Param("query", "Domain or IP", "host", required=True, placeholder="example.com"),)),
    Tool("resolvectl-status", "Resolver Status", "dns",
         "systemd-resolved configuration: DNS servers per link, DNSSEC and DoT state.",
         "resolvectl", lambda p: ["resolvectl", "status"], params=()),
    Tool("resolvectl-query", "Resolve via systemd", "dns",
         "Resolve a name exactly like applications do and show which link answered.",
         "resolvectl", lambda p: ["resolvectl", "query", "--", p["name"]], params=(
             Param("name", "Name", "host", required=True, placeholder="example.com"),)),

    # ── Discovery & scanning ─────────────────────────────────────────────────
    Tool("nmap-sweep", "Host Discovery", "discovery", "Find which devices are alive on a network (ping sweep).",
         "nmap", lambda p: ["nmap", "-sn"] + _if(p["numeric"], "-n") + ["--", p["target"]],
         popular=True, keywords=("devices", "lan", "sweep", "who is on my network"), params=(
             TARGET, Param("numeric", "Skip reverse DNS (faster)", "bool", False))),
    Tool("nmap-scan", "Port Scan", "discovery", "Scan hosts for open ports, with optional service detection.",
         "nmap", _nmap_scan, privileged=lambda p: p["scan"] in ("syn", "udp"), popular=True,
         keywords=("ports", "services", "open"), notes="Only scan networks you own or are authorized to test.",
         params=(
             TARGET,
             Param("preset", "Ports", "choice", "fast", choices=(("fast", "Top 100 (fast)"),
                   ("top1000", "Top 1000"), ("all", "All 65535"))),
             Param("ports", "Custom ports", "ports", placeholder="22,80,443,8000-8100",
                   help="Overrides the preset when set"),
             Param("scan", "Scan type", "choice", "connect", choices=(("connect", "TCP connect"),
                   ("syn", "TCP SYN — stealthier (admin)"), ("udp", "UDP (admin, slow)"))),
             Param("service", "Detect service versions", "bool", False),
             Param("open_only", "Show open ports only", "bool", True),
             Param("timing", "Speed", "choice", "4", choices=(("2", "Polite"), ("3", "Normal"),
                   ("4", "Aggressive"), ("5", "Insane")), advanced=True),
             Param("scripts", "Run default scripts (-sC)", "bool", False, advanced=True),
             Param("skip_ping", "Treat hosts as online (-Pn)", "bool", False, advanced=True))),
    Tool("nmap-os", "OS Fingerprint", "discovery", "Guess the operating system and services of a host.",
         "nmap", lambda p: ["nmap", "-O", "-sV", "--osscan-guess", "-T4", "--", p["target"]],
         privileged=True, params=(Param("target", "Target", "target", required=True, placeholder="192.168.1.10"),)),
    Tool("arp-scan", "ARP Scan", "discovery", "Fastest way to list every device on your LAN with vendor names.",
         "arp-scan", lambda p: ["arp-scan", "--interface", p["iface"], "--localnet"] + _if(p["plain"], "--plain"),
         privileged=lambda p: not capture_capable("arp-scan"), popular=True, keywords=("lan", "mac", "vendor"),
         params=(IFACE, Param("plain", "Plain output", "bool", False, advanced=True))),
    Tool("neighbors", "Neighbor Table", "discovery", "Devices your machine has recently talked to (ARP / NDP cache).",
         "ip", lambda p: ["ip"] + _if(p["family"] != "all", "-" + p["family"]) + ["neigh", "show"], params=(
             Param("family", "Family", "choice", "all",
                   choices=(("all", "IPv4 + IPv6"), ("4", "IPv4"), ("6", "IPv6"))),)),
    Tool("zenmap", "Zenmap", "discovery", "Official graphical front-end for nmap with topology maps.",
         "zenmap", lambda p: ["zenmap"], mode=GUI),
    Tool("ipscan", "Angry IP Scanner", "discovery", "Fast graphical IP and port scanner.",
         "ipscan", lambda p: ["ipscan"], mode=GUI),

    # ── Performance ─────────────────────────────────────────────────────────
    Tool("iperf-client", "iperf3 Client", "performance", "Measure throughput to an iperf3 server.",
         "iperf3", _iperf_client, popular=True, keywords=("bandwidth", "throughput", "speed"), params=(
             Param("host", "Server", "host", required=True, placeholder="iperf.example.net"),
             Param("port", "Port", "port", 5201),
             Param("duration", "Duration (s)", "int", 10, min=1, max=600),
             Param("parallel", "Parallel streams", "int", 1, min=1, max=64),
             Param("reverse", "Download (server → you)", "bool", False),
             Param("bidir", "Both directions at once", "bool", False, advanced=True),
             Param("udp", "UDP mode", "bool", False, advanced=True),
             Param("bitrate", "UDP target bitrate", "rate", placeholder="100M", advanced=True),
             IPVER)),
    Tool("iperf-server", "iperf3 Server", "performance",
         "Run an iperf3 server so another machine can test against you.",
         "iperf3", lambda p: ["iperf3", "-s", "-p", str(p["port"]), "--forceflush"] + _if(p["once"], "-1"),
         long_running=True, params=(
             Param("port", "Port", "port", 5201),
             Param("once", "Exit after one test", "bool", False))),
    Tool("speedtest", "Internet Speed Test", "performance",
         "Download / upload speed and latency to the nearest Speedtest server.",
         "speedtest-cli", lambda p: ["speedtest-cli", "--secure"] + _if(p["simple"], "--simple") +
         _if(p["bytes"], "--bytes"), popular=True, keywords=("internet", "isp", "download", "upload"),
         notes="Contacts speedtest.net servers.", params=(
             Param("simple", "Compact output", "bool", False),
             Param("bytes", "Show MB/s instead of Mbit/s", "bool", False, advanced=True))),

    # ── Traffic monitor ─────────────────────────────────────────────────────
    Tool("nethogs", "Bandwidth per Process", "traffic", "Which programs are using bandwidth, sampled over time.",
         "nethogs", lambda p: ["nethogs", "-t", "-d", str(p["delay"]), "-c", str(p["cycles"])] +
         _if(p["iface"], str(p["iface"])), privileged=lambda p: not capture_capable("nethogs"), popular=True,
         keywords=("process", "app", "usage"), params=(
             IFACE_OPT,
             Param("delay", "Refresh every (s)", "int", 2, min=1, max=60),
             Param("cycles", "Samples", "int", 15, min=1, max=1000))),
    Tool("nethogs-live", "NetHogs Live", "traffic", "Interactive per-process bandwidth view in a terminal.",
         "nethogs", lambda p: ["nethogs"], mode=TERMINAL, privileged=lambda p: not capture_capable("nethogs")),
    Tool("iftop", "Bandwidth per Connection", "traffic", "Top talkers: which remote hosts use the most bandwidth.",
         "iftop", lambda p: ["iftop", "-t", "-s", str(p["seconds"]), "-L", str(p["lines"]), "-i", p["iface"]] +
         _if(p["numeric"], "-n", "-N") + ["-P"], privileged=lambda p: not capture_capable("iftop"),
         keywords=("talkers", "hosts"), notes="Prints a summary after the sample period.", params=(
             IFACE,
             Param("seconds", "Sample period (s)", "int", 10, min=2, max=600),
             Param("lines", "Rows", "int", 20, min=5, max=200),
             Param("numeric", "Don't resolve names", "bool", True))),
    Tool("iftop-live", "iftop Live", "traffic", "Interactive per-connection bandwidth view in a terminal.",
         "iftop", lambda p: ["iftop", "-i", p["iface"], "-P"], mode=TERMINAL,
         privileged=lambda p: not capture_capable("iftop"), params=(IFACE,)),
    Tool("bmon", "bmon", "traffic", "Live per-interface bandwidth graphs in a terminal.",
         "bmon", lambda p: ["bmon"], mode=TERMINAL),
    Tool("vnstat", "Usage History", "traffic", "Long-term traffic totals recorded by the vnStat daemon.",
         "vnstat", lambda p: ["vnstat"] + _if(p["iface"], "-i", str(p["iface"])) +
         ({"summary": [], "hourly": ["-h"], "daily": ["-d"], "monthly": ["-m"], "top": ["-t"],
           "rate": ["-tr", "5"]}[p["view"]]), keywords=("history", "data usage", "quota"), params=(
             Param("view", "View", "choice", "summary", choices=(("summary", "Summary"), ("hourly", "Hourly"),
                   ("daily", "Daily"), ("monthly", "Monthly"), ("top", "Top days"), ("rate", "Current rate (5 s)"))),
             IFACE_OPT)),
    Tool("link-stats", "Interface Counters", "traffic", "Packets, bytes, errors and drops per interface.",
         "ip", lambda p: ["ip", "-s", "-s", "link", "show"] + _if(p["iface"], "dev", str(p["iface"])),
         keywords=("errors", "drops"), params=(IFACE_OPT,)),
    Tool("sniffnet", "Sniffnet", "traffic", "Beautiful graphical traffic monitor.",
         "sniffnet", lambda p: ["sniffnet"], mode=GUI),

    # ── Packet capture ──────────────────────────────────────────────────────
    Tool("tcpdump", "Live Capture (tcpdump)", "capture", "Print packets as they cross an interface.",
         "tcpdump", _tcpdump, privileged=lambda p: not capture_capable("tcpdump"), popular=True,
         keywords=("sniff", "packets", "bpf"), params=(
             IFACE_ANY,
             Param("filter", "Filter (BPF)", "expr", placeholder="port 53 or host 1.1.1.1",
                   help="tcpdump filter syntax, e.g. 'tcp port 443 and host 10.0.0.5'"),
             Param("count", "Stop after packets", "int", 200, min=1, max=1000000),
             Param("numeric", "Don't resolve names/ports", "bool", True),
             Param("verbosity", "Detail", "choice", "1", choices=(("1", "Normal"), ("2", "Verbose"),
                   ("3", "Very verbose"))),
             Param("ascii", "Show payload as text", "bool", False, advanced=True),
             Param("link", "Show MAC addresses", "bool", False, advanced=True))),
    Tool("tcpdump-file", "Capture to File", "capture",
         "Record packets to a .pcap file and open it in Wireshark afterwards.",
         "tcpdump", _tcpdump_file, privileged=lambda p: not capture_capable("tcpdump"),
         keywords=("pcap", "save", "wireshark"), params=(
             IFACE_ANY,
             Param("duration", "Duration (s)", "int", 30, min=1, max=3600),
             Param("count", "Max packets", "int", 100000, min=1, max=10000000),
             Param("filter", "Filter (BPF)", "expr", placeholder="optional"))),
    Tool("tshark", "Live Capture (tshark)", "capture", "Wireshark's dissectors in text form, with display filters.",
         "tshark", _tshark, privileged=lambda p: not capture_capable("tshark"), keywords=("wireshark", "dissect"),
         params=(
             IFACE_ANY,
             Param("display_filter", "Display filter", "expr", placeholder="http or dns",
                   help="Wireshark display filter syntax"),
             Param("capture_filter", "Capture filter (BPF)", "expr", placeholder="optional", advanced=True),
             Param("count", "Stop after packets", "int", 200, min=1, max=1000000),
             Param("duration", "Stop after seconds", "int", 60, min=1, max=3600),
             Param("numeric", "Don't resolve names", "bool", True, advanced=True))),
    Tool("termshark", "Termshark", "capture", "Wireshark-like interface in the terminal.",
         "termshark", lambda p: ["termshark", "-i", p["iface"]], mode=TERMINAL,
         privileged=lambda p: not capture_capable("termshark"), params=(IFACE_ANY,)),
    Tool("wireshark", "Wireshark", "capture", "The full graphical packet analyzer.",
         "wireshark", lambda p: ["wireshark"] + _if(p["iface"], "-k", "-i", str(p["iface"])), mode=GUI,
         popular=True, params=(Param("iface", "Start capturing on", "iface", allow_any=True,
                                     help="Optional — leave empty to just open Wireshark"),)),

    # ── Interfaces & routing ────────────────────────────────────────────────
    Tool("ip-addr", "Addresses", "interfaces", "IP addresses assigned to each interface.",
         "ip", lambda p: ["ip"] + _if(p["brief"], "-br") + ["addr", "show"] +
         _if(p["iface"], "dev", str(p["iface"])), popular=True, keywords=("ip address", "ifconfig"), params=(
             IFACE_OPT, Param("brief", "Brief", "bool", True))),
    Tool("ip-route", "Routing Table", "interfaces", "Where packets go: routes and default gateways.",
         "ip", lambda p: ["ip", "-" + p["family"], "route", "show"] + _if(p["table"] == "all", "table", "all"),
         keywords=("gateway", "routes"), params=(
             Param("family", "Family", "choice", "4", choices=(("4", "IPv4"), ("6", "IPv6"))),
             Param("table", "Table", "choice", "main", choices=(("main", "Main"), ("all", "All tables"))))),
    Tool("route-get", "Route Lookup", "interfaces",
         "Which interface, gateway and source IP will be used to reach an address.",
         "ip", lambda p: ["ip", "route", "get", p["ip"]], keywords=("path", "which interface"), params=(
             Param("ip", "Destination IP", "ip", "1.1.1.1", required=True),)),
    Tool("ip-link", "Link Details", "interfaces", "Link-layer details: MTU, state, MAC and driver flags.",
         "ip", lambda p: ["ip", "-d", "link", "show"] + _if(p["iface"], "dev", str(p["iface"])), params=(IFACE_OPT,)),
    Tool("nmcli-devices", "NetworkManager Devices", "interfaces", "Device and connection state from NetworkManager.",
         "nmcli", lambda p: ["nmcli", "device", "show", str(p["iface"])] if p["iface"] else
         [Step(["nmcli", "general", "status"], "General"), Step(["nmcli", "device", "status"], "Devices"),
          Step(["nmcli", "connection", "show", "--active"], "Active connections")],
         params=(IFACE_OPT,)),
    Tool("wifi-scan", "Wi-Fi Scan", "interfaces", "Nearby wireless networks with channel, signal and security.",
         "nmcli", lambda p: ["nmcli", "-f", "IN-USE,SSID,BSSID,CHAN,FREQ,RATE,SIGNAL,BARS,SECURITY",
                             "device", "wifi", "list", "--rescan", "yes" if p["rescan"] else "no"],
         popular=True, keywords=("wireless", "ssid", "channel", "signal"), params=(
             Param("rescan", "Force fresh scan", "bool", True),)),
    Tool("wifi-link", "Wi-Fi Link", "interfaces", "Current Wi-Fi association: signal, bitrate and frequency.",
         "iw", lambda p: ["iw", "dev", p["iface"], "link"], params=(IFACE,)),
    Tool("ethtool", "Ethernet Link", "interfaces", "Negotiated speed, duplex and NIC driver statistics.",
         "ethtool", lambda p: ["ethtool"] + _if(p["view"] == "stats", "-S") + _if(p["view"] == "driver", "-i") +
         [p["iface"]], keywords=("duplex", "speed", "nic"), params=(
             IFACE,
             Param("view", "Show", "choice", "link", choices=(("link", "Link settings"), ("driver", "Driver info"),
                   ("stats", "NIC statistics"))))),
    Tool("nmtui", "nmtui", "interfaces", "Edit and activate connections with NetworkManager's text UI.",
         "nmtui", lambda p: ["nmtui"], mode=TERMINAL),
    Tool("nm-connection-editor", "Connection Editor", "interfaces", "NetworkManager's graphical connection editor.",
         "nm-connection-editor", lambda p: ["nm-connection-editor"], mode=GUI),

    # ── Connections & ports ─────────────────────────────────────────────────
    Tool("listening", "Listening Ports", "connections", "Every service listening on this machine and its process.",
         "ss", lambda p: ["ss", "-ulpn" if p["udp_only"] else "-tulpn"],
         privileged=lambda p: p["all_procs"], popular=True, keywords=("netstat", "open ports", "services"), params=(
             Param("all_procs", "Show processes of all users (admin)", "bool", False),
             Param("udp_only", "UDP only", "bool", False, advanced=True))),
    Tool("established", "Active Connections", "connections", "Established connections and which program owns them.",
         "ss", lambda p: ["ss", "-tup" if p["resolve"] else "-tunp", "state", "established"],
         privileged=lambda p: p["all_procs"], keywords=("netstat", "sessions"), params=(
             Param("resolve", "Resolve names", "bool", False),
             Param("all_procs", "Show processes of all users (admin)", "bool", False))),
    Tool("port-owner", "Who Uses This Port?", "connections", "Find the process bound to or connected through a port.",
         "lsof", lambda p: ["lsof", "-nP", f"-i:{p['port']}"], privileged=lambda p: p["all_procs"],
         keywords=("lsof", "busy", "address already in use"), params=(
             Param("port", "Port", "port", required=True, placeholder="8080"),
             Param("all_procs", "Include all users' processes (admin)", "bool", False))),
    Tool("socket-summary", "Socket Summary", "connections", "Totals of TCP/UDP sockets by state.",
         "ss", lambda p: ["ss", "-s"]),
    Tool("tcp-states", "TCP Connection States", "connections", "All TCP sockets with timers and queue sizes.",
         "ss", lambda p: ["ss", "-tanoi"] + _if(p["port"], "(", "sport", "=", f":{p['port']}", "or",
                                                 "dport", "=", f":{p['port']}", ")"),
         keywords=("time_wait", "close_wait", "retransmit"), params=(
             Param("port", "Filter by port", "port", placeholder="optional"),)),

    # ── Web & TLS ───────────────────────────────────────────────────────────
    Tool("http-headers", "HTTP Headers", "web", "Status line and response headers, following redirects.",
         "curl", lambda p: ["curl", "-sS", "-D", "-", "-o", "/dev/null", "--max-time", "20",
                            "-A", "NetDeck"] + _if(p["follow"], "-L") + _if(p["method"] == "HEAD", "-I") +
         ["--", p["url"]], popular=True, keywords=("curl", "status", "redirect"), params=(
             Param("url", "URL", "url", required=True, placeholder="https://example.com"),
             Param("follow", "Follow redirects", "bool", True),
             Param("method", "Method", "choice", "GET", choices=(("GET", "GET"), ("HEAD", "HEAD"))))),
    Tool("http-timing", "HTTP Timing", "web", "Break down where time goes: DNS, connect, TLS, first byte, total.",
         "curl", lambda p: ["curl", "-sS", "-o", "/dev/null", "--max-time", "30", "-w", CURL_TIMING] +
         _if(p["follow"], "-L") + ["--", p["url"]], keywords=("latency", "slow website", "ttfb"), params=(
             Param("url", "URL", "url", required=True, placeholder="https://example.com"),
             Param("follow", "Follow redirects", "bool", True))),
    Tool("tls-inspect", "TLS Certificate", "web", "Verify a server's certificate, chain, expiry and protocol.",
         None, lambda p: Internal(probes.tls_inspect, "TLS handshake"), popular=True,
         keywords=("ssl", "https", "expiry", "openssl"), params=(
             Param("host", "Host", "host", required=True, placeholder="example.com"),
             Param("port", "Port", "port", 443),
             Param("sni", "SNI name", "host", placeholder="same as host", advanced=True))),
    Tool("public-ip", "Public IP", "web", "Your public IPv4/IPv6 address and approximate location.",
         "curl", lambda p: [Step(["curl", "-sS", "-4", "--max-time", "10", "https://ifconfig.co/json"], "IPv4")] +
         ([Step(["curl", "-sS", "-6", "--max-time", "10", "https://ifconfig.co/json"], "IPv6")] if p["v6"] else []),
         keywords=("wan", "external ip", "nat"), notes="Contacts ifconfig.co.", params=(
             Param("v6", "Also check IPv6", "bool", True),)),

    # ── Firewall ────────────────────────────────────────────────────────────
    Tool("nft", "nftables Ruleset", "firewall", "The complete active nftables ruleset.",
         "nft", lambda p: ["nft"] + _if(p["handles"], "-a") + ["list", "ruleset"], privileged=True,
         popular=True, params=(Param("handles", "Show rule handles", "bool", False),)),
    Tool("iptables", "iptables Rules", "firewall", "Legacy iptables rules with packet counters.",
         "iptables", lambda p: ["iptables", "-t", p["table"], "-L", "-n", "-v", "--line-numbers"], privileged=True,
         params=(Param("table", "Table", "choice", "filter", choices=(("filter", "filter"), ("nat", "nat"),
                                                                       ("mangle", "mangle"), ("raw", "raw"))),)),
    Tool("ufw", "UFW Status", "firewall", "Uncomplicated Firewall status and rules.",
         "ufw", lambda p: ["ufw", "status", "verbose"], privileged=True),
    Tool("firewalld", "firewalld Zones", "firewall", "Active firewalld zones, services and ports.",
         "firewall-cmd", lambda p: ["firewall-cmd", "--list-all-zones" if p["all"] else "--list-all"],
         params=(Param("all", "All zones", "bool", False),)),
)

TOOLS_BY_ID: Dict[str, Tool] = {t.id: t for t in TOOLS}

# Package names per distro family for install hints and the installer.
PACKAGES: Dict[str, Dict[str, str]] = {
    "ping": {"arch": "iputils", "debian": "iputils-ping", "fedora": "iputils", "suse": "iputils"},
    "tracepath": {"arch": "iputils", "debian": "iputils-tracepath", "fedora": "iputils", "suse": "iputils"},
    "arping": {"arch": "iputils", "debian": "iputils-arping", "fedora": "iputils", "suse": "iputils"},
    "traceroute": {"arch": "traceroute", "debian": "traceroute", "fedora": "traceroute", "suse": "traceroute"},
    "mtr": {"arch": "mtr", "debian": "mtr-tiny", "fedora": "mtr", "suse": "mtr"},
    "gping": {"arch": "gping", "debian": "gping", "fedora": "gping"},
    "trip": {"arch": "trippy"},
    "dig": {"arch": "bind", "debian": "dnsutils", "fedora": "bind-utils", "suse": "bind-utils"},
    "host": {"arch": "bind", "debian": "dnsutils", "fedora": "bind-utils", "suse": "bind-utils"},
    "whois": {"arch": "whois", "debian": "whois", "fedora": "whois", "suse": "whois"},
    "resolvectl": {"arch": "systemd", "debian": "systemd-resolved", "fedora": "systemd-resolved"},
    "nmap": {"arch": "nmap", "debian": "nmap", "fedora": "nmap", "suse": "nmap"},
    "arp-scan": {"arch": "arp-scan", "debian": "arp-scan", "fedora": "arp-scan", "suse": "arp-scan"},
    "zenmap": {"debian": "zenmap", "fedora": "nmap-frontend"},
    "iperf3": {"arch": "iperf3", "debian": "iperf3", "fedora": "iperf3", "suse": "iperf"},
    "speedtest-cli": {"arch": "speedtest-cli", "debian": "speedtest-cli", "fedora": "speedtest-cli"},
    "nethogs": {"arch": "nethogs", "debian": "nethogs", "fedora": "nethogs", "suse": "nethogs"},
    "iftop": {"arch": "iftop", "debian": "iftop", "fedora": "iftop", "suse": "iftop"},
    "bmon": {"arch": "bmon", "debian": "bmon", "fedora": "bmon", "suse": "bmon"},
    "vnstat": {"arch": "vnstat", "debian": "vnstat", "fedora": "vnstat", "suse": "vnstat"},
    "sniffnet": {"arch": "sniffnet"},
    "tcpdump": {"arch": "tcpdump", "debian": "tcpdump", "fedora": "tcpdump", "suse": "tcpdump"},
    "tshark": {"arch": "wireshark-cli", "debian": "tshark", "fedora": "wireshark-cli", "suse": "wireshark"},
    "termshark": {"arch": "termshark", "debian": "termshark"},
    "wireshark": {"arch": "wireshark-qt", "debian": "wireshark", "fedora": "wireshark", "suse": "wireshark-ui-qt"},
    "ip": {"arch": "iproute2", "debian": "iproute2", "fedora": "iproute", "suse": "iproute2"},
    "ss": {"arch": "iproute2", "debian": "iproute2", "fedora": "iproute", "suse": "iproute2"},
    "nmcli": {"arch": "networkmanager", "debian": "network-manager", "fedora": "NetworkManager",
              "suse": "NetworkManager"},
    "nmtui": {"arch": "networkmanager", "debian": "network-manager", "fedora": "NetworkManager-tui",
              "suse": "NetworkManager"},
    "nm-connection-editor": {"arch": "nm-connection-editor", "debian": "network-manager-gnome",
                             "fedora": "nm-connection-editor", "suse": "NetworkManager-connection-editor"},
    "iw": {"arch": "iw", "debian": "iw", "fedora": "iw", "suse": "iw"},
    "ethtool": {"arch": "ethtool", "debian": "ethtool", "fedora": "ethtool", "suse": "ethtool"},
    "lsof": {"arch": "lsof", "debian": "lsof", "fedora": "lsof", "suse": "lsof"},
    "curl": {"arch": "curl", "debian": "curl", "fedora": "curl", "suse": "curl"},
    "nft": {"arch": "nftables", "debian": "nftables", "fedora": "nftables", "suse": "nftables"},
    "iptables": {"arch": "iptables", "debian": "iptables", "fedora": "iptables", "suse": "iptables"},
    "ufw": {"arch": "ufw", "debian": "ufw", "fedora": "ufw", "suse": "ufw"},
    "firewall-cmd": {"arch": "firewalld", "debian": "firewalld", "fedora": "firewalld", "suse": "firewalld"},
}
