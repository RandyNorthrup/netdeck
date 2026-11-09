"""Field self-test: run the hardware-free field tools through a real NetDeck on the network you are on.

Opt-in (it sends real traffic on the local network): NETDECK_TEST_LIVE=1 pytest tests/test_field_live.py
Use it on site to confirm the kit works before you start. It uses the default gateway and interface of the
machine; SNMP is checked against a temporary local agent because most gateways do not run one.
On a UniFi network, set NETDECK_TEST_UNIFI_CONTROLLER=<controller address> to also require that UniFi devices are
found and the controller's inform endpoint answers.
"""

import json
import os
import shutil
import subprocess
import time

import pytest

from netdeck import sysinfo
from test_cli import api, start_server

pytestmark = pytest.mark.skipif(os.environ.get("NETDECK_TEST_LIVE") != "1",
                                reason="sends traffic on the local network; set NETDECK_TEST_LIVE=1")


@pytest.fixture(scope="module")
def lan():
    primary = sysinfo.primary()
    if not primary["gateway"]:
        pytest.fail("no default gateway: connect to a network first")
    return primary


@pytest.fixture(scope="module")
def deck(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("live")
    (tmp / "run").mkdir(mode=0o700)
    env = dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"),
               XDG_RUNTIME_DIR=str(tmp / "run"), XDG_CONFIG_HOME=str(tmp / "cfg"),
               NETDECK_CAPTURES_DIR=str(tmp / "captures"), PYTHONUNBUFFERED="1")
    proc, port, token = start_server(env, tmp)
    yield port, token
    proc.terminate()
    proc.wait(30)
    proc.log.close()


def run(deck, tool, params, timeout=240):
    """Run a tool through the API; return (status, exit code, seconds, output text)."""
    port, token = deck
    start = time.monotonic()
    status, data = api(port, token, "POST", "/api/run", {"tool": tool, "params": params})
    assert status == 200, data
    job_id = data["job"]["id"]
    while time.monotonic() - start < timeout:
        _, job = api(port, token, "GET", f"/api/jobs/{job_id}")
        if job["status"] != "running":
            break
        time.sleep(0.5)
    else:
        pytest.fail(f"{tool} still running after {timeout} s")
    output = "\n".join(job["command"]) + "\n" + _output(deck, job_id)
    return job["status"], job["exit_code"], time.monotonic() - start, output


def _output(deck, job_id):
    import http.client

    port, token = deck
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request("GET", f"/api/jobs/{job_id}/output",
                 headers={"Host": f"127.0.0.1:{port}", "Cookie": f"netdeck_{port}={token}"})
    return conn.getresponse().read().decode()


def test_dhcp_check_finds_the_dhcp_server(deck, lan):
    status, _, _, out = run(deck, "dhcp-check", {"iface": lan["iface"]})
    assert status == "done", out
    assert "Server Identifier" in out, f"no DHCP server answered:\n{out}"


def test_device_discovery_and_netbios_scan_complete(deck, lan):
    for tool, params in (("lan-discovery", {"iface": lan["iface"]}), ("netbios-scan", {"target": lan["subnet"]})):
        status, code, _, out = run(deck, tool, params)
        assert (status, code) == ("done", 0), out


@pytest.fixture
def snmp_agent(tmp_path):
    if not shutil.which("snmpd"):
        pytest.skip("snmpd not installed")
    conf = tmp_path / "snmpd.conf"
    conf.write_text("agentaddress udp:127.0.0.1:16161\nrocommunity netdeck-selftest 127.0.0.1\n"
                    "sysDescr NetDeck field self-test agent\n")
    agent = subprocess.Popen([shutil.which("snmpd"), "-f", "-Lo", "-C", "-c", str(conf)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    yield
    agent.terminate()
    agent.wait(10)


def test_snmp_query_reads_the_agent(deck, snmp_agent):
    status, code, _, out = run(deck, "snmp", {"host": "127.0.0.1", "port": 16161, "community": "netdeck-selftest"})
    assert (status, code) == ("done", 0), out
    assert "NetDeck field self-test agent" in out, out


def test_mtu_test_passes_at_1472_and_reports_fragmentation_at_1500(deck, lan):
    status, code, _, out = run(deck, "mtu-test", {"host": lan["gateway"], "size": 1472})
    assert (status, code) == ("done", 0), out
    status, code, _, out = run(deck, "mtu-test", {"host": lan["gateway"], "size": 1500})
    assert status == "failed" and code != 0, f"a 1528-byte packet passed with fragmentation forbidden:\n{out}"
    assert "message too long" in out.lower() or "frag needed" in out.lower(), out


def test_duplicate_ip_check_flags_an_address_in_use(deck, lan):
    _, code, _, out = run(deck, "dup-ip", {"ip": lan["gateway"], "iface": lan["iface"]})
    assert code == 1, f"the gateway's address should be reported as in use:\n{out}"
    assert "Received" in out and "response" in out, out


def test_os_fingerprint_is_quick_by_default(deck, lan):
    status, code, seconds, out = run(deck, "nmap-os", {"target": lan["gateway"]})
    assert (status, code) == ("done", 0), out
    assert seconds < 60, f"took {seconds:.0f} s"
    assert "OS details" in out or "Running" in out or "OS guesses" in out, out


def test_switch_port_capture_ends_within_its_limit(deck, lan):
    _, code, seconds, out = run(deck, "switch-port", {"iface": lan["iface"], "wait": 12}, timeout=40)
    assert code in (0, 124), out  # 0: an LLDP/CDP frame arrived; 124: none within the limit
    assert seconds < 25


def test_switch_neighbors_reads_lldpd(deck):
    status, code, _, out = run(deck, "switch-neighbors", {}, timeout=30)
    assert (status, code) == ("done", 0), f"is the lldpd service running?\n{out}"
    assert "LLDP neighbors" in out, out


def test_ipv6_ra_tls_audit_public_ip_and_usage_history_complete(deck, lan):
    status, _, _, out = run(deck, "ipv6-ra", {"iface": lan["iface"]}, timeout=30)
    assert status in ("done", "failed") and "Soliciting" in out, out
    status, code, _, out = run(deck, "tls-audit", {"host": "example.com"}, timeout=420)
    assert (status, code) == ("done", 0), out[-2000:]
    assert "Testing protocols" in out, out[-2000:]
    status, code, _, out = run(deck, "public-ip", {})
    assert (status, code) == ("done", 0), out
    assert json.loads(out[out.index("{"):])["ip"], out
    status, code, _, out = run(deck, "vnstat", {})
    assert (status, code) == ("done", 0), out


UNIFI_CONTROLLER = os.environ.get("NETDECK_TEST_UNIFI_CONTROLLER")


def test_unifi_discovery_completes_and_finds_devices_on_unifi_networks(deck, lan):
    status, code, seconds, out = run(deck, "unifi-discover", {"target": lan["subnet"]})
    assert (status, code) == ("done", 0), out
    assert seconds < 90, f"took {seconds:.0f} s"
    if UNIFI_CONTROLLER:
        assert "ubiquiti-discovery:" in out and "config_status:" in out, f"no UniFi device answered:\n{out}"


def test_unifi_inform_check(deck, lan):
    status, code, _, out = run(deck, "unifi-inform", {"controller": UNIFI_CONTROLLER or lan["gateway"]}, timeout=30)
    assert status in ("done", "failed") and "Checking http://" in out, out
    if UNIFI_CONTROLLER:
        assert (status, code) == ("done", 0), out
        assert "UniFi inform endpoint answers" in out, out
