#!/usr/bin/env bash
# NetDeck installer — per-user by default, no root required for NetDeck itself.
#
#   ./scripts/install.sh                 install for the current user
#   ./scripts/install.sh --with-tools    also install the network tools via your package manager
#   ./scripts/install.sh --service       also start NetDeck automatically at login (systemd --user)
#   ./scripts/install.sh --system        install for all users under /opt/netdeck (needs sudo)
#   curl -fsSL https://raw.githubusercontent.com/randynorthrup/netdeck/main/scripts/install.sh | bash
set -euo pipefail

REPO_URL="${NETDECK_REPO:-https://github.com/randynorthrup/netdeck.git}"
REF="${NETDECK_REF:-main}"
MIN_PY="3.10"
WITH_TOOLS=0
SERVICE=0
SYSTEM=0
ASSUME_YES=0

c_blue=$'\033[1;34m'; c_green=$'\033[1;32m'; c_yellow=$'\033[1;33m'; c_red=$'\033[1;31m'; c_off=$'\033[0m'
[ -t 1 ] || { c_blue=; c_green=; c_yellow=; c_red=; c_off=; }
info() { printf '%s==>%s %s\n' "$c_blue" "$c_off" "$*"; }
ok()   { printf '%s ✓%s  %s\n' "$c_green" "$c_off" "$*"; }
warn() { printf '%s !%s  %s\n' "$c_yellow" "$c_off" "$*" >&2; }
die()  { printf '%s ✗%s  %s\n' "$c_red" "$c_off" "$*" >&2; exit 1; }

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

for arg in "$@"; do
  case "$arg" in
    --with-tools) WITH_TOOLS=1 ;;
    --service) SERVICE=1 ;;
    --system) SYSTEM=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage ;;
    *) die "unknown option: $arg (see --help)" ;;
  esac
done

[ "$(uname -s)" = "Linux" ] || die "NetDeck supports Linux only."

# ── Python ──────────────────────────────────────────────────────────────────
PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 is required (>= $MIN_PY). Install it with your package manager first."
"$PY" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" \
  || die "Python >= $MIN_PY is required; found $("$PY" -V 2>&1)."
"$PY" -c "import venv, ensurepip" 2>/dev/null \
  || die "Python's venv module is missing. On Debian/Ubuntu: sudo apt install python3-venv"
ok "Python $("$PY" -c 'import platform; print(platform.python_version())')"

# ── Source ──────────────────────────────────────────────────────────────────
SRC_DIR=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
  SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  command -v git >/dev/null || die "git is required to download NetDeck."
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  info "Downloading NetDeck ($REF)…"
  git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$TMP/netdeck"
  SRC_DIR="$TMP/netdeck"
fi

# ── Locations ───────────────────────────────────────────────────────────────
if [ "$SYSTEM" = 1 ]; then
  SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
  PREFIX="/opt/netdeck"; BIN_DIR="/usr/local/bin"
  APP_DIR="/usr/share/applications"; ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
else
  SUDO=""
  PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/netdeck"; BIN_DIR="$HOME/.local/bin"
  APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
fi

# ── Stop a running NetDeck from this installation before replacing its files ──
# A running server keeps its old code in memory but reads the web UI from disk, so upgrading underneath it
# would serve pages its code does not support. NetDeck run from elsewhere (a source tree, another install)
# is left alone; a systemd-managed NetDeck is stopped and started through systemd.
installed_pid() {
  [ -x "$PREFIX/venv/bin/python" ] || return 1
  # The installed copy knows where its instance file lives; reuse it rather than re-implementing that here.
  "$PREFIX/venv/bin/python" - "$PREFIX/venv/" 2>/dev/null <<'PY'
import sys
from netdeck.cli import read_instance

inst = read_instance()
if not inst:
    sys.exit(1)
pid = int(inst["pid"])
with open(f"/proc/{pid}/cmdline", "rb") as fh:
    exe = fh.read().split(b"\0")[0].decode()
if not exe.startswith(sys.argv[1]):
    sys.exit(1)  # running from somewhere else
print(pid)
PY
}

RESTART=""
if command -v systemctl >/dev/null && systemctl --user is-active --quiet netdeck.service 2>/dev/null; then
  info "Stopping the NetDeck service for the upgrade…"
  systemctl --user stop netdeck.service
  RESTART=service
elif OLD_PID="$(installed_pid)"; then
  info "Stopping the running NetDeck (pid $OLD_PID) for the upgrade…"
  "$PREFIX/venv/bin/netdeck" stop >/dev/null 2>&1 || true
  for _ in $(seq 1 100); do  # older versions' `netdeck stop` does not wait, so wait here
    kill -0 "$OLD_PID" 2>/dev/null || break
    sleep 0.2
  done
  if kill -0 "$OLD_PID" 2>/dev/null; then
    die "NetDeck (pid $OLD_PID) did not stop. Close it (netdeck stop) and run the installer again."
  fi
  RESTART=instance
fi

# ── Install into an isolated virtualenv ─────────────────────────────────────
info "Installing NetDeck into $PREFIX"
$SUDO mkdir -p "$PREFIX" "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
$SUDO "$PY" -m venv --clear "$PREFIX/venv"
$SUDO "$PREFIX/venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null
$SUDO "$PREFIX/venv/bin/python" -m pip install --quiet "$SRC_DIR"
$SUDO ln -sf "$PREFIX/venv/bin/netdeck" "$BIN_DIR/netdeck"
ok "netdeck $("$PREFIX/venv/bin/netdeck" --version | awk '{print $2}') installed to $BIN_DIR/netdeck"

