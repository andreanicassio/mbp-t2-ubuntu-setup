#!/bin/bash
# MacBook Pro (T2, MacBookPro16,2) on Ubuntu 24.04 + linux-t2: reproduce the working setup.
# Idempotent. Run from the repo root:  bash install.sh          (asks for sudo)
# Model-specific parts (trackpad quirk product id, speaker DSP FIRs, mic driver fix) are skipped on other models.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
MODEL=$(cat /sys/class/dmi/id/product_name 2>/dev/null || echo unknown)
KREL=$(uname -r)
say(){ printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
[[ "$KREL" == *t2* ]] || { echo "WARNING: kernel '$KREL' is not a linux-t2 kernel; T2 parts will not work."; }
[[ "$MODEL" == "MacBookPro16,2" ]] || echo "WARNING: model is '$MODEL' (repo was built on MacBookPro16,2); model-specific parts skipped."
IS_162=$([[ "$MODEL" == "MacBookPro16,2" ]] && echo 1 || echo 0)

say "packages"
sudo apt-get update -qq
sudo apt-get install -y git build-essential cmake meson ninja-build pkg-config scdoc dkms "linux-headers-$KREL" \
  libinput-tools libinput-dev libudev-dev libgtk-layer-shell0 \
  lsp-plugins-ladspa ladspa-sdk swh-lv2 bankstown-lv2 pipewire-audio wireplumber

say "trackpad: libinput quirks (needs log out/in to take effect)"
if [[ $IS_162 == 1 ]]; then sudo install -D -m 0644 files/etc/libinput/local-overrides.quirks /etc/libinput/local-overrides.quirks; sudo libinput quirks validate; else echo "skipped (product id in the quirk is 0x027E)"; fi

say "trackpad/gnome settings"
gsettings set org.gnome.desktop.peripherals.touchpad disable-while-typing true    # palm rejection while typing; relies on the XWayKeyz quirk above (Toshy grabs the physical keyboard)
gsettings set org.gnome.desktop.peripherals.touchpad tap-and-drag true
gsettings set org.gnome.desktop.peripherals.touchpad tap-and-drag-lock true        # physical click drops at the T2's force threshold
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
gsettings set org.gnome.desktop.sound allow-volume-above-100-percent true          # T2 card has no hardware gain

say "Touch Bar: no auto-dim (its dim/restore path flaps)"
sudo install -D -m 0644 files/etc/modprobe.d/hid-appletb-kbd.conf /etc/modprobe.d/hid-appletb-kbd.conf
[ -w /sys/module/hid_appletb_kbd/parameters/autodim ] && echo N | sudo tee /sys/module/hid_appletb_kbd/parameters/autodim >/dev/null || true

say "T2 link: keep devices powered (harmless; measured not to be the stall cause)"
sudo install -D -m 0644 files/etc/udev/rules.d/99-t2-no-autosuspend.rules /etc/udev/rules.d/99-t2-no-autosuspend.rules
sudo udevadm control --reload-rules

say "two-finger scroll speed: libinput-config shim (GNOME 46 has no scroll-factor setting)"
if ! grep -q libinput-config /etc/ld.so.preload 2>/dev/null; then
  tmp=$(mktemp -d); git clone -q https://gitlab.com/warningnonpotablewater/libinput-config.git "$tmp/lic"; git -C "$tmp/lic" checkout -q 6f359b8
  (cd "$tmp/lic" && meson setup build -Dshitty_sandboxing=true >/dev/null && ninja -C build >/dev/null && sudo ninja -C build install >/dev/null); sudo chmod 644 /etc/libinput-config.so; rm -rf "$tmp"
fi
sudo install -m 0644 files/etc/libinput.conf /etc/libinput.conf

say "ydotool (Wayland typing for Handy): Ubuntu's package has no daemon -> build 1.0.x"
if [ ! -x /usr/local/bin/ydotoold ]; then
  tmp=$(mktemp -d); git clone -q https://github.com/ReimuNotMoe/ydotool.git "$tmp/y"; git -C "$tmp/y" checkout -q 708e96f
  (cd "$tmp/y" && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release >/dev/null && make -j"$(nproc)" >/dev/null && sudo make install >/dev/null); rm -rf "$tmp"
fi
sudo apt-get remove -y ydotool >/dev/null 2>&1 || true
sudo install -D -m 0644 files/etc/modules-load.d/uinput.conf /etc/modules-load.d/uinput.conf; sudo modprobe uinput || true
sudo install -D -m 0644 files/etc/systemd/system/ydotool.service /etc/systemd/system/ydotool.service
sudo systemctl daemon-reload; sudo systemctl enable --now ydotool.service
install -D -m 0644 files/home/.config/environment.d/ydotool.conf ~/.config/environment.d/ydotool.conf
install -D -m 0644 files/home/.config/user-tmpfiles.d/ydotool.conf ~/.config/user-tmpfiles.d/ydotool.conf
ln -sfn /tmp/.ydotool_socket "${XDG_RUNTIME_DIR:-/run/user/$UID}/.ydotool_socket"

say "Handy (speech-to-text) AppImage + launcher + GNOME shortcut Ctrl+Super+H"
mkdir -p ~/Applications
[ -x ~/Applications/Handy.AppImage ] || { curl -fL -o ~/Applications/Handy.AppImage "https://github.com/cjpais/Handy/releases/download/v0.9.6/Handy_0.9.6_amd64.AppImage" && chmod +x ~/Applications/Handy.AppImage; }
install -D -m 0644 files/home/.local/share/icons/hicolor/256x256/apps/handy.png ~/.local/share/icons/hicolor/256x256/apps/handy.png
sed "s|__HOME__|$HOME|g" files/home/.local/share/applications/handy.desktop > ~/.local/share/applications/handy.desktop; update-desktop-database ~/.local/share/applications 2>/dev/null || true
P=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/handy/
cur=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings); case "$cur" in *"$P"*) ;; "@as []"|"[]") gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['$P']";; *) gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "${cur%]}, '$P']";; esac
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$P name 'Handy: toggle dictation'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$P command "env YDOTOOL_SOCKET=/tmp/.ydotool_socket $HOME/Applications/Handy.AppImage --toggle-transcription"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$P binding '<Control><Super>h'

