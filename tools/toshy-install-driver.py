#!/usr/bin/env python3
"""Drive setup_toshy.py interactively: answer y/n prompts with 'y' and echo back its per-run secret code."""
import os, pty, re, select, sys, time
pid, fd = pty.fork()
if pid == 0:
    os.execv(sys.executable, [sys.executable, './setup_toshy.py', 'install'])
buf = b''; log = open('/tmp/toshy-install.log', 'wb'); answered_code = set(); last_prompt_pos = 0
while True:
    r, _, _ = select.select([fd], [], [], 600)
    if not r: print("timeout"); break
    try: data = os.read(fd, 4096)
    except OSError: break
    if not data: break
    log.write(data); log.flush(); buf += data; tail = buf[-600:].decode(errors='ignore')
    m = re.search(r"secret code '([A-Za-z0-9]+)':\s*$", tail)
    if m and m.group(1) not in answered_code:
        answered_code.add(m.group(1)); os.write(fd, (m.group(1) + '\n').encode()); continue
    if re.search(r"\[y/n\]:\s*$|\[y/N\]:\s*$|\[Y/n\]:\s*$", tail, re.I) and len(buf) != last_prompt_pos:
        last_prompt_pos = len(buf); os.write(fd, b'y\n'); continue
    if re.search(r"(press enter|hit enter|\(enter\))", tail, re.I) and len(buf) != last_prompt_pos:
        last_prompt_pos = len(buf); os.write(fd, b'\n')
_, status = os.waitpid(pid, 0); print("installer exit status:", os.waitstatus_to_exitcode(status))
