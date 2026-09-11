#!/usr/bin/env python3
"""True-Tone-like adaptive white point for GNOME, driven by the T2 ambient light sensor's colour temperature.
Reads iio 'als' colortemp, smooths it, maps it to a display temperature, and folds in a night schedule.
Writes gsettings night-light-temperature (gsd-color applies the gamma). Config: ~/.config/truetone.json"""
import json, os, time, glob, math, sys
from gi.repository import Gio

CFG = os.path.expanduser('~/.config/truetone.json')
DEFAULTS = dict(
    enabled=True,
    strength=0.45,        # 0 = never adapt, 1 = match ambient fully. True Tone feels like ~0.3-0.5
    min_temp=3400,        # never warm the display below this from ambient alone (K)
    neutral=6500,         # display's neutral white (K); can't go cooler than this
    night_enabled=True,   # apply the night floor at all
    night_temp=3800,      # Night Light warmth during the night window (K) -- the "orange" amount
    night_from=20.0,      # hours, local
    night_to=6.0,
    smoothing_s=8.0,      # EMA time constant for the sensor (s)
    step=75,              # only re-apply when target moves by this many K (avoids visible stepping)
    interval_s=2.0,
)

def load_cfg():
    cfg = dict(DEFAULTS)
    try: cfg.update(json.load(open(CFG)))
    except FileNotFoundError:
        json.dump(DEFAULTS, open(CFG, 'w'), indent=2)
    except Exception as e: print('config error, using defaults:', e, flush=True)
    return cfg

def find_als():
    for d in glob.glob('/sys/bus/iio/devices/iio:device*'):
        try:
            if open(d + '/name').read().strip() == 'als' and os.path.exists(d + '/in_colortemp_raw'): return d
        except OSError: pass
    return None

def read(d, ch):
    try: return float(open(f'{d}/{ch}').read())
    except (OSError, ValueError): return None

def night_active(now_h, f, t):
    if f == t: return False
    return (f <= now_h < t) if f < t else (now_h >= f or now_h < t)

def main():
    s = Gio.Settings.new('org.gnome.settings-daemon.plugins.color')
    # make Night Light a permanent, manually-scheduled canvas we drive
    s.set_boolean('night-light-enabled', True)
    s.set_boolean('night-light-schedule-automatic', False)
    s.set_double('night-light-schedule-from', 0.0)
    s.set_double('night-light-schedule-to', 24.0)
    d = find_als()
    if not d: print('no ALS with colortemp found; exiting', flush=True); sys.exit(1)
    print('using', d, flush=True)
    ema = None; last_applied = None; last_cfg_check = 0; cfg = load_cfg()
    while True:
        now = time.time()
        if now - last_cfg_check > 5: cfg = load_cfg(); last_cfg_check = now
        ct = read(d, 'in_colortemp_raw')
        if ct and 1000 < ct < 20000:
            if ema is None: ema = ct
            else:
                a = 1 - math.exp(-cfg['interval_s'] / max(cfg['smoothing_s'], 0.1)); ema += a * (ct - ema)
        # ambient -> display: pull the white point toward the ambient by 'strength', never cooler than neutral
        neutral = cfg['neutral']
        target = neutral
        if cfg['enabled'] and ema is not None and ema < neutral:
            target = neutral - cfg['strength'] * (neutral - ema)
            target = max(target, cfg['min_temp'])
        # night schedule: at least this warm
        lt = time.localtime(); h = lt.tm_hour + lt.tm_min / 60.0
        night = cfg.get('night_enabled', True) and night_active(h, cfg['night_from'], cfg['night_to'])
        if night: target = min(target, cfg['night_temp'])
        target = int(round(target))
        if last_applied is None or abs(target - last_applied) >= cfg['step'] or target in (neutral, cfg['night_temp']) and target != last_applied:
            s.set_uint('night-light-temperature', target); Gio.Settings.sync(); last_applied = target
            print(f"ambient={ema:.0f}K -> display={target}K (night={'on' if night else 'off'})", flush=True)
        time.sleep(cfg['interval_s'])

if __name__ == '__main__': main()