say "internal microphone: t2bce_audio with the mic-capture fix (DKMS)"
if [[ $IS_162 == 1 ]] && [[ "$KREL" == *t2* ]]; then
  sudo rm -rf /usr/src/t2bce-audio-micfix-1.0; sudo cp -r files/usr/src/t2bce-audio-micfix-1.0 /usr/src/
  sudo dkms add t2bce-audio-micfix/1.0 >/dev/null 2>&1 || true; sudo dkms build t2bce-audio-micfix/1.0 && sudo dkms install t2bce-audio-micfix/1.0 --force && sudo depmod -a
  echo "takes effect at next boot (do NOT rmmod/insmod t2bce_audio alone: the T2 accepts only the first audio probe per boot)"
else echo "skipped"; fi

say "speakers: 16_2 DSP chain (FIR crossover/EQ + loudness + limiters), LADSPA edition for PipeWire 1.0"
if [[ $IS_162 == 1 ]]; then
  sudo install -d /usr/share/t2linux-audio/16_2; sudo install -m 0644 files/usr/share/t2linux-audio/16_2/* /usr/share/t2linux-audio/16_2/
  install -D -m 0644 files/home/.config/pipewire/pipewire.conf.d/10-t2_162_speakers.conf ~/.config/pipewire/pipewire.conf.d/10-t2_162_speakers.conf
  systemctl --user restart pipewire pipewire-pulse wireplumber; sleep 4
  DSP=$(wpctl status | sed -n '/Sinks:/,/Sink endpoints/p' | grep "DSP Speakers" | grep -oE "[0-9]+\." | head -1 | tr -d .) || true
  RAW=$(wpctl status | sed -n '/Sinks:/,/Sink endpoints/p' | grep "Apple Audio Device Speakers" | grep -oE "[0-9]+\." | head -1 | tr -d .) || true
  [ -n "${DSP:-}" ] && { wpctl set-default "$DSP"; wpctl set-volume "$DSP" 0.7; [ -n "${RAW:-}" ] && wpctl set-volume "$RAW" 1.0; echo "default sink -> MacBook Pro T2 DSP Speakers (keep the raw sink at 100%, never select it)"; } || echo "DSP sink not visible yet (check journalctl --user -u pipewire)"
else echo "skipped"; fi

say "display: True-Tone-like white point + milder Night Light (config ~/.config/truetone.json)"
install -D -m 0755 files/home/.local/bin/truetone.py ~/.local/bin/truetone.py
[ -f ~/.config/truetone.json ] || install -D -m 0644 files/home/.config/truetone.json ~/.config/truetone.json
install -D -m 0644 files/home/.config/systemd/user/truetone.service ~/.config/systemd/user/truetone.service
systemctl --user daemon-reload; systemctl --user enable --now truetone.service

say "Mac-style shortcuts: Toshy (Cmd+C/V/X/Z/A/W/Q/Tab/Space..., terminal-aware) + Xremap GNOME extension"
E=~/.local/share/gnome-shell/extensions/xremap@k0kubun.com
if [ ! -d "$E" ]; then
  url=$(curl -sf "https://extensions.gnome.org/extension-info/?uuid=xremap%40k0kubun.com&shell_version=$(gnome-shell --version | grep -oE '[0-9]+' | head -1)" | python3 -c "import sys,json; print(json.load(sys.stdin).get('download_url',''))")
  [ -n "$url" ] && { curl -sfL "https://extensions.gnome.org$url" -o /tmp/xremap-ext.zip; mkdir -p "$E"; unzip -o -q /tmp/xremap-ext.zip -d "$E"; }
fi
cur=$(gsettings get org.gnome.shell enabled-extensions); case "$cur" in *xremap*) ;; *) gsettings set org.gnome.shell enabled-extensions "${cur%]}, 'xremap@k0kubun.com']";; esac
if [ ! -x ~/.local/bin/toshy-services-start ]; then
  tmp=$(mktemp -d); git clone -q --depth 1 https://github.com/RedBearAK/toshy.git "$tmp/toshy"; cp tools/toshy-install-driver.py "$tmp/toshy/drive.py"
  echo "Toshy's installer needs passwordless sudo for a few minutes (it prompts interactively); granting a temporary rule..."
  sudo bash -c "printf '$USER ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/zz-toshy-install; chmod 0440 /etc/sudoers.d/zz-toshy-install"
  (cd "$tmp/toshy" && python3 drive.py) || true
  sudo rm -f /etc/sudoers.d/zz-toshy-install; rm -rf "$tmp"
fi
sudo usermod -aG input "$USER"
# classify the T2 internal keyboard as Apple (not in Toshy's built-in list -> would be treated as a PC keyboard)
[ -f "$C" ] && ! grep -q "Apple Internal Keyboard / Trackpad': 'Apple'" "$C" && python3 - <<'PY'
import re,os
p=os.path.expanduser('~/.config/toshy/toshy_config.py'); s=open(p).read()
entry="    'Apple Inc. Apple Internal Keyboard / Trackpad': 'Apple',   # T2 MacBook internal keyboard\n"
s,n=re.subn(r"(keyboards_UserCustom_dct\s*=\s*\{.*?\n)(\})", lambda m: m.group(1)+entry+m.group(2), s, count=1, flags=re.S)
open(p,'w').write(s)
PY
[ -f "$C" ] && python3 -m py_compile "$C"
# keep Handy's ydotool virtual keyboard out of the keymapper
C=~/.config/toshy/toshy_config.py; [ -f "$C" ] && ! grep -q "ydotoold virtual device" "$C" && sed -i "0,/ignore_devices = \[/s//ignore_devices = [\n        'ydotoold virtual device',/" "$C" || true

say "Touch Bar: off when the screen sleeps/locks, on when it wakes (autodim is off to avoid its flapping)"
sudo install -D -m 0644 files/etc/udev/rules.d/99-touchbar-backlight-perms.rules /etc/udev/rules.d/99-touchbar-backlight-perms.rules
sudo udevadm control --reload-rules; sudo udevadm trigger --subsystem-match=backlight --action=change; sudo usermod -aG video "$USER"
install -D -m 0755 files/home/.local/bin/touchbar-follow-screen.py ~/.local/bin/touchbar-follow-screen.py
install -D -m 0644 files/home/.config/systemd/user/touchbar-follow-screen.service ~/.config/systemd/user/touchbar-follow-screen.service
systemctl --user daemon-reload; systemctl --user enable --now touchbar-follow-screen.service

say "done"
cat <<'MSG'
Next:
  1. Log out and back in (libinput quirks, the scroll shim, Toshy's input-group access and its GNOME extension all load with the session).
  2. Reboot once for the microphone driver (DKMS) to be the first-loaded audio module.
  3. Open Handy once, download the Parakeet V3 model (English+Italian, auto-detect); dictate with Ctrl+Super+H.
  4. Speaker/Night Light tuning: /etc/libinput.conf (scroll-factor), ~/.config/truetone.json (night_temp, strength).
Diagnostics for the trackpad live in tools/ (start.sh / report.sh).
MSG
