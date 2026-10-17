import cv2, numpy as np, subprocess, json, hashlib
from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise
ffmpeg = get_or_fetch_platform_executables_else_raise()[0]
from pathlib import Path
out=Path('output/spatial-fix/positive-e2e'); source='clips/demo-set-1-center.mp4'
cap=cv2.VideoCapture(source); w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); fps=cap.get(cv2.CAP_PROP_FPS)
corners=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
# Coordinates only used to generate/score the fixture; never sent to the application.
dests=[corners, np.float32([[9,5],[w-15,1],[w-5,h-8],[14,h-2]]), np.float32([[2,9],[w-7,4],[w-18,h-4],[6,h-12]])]
Hs=[cv2.getPerspectiveTransform(corners,p) for p in dests]; procs=[]
for i in range(3):
 p=out/f'projective-control-{i+1}.mp4'
 procs.append(subprocess.Popen([ffmpeg,'-loglevel','error','-y','-f','rawvideo','-pixel_format','bgr24','-video_size',f'{w}x{h}','-framerate',str(fps),'-i','-','-an','-c:v','libx264','-pix_fmt','yuv420p','-crf','20',str(p)],stdin=subprocess.PIPE))
frames=0
while True:
 ok,im=cap.read()
 if not ok:break
 for p,H in zip(procs,Hs):
  frame=cv2.warpPerspective(im,H,(w,h)); p.stdin.write(frame.tobytes())
 frames+=1
cap.release()
for p in procs:
 p.stdin.close(); assert p.wait()==0
# Independently visually reviewed reference flame centers on the source still, x/y fractions.
centers=[[.369,.540],[.411,.406],[.659,.379],[.686,.538]]
meta={'scope':'Three planar projective variants of the same existing synthetic video; not independent cameras, physical 3D geometry, or calibration.', 'source':source,'size':[w,h],'fps':fps,'frames':frames,'known_reference_centers_xy':centers,'videos':[]}
for i,H in enumerate(Hs):
 path=out/f'projective-control-{i+1}.mp4'
 xy=np.float32([[[x*w,y*h] for x,y in centers]])
 warped=cv2.perspectiveTransform(xy,H)[0]
 meta['videos'].append({'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'homography':H.tolist(),'reference_centers_xy':[[round(float(x/w),6),round(float(y/h),6)] for x,y in warped]})
(out/'fixture_truth.json').write_text(json.dumps(meta,indent=2))
print('Generated 3 projective controls',w,h,fps,frames)
