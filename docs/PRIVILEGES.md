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

With `sudo`, *Stop* and *Exit* signal the process normally (sudo passes the signal on).

Processes started through `pkexec` run with root's user id, so your user cannot signal them. NetDeck therefore
starts them under a tiny root-side supervisor (a fixed POSIX `sh` script; the tool's arguments are passed as
positional parameters and never interpolated) and keeps the supervisor's stdin open. To stop the tool, NetDeck
closes that pipe, which needs no privileges; the supervisor then sends `SIGINT` (so tools print their summary),
then `SIGTERM` and `SIGKILL` two seconds apart. The pipe also closes if NetDeck itself dies, so an elevated
tool cannot outlive it. Because of this, the polkit dialog names `/bin/sh` as the program to run; its details
show the full command line.

## Optional: avoid password prompts for capture tools

Prefer capabilities over blanket sudo rules. For example:

```bash
sudo usermod -aG wireshark "$USER"          # tshark / termshark / Wireshark (log out and in again)
sudo setcap cap_net_raw,cap_net_admin=eip "$(command -v tcpdump)"
sudo setcap cap_net_raw,cap_net_admin=eip "$(command -v iftop)"
```

Package upgrades may reset capabilities. Only grant them on machines where every local user is trusted with
packet capture.
