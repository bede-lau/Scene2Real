"""Score saved actual video observations against existing independent annotations.

python -m evals.perception --runs runs/ID/run.json --output output/perception.json
No requests are made. Results retain cached/live provenance; source hashes must match.
"""
import argparse
import json
from pathlib import Path

from scripts.check_spatial_accuracy import score


def exact_sources(sources, timestamp):
    result=[]
    for source in sources:
        item=dict(source)
        if source.get('bbox_by_frame'):
            matching=[b for b in source['bbox_by_frame'] if abs(b.get('t_s',-100)-timestamp)<1e-6]
            item['bbox_by_frame']=matching or [{'t_s':timestamp,'bbox_normalized':None}]
        elif source.get('bbox_at_s') is None or abs(source['bbox_at_s']-timestamp)>1e-6:
            item['bbox_normalized']=None
        result.append(item)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    fixture=json.loads(Path('tests/fixtures/fire_localization.json').read_text())
    refs={v['source_sha256']:(name,v) for name,v in fixture['views'].items()}
    timestamp=fixture['requested_timestamp_seconds']
    results=[]
    for path in args.runs:
        run=json.loads(path.read_text())
        videos={r['view_id']:r for r in run.get('video_refs',[])}
        for view in run.get('analysis',{}).get('views',[]):
            ref=videos.get(view['view_id'],{})
            if ref.get('sha256') not in refs:
                results.append({'run_id':run['run_id'],'view_id':view['view_id'],'status':'unscored_no_independent_annotation'})
                continue
            name,label=refs[ref['sha256']]
            sources=view.get('observations',{}).get('fire_sources',[])
            results.append({'run_id':run['run_id'],'view_id':view['view_id'],'source_name':name,
                            'source_sha256':ref['sha256'],'timestamp_s':timestamp,
                            'cached':view.get('analysis',{}).get('cached',False),
                            'source_kind':'synthetic_video_from_independently_generated_still',
                            'scores':score(exact_sources(sources,timestamp),label['boxes'],timestamp)})
    report={'annotation_method':fixture['annotation_method'],'views':results,
            'association':'Not quantitatively established: annotations deliberately provide no cross-view physical identity truth.',
            'scoring_only':True,'fresh_inference_requests':0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
