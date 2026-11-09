import pytest

from netdeck import validators as v
from netdeck.catalog import Param


@pytest.mark.parametrize("value", ["example.com", "a.b-c.io", "1.1.1.1", "::1", "[2606:4700::1111]", "localhost"])
def test_host_accepts(value):
    assert v.host(value)


BAD_HOSTS = ["-oProxyCommand=x", "a b", "exa$mple.com", "", "x" * 300, "foo;rm", "-", "a..b", "bad\nhost"]


@pytest.mark.parametrize("value", BAD_HOSTS)
def test_host_rejects(value):
    with pytest.raises(v.ValidationError):
        v.host(value)


def test_target_forms():
    assert v.target("192.168.1.0/24") == "192.168.1.0/24"
    assert v.target("192.168.1.7/24") == "192.168.1.0/24"  # normalised
    assert v.target("10.0.0.1-50") == "10.0.0.1-50"
    assert v.target("scanme.nmap.org") == "scanme.nmap.org"
    with pytest.raises(v.ValidationError):
        v.target("10.0.0.0/8")  # too large
    with pytest.raises(v.ValidationError):
        v.target("10.0.0.9-3")


@pytest.mark.parametrize("value", ["22", "22,80,443", "1-1024", "80,8000-8100"])
def test_ports_ok(value):
    assert v.ports(value) == value


@pytest.mark.parametrize("value", ["0", "70000", "80-20", "a", "22;ls", "-p-"])
def test_ports_bad(value):
    with pytest.raises(v.ValidationError):
        v.ports(value)


def test_integer_bounds():
    assert v.integer("5", 1, 10) == 5
    for bad in ("0", "11", "x", True, None):
        with pytest.raises(v.ValidationError):
            v.integer(bad, 1, 10)


def test_url():
    assert v.url("example.com") == "https://example.com"
    assert v.url("http://a.b/c?d=1") == "http://a.b/c?d=1"
    for bad in ("ftp://x", "file:///etc/passwd", "-K", "https://exa mple.com", "javascript:alert(1)"):
        with pytest.raises(v.ValidationError):
            v.url(bad)


def test_interface_rejects_traversal(tmp_path, monkeypatch):
    (tmp_path / "eth0").mkdir()
    monkeypatch.setattr(v, "SYS_NET", str(tmp_path))
    assert v.interface("eth0") == "eth0"
    assert v.interface("any", allow_any=True) == "any"
    for bad in ("../etc", "eth9", "-i", "a" * 20, "any"):
        with pytest.raises(v.ValidationError):
            v.interface(bad)


def test_expression_no_option():
    assert v.expression("port 53 or host 1.1.1.1") == "port 53 or host 1.1.1.1"
    with pytest.raises(v.ValidationError):
        v.expression("-w /etc/shadow")


def test_validate_defaults_and_required():
    p = Param("count", "Count", "int", 5, min=1, max=9)
    assert v.validate(p, None) == 5
    assert v.validate(p, "") == 5
    req = Param("host", "Host", "host", required=True)
    with pytest.raises(v.ValidationError):
        v.validate(req, "  ")
    b = Param("flag", "Flag", "bool", False)
    assert v.validate(b, None) is False
    assert v.validate(b, "true") is True
    c = Param("m", "M", "choice", "a", choices=(("a", "A"), ("b", "B")))
    with pytest.raises(v.ValidationError):
        v.validate(c, "z")
