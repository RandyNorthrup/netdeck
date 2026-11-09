# Administrator access

NetDeck itself always runs as your normal user. Tools that need root are elevated **per command**, and the UI
marks them with an *Admin* badge and shows the elevated command (`pkexec …` / `sudo …`) before you run it.

## How NetDeck decides

1. If the tool's binary already has **file capabilities** (e.g. `cap_net_raw`) and you can execute it, it runs
   unprivileged. Arch Linux ships `nethogs`, `arp-scan`, `mtr-packet` and Wireshark's `dumpcap` this way.
   For `tshark`/`termshark`/Wireshark, membership of the `wireshark` group is enough.
2. Otherwise NetDeck uses the method chosen in **Settings → Administrator access**:

| Mode | Behaviour |
| --- | --- |
| `auto` (default) | `sudo` if it works without a password, else `pkexec` in a graphical session, else none |
| `pkexec` | polkit asks for your password in a dialog for every elevated command |
| `sudo` | requires a passwordless sudo rule (`sudo -n`) |
| `none` | privileged tools are disabled |

Interactive terminal tools are started with `sudo` inside the terminal window, where you can type your password.

## Stopping elevated tools

With `sudo`, *Stop* signals the process normally. Processes started through `pkexec` run with root's user id
and cannot be signalled by your user; NetDeck closes their output pipe instead, so they exit at their next
write. Every elevated streaming tool also ends on its own (packet count, sample period, or one-shot output).

## Optional: avoid password prompts for capture tools

Prefer capabilities over blanket sudo rules. For example:

```bash
sudo usermod -aG wireshark "$USER"          # tshark / termshark / Wireshark (log out and in again)
sudo setcap cap_net_raw,cap_net_admin=eip "$(command -v tcpdump)"
sudo setcap cap_net_raw,cap_net_admin=eip "$(command -v iftop)"
```

Package upgrades may reset capabilities. Only grant them on machines where every local user is trusted with
packet capture.