$SUDO install -m 644 "$SRC_DIR/src/netdeck/static/icon.svg" "$ICON_DIR/netdeck.svg"
sed "s|@BIN@|$BIN_DIR/netdeck|g" "$SRC_DIR/packaging/netdeck.desktop" | $SUDO tee "$APP_DIR/netdeck.desktop" >/dev/null
command -v update-desktop-database >/dev/null && $SUDO update-desktop-database -q "$APP_DIR" 2>/dev/null || true
ok "Desktop launcher added (search for \"NetDeck\" in your app menu)"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH. Add this to your shell profile:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# ── Optional: network tools ─────────────────────────────────────────────────
if [ "$WITH_TOOLS" = 1 ]; then
  # shellcheck source=/dev/null
  . /etc/os-release 2>/dev/null || true
  family="${ID:-} ${ID_LIKE:-}"
  case "$family" in
    *arch*|*manjaro*|*endeavouros*|*cachyos*)
      pkgs="iputils traceroute mtr bind whois nmap arp-scan iperf3 speedtest-cli nethogs iftop bmon vnstat tcpdump wireshark-cli termshark iproute2 networkmanager iw ethtool lsof curl nftables gping trippy"
      cmd=(sudo pacman -S --needed); [ "$ASSUME_YES" = 1 ] && cmd+=(--noconfirm) ;;
    *debian*|*ubuntu*)
      pkgs="iputils-ping iputils-tracepath iputils-arping traceroute mtr-tiny dnsutils whois nmap arp-scan iperf3 speedtest-cli nethogs iftop bmon vnstat tcpdump tshark iproute2 iw ethtool lsof curl nftables"
      sudo apt-get update -qq
      cmd=(sudo apt-get install); [ "$ASSUME_YES" = 1 ] && cmd+=(-y) ;;
    *fedora*|*rhel*|*centos*|*rocky*|*almalinux*)
      pkgs="iputils traceroute mtr bind-utils whois nmap arp-scan iperf3 nethogs iftop bmon vnstat tcpdump wireshark-cli iproute iw ethtool lsof curl nftables"
      cmd=(sudo dnf install); [ "$ASSUME_YES" = 1 ] && cmd+=(-y) ;;
    *suse*)
      pkgs="iputils traceroute mtr bind-utils whois nmap arp-scan iperf nethogs iftop bmon vnstat tcpdump wireshark iproute2 iw ethtool lsof curl nftables"
      cmd=(sudo zypper install); [ "$ASSUME_YES" = 1 ] && cmd+=(-y) ;;
    *) warn "Unknown distribution — skipping tool installation. Run 'netdeck doctor' to see what is missing."; pkgs="" ;;
  esac
  if [ -n "$pkgs" ]; then
    info "Installing network tools: $pkgs"
    # shellcheck disable=SC2086 # word splitting of the package list is intended
    "${cmd[@]}" $pkgs || warn "Some packages could not be installed; 'netdeck doctor' lists what is missing."
  fi
fi

# ── Optional: autostart service ─────────────────────────────────────────────
if [ "$SERVICE" = 1 ]; then
  if [ "$SYSTEM" = 1 ]; then
    UNIT_DIR="/usr/lib/systemd/user"
  else
    UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  fi
  $SUDO mkdir -p "$UNIT_DIR"
  sed "s|@BIN@|$BIN_DIR/netdeck|g" "$SRC_DIR/packaging/netdeck.service" | $SUDO tee "$UNIT_DIR/netdeck.service" >/dev/null
  if [ "$SYSTEM" = 0 ]; then
    systemctl --user daemon-reload
    systemctl --user enable --now netdeck.service
    ok "NetDeck starts automatically at login (systemctl --user status netdeck)"
  else
    ok "User unit installed; each user can enable it with: systemctl --user enable --now netdeck"
  fi
fi

# ── Restart what was running before the upgrade ──────────────────────────────
if [ "$RESTART" = service ]; then
  if systemctl --user start netdeck.service; then
    ok "Restarted the NetDeck service"
  else
    warn "Could not restart the NetDeck service; check: systemctl --user status netdeck"
  fi
elif [ "$RESTART" = instance ]; then
  START_ARGS=()
  [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ] || START_ARGS=(--no-browser)  # never open a console browser
  if command -v setsid >/dev/null; then
    setsid -f "$BIN_DIR/netdeck" ${START_ARGS[@]+"${START_ARGS[@]}"} >/dev/null 2>&1 </dev/null
  else
    nohup "$BIN_DIR/netdeck" ${START_ARGS[@]+"${START_ARGS[@]}"} >/dev/null 2>&1 </dev/null &
  fi
  STARTED=""
  for _ in $(seq 1 50); do
    if "$BIN_DIR/netdeck" url >/dev/null 2>&1; then STARTED=1; break; fi
    sleep 0.2
  done
  if [ -n "$STARTED" ]; then
    ok "Restarted NetDeck with the new version"
  else
    warn "NetDeck did not restart by itself; start it with: netdeck"
  fi
fi

echo
ok "Done! Start NetDeck with:  ${c_green}netdeck${c_off}   (or from your application menu)"
echo "    Check available tools:  netdeck doctor"
