"""Field kit: exact commands for the field tools, their validators, and the fixes from the field smoke run."""

import os

import pytest

from netdeck import probes, sysinfo, validators
from netdeck.catalog import LLDP_CDP_FILTER, SSH_LEGACY, TOOLS_BY_ID, Step


def build(tool_id, **params):
    """Validate params exactly as the server does, then build the plan's argv lists."""
    tool = TOOLS_BY_ID[tool_id]
    clean = {p.name: validators.validate(p, params.get(p.name)) for p in tool.params}
    plan = tool.plan(dict(clean, _elevated=False, _user="tester"))
    argvs = [s.argv for s in plan.steps if isinstance(s, Step)]
    return tool, clean, argvs


@pytest.fixture(autouse=True)
def lenient_devices(monkeypatch):
    monkeypatch.setattr(validators, "SYS_NET", "/nonexistent")
    monkeypatch.setattr(validators, "DEV_DIR", "/nonexistent")


# -- fixes ----------------------------------------------------------------------------------------------

def test_os_fingerprint_shows_progress_and_skips_service_detection_by_default():
    _, _, argvs = build("nmap-os", target="10.0.0.1")
    assert argvs == [["nmap", "-O", "--osscan-guess", "-T4", "--stats-every", "10s", "--", "10.0.0.1"]]
    _, _, argvs = build("nmap-os", target="10.0.0.1", service=True)
    assert "-sV" in argvs[0]


def test_public_ip_checks_ipv4_only_by_default():
    _, _, argvs = build("public-ip")
    assert len(argvs) == 1 and "-4" in argvs[0]
    _, _, argvs = build("public-ip", v6=True)
    assert [a[2] for a in argvs] == ["-4", "-6"]


def make_iface(root, name, product=None):
    base = root / name
    (base / "device").mkdir(parents=True)
    if product is not None:
        (root / name / "product").write_text(product + "\n")  # device/.. resolves to the iface directory here
    return base


def test_apple_t2_link_is_internal_not_ethernet(tmp_path, monkeypatch):
    monkeypatch.setattr(sysinfo, "SYS_NET", str(tmp_path))
    make_iface(tmp_path, "enp1s0f1u1", "Apple T2 Controller")
    make_iface(tmp_path, "enx001122334455", "USB 10/100/1000 LAN")
    assert sysinfo._iface_kind("enp1s0f1u1") == "internal"
    assert sysinfo._iface_kind("enx001122334455") == "ethernet"


