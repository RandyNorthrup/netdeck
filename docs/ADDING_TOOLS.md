# Adding a tool

Every tool is one `Tool(...)` entry in [`src/netdeck/catalog.py`](../src/netdeck/catalog.py). The UI form,
validation, command preview, install hints and search are all generated from it.

```python
Tool(
    "http-timing",                 # unique id (used in URLs: #/t/http-timing)
    "HTTP Timing",                 # display name
    "web",                         # category id (see CATEGORIES)
    "Break down where time goes: DNS, connect, TLS, first byte, total.",  # one sentence
    "curl",                        # binary that must be installed (None for built-in Python probes)
    lambda p: ["curl", "-sS", "-o", "/dev/null", "-w", CURL_TIMING, "--", p["url"]],
    params=(
        Param("url", "URL", "url", required=True, placeholder="https://example.com"),
        Param("follow", "Follow redirects", "bool", True),
    ),
    keywords=("latency", "slow website", "ttfb"),   # extra words for the command palette
    popular=False,                 # show on the Overview page
)
```

## Parameters

| kind | UI control | validation |
| --- | --- | --- |
| `host` | text + recent hosts | hostname or IP, no leading `-` |
| `hosts` | text | up to 6 hosts separated by spaces/commas |
| `target` | text | host, IP, CIDR (≤ /16) or `a.b.c.d-e` range |
| `ip` / `cidr` | text | IPv4/IPv6 address / network |
| `int` / `port` | number | integer within `min`/`max` / 1–65535 |
| `ports` | text | `22,80,8000-8100` |
| `choice` | segmented control (≤ 4 short options) or select | one of `choices` |
| `bool` | toggle | — |
| `iface` | interface picker | must exist in `/sys/class/net`; `allow_any=True` adds `any` |
| `url` | text | http(s) URL |
| `rate` | text | bitrate such as `100M` |
| `expr` | text | free-form filter (BPF / display filter), passed as **one** argv item |

Useful `Param` options: `default`, `required`, `help`, `placeholder`, `min`, `max`, `advanced=True`
(collapsed under *Advanced options*) and `prefill="gateway" | "subnet" | "iface" | "ip"` (filled from the
live network state).

## Builders

A builder receives **validated** parameters and returns one of:

- an argv list — `["dig", p["name"], p["rtype"]]`
- a list of `Step(argv, label)` — run sequentially with section headers
- an `Internal(fn, label)` — a Python probe `fn(params, emit, stop_event) -> exit_code`
- a `Plan(steps, artifact=path)` — when the tool produces a file (e.g. a `.pcap`)

Rules:

1. **Never** create shell strings or call `sh -c`.
2. Put user-supplied positional values after `--` whenever the tool supports it.
3. Use `_if(condition, *args)` for optional flags.

## Modes and privileges

- `mode=STREAM` (default) streams output into the console; `TERMINAL` opens the user's terminal (for TUIs);
  `GUI` launches a desktop application.
- `privileged=True` always elevates; `privileged=lambda p: ...` decides per run (e.g. only for SYN scans).
  Use `capture_capable("binary")` to skip elevation when the binary already has file capabilities.
- `long_running=True` marks tools that run until stopped.

## Install hints

Add the binary's package name per distro family to `PACKAGES` at the bottom of `catalog.py`.
`tests/test_catalog.py` fails if a binary has no hint and checks that every tool builds a valid argv.
