#!/usr/bin/env python3
"""Animate API-generated stills as labelled CCTV test fixtures, not real video."""
from pathlib import Path
import math
import subprocess
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scene2real.ingest import media_tool


def create(still, destination, camera):
    src = cv2.imread(str(still))
    if src is None:
        raise ValueError(f'Cannot read {still}')
    src = cv2.resize(src, (720, 480), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((480, 854, 3), dtype=np.uint8)
    canvas[:, 67:787] = src
    base = canvas
    b, g, r = [base[:, :, k].astype(np.float32) for k in range(3)]
    mask = np.clip((r-b-30)/65, 0, 1) * np.clip((r-110)/90, 0, 1) * np.clip((r-g+20)/80,0,1)
    mask = cv2.GaussianBlur(mask, (0, 0), 2.5)
    # Loosely select low-saturation smoke immediately above warm flame pixels.
    fire = (mask > .15).astype(np.uint8)
    plume = cv2.dilate(fire, np.ones((75, 41), dtype=np.uint8), anchor=(20, 70))
    saturation = np.maximum.reduce((r, g, b)) - np.minimum.reduce((r, g, b))
    smoke = plume * np.clip((35 - saturation) / 35, 0, 1) * np.clip((215 - r) / 120, 0, 1)
    smoke = cv2.GaussianBlur(smoke.astype(np.float32), (0, 0), 3) * .32
    yy, xx = np.mgrid[:480,:854].astype(np.float32)
    command = [media_tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '854x480', '-r', '12', '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '28', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-metadata', 'comment=Synthetic, API-generated image animated computationally', str(destination)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    rng = np.random.default_rng(27)
    for i in range(60):
        t = i / 12
        dx = 2.0*np.sin(yy*.08+t*7) + np.sin(yy*.14+t*11)
        dy = 2.2*np.sin(xx*.08-t*8)
        shifted = cv2.remap(base, xx+dx, yy+dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        flicker = 1 + .055*math.sin(t*9) + .025*math.sin(t*14)
        alpha = np.maximum(mask, smoke)[:,:,None]
        frame = base.astype(np.float32)*(1-alpha)+np.clip(shifted*flicker,0,255)*alpha
        frame += rng.normal(0,1.5,(480,854,1)).astype(np.float32)
        frame = np.clip(frame,0,255).astype(np.uint8)
        cv2.rectangle(frame,(0,0),(300,24),(15,15,15),-1)
        cv2.putText(frame, f'SYNTHETIC  CAM {camera}  14:03:{i//12:02d}', (8,17), cv2.FONT_HERSHEY_SIMPLEX,.42,(230,230,230),1,cv2.LINE_AA)
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait():
        raise RuntimeError('ffmpeg failed')
    print(destination, flush=True)

if __name__ == '__main__':
    for s in (1,2):
        for idx,view in enumerate(('west','center','east'),1):
            create(ROOT/f'output/demo_cctv/images/set_{s}_{view}.png', ROOT/f'output/demo_cctv/set_{s}/warehouse_{view}.mp4', idx)
