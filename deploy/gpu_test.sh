#!/usr/bin/env bash
cd /home/ubuntu/audio-portal
sudo -n systemctl stop audio-portal; sleep 2
pkill -x mpv 2>/dev/null; sleep 1

# one still image: black 1920x1080 with the clock block centred
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
ffmpeg -loglevel error -y -f lavfi -i color=c=black:s=1920x1080 -vf \
 "drawtext=fontfile=$FONT:text='13\:42':fontsize=150:fontcolor=0x8d949e:x=(w-text_w)/2:y=(h/2)-130,\
drawtext=fontfile=$FONT:text='FRI  ·  23 OCT':fontsize=30:fontcolor=0x6b727c:x=(w-text_w)/2:y=(h/2)+60,\
drawtext=fontfile=$FONT:text='NEXT  ›  14\:00  ·  FOCUS TIME':fontsize=22:fontcolor=0x4a505a:x=(w-text_w)/2:y=(h/2)+115" \
 -frames:v 1 /tmp/clock.png

rm -f /tmp/gpu.sock
mpv --no-config --msg-level=all=v --log-file=/tmp/gpu_mpv.log --input-terminal=no --idle=yes --force-window=yes \
  --fs --osc=no --vo=gpu --gpu-context=drm --drm-device=/dev/dri/card1 --drm-connector=HDMI-A-1 \
  --drm-mode=1920x1080 --image-display-duration=inf --background-color='#000000' \
  --input-ipc-server=/tmp/gpu.sock /tmp/clock.png >/dev/null 2>&1 &
MP=$!
sleep 4
echo "mpv alive: $(kill -0 $MP 2>/dev/null && echo yes || echo NO)"
grep -iE "GL_RENDERER|Using .*(hardware|drm)|gpu-context|Failed|error|fallback" /tmp/gpu_mpv.log | head -8

/home/ubuntu/audio-portal/venv/bin/python - <<'EOF'
import socket, json, time, math, os
s = socket.socket(socket.AF_UNIX); s.connect("/tmp/gpu.sock"); s.setblocking(False)
pid = int(os.popen("pgrep -x mpv").read().split()[0])
def cpu():
    f = open(f"/proc/{pid}/stat").read().split(); return (int(f[13]) + int(f[14])) / os.sysconf("SC_CLK_TCK")
def send(name, v):
    s.sendall((json.dumps({"command": ["set_property", name, v]}) + "\n").encode())
    try: s.recv(65536)
    except BlockingIOError: pass
AX, AY, VX, VY = 0.30, 0.36, 18/1920, 11/1080     # pan limits (fraction of image) and speed (fraction/s)
def tri(x, a):                                      # triangle wave bouncing in [-a, a]
    p = (x % (4*a)); return p - a if p < 2*a else 3*a - p
c0, t0 = cpu(), time.time()
n = 0
while time.time() - t0 < 20:
    t = time.time() - t0
    send("video-pan-x", tri(t*VX, AX)); send("video-pan-y", tri(t*VY + 0.1, AY)); n += 1
    time.sleep(1/30)
dt = time.time() - t0
print(f"20s run: {n} updates ({n/dt:.0f}/s)  mpv CPU = {(cpu()-c0)/dt*100:.1f}% of one core")
EOF
kill $MP 2>/dev/null; sleep 1
echo "--- errors in mpv log ---"; grep -ciE "error|fail" /tmp/gpu_mpv.log
sudo -n systemctl start audio-portal
