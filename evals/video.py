"""Two bounded fresh video perception checks. No planner/motion authorization.

python -m evals.video --positive clips/demo-set-1-center.mp4 --negative /path/to/no-fire.mp4 --output output/video
Positive must match independent repository annotations; negative is explicitly
the verified historical authored no-fire fixture, not real source footage.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from scene2real import config, cosmos, ingest
from scripts.check_spatial_accuracy import score
from .perception import exact_sources

NEGATIVE_SHA256='773beb179fef76127feaecb07e4a8c7c7e7ab23086d33d988396fb4017549ff3'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--positive',type=Path,required=True)
    p.add_argument('--negative',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise SystemExit('Use a fresh output directory')
    args.output.mkdir(parents=True)
    annotations=json.loads(Path('tests/fixtures/fire_localization.json').read_text())
    positive_sha=ingest.sha256_file(args.positive)
    matches=[v for v in annotations['views'].values() if v['source_sha256']==positive_sha]
    assert len(matches)==1,'Positive video must match independent annotation source hash'
    assert ingest.sha256_file(args.negative)==NEGATIVE_SHA256,'Negative fixture hash differs from verified source'
    os.environ['SCENE2REAL_USE_CACHE']='0'
    config.init_weave()
    import weave
    @weave.op()
    def evaluate_video(path, expected_fire, source_kind):
        path=Path(path)
        duration=ingest.probe(path)['duration_s']
        frames=ingest.extract_frames(path,duration,args.output/path.stem)
        result={'source_sha256':ingest.sha256_file(path),'source_kind':source_kind,
                'expected_fire':expected_fire,'fresh_inference':True,'cached':False,
                'frames':[{'t_s':f['t_s'],'image_sha256':ingest.sha256_file(Path(f['path']))} for f in frames],
                'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                'model':cosmos.MODEL_ID,'prompt_id':cosmos.PROMPT_ID,'motion_authorized':False}
        started=time.monotonic()
        try:
            analysis,observations=cosmos.analyse(frames,duration,result['source_sha256'],allow_empty=True)
            result.update(analysis=analysis,observations=observations,
                          fire_detected=bool(observations['fire_sources']),
                          detection_correct=bool(observations['fire_sources'])==expected_fire)
            timestamp=annotations['requested_timestamp_seconds']
            if expected_fire and any(abs(f['t_s']-timestamp)<1e-6 for f in frames):
                timestamped=all(s.get('bbox_by_frame') or s.get('bbox_at_s') is not None for s in observations['fire_sources'])
                if timestamped:
                    result['localization_at_annotated_timestamp']=score(exact_sources(observations['fire_sources'],timestamp),matches[0]['boxes'],timestamp)
                else:
                    result['localization']='unscored: Cosmos per-source static boxes have no exact bbox timestamp; independent Astra grounding unavailable'
                    result['static_box_diagnostic_not_timestamp_grounded']=score(observations['fire_sources'],matches[0]['boxes'],timestamp)
            else:result['localization']='unscored: no independently annotated exact sampled timestamp'
        except Exception as exc:
            result.update(error_type=type(exc).__name__,detection_correct=False)
        result['wall_inference_s']=round(time.monotonic()-started,3)
        return result
    rows=[]
    for path,expected,kind in [(args.positive,True,'synthetic_video_from_independent_API_still'),
                                (args.negative,False,'historical_authored_static_no_fire_video')]:
        result,call=evaluate_video.call(str(path),expected,kind)
        result['weave_url']=call.ui_url
        rows.append(result)
        (args.output/'results.json').write_text(json.dumps(rows,indent=2))
        print(json.dumps({k:result.get(k) for k in ('source_kind','fire_detected','detection_correct','weave_url')}),flush=True)
    (args.output/'ledger.json').write_text(json.dumps({'cosmos':2,'wandb':0,'astra':0,'cache_replay':0},indent=2))


if __name__=='__main__':main()
