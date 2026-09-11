#!/usr/bin/env python3
"""Decode T2 trackpad reports using the t2linux/asahi layout:
tp_header (46 B): id, buttons, rel_x, rel_y, pad[4], unknown[22], num_fingers, clicked, unknown3[14]
tp_finger (30 B): unknown1, unknown2, abs_x, abs_y, rel_x, rel_y, tool_major, tool_minor, orientation,
                  touch_major, touch_minor, unused[2], pressure, multi   (all le16)
Driver rule: a finger slot is a real finger iff touch_major != 0."""
import sys, struct, collections
HDR=46; FIN=30
def s16(v): return v-65536 if v>32767 else v
reps=[]
for line in open(sys.argv[1]):
    try: ts,hx=line.split(); b=bytes.fromhex(hx)
    except ValueError: continue
    if len(b)<HDR or b[0]!=0x02: continue
    n=(len(b)-HDR)//FIN
    fs=[]
    for i in range(n):
        f=struct.unpack('<15h', b[HDR+i*FIN:HDR+(i+1)*FIN])
        fs.append(dict(x=f[2],y=f[3],tool_major=f[6],tool_minor=f[7],orient=f[8],touch_major=f[9],touch_minor=f[10],pressure=f[13],multi=f[14],u1=f[0],u2=f[1]))
    reps.append(dict(t=float(ts),buttons=b[1],num_fingers=b[30],clicked=b[31],fs=fs,len=len(b)))
print(f"reports={len(reps)}  span={reps[-1]['t']-reps[0]['t']:.0f}s  lengths={dict(collections.Counter(r['len'] for r in reps))}")
print(f"num_fingers header values: {dict(collections.Counter(r['num_fingers'] for r in reps))}")
# consistency: header says N fingers vs slots with touch_major != 0
mism=collections.Counter()
for r in reps:
    real=sum(1 for f in r['fs'] if f['touch_major']!=0)
    mism[(r['num_fingers'],real)]+=1
print("(header num_fingers, slots with touch_major!=0):", dict(mism))
tm=[f['touch_major'] for r in reps for f in r['fs'] if f['touch_major']!=0]
pr=[f['pressure'] for r in reps for f in r['fs'] if f['touch_major']!=0]
q=lambda a,p: sorted(a)[min(len(a)-1,int(len(a)*p/100))]
if tm: print(f"touch_major (raw, evdev = x2): min={min(tm)} p5={q(tm,5)} med={q(tm,50)} p95={q(tm,95)} max={max(tm)}")
if pr: print(f"pressure   (raw):              min={min(pr)} p5={q(pr,5)} med={q(pr,50)} p95={q(pr,95)} max={max(pr)}")
# spurious lifts: finger goes touch_major==0 (driver: lifted) but header still counts a finger or it returns within 300ms near the same spot
lifts=0; ex=[]; last=None
for r in reps:
    real=[f for f in r['fs'] if f['touch_major']!=0]
    if last is not None and last['real'] and not real and r['num_fingers']>0:
        lifts+=1
        if len(ex)<6: ex.append(f"   {r['t']-reps[0]['t']:7.2f}s: header num_fingers={r['num_fingers']} but touch_major==0 (pressure={r['fs'][0]['pressure']}, tool_major={r['fs'][0]['tool_major']}) -> driver reports finger LIFTED")
    last=dict(real=real)
print(f"\nreports where the header says a finger is present but touch_major==0 (driver drops it): {lifts}")
for e in ex: print(e)
# brief vanish-and-return
van=0; exv=[]; state=None
for i,r in enumerate(reps):
    real=[f for f in r['fs'] if f['touch_major']!=0]
    if state and not real: state['gone_at']=state.get('gone_at',r['t'])
    if real:
        if state and state.get('gone_at') is not None:
            dtm=(r['t']-state['gone_at'])*1000
            if dtm<300:
                van+=1; f=real[0]; d=(((f['x']-state['x'])/95)**2+((f['y']-state['y'])/92)**2)**0.5
                if len(exv)<6: exv.append(f"   finger vanished {dtm:4.0f}ms, returned {d:4.1f}mm away  (before: major={state['tm']} pressure={state['pr']})")
        f=real[0]; state=dict(x=f['x'],y=f['y'],tm=f['touch_major'],pr=f['pressure'],gone_at=None)
print(f"finger vanished then returned within 300ms (looks like a jump/new contact to libinput): {van}")
for e in exv: print(e)
# click
cl=[r for r in reps if r['clicked'] or r['buttons']]
print(f"\nclicked reports: {len(cl)}  (buttons byte values: {dict(collections.Counter(r['buttons'] for r in cl))}, clicked byte: {dict(collections.Counter(r['clicked'] for r in cl))})")
if cl:
    pc=[max([f['pressure'] for f in r['fs'] if f['touch_major']] or [0]) for r in cl]
    print(f"   pressure while clicked: min={min(pc)} med={q(pc,50)} max={max(pc)}")
    rel=[max([f['pressure'] for f in reps[i-1]['fs'] if f['touch_major']] or [0]) for i in range(1,len(reps)) if (reps[i-1]['clicked'] or reps[i-1]['buttons']) and not (reps[i]['clicked'] or reps[i]['buttons'])]
    print(f"   pressure on the report just before each release: {sorted(rel)}")
