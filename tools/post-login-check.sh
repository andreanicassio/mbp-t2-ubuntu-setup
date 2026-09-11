#!/bin/bash
# Run after logging back in, then again after ~10 min of normal use.
D=$(dirname "$(readlink -f "$0")")
echo "=== session ==="; echo "  gnome-shell started: $(ps -o lstart= -p $(pgrep -x gnome-shell | head -1))"
echo "  override file:       $(stat -c %y /etc/libinput/local-overrides.quirks | cut -c1-19)   (shell must be newer)"
echo; echo "=== did the session accept the quirk file? (no lines = fine) ==="
journalctl --user -b -u gnome-shell 2>/dev/null | grep -iE "quirk|local-overrides" | tail -3
journalctl -b 2>/dev/null | grep -iE "libinput.*(quirk|parse|invalid)" | tail -3
echo; echo "=== libinput jump errors this boot (must stop growing while you use the pad) ==="; echo "  $(journalctl -b 2>/dev/null | grep -c 'Touch jump')   last: $(journalctl -b 2>/dev/null | grep 'Touch jump' | tail -1 | awk '{print $3}')"
echo; echo "=== watcher / capture alive? ==="; pgrep -f '^python3 .*trackpad-watch' >/dev/null && echo "  watcher: running" || echo "  watcher: NOT running -> run $D/start.sh"
pgrep -f '[l]ibinput debug-events' >/dev/null && echo "  libinput decision capture: running" || echo "  decision capture: not running (optional: $D/libinput-decisions.sh)"
echo; echo "=== last 5 activity buckets ==="; grep "\[30s\]" $D/watch.log 2>/dev/null | grep -v "NO TRACKPAD" | tail -5 | cut -c1-140
echo; echo "=== scroll shim loaded into the compositor? ==="
grep -q libinput-config /proc/$(pgrep -x gnome-shell | head -1)/maps 2>/dev/null && echo "  yes: libinput-config.so is mapped in gnome-shell (scroll-factor=$(grep scroll-factor /etc/libinput.conf | cut -d= -f2))" || echo "  NO: gnome-shell started without the preload -> log out/in again"
