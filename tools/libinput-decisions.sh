#!/bin/bash
# Passive capture of libinput's own touch decisions (thumb/palm/jump/suppression) on the internal trackpad.
# Uses a udev seat context (no --device) so it follows device re-creation after rebind/suspend. Low volume.
D=$(dirname "$(readlink -f "$0")")
exec sudo bash -c "stdbuf -oL libinput debug-events --verbose 2>&1 \
  | grep --line-buffered -E 'Trackpad|event[0-9]+ ' \
  | grep --line-buffered -iE 'thumb|palm|jump|suppress|speed|DEVICE_(ADDED|REMOVED)' \
  | grep --line-buffered -vE 'event7 |Touch Bar|Button|Lid Switch|Video Bus|Headset|HDMI|Codec' \
  | while IFS= read -r l; do printf '%s %s\n' \"\$(date +%H:%M:%S.%3N)\" \"\$l\"; done >> $D/libinput-decisions.log"
