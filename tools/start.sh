#!/bin/bash
# Start the passive trackpad stall/jump watcher (root needed for /dev/input). Log: ~/t2-trackpad-diag/watch.log
D=$(dirname "$(readlink -f "$0")")
for p in $(pgrep -f '^python3 .*trackpad-watch'); do sudo kill $p; done
[ -L "$D/watch.log" ] && rm -f "$D/watch.log"
sudo bash -c "setsid python3 $D/trackpad-watch.py $D/watch.log >/dev/null 2>&1 </dev/null &"
sleep 1; pgrep -f '^python3 .*trackpad-watch' >/dev/null && echo "watching /dev/input/event8 -> $D/watch.log" || echo "failed to start"