def test_health_check_does_not_count_the_t2_link_as_a_network_link(monkeypatch):
    internal_only = [{"name": "enp1s0f1u1", "kind": "internal", "state": "up", "loopback": False,
                      "addresses": [{"family": "inet", "address": "169.254.1.2", "prefix": 16}]}]
    monkeypatch.setattr(sysinfo, "interfaces", lambda: internal_only)
    monkeypatch.setattr(sysinfo, "default_gateway", lambda: None)
    monkeypatch.setattr(probes.socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(probes.socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(OSError("off")))
    link = next(s for s in probes.health_check() if s["id"] == "link")
    assert link["status"] == "fail", link


# -- new tools: exact commands, categories, elevation ---------------------------------------------------

EXPECTED = [
    ("mtu-test", "connectivity", {"host": "1.1.1.1"},
     [["ping", "-M", "do", "-s", "1472", "-c", "3", "-W", "2", "--", "1.1.1.1"]]),
    ("dup-ip", "connectivity", {"ip": "10.0.0.5", "iface": "eth0"},
     [["arping", "-D", "-c", "3", "-I", "eth0", "--", "10.0.0.5"]]),
    ("dhcp-check", "lan", {"iface": "eth0"}, [["nmap", "--script", "broadcast-dhcp-discover", "-e", "eth0"]] * 2),
    ("switch-port", "lan", {"iface": "eth0"},
     [["timeout", "65", "tcpdump", "-i", "eth0", "-nn", "-v", "-s", "1500", "-c", "1", "--", LLDP_CDP_FILTER]]),
    ("snmp", "lan", {"host": "10.0.0.2", "community": "s3cret"},
     [["snmpwalk", "-v", "2c", "-c", "s3cret", "-t", "2", "-r", "1", "udp:10.0.0.2:161", "1.3.6.1.2.1.1"]]),
    ("snmp", "lan", {"host": "fd00::2", "community": "public", "view": "lldp", "version": "1"},
     [["snmpwalk", "-v", "1", "-c", "public", "-t", "2", "-r", "1", "udp6:[fd00::2]:161", "1.0.8802.1.1.2.1.4.1.1.9"],
      ["snmpwalk", "-v", "1", "-c", "public", "-t", "2", "-r", "1", "udp6:[fd00::2]:161", "1.0.8802.1.1.2.1.4.1.1.7"]]),
    ("lan-discovery", "lan", {"iface": "wlan0"},
     [["nmap", "--script",
       "broadcast-dns-service-discovery,broadcast-upnp-info,broadcast-netbios-master-browser", "-e", "wlan0"]]),
    ("netbios-scan", "lan", {"target": "192.168.1.0/24"}, [["nbtscan", "192.168.1.0/24"]]),
    ("ipv6-ra", "lan", {"iface": "eth0"}, [["rdisc6", "-w", "2000", "eth0"]]),
    ("wifi-scan", "wifi", {}, None),
    ("wifi-link", "wifi", {"iface": "wlan0"}, [["iw", "dev", "wlan0", "link"]]),
    ("wifi-meter", "wifi", {"iface": "wlan0"}, [["wavemon", "-i", "wlan0"]]),
    ("wifi-chart", "wifi", {}, [["linssid-pkexec"]]),
    ("monitor-on", "wifi", {"iface": "wlan1"}, [["airmon-ng", "start", "wlan1"]]),
    ("monitor-off", "wifi", {"iface": "wlan1mon"}, [["airmon-ng", "stop", "wlan1mon"]]),
    ("wifi-survey", "wifi", {"iface": "wlan1mon", "band": "a"}, [["airodump-ng", "--band", "a", "wlan1mon"]]),
    ("serial-console", "access", {"device": "/dev/ttyUSB0"}, [["picocom", "-b", "9600", "/dev/ttyUSB0"]]),
    ("ssh", "access", {"host": "10.0.0.2", "user": "admin"}, [["ssh", "-p", "22", "--", "admin@10.0.0.2"]]),
    ("ssh", "access", {"host": "10.0.0.2", "legacy": True}, [["ssh", "-p", "22", *SSH_LEGACY, "--", "10.0.0.2"]]),
    ("telnet", "access", {"host": "10.0.0.2"}, [["telnet", "10.0.0.2", "23"]]),
    ("bandwhich", "traffic", {"iface": "wlan0"}, [["bandwhich", "-i", "wlan0"]]),
    ("tls-audit", "web", {"host": "example.com"},
     [["testssl", "--quiet", "--color", "0", "--warnings", "batch", "example.com:443"]]),
    ("ethtool", "interfaces", {"iface": "eth0", "view": "cable"}, [["ethtool", "--cable-test", "eth0"]]),
]


@pytest.mark.parametrize(("tool_id", "category", "params", "argvs"), EXPECTED,
                         ids=[f"{e[0]}-{i}" for i, e in enumerate(EXPECTED)])
def test_field_tool_commands(tool_id, category, params, argvs):
    tool, _, built = build(tool_id, **params)
    assert tool.category == category
    if argvs is not None:
        assert built == argvs


@pytest.mark.parametrize(("tool_id", "params", "elevated"), [
    ("dhcp-check", {"iface": "eth0"}, True),
    ("lan-discovery", {"iface": "eth0"}, True),
    ("monitor-on", {"iface": "wlan1"}, True),
    ("wifi-survey", {"iface": "wlan1mon"}, True),
    ("ethtool", {"iface": "eth0", "view": "cable"}, True),
    ("ethtool", {"iface": "eth0", "view": "link"}, False),
    ("netbios-scan", {"target": "10.0.0.0/24"}, False),
    ("ipv6-ra", {"iface": "eth0"}, False),
    ("telnet", {"host": "10.0.0.2"}, False),
])
def test_field_tool_elevation(tool_id, params, elevated):
    if os.geteuid() == 0:
        pytest.skip("everything runs unelevated as root")
    tool, clean, _ = build(tool_id, **params)
    assert tool.needs_root(clean) is elevated


def test_serial_console_elevates_only_without_device_access(tmp_path, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root can open any device")
    tool = TOOLS_BY_ID["serial-console"]
    port = tmp_path / "ttyUSB0"
    port.write_text("")
    port.chmod(0o600)
    assert tool.needs_root({"device": str(port), "baud": "9600"}) is False
    port.chmod(0o000)
    assert tool.needs_root({"device": str(port), "baud": "9600"}) is True


# -- validators -------------------------------------------------------------------------------------------

def test_serial_device_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(validators, "DEV_DIR", str(tmp_path))
    (tmp_path / "ttyUSB0").write_text("")
    assert validators.serial_device("/dev/ttyUSB0") == "/dev/ttyUSB0"
    assert validators.serial_device("ttyUSB0") == "/dev/ttyUSB0"
    for bad in ("/dev/ttyUSB1", "/dev/sda", "/etc/passwd", "/dev/../dev/ttyUSB0", "-b", "ttyUSB0;reboot", ""):
        with pytest.raises(validators.ValidationError):
            validators.serial_device(bad)


@pytest.mark.parametrize("good", ["public", "s3cr3t-RO", "c0mm@site#1"])
def test_community_accepts(good):
    assert validators.community(good) == good


@pytest.mark.parametrize("bad", ["-v1", "pub lic", "a;b", "$(id)", "x" * 65, "back`tick`"])
def test_community_rejects(bad):
    with pytest.raises(validators.ValidationError):
        validators.community(bad)


@pytest.mark.parametrize(("value", "ok"), [("admin", True), ("Cisco_1", True), ("ops.team", True),
                                           ("-oProxyCommand=x", False), ("a b", False), ("root;id", False),
                                           ("9lives", False)])
def test_username_validation(value, ok):
    if ok:
        assert validators.username(value) == value
    else:
        with pytest.raises(validators.ValidationError):
            validators.username(value)
