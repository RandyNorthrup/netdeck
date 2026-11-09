#!/usr/bin/env bash
# Remove NetDeck. Your settings (~/.config/netdeck) and captures (~/netdeck-captures)
# are kept unless you pass --purge.
#
#   ./scripts/uninstall.sh            remove the per-user installation
#   ./scripts/uninstall.sh --system   remove the /opt/netdeck installation (needs sudo)
#   ./scripts/uninstall.sh --purge    also delete settings
set -euo pipefail

SYSTEM=0; PURGE=0
for arg in "$@"; do
  case "$arg" in
    --system) SYSTEM=1 ;;
    --purge) PURGE=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

if command -v netdeck >/dev/null 2>&1; then netdeck stop >/dev/null 2>&1 || true; fi

if [ "$SYSTEM" = 1 ]; then
  SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
  $SUDO rm -rf /opt/netdeck
  $SUDO rm -f /usr/local/bin/netdeck /usr/share/applications/netdeck.desktop \
    /usr/share/icons/hicolor/scalable/apps/netdeck.svg /usr/lib/systemd/user/netdeck.service
else
  if systemctl --user is-enabled netdeck.service >/dev/null 2>&1; then
    systemctl --user disable --now netdeck.service || true
  fi
  data="${XDG_DATA_HOME:-$HOME/.local/share}"
  rm -rf "$data/netdeck"
  rm -f "$HOME/.local/bin/netdeck" "$data/applications/netdeck.desktop" \
    "$data/icons/hicolor/scalable/apps/netdeck.svg" \
    "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/netdeck.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi

if [ "$PURGE" = 1 ]; then
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/netdeck"
  echo "Settings removed. Packet captures in ~/netdeck-captures were kept — delete them manually if you wish."
fi
echo "NetDeck has been uninstalled."
