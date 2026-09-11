#!/bin/bash
# Summarise the last N minutes (default 30): stalls/jumps seen by the watcher, libinput jump errors,
# Touch Bar control transfers, and kernel messages from the T2 link.
N=${1:-30}; D=$(dirname "$(readlink -f "$0")")
echo "=== watcher (30s buckets with activity, last $N min) ==="
awk -v s="$(date -d "-$N min" +%H:%M:%S)" '$1>=s && /\[30s\]/ && !/NO TRACKPAD USE/' "$D"/watch.log 2>/dev/null | tail -20
echo; echo "=== stalls / jumps ==="; awk -v s="$(date -d "-$N min" +%H:%M:%S)" '$1>=s && /GAP|JUMP/' "$D"/watch.log 2>/dev/null || true
echo; echo "=== libinput 'Touch jump detected' (motion discarded) ==="; journalctl -b --since "-$N min" 2>/dev/null | grep "Touch jump" | awk '{print "  "$3}'
echo; echo "=== Touch Bar backlight control transfers (needs the t2bce_vhci debug sites enabled) ==="
journalctl -k --since "-$N min" -o short-precise 2>/dev/null | grep -E "EP0 control complete dev=5 port=7" | sed -E 's/^.* ([0-9:]{8}\.[0-9]{3})[0-9]* .*value=([0-9a-f]+).*/  \1 backlight=\2/'
echo; echo "=== kernel messages from the T2 link ==="; journalctl -k --since "-$N min" 2>/dev/null | grep -iE "t2bce|bce|magicmouse|appletb|hid_field" | grep -v "EP0" | tail -10
