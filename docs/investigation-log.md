# T2 trackpad diagnostics (MacBookPro16,2, linux-t2 7.2.4, Ubuntu 24.04, GNOME/Wayland)

## Applied (persistent)
- `/etc/libinput/local-overrides.quirks` — measured thresholds for this pad (was: palm=800 on a scale where firm
  fingers hit 852; touch-down=150 on contacts that start at 42–124). Same lever the t2linux maintainer used in
  t2linux/T2-Ubuntu#178.
- gsettings: `disable-while-typing=false` (the Touch Bar enumerates as a keyboard and emits real key events, which
  mutes the trackpad); `tap-and-drag=true`, `tap-and-drag-lock=true` (drags without depending on the physical click).
- `/etc/udev/rules.d/99-t2-no-autosuspend.rules` — harmless; measured NOT to be this machine's problem.

## Measured, not fixed
- Kernel-level report-stream stalls of 50–215 ms (cursor freeze). Seen once as a burst (03:59, 6 in 16 s) with the
  Touch Bar driver loaded; 0 in 3.5 min heavy use with `hid_appletb_kbd`/`hid_appletb_bl` unloaded. Control run
  (driver loaded) still has no data. Mechanism unknown: backlight control transfers take 0.1 ms, so not that.
- Position jumps ~1 per 5 min (libinput "Touch jump detected", motion discarded). Independent of the Touch Bar driver.
- Physical click releases when raw force drops to ~100 (T2 firmware threshold) → click-drag cuts out while sliding.
  Use tap-and-drag or click with one finger / move with another.

## Tools
- `./start.sh` — start the passive watcher (after reboot/suspend it must be restarted).
- `./report.sh [minutes]` — summarise stalls, jumps, Touch Bar transfers and kernel messages.
- Test the Touch Bar hypothesis: `sudo modprobe -r hid_appletb_kbd hid_appletb_bl` (Esc key is on the Touch Bar;
  Ctrl+[ substitutes), use the pad, `./report.sh`; restore with `sudo modprobe hid_appletb_bl hid_appletb_kbd`.

## 2026-09-09 afternoon
- Suspend/resume re-creates the trackpad HID device (new hidraw/input index). The watcher now reopens automatically on
  ENODEV; older logs went blind after the 04:27 suspend.
- Auto-brightness: GNOME `idle-dim=false`; Touch Bar `autodim=0` (`/etc/modprobe.d/hid-appletb-kbd.conf`). The Touch
  Bar dim/restore path was flapping (10 of 22 writes were <100 ms apart) — a race between its two work items in
  `hid-appletb-kbd`; worth an upstream report.
- 14:40 — added `ModelLenovoX1Gen6Touchpad=1` to the quirk section: in libinput 1.25 that flag only sets
  `jump.detection_disabled`. libinput's jump rule (`abs>20mm || rel>7mm`, normalised to a 12 ms interval) was firing on
  ordinary fast strokes at this pad's 123 Hz rate and discarding the frame ("cursor sticks at the start of a flick").
  Verify: `journalctl -b | grep "Touch jump"` should stop growing. Revert: delete that line, rebind or re-login.

## IMPORTANT (found 15:15): quirk files load once per compositor session
libinput parses `/etc/libinput/local-overrides.quirks` only when the compositor creates its context. Every quirk
change needs a **log out / log in** (Wayland) to take effect; rebinding the device does NOT reload them. `libinput
quirks list` shows the *files*, not what the running session uses. gnome-shell started 03:18:46, the override was
written 03:40:20 -> the session ran stock quirks (150:130 / palm 800) all day; the first session with the override
is the one after the next login. Verify after login: `journalctl -b | grep -c "Touch jump"` must stop growing.

## 2026-09-11 — confirmed
Rebooted; gnome-shell (01:29:52) is newer than the override, no quirk parse errors, 0 libinput jump errors this boot,
user reports "feels good now". Residual: rare transport stalls still possible (2 gaps, worst 173 ms, at 15:12 on
09-09 in the old session). Watcher keeps logging; `./report.sh` if it ever sticks again.

## 2026-09-11 — two-finger scroll speed
GNOME 46 / libinput 1.25 have no scroll-speed setting and no Lua plugin system, so the `libinput-config` shim is
installed (built in this folder with `-Dshitty_sandboxing=true` for snaps): `/etc/libinput-config.so` +
`/etc/ld.so.preload`. Config: `/etc/libinput.conf` → `scroll-factor=0.5`. Change the number and log out/in to tune.
Remove: `cd libinput-config/build && sudo ninja pre-uninstall uninstall` (or delete the line in /etc/ld.so.preload).

## 2026-09-11 — audio "not working"
Driver/card/profile were fine; the Speakers sink was at 0 %. The T2 card has no hardware mixer, so volume is purely
PipeWire software gain with GNOME's cubic slider: the lower half of the slider is nearly silent (36 % slider = 4.7 %
gain). Set `org.gnome.desktop.sound allow-volume-above-100-percent=true`. Quick fix if it happens again:
`wpctl set-mute @DEFAULT_AUDIO_SINK@ 0; wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.8`.

