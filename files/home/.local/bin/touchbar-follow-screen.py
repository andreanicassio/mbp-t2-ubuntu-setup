#!/usr/bin/env python3
"""Turn the Touch Bar backlight off when the screen sleeps or locks, on when it wakes (like macOS).
Watches GNOME/mutter: DisplayConfig.PowerSaveMode (0 = on) and ScreenSaver active. No timers, no flapping."""
import time, sys
from gi.repository import Gio, GLib
BL = '/sys/class/backlight/appletb_backlight/brightness'
ON, OFF = '2', '0'
state = {'psm': 0, 'saver': False, 'last': None}
def apply():
    want = OFF if (state['psm'] != 0 or state['saver']) else ON
    if want == state['last']: return
    try:
        open(BL, 'w').write(want); state['last'] = want
        print(f"touch bar -> {'off' if want == OFF else 'on'} (PowerSaveMode={state['psm']} saver={state['saver']})", flush=True)
    except PermissionError:
        print("no write access to the Touch Bar backlight yet (needs the 'video' group: log out/in)", flush=True)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
def on_props(conn, sender, path, iface, signal, params):
    changed_iface, changed, _ = params.unpack()
    if changed_iface == 'org.gnome.Mutter.DisplayConfig' and 'PowerSaveMode' in changed:
        state['psm'] = changed['PowerSaveMode']; apply()
def on_saver(conn, sender, path, iface, signal, params):
    state['saver'] = bool(params.unpack()[0]); apply()
bus.signal_subscribe('org.gnome.Mutter.DisplayConfig', 'org.freedesktop.DBus.Properties', 'PropertiesChanged', '/org/gnome/Mutter/DisplayConfig', None, Gio.DBusSignalFlags.NONE, on_props)
bus.signal_subscribe('org.gnome.ScreenSaver', 'org.gnome.ScreenSaver', 'ActiveChanged', '/org/gnome/ScreenSaver', None, Gio.DBusSignalFlags.NONE, on_saver)
def initial():
    try:
        r = bus.call_sync('org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig', 'org.freedesktop.DBus.Properties', 'Get', GLib.Variant('(ss)', ('org.gnome.Mutter.DisplayConfig', 'PowerSaveMode')), None, Gio.DBusCallFlags.NONE, 2000, None)
        state['psm'] = r.unpack()[0]
    except Exception as e: print('PowerSaveMode query failed:', e, flush=True)
    try:
        r = bus.call_sync('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver', 'org.gnome.ScreenSaver', 'GetActive', None, None, Gio.DBusCallFlags.NONE, 2000, None)
        state['saver'] = bool(r.unpack()[0])
    except Exception as e: print('ScreenSaver query failed:', e, flush=True)
    apply(); return False
GLib.idle_add(initial)
# safety net: re-assert every 60 s (covers a missed signal or a permission that arrives later)
GLib.timeout_add_seconds(60, lambda: (state.update(last=None), apply(), True)[2])
GLib.MainLoop().run()
