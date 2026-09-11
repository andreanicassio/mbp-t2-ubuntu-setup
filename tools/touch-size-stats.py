#!/usr/bin/env python3
"""Measure real touch_major / pressure values per contact, so quirk thresholds come from data."""
import os, select, struct, sys, time
EV_FMT='llHHi'; EV_SZ=struct.calcsize(EV_FMT)
EV_ABS, EV_SYN, EV_KEY = 0x03, 0x00, 0x01
A_SLOT,A_MAJ,A_MIN,A_TID,A_PRES,A_X,A_Y = 0x2f,0x30,0x31,0x39,0x3a,0x35,0x36
DUR = int(sys.argv[1]) if len(sys.argv)>1 else 30
fd = os.open('/dev/input/event8', os.O_RDONLY|os.O_NONBLOCK)
slot=0; cur={}; seqs=[]
hard_end=time.time()+240; t_end=None
print(f"Waiting for first touch, then recording {DUR}s.", flush=True)
while time.time()<hard_end and (t_end is None or time.time()<t_end):
    if not select.select([fd],[],[],0.5)[0]: continue
    data=os.read(fd, EV_SZ*256)
    for i in range(0,len(data)-EV_SZ+1,EV_SZ):
        _,_,et,code,val=struct.unpack(EV_FMT,data[i:i+EV_SZ])
        if et!=EV_ABS: continue
        if code==A_SLOT: slot=val
        elif code==A_TID:
            if val==-1:
                s=cur.pop(slot,None)
                if s and s['maj']: seqs.append(s)
            else:
                cur[slot]={'maj':[], 'pres':[], 'n':0}
                if t_end is None: t_end=time.time()+DUR
        elif slot in cur:
            s=cur[slot]
            if code==A_MAJ: s['maj'].append(val)
            elif code==A_PRES: s['pres'].append(val)
            elif code in (A_X,A_Y): s['n']+=1
for s in cur.values():
    if s['maj']: seqs.append(s)
if not seqs:
    print("No contacts recorded."); sys.exit(1)
allmaj=[v for s in seqs for v in s['maj']]
allpres=[v for s in seqs for v in s['pres']]
def pct(a,p):
    a=sorted(a); return a[min(len(a)-1,int(len(a)*p/100))]
print(f"\ncontacts={len(seqs)}  major samples={len(allmaj)}  pressure samples={len(allpres)}")
print("\nABS_MT_TOUCH_MAJOR (axis max 5000):")
for p in (0,1,5,25,50,75,95,99,100): print(f"   p{p:<3} = {pct(allmaj,p)}")
print(f"   per-contact minimum major: {sorted(min(s['maj']) for s in seqs)}")
print(f"   per-contact maximum major: {sorted(max(s['maj']) for s in seqs)}")
if allpres:
    print("\nABS_MT_PRESSURE (axis max 6000):")
    for p in (0,1,5,25,50,75,95,99,100): print(f"   p{p:<3} = {pct(allpres,p)}")
    print(f"   per-contact maximum pressure: {sorted(max(s['pres']) for s in seqs)}")
print("\ncurrent quirk in force: AttrTouchSizeRange=150:130  AttrPalmSizeThreshold=800")
below=sum(1 for v in allmaj if v<150)
print(f"  -> {below}/{len(allmaj)} ({100*below/len(allmaj):.1f}%) of samples are BELOW the 150 touch-down threshold")
above=sum(1 for v in allmaj if v>=800)
print(f"  -> {above}/{len(allmaj)} ({100*above/len(allmaj):.1f}%) of samples are AT/ABOVE the 800 palm threshold")
dead=sum(1 for s in seqs if max(s['maj'])<150)
palm=sum(1 for s in seqs if max(s['maj'])>=800)
print(f"  -> {dead}/{len(seqs)} contacts would NEVER register (cursor ignores the finger entirely)")
print(f"  -> {palm}/{len(seqs)} contacts would be rejected as PALM")
