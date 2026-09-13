# MacBook Pro (T2) on Ubuntu — working setup

Everything needed to make a **MacBookPro16,2** (13" 2020, four ports, T2) behave on **Ubuntu 24.04 + the linux-t2 kernel**,
reproduced from a long debugging session (see `docs/investigation-log.md`). One command: `bash install.sh`.

| Problem | Cause found | Fix in this repo |
|---|---|---|
| Trackpad "gets stuck" / insensitive | libinput applied old `bcm5974` thresholds (palm 800, touch-down 150) to a Magic-Trackpad-2-class device | `files/etc/libinput/local-overrides.quirks` (thresholds measured on the hardware, jump-detection off) |
| Accidental clicks / cursor jumps while typing (the pad is huge) | disable-while-typing had been switched off, wrongly blamed on the Touch Bar (it has no letter keys, so libinput never pairs it, and Esc/F-keys/media keys are exempt anyway). Also, Toshy grabs the physical keyboard, so libinput only sees its virtual keyboard, which is untagged (USB, vid 0001) and never paired | `disable-while-typing=true` + quirk `AttrKeyboardIntegration=internal` for `XWayKeyz (virtual) Keyboard` (same file); ydotool stays unpaired so dictation does not mute the pad |
| Click-and-drag cuts out | the T2 releases the physical click when force drops below its own threshold | tap-and-drag + drag-lock |
| Two-finger scroll too fast | GNOME 46 / libinput 1.25 have no scroll-factor setting | `libinput-config` preload shim, `/etc/libinput.conf` `scroll-factor=0.5` |
| Touch Bar brightness flickers / never turns off | its dim/restore work items race; with `autodim=0` it never sleeps | `hid_appletb_kbd autodim=0` + `touchbar-follow-screen` user service: backlight follows mutter's PowerSaveMode and the lock screen (udev rule grants the `video` group write access) |
| "Audio not working" | T2 card has no hardware gain; GNOME's cubic slider is near-silent in its lower half | allow volume above 100 % |
| Internal mic dead (dictation impossible) | `t2bce_audio` capture bug; upstream fix (t2bce PR #6) not in the kernel; the upstream module can't load (core API names differ) | fix ported onto the kernel's own driver source, installed via **DKMS** (`files/usr/src/t2bce-audio-micfix-1.0`) |
| Speakers sound terrible vs macOS | macOS runs a per-model DSP chain; Linux played raw | 16_2 FIR crossover/EQ + loudness + limiters (from lemmyg/t2-apple-audio-dsp, Asahi-derived), translated to **LADSPA** because Ubuntu's PipeWire 1.0 has no LV2 in filter-chain |
| No True Tone; Night Light too orange | GNOME has no ambient-colour adaptation; default 2700 K | `truetone.py` user service reads the T2 ambient light sensor's colour temperature (iio `als`) and drives `night-light-temperature`; night floor 3800 K, all in `~/.config/truetone.json` |
| Mac-style shortcuts (Cmd+C etc.) | Linux uses Ctrl; a plain modifier swap breaks terminals and Cmd+Tab | **Toshy** keymapper (app-aware: Cmd+C copies in the terminal, Ctrl+C still interrupts) + Xremap GNOME extension for focus detection; installer driven by `tools/toshy-install-driver.py` (it has an interactive captcha) |
| Speech-to-text (Handy) on Wayland | needs a virtual keyboard and a system-level shortcut | ydotool 1.0 built from source (+ service), GNOME shortcut Ctrl+Super+H, Handy AppImage + launcher |
| AirDrop / AWDL (**experimental, opt-in**, not in `install.sh`) | OWL/OpenDrop need monitor mode + injection, which brcmfmac cannot do; but Apple's Broadcom firmware has the whole AWDL engine built in, driven by private iovars | Public project: [brcmfmac-awdl](https://github.com/andreanicassio/brcmfmac-awdl) (mirrored in `awdl/`): brcmfmac patch that turns the firmware's AWDL bsscfg into an `awdl0` netdev and forwards AWDL events to userspace, `brcmiovar.py` (raw iovars over nl80211), `awdl-up.sh`/`awdl-down.sh`. Control plane works both ways (AWDL sync, service discovery — an actively-sending Mac/iPhone browses and the laptop hears it), but the AWDL **data** plane does not work in either direction: cross-verified from a Mac capturing its own awdl0, our data frames never arrive and a passive Apple receiver never wakes its data path (no Bluetooth trigger from us). AWDL discovery under Linux works; AWDL file transfer does not on this stack. See `awdl/NOTES.md` |

## Gotchas learned the hard way
- **AWDL hops the radio away from your access point.** With AWDL enabled the firmware follows the AWDL channel sequence (ch 44/6); a sequence that fills all 16 slots makes normal Wi-Fi unusable. `awdl/awdl-up.sh` uses Apple's sparse pattern (3 of 16 slots) and even then expect lower throughput; `awdl/awdl-down.sh` restores normal Wi-Fi. Reloading brcmfmac drops Wi-Fi for ~10 s.
- **libinput quirk files are read once per compositor session** — every change needs a log out/in. `libinput quirks list` shows the *files*, not what GNOME is using.
- **Never `rmmod`/`insmod` `t2bce_audio` on its own**: the T2 accepts only the first audio probe after `t2bce_core` loads; later probes fail (`Failed to init BCE command transport -22`) and you get a Dummy Output. Recovery: reload the whole stack (`hid_appletb_kbd hid_appletb_bl t2bce_audio t2bce_vhci t2bce_core t2bce_dma`, then back in reverse) or reboot.
- A PipeWire `filter-chain` module without `flags = [ nofail ]` takes the daemon down if a plugin fails to load.
- A `pw-record` "loopback" that shows a perfect tone with exact digital silence around it is the speaker *monitor*, not the mic — target the mic node explicitly.
- Suspend/resume re-creates the trackpad HID device; anything holding `/dev/input/eventN` must reopen.
- Toshy's installer changes GNOME shortcuts: Super alone no longer opens the overview (Cmd+Space does; the raw binding becomes Shift+Ctrl+Space) and sets Nautilus to list view.
- The physical click on the Force Touch pad is decided by the T2 (raw force ≈ 75–105); not fixable in software.

## Model-specific pieces
The quirk file matches USB product `0x027E`; the DSP FIRs and the mic fix are for `MacBookPro16,2` and linux-t2 7.2.x. Other T2 Macs: look up your product id (`lsusb`), take the matching `configs/<model>` from lemmyg/t2-apple-audio-dsp, and re-port the mic fix against your kernel's `drivers/staging/t2bce`.

## Credits / licenses
FIR data and DSP graph: lemmyg/t2-apple-audio-dsp (derived from AsahiLinux/asahi-audio, see `files/usr/share/t2linux-audio/16_2/LICENSE.asahi-audio`). Mic fix: woodcockjosh's PR #6 to deqrocks/t2bce, GPL-2.0, on top of the linux-t2 staging driver. Scroll shim: libinput-config (ISC). ydotool (AGPL-3.0). Handy: cjpais/Handy.