## 2026-09-11 — internal microphone (Handy dictation)
Internal mic captured a flat line (acoustic loopback: no response to a 1 kHz tone) — known `t2bce_audio` bug
(deqrocks/t2bce issue/PR #6). The PR ported onto the kernel's own driver source (from linux-t2-patches 1001..1003)
builds and loads; loopback ratio went 0.4x -> 9334x. Installed as DKMS `t2bce-audio-micfix/1.0`
(source in ~/src/t2bce-micfix, /usr/src/t2bce-audio-micfix-1.0). If a kernel update breaks the DKMS build the stock
in-tree module loads instead (audio works, mic dead again). Revert: `sudo dkms remove t2bce-audio-micfix/1.0 --all`.
CORRECTION: the "9334x" loopback above was recorded from PipeWire's fallback (speaker monitor), not the mic — after the
module swap PipeWire had no Apple capture source. Mic status with the patched driver: being verified at ALSA level.
RESOLVED 12:15: with the patched module loaded FIRST on a fresh BCE stack, the mic works — test targeted at the
BuiltinMic node (id 57): room noise -66 dBFS with 0% zero samples, tone loopback ratio 6.8x. DKMS
`t2bce-audio-micfix/1.0` is installed and is what modprobe loads at boot. The earlier failure was my script's
node-id parse, not the driver. Never cycle t2bce_audio alone (see the gotcha above); reload the whole stack.

## 2026-09-11 — speaker DSP (sound quality)
macOS runs a per-model DSP chain before the speakers; Linux played raw. Installed the MacBookPro16,2 chain from
lemmyg/t2-apple-audio-dsp (Asahi-derived: 4-channel FIR crossover/EQ, loudness compensation, per-band limiters).
Ubuntu 24.04's PipeWire 1.0.5 filter-chain has no LV2 support, so the graph was translated to LADSPA
(lsp-plugins-ladspa) and loaded via `~/.config/pipewire/pipewire.conf.d/10-t2_162_speakers.conf` (FIRs in
/usr/share/t2linux-audio/16_2). Omitted: the `bankstown` bass enhancer (LV2-only). To get it: upgrade PipeWire from
ppa:pipewire-debian/pipewire-upstream (1.0.7 build links lilv) + wireplumber-upstream (0.5.2), then use the project's
own install.sh. Use the "MacBook Pro T2 DSP Speakers" sink (default); keep "Apple Audio Device Speakers" (raw) at
100% and never select it directly. Revert: delete the conf file, restart pipewire.
Work tree: ~/src/t2-audio-dsp (repo clone + the failed LV2 attempt kept as *.disabled).

## 2026-09-11 — True-Tone-like display + Night Light strength
`~/.local/bin/truetone.py` (user service `truetone.service`) reads the T2 ambient light sensor's colour temperature
(iio `als`: in_colortemp_raw, chromaticity) and drives GNOME's night-light-temperature: display white point is pulled
toward the ambient by `strength` (0.45), never below `min_temp`, never cooler than 6500 K (GNOME can only warm). A
night window applies a floor `night_temp` (3800 K = milder than GNOME's 2700 default; higher = less orange).
Config: `~/.config/truetone.json` (re-read every 5 s, no restart needed). While it runs, GNOME's own Night Light
slider/schedule are overridden (schedule forced 0-24, temperature written by the daemon).
Disable: `systemctl --user disable --now truetone.service`, then `gsettings reset-recursively org.gnome.settings-daemon.plugins.color`.

## 2026-09-11 — AirDrop via the firmware's AWDL engine (experimental)
Wi-Fi is BCM4364 on brcmfmac; no monitor mode/injection, so OWL/OpenDrop are out. The Apple firmware
(9.30.503.0.32.5.92, "roml") advertises `awdl` in its capability string and implements the whole AWDL engine
(timing, channel hopping, sync-frame TX). Iovar names and payload sizes were taken from a decompile of the iOS 26
AppleBCMWLAN DriverKit driver plus Broadcom's `wlioctl.h`/`bcmevent.h` from router GPL drops. Talking to the
firmware from userspace works through brcmfmac's nl80211 vendor dcmd (`awdl/brcmiovar.py`). Findings:
`awdl_if` makes the firmware add a role-7 bsscfg (stock brcmfmac ignores it: no netdev); the patch in
`awdl/brcmfmac-awdl.patch` creates `awdl0` (iftype OCB) and forwards AWDL events (96-98, 111-120, action-frame
TX/RX) as vendor events. Accepted payload formats and the enable sequence (sync params, channel sequence,
`awdl_config`=115, `awdl`=1) are in `awdl/NOTES.md`. Result: firmware becomes AWDL master and sends PSF/MIF
frames on its own. Not yet done: receiving from an Apple peer (none tested), peer table, data path, OpenDrop.
Lesson: a full 16-slot channel sequence took the radio off the AP's channel and broke Wi-Fi (Ethernet needed);
use the sparse Apple pattern and always run `awdl-down.sh` after tests.
