#!/usr/bin/env python3
"""v4: time gaps + position jumps (>20mm in one frame, libinput's discard threshold) + 30s summary."""
import os, select, struct, sys, time
EV_FMT='llHHi'; EV_SZ=struct.calcsize(EV_FMT)
EV_ABS,EV_SYN,EV_KEY=0x03,0x00,0x01
A_SLOT,A_TID,A_X,A_Y=0x2f,0x39,0x35,0x36; BTN_LEFT=0x110
RX,RY=95.0,92.0
def find_touchpad():
    import glob,subprocess
    for e in sorted(glob.glob('/dev/input/event*')):
        try:
            if b'ID_INPUT_TOUCHPAD=1' in subprocess.run(['udevadm','info',e],capture_output=True).stdout: return e
        except Exception: pass
    return None
def open_touchpad():
    while True:
        e=find_touchpad()
        if e:
            try: return os.open(e,os.O_RDONLY|os.O_NONBLOCK), e
            except OSError: pass
        time.sleep(2)
fd,dev=open_touchpad()
out=open(sys.argv[1],'a',buffering=1)
slot=0; pos={}; prev={}; t_prev=None; ivals=[]; btn=0
import collections, subprocess
ring=collections.deque(maxlen=60)   # (t, dt_ms, {slot:(x,y)}, btn)
jr=subprocess.Popen(['journalctl','-f','-n','0','-o','short-precise'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
import fcntl; fl=fcntl.fcntl(jr.stdout,fcntl.F_GETFL); fcntl.fcntl(jr.stdout,fcntl.F_SETFL,fl|os.O_NONBLOCK)
def dump(reason):
    out.write(f"{time.strftime('%H:%M:%S')} ---- frames before {reason} (t_rel_ms, dt_ms, slot:x,y[evdev], btn) ----\n")
    if ring:
        t0=ring[-1][0]
        for t,dt,ps,b in list(ring)[-40:]:
            out.write(f"   {1000*(t-t0):8.1f} {dt:6.1f}  "+"  ".join(f"s{k}:{v[0]},{v[1]}" for k,v in sorted(ps.items()))+("  BTN" if b else "")+"\n")
    out.write(f"{time.strftime('%H:%M:%S')} ----\n")
touches=frames=gaps=jumps=0; worst=0.0; t_sum=time.time()
last_abs={}; lijumps=0
tb=lambda: 'loaded' if os.path.exists('/sys/module/hid_appletb_kbd') else 'UNLOADED'
out.write(f"\n=== watcher started {time.strftime('%H:%M:%S')} on {dev}  touchbar driver: {tb()} ===\n")
while True:
    r,_,_=select.select([fd],[],[],1.0); now=time.time()
    if r:
        try: data=os.read(fd,EV_SZ*256)
        except OSError as e:
            if e.errno==19:   # ENODEV: device re-enumerated (suspend/resume, driver rebind) -> reopen
                os.close(fd); out.write(f"{time.strftime('%H:%M:%S')} device lost ({dev}); rescanning...\n")
                fd,dev=open_touchpad(); pos.clear(); prev.clear(); t_prev=None
                out.write(f"{time.strftime('%H:%M:%S')} reopened {dev}\n"); continue
            data=b''
        for i in range(0,len(data)-EV_SZ+1,EV_SZ):
            sec,usec,et,code,val=struct.unpack(EV_FMT,data[i:i+EV_SZ]); t=sec+usec/1e6
            if et==EV_KEY and code==BTN_LEFT: btn=val
            elif et==EV_ABS:
                if code==A_SLOT: slot=val
                elif code==A_TID:
                    if val==-1: pos.pop(slot,None); prev.pop(slot,None); last_abs.pop(slot,None)
                    else:
                        if not pos: touches+=1
                        pos[slot]=[None,None]; prev.pop(slot,None)   # new contact: no delta vs old occupant
                elif code==A_X and slot in pos: pos[slot][0]=val
                elif code==A_Y and slot in pos: pos[slot][1]=val
            elif et==EV_SYN and code==0:
                if not pos: t_prev=None; prev.clear(); continue
                frames+=1
                if t_prev is not None:
                    dt=(t-t_prev)*1000.0; ivals.append(dt); ivals[:]=ivals[-2000:]
                    med=sorted(ivals)[len(ivals)//2] if len(ivals)>20 else 8.0
                    worst=max(worst,dt)
                    if dt>max(3*med,40):
                        gaps+=1; out.write(f"{time.strftime('%H:%M:%S')} GAP  {dt:6.1f}ms (normal {med:.1f}ms)\n"); dump(f"GAP {dt:.0f}ms")
                    for s,(x,y) in pos.items():
                        if x is None or y is None or s not in prev: continue
                        d=(((x-prev[s][0])/RX)**2+((y-prev[s][1])/RY)**2)**0.5
                        # libinput 1.25 tp_detect_jumps(): normalize to 12ms; jump if abs>20mm or rel>7mm
                        if 0<dt<=30.0:
                            ab=d*12.0/dt; rel=ab-last_abs.get(s,0.0)
                            if ab>20.0 or rel>7.0:
                                lijumps+=1
                                out.write(f"{time.strftime('%H:%M:%S')} LIBINPUT-RULE jump: moved {d:4.1f}mm in {dt:4.1f}ms -> abs={ab:4.1f} rel={rel:+5.1f} (limits 20 / 7) slot={s} fingers={len(pos)}   <-- this frame's motion is DISCARDED\n")
                                dump(f"libinput-rule jump (abs {ab:.1f} rel {rel:+.1f})")
                            last_abs[s]=ab
                        if d>20:
                            jumps+=1; out.write(f"{time.strftime('%H:%M:%S')} JUMP {d:5.1f}mm in {dt:5.1f}ms slot={s} fingers={len(pos)} button={'DOWN' if btn else 'up'}   <-- libinput discards this\n"); dump(f"JUMP {d:.0f}mm")
                ring.append((t, (t-t_prev)*1000.0 if t_prev else 0.0, {k:(v[0],v[1]) for k,v in pos.items() if v[0] is not None}, btn))
                t_prev=t
                for s,(x,y) in pos.items():
                    if x is not None and y is not None: prev[s]=(x,y)
    try:
        for jl in iter(jr.stdout.readline,''):
            if 'Touch jump detected' in jl: out.write(f"{time.strftime('%H:%M:%S')} LIBINPUT-JUMP (journal)\n"); dump("libinput 'Touch jump'")
    except (OSError, ValueError): pass
    if now-t_sum>=30:
        out.write(f"{time.strftime('%H:%M:%S')} [30s] touches={touches:3d} frames={frames:5d} gaps={gaps:2d} jumps={jumps:2d} li_rule_jumps={lijumps:2d} worst_gap={worst:6.1f}ms  touchbar={tb()}{'   <-- NO TRACKPAD USE' if frames==0 else ''}\n")
        touches=frames=gaps=jumps=lijumps=0; worst=0.0; t_sum=now
