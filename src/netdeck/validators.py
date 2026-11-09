"""Strict validation for every user-supplied tool parameter.

Nothing a user types ever reaches a shell: commands are executed as argv lists.
These validators additionally guarantee that values cannot be interpreted as
command-line options (no leading ``-``), contain no control characters, and fit
the shape each tool expects.
"""

from __future__ import annotations

import ipaddress
import os
import re
from typing import Any, Optional
from urllib.parse import urlsplit

_HOST_LABEL = re.compile(r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$")
_IFACE = re.compile(r"^[A-Za-z0-9_.:@-]{1,15}$")
_PORTSPEC = re.compile(r"^[0-9]{1,5}(-[0-9]{1,5})?(,[0-9]{1,5}(-[0-9]{1,5})?)*$")
_IPV4_RANGE = re.compile(r"^((?:\d{1,3}\.){3})(\d{1,3})-(\d{1,3})$")
_RATE = re.compile(r"^\d{1,6}(\.\d{1,3})?[KMGkmg]?$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SERIAL = re.compile(r"^(?:/dev/)?(tty(?:USB|ACM|S)\d{1,3})$")
_COMMUNITY = re.compile(r"^[A-Za-z0-9._@#%+=:~^*!-]{1,64}$")
_USERNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.@-]{0,63}$")

SYS_NET = "/sys/class/net"
DEV_DIR = "/dev"


class ValidationError(ValueError):
    """Raised when a parameter value is rejected."""


def _no_option(value: str) -> str:
    if value.startswith("-"):
        raise ValidationError("must not start with '-'")
    if _CONTROL.search(value):
        raise ValidationError("contains control characters")
    return value


def is_hostname(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    labels = value.rstrip(".").split(".")
    return all(_HOST_LABEL.match(label) for label in labels)


def host(value: str) -> str:
    value = _no_option(value.strip())
    if not value:
        raise ValidationError("is required")
    try:
        return str(ipaddress.ip_address(value.strip("[]")))
    except ValueError:
        pass
    if is_hostname(value):
        return value
    raise ValidationError("must be a hostname or IP address")


def ip(value: str) -> str:
    value = _no_option(value.strip())
    try:
        return str(ipaddress.ip_address(value.strip("[]")))
    except ValueError as exc:
        raise ValidationError("must be an IPv4 or IPv6 address") from exc


def cidr(value: str) -> str:
    value = _no_option(value.strip())
    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError as exc:
        raise ValidationError("must be a network in CIDR form, e.g. 192.168.1.0/24") from exc


def target(value: str) -> str:
    """A scan target: host, IP, CIDR network or IPv4 last-octet range."""
    value = _no_option(value.strip())
    if "/" in value:
        net = cidr(value)
        if ipaddress.ip_network(net).num_addresses > 65536:
            raise ValidationError("network is too large (max /16)")
        return net
    m = _IPV4_RANGE.match(value)
    if m:
        lo, hi = int(m.group(2)), int(m.group(3))
        ip(m.group(1) + m.group(2))
        if not (0 <= lo <= hi <= 255):
            raise ValidationError("invalid address range")
        return value
    try:
        return host(value)
    except ValidationError as exc:
        raise ValidationError("must be a host, IP, CIDR network or range like 10.0.0.1-50") from exc


def hosts(value: str, max_items: int = 6) -> list:
    items = [v for v in re.split(r"[\s,]+", value.strip()) if v]
    if not items:
        raise ValidationError("is required")
    if len(items) > max_items:
        raise ValidationError(f"at most {max_items} hosts")
    return [host(v) for v in items]


def integer(value: Any, lo: Optional[int] = None, hi: Optional[int] = None) -> int:
    try:
        if isinstance(value, bool):
            raise TypeError
        num = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("must be a whole number") from exc
    if lo is not None and num < lo:
        raise ValidationError(f"must be at least {lo}")
    if hi is not None and num > hi:
        raise ValidationError(f"must be at most {hi}")
    return num


def port(value: Any) -> int:
    return integer(value, 1, 65535)


def ports(value: str) -> str:
    value = value.strip().replace(" ", "")
    if not _PORTSPEC.match(value) or len(value) > 256:
        raise ValidationError("use ports and ranges like 22,80,443,8000-8100")
    for part in value.split(","):
        bounds = [int(x) for x in part.split("-")]
        if any(not 1 <= b <= 65535 for b in bounds) or bounds != sorted(bounds):
            raise ValidationError(f"invalid port or range: {part}")
    return value


def boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("1", "true", "yes", "on"):
        return True
    if str(value).lower() in ("0", "false", "no", "off", ""):
        return False
    raise ValidationError("must be true or false")


def choice(value: Any, choices: tuple) -> str:
    allowed = [c[0] for c in choices]
    value = str(value)
    if value not in allowed:
        raise ValidationError("is not one of the allowed options")
    return value


def interface(value: str, allow_any: bool = False) -> str:
    value = value.strip()
    if allow_any and value == "any":
        return value
    if not _IFACE.match(value) or value.startswith("-") or value in (".", ".."):
        raise ValidationError("is not a valid interface name")
    if os.path.isdir(SYS_NET) and not os.path.exists(os.path.join(SYS_NET, value)):
        raise ValidationError(f"interface '{value}' does not exist")
    return value


def url(value: str) -> str:
    value = _no_option(value.strip())
    if len(value) > 2048 or re.search(r"\s", value):
        raise ValidationError("must be a single URL without spaces")
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValidationError("must be an http:// or https:// URL")
    try:
        parts.port  # noqa: B018 — raises ValueError for a non-numeric or out-of-range port
    except ValueError as exc:
        raise ValidationError("has an invalid port") from exc
    host(parts.hostname)
    return value


def rate(value: str) -> str:
    value = value.strip()
    if not _RATE.match(value):
        raise ValidationError("use a bitrate like 50M, 1G or 500K")
    return value


def expression(value: str) -> str:
    """Free-form filter expression (BPF / display filter). Passed as one argv item."""
    value = _no_option(value.strip())
    if len(value) > 512:
        raise ValidationError("is too long (max 512 characters)")
    return value


def serial_device(value: str) -> str:
    """A USB/ACM/onboard serial port, e.g. /dev/ttyUSB0. Returned as an absolute /dev path."""
    m = _SERIAL.match(value.strip())
    if not m:
        raise ValidationError("must be a serial port such as /dev/ttyUSB0 or /dev/ttyACM0")
    name = m.group(1)
    if os.path.isdir(DEV_DIR) and not os.path.exists(os.path.join(DEV_DIR, name)):
        raise ValidationError(f"/dev/{name} does not exist — is the console cable plugged in?")
    return f"/dev/{name}"


def community(value: str) -> str:
    """An SNMP v1/v2c community string."""
    value = _no_option(value.strip())
    if not _COMMUNITY.match(value):
        raise ValidationError("may only contain letters, digits and . _ @ # % + = : ~ ^ * ! -")
    return value


def username(value: str) -> str:
    value = _no_option(value.strip())
    if not _USERNAME.match(value):
        raise ValidationError("must be a user name such as admin or cisco")
    return value


def validate(param, raw: Any) -> Any:
    """Validate ``raw`` against a :class:`netdeck.catalog.Param`. Returns the clean value."""
    kind = param.kind
    if kind == "bool":
        return boolean(raw if raw is not None else param.default or False)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        if param.required:
            raise ValidationError("is required")
        return param.default
    if kind == "host":
        return host(str(raw))
    if kind == "hosts":
        return hosts(str(raw))
    if kind == "target":
        return target(str(raw))
    if kind == "ip":
        return ip(str(raw))
    if kind == "cidr":
        return cidr(str(raw))
    if kind == "int":
        return integer(raw, param.min, param.max)
    if kind == "port":
        return port(raw)
    if kind == "ports":
        return ports(str(raw))
    if kind == "choice":
        return choice(raw, param.choices)
    if kind == "iface":
        return interface(str(raw), param.allow_any)
    if kind == "url":
        return url(str(raw))
    if kind == "rate":
        return rate(str(raw))
    if kind == "expr":
        return expression(str(raw))
    if kind == "serial":
        return serial_device(str(raw))
    if kind == "community":
        return community(str(raw))
    if kind == "username":
        return username(str(raw))
    raise ValidationError(f"unknown parameter kind {kind!r}")
