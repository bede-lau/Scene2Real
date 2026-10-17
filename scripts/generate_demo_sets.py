#!/usr/bin/env python3
"""Generate six synthetic multi-view warehouse clips with shared scene truth."""
import argparse, hashlib, json, math, subprocess, random, sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
import cv2
import mujoco
import numpy as np
from scene2real.ingest import media_tool, probe

ROOT = PROJECT_ROOT / 'output' / 'demo_sets'
WIDTH, HEIGHT, FPS, SECONDS = 960, 540, 24, 4
SEED = 17531
rng = random.Random(SEED)
counts = rng.sample(range(1, 5), 2)
positions = {1: [(-3.0, -1.5), (3.0, -1.5), (-3.0, 1.5), (3.0, 1.5)], 2: [(-3.0, -1.5), (3.0, -1.5), (0.0, 1.5)]}
cameras = {
    'west': ((-4.5, -9.5, 5.2), (0, 0, 0.9)),
    'center': ((0., -12., 5.8), (0, 0, 0.9)),
    'east': ((7.5, -10.5, 5.8), (0, 0, 0.9)),
}

def camera_xml(name, pos, target):
    p, t = np.array(pos, float), np.array(target, float)
    z = (p-t); z /= np.linalg.norm(z)
    x = np.cross(np.array([0,0,1.]), z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return f'<camera name="{name}" pos="{vec(p)}" xyaxes="{vec(x)} {vec(y)}" fovy="45"/>'

def vec(a): return ' '.join(f'{v:.5f}' for v in a)

def scene_xml(count, index):
    parts = ['''<mujoco><visual><global offwidth="960" offheight="540"/><quality shadowsize="2048"/><map znear="0.05"/></visual><worldbody>
    <light pos="0 -3 8" dir="0 0 -1" diffuse="0.9 0.9 0.9" castshadow="true"/>
    <light pos="-4 3 6" dir=".2 -.3 -1" diffuse=".4 .4 .45"/>
    <geom name="floor" type="plane" size="15 15 .1" rgba=".40 .42 .43 1"/>
    <geom type="box" pos="0 4.6 2" size="7 .12 2" rgba=".38 .41 .43 1"/>
    <geom type="box" pos="-6.8 0 2" size=".12 4.7 2" rgba=".32 .36 .39 1"/>
    <geom type="box" pos="6.8 0 2" size=".12 4.7 2" rgba=".32 .36 .39 1"/>
    <geom type="box" pos="0 4.35 3.7" size="6.7 .14 .12" rgba=".17 .20 .23 1"/>
    <geom type="box" pos="0 4.3 4.0" size="6.7 .2 .1" rgba=".18 .20 .22 1"/>
    ''']
    # Racks are against rear and side walls; the clear central aisle keeps fires visible.
    for x in (-5.5, -3.7, 3.7, 5.5):
        for z in (.2, 1.35, 2.5):
            parts.append(f'<geom type="box" pos="{x} 3.65 {z}" size=".75 .46 .07" rgba=".22 .24 .25 1"/>')
            if z < 2:
                for bx in (-.37, .30):
                    parts.append(f'<geom type="box" pos="{x+bx} 3.65 {z+.36}" size=".28 .31 .29" rgba=".56 .39 .23 1"/>')
        for dx in (-.73, .73):
            parts.append(f'<geom type="box" pos="{x+dx} 3.65 1.4" size=".045 .06 1.4" rgba=".18 .23 .27 1"/>')
    parts.append('<geom type="box" pos="-5.65 1.25 .65" size=".5 .4 .65" rgba=".22 .34 .43 1"/><geom type="box" pos="-5.65 0.82 .95" size=".28 .02 .23" rgba=".36 .75 .78 1"/>')
    for name, (p,t) in cameras.items(): parts.append(camera_xml(name,p,t))
    for fi, (x,y) in enumerate(positions[index][:count]):
        # Animated ellipsoids sit within a pallet fire, in multiple yellow/orange layers.
        parts.append(f'<geom type="box" pos="{x} {y} .09" size=".48 .42 .09" rgba=".29 .18 .1 1"/><geom type="box" pos="{x} {y} .30" size=".36 .30 .21" rgba=".52 .30 .13 1"/>')
        for tongue in range(7):
            a = tongue*2*math.pi/7
            dx,dy = .24*math.cos(a),.20*math.sin(a)
            shade = ('1 .27 .01 1' if tongue%2 else '1 .52 .03 1')
            parts.append(f'<body name="f{fi}_t{tongue}" pos="{x+dx} {y+dy} .62"><geom name="flame_{fi}_{tongue}" type="ellipsoid" size=".19 .17 .59" rgba="{shade}" contype="0" conaffinity="0"/></body>')
        parts.append(f'<body name="f{fi}_core" pos="{x} {y} .55"><geom type="ellipsoid" size=".28 .26 .48" rgba="1 .85 .20 1" contype="0" conaffinity="0"/></body>')
        for s in range(3):
            parts.append(f'<body name="smoke{fi}_{s}" pos="{x} {y} {1.5+s*.38}"><geom type="sphere" size=".28" rgba=".30 .31 .31 .32" contype="0" conaffinity="0"/></body>')
    parts.append('</worldbody></mujoco>')
    return ''.join(parts)

def projection(model, data, name, xyz):
    ci = mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_CAMERA,name)
    local = data.cam_xmat[ci].reshape(3,3).T @ (np.array(xyz) - data.cam_xpos[ci])
    f = HEIGHT / (2 * math.tan(math.radians(model.cam_fovy[ci])/2))
    return [round((WIDTH/2 + f*local[0]/-local[2])/WIDTH, 4), round((HEIGHT/2-f*local[1]/-local[2])/HEIGHT, 4)]

def make_one(index, count):
    dest=ROOT / f'set_{index}'; dest.mkdir(exist_ok=True)
    xml=scene_xml(count,index); (dest/'warehouse.xml').write_text(xml)
    model=mujoco.MjModel.from_xml_string(xml); data=mujoco.MjData(model); mujoco.mj_forward(model,data)
    truth={'set':index,'fire_count':count,'seed':SEED,'synthetic':True,'dimensions':[WIDTH,HEIGHT],'fps':FPS,'duration_seconds':SECONDS,'fires':[], 'videos':[]}
    for fi,(x,y) in enumerate(positions[index][:count]):
        truth['fires'].append({'id':f'fire_{fi+1}','world_position_m':[x,y,.6], 'camera_center_normalized':{name:projection(model,data,name,(x,y,.6)) for name in cameras}})
    renderer=mujoco.Renderer(model,height=HEIGHT,width=WIDTH)
    bodies={}
    for fi in range(count):
        for j in range(7): bodies[(fi,'t',j)]=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,f'f{fi}_t{j}')
        for j in range(3): bodies[(fi,'s',j)]=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,f'smoke{fi}_{j}')
    original=model.body_pos.copy()
    for name in cameras:
        out=dest/f'warehouse_{name}.mp4'
        cmd=[media_tool('ffmpeg'),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{WIDTH}x{HEIGHT}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
        pipe=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for frame in range(FPS*SECONDS):
                t=frame/FPS
                for (fi,kind,j),bid in bodies.items():
                    if kind=='t':
                        model.body_pos[bid,0] = original[bid,0] + .05*math.sin(t*8+j+fi)
                        model.body_pos[bid,2] = original[bid,2] + .10*math.sin(t*10+j*1.7+fi)
                    else:
                        model.body_pos[bid,0] = original[bid,0] + .12*math.sin(t*1.5+j+fi)
                        model.body_pos[bid,2] = original[bid,2] + ((t*.20 + j*.35) % .65)
                mujoco.mj_forward(model,data); renderer.update_scene(data,camera=name)
                image=renderer.render().copy()
                cv2.rectangle(image,(12,12),(348,53),(24,24,24),-1)
                cv2.putText(image,f'SYNTHETIC 3D  |  SET {index}  |  {name.upper()}',(20,39),cv2.FONT_HERSHEY_SIMPLEX,.57,(245,245,245),1,cv2.LINE_AA)
                pipe.stdin.write(image.tobytes())
        finally:
            pipe.stdin.close()
        if pipe.wait()!=0: raise RuntimeError(f'FFmpeg failed: {out}')
        print(f'rendered {out}',flush=True)
        info=probe(out)
        truth['videos'].append({'view':name,'path':str(out),'probe':info,'camera_position_m':list(cameras[name][0]),'camera_look_at_m':list(cameras[name][1])})
    renderer.close()
    (dest/'ground_truth.json').write_text(json.dumps(truth,indent=2)+'\n')
    return truth

def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT,
                        help='directory for rendered clips and separate evaluation truth')
    args = parser.parse_args()
    ROOT = args.output_dir.expanduser().resolve()
    ROOT.mkdir(parents=True, exist_ok=True)
    for i, count in enumerate(counts):
        make_one(i + 1, count)
    # Keep evaluation truth separate from ordinary app metadata and model input.
    manifest = {'description': 'Synthetic multi-camera warehouse videos; evaluation truth is separate.',
                'seed': SEED, 'renderer': f'MuJoCo {mujoco.__version__}', 'sets': []}
    for number in (1, 2):
        folder = ROOT / f'set_{number}'
        files = []
        for view in cameras:
            clip = folder / f'warehouse_{view}.mp4'
            files.append({'view': view, 'path': str(clip.relative_to(ROOT)),
                          'sha256': hashlib.sha256(clip.read_bytes()).hexdigest()})
        truth = folder / 'ground_truth.json'
        manifest['sets'].append({'set': number, 'videos': files,
                                 'evaluation_truth': str(truth.relative_to(ROOT))})
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'PROVENANCE.txt').write_text(
        'Synthetic 3D shared-scene test clips. Generated by scripts/generate_demo_sets.py.\n'
        'MuJoCo renders three cameras; OpenCV adds labels; FFmpeg encodes H.264.\n'
        'The per-set ground truth is evaluation data, not a model response.\n')
    print(f'Wrote {ROOT / "manifest.json"}')

if __name__=='__main__':
    main()
