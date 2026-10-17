"""Reproducible integration campaign; network calls require --live.

python -m evals.runner --output output/integration-eval [--live]
Use a new output directory for each fresh campaign. Existing output is never overwritten.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scene2real import config, mobile, planner
from .scorers import acceptance, mobile_score, replay_exposure

DATA = Path(__file__).parent / 'datasets/integration_v1.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(targets):
    return {'instruction':'Leave the station and suppress every confirmed target.',
            'skill':{'name':'mobile_suppress_demo','target_ids': [t['fire_id'] for t in sorted(targets,key=lambda t:t['template_position_m'][0])]},
            'scene_settings':{'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':.6,
                              'spray_profile':'water_demo','spray_duration_s':4.}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output/integration-eval'))
    parser.add_argument('--live', action='store_true', help='Spend bounded W&B/Astra inference requests')
    parser.add_argument('--providers', nargs='+', choices=['reference','astra','wandb'],
                        default=['reference','astra','wandb'])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output/'manifest.json').exists():
        raise SystemExit('Output already contains a campaign; choose a fresh --output directory')
    config.RUNS_DIR=args.output/'runs'
    rows = json.loads(DATA.read_text())
    frozen = json.loads(DATA.with_suffix('.manifest.json').read_text())
    assert digest(DATA) == frozen['dataset_sha256'], 'Frozen dataset digest changed'
    revision = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    manifest = {'argv':sys.argv, 'source_commit':revision, 'started_at':time.time(), 'dataset':frozen,
                'live_requested':args.live, 'cache_enabled':False,
                'budget':{'wandb':20,'astra':20,'cosmos':0},
                'source_hashes':{str(p):digest(p) for p in sorted(list(Path('scene2real').glob('*.py'))+list(Path('evals').glob('*.py')))},
                'boundary':'Planner-only synthetic reviewed evidence. No video perception inference in this campaign.',
                'providers_configured':{p:bool(config.get(k)) for p,k in [('wandb','WANDB_API_KEY'),('astra','OPENAI_API_KEY')]}}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (args.output/'dataset.json').write_bytes(DATA.read_bytes())
    os.environ['SCENE2REAL_USE_CACHE']='0'
    os.environ['SCENE2REAL_PLANNER_MAX_ATTEMPTS']='1'
    from .live_controls import run_controls
    live_controls=run_controls()
    (args.output/'g1-controls.json').write_text(json.dumps(live_controls,indent=2))
    results=[]
    ledger={'wandb':0,'astra':0,'cosmos':0}
    # Count actual HTTP attempts, including provider retries, before transmission.
    import requests
    original_post=requests.post
    def bounded_post(url,*a,**kw):
        provider='wandb' if str(url).startswith(config.WANDB_BASE) else 'astra' if str(url).startswith('https://api.openai.com/') else None
        if provider:
            if ledger[provider]>=manifest['budget'][provider]:
                raise RuntimeError(f'{provider} campaign request budget exhausted')
            ledger[provider]+=1
            (args.output/'request-ledger.json').write_text(json.dumps(ledger,indent=2))
        return original_post(url,*a,**kw)
    requests.post=bounded_post
    def predict(case,case_id,split,provider,trial):
        t0=time.monotonic()
        result={'case_id':case_id,'split':split,'provider':provider,'trial':trial,
                'source_kind':'live_inference' if provider!='reference' else 'deterministic_reference',
                'input_sha256':hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
                'valid':False,'simulation_success':False,'collision_count':None,
                'source_commit':revision,'fresh_inference':provider!='reference'}
        try:
            targets,evidence=case['targets'],case['evidence']
            if provider=='reference':
                plan,model,meta=reference(targets),'deterministic_reference',{}
            elif provider=='wandb':
                plan,model,meta=planner.call_wandb_mobile(targets,evidence)
            else:
                value=planner.call_astra(targets,evidence)
                plan,model=value[:2];meta=value[2] if len(value)>2 else {}
            result['inference_latency_s']=round(time.monotonic()-t0,4)
            result.update(returned_model=model,metadata=meta,plan=plan)
            _,skill,settings=planner.validate_mobile_payload(plan,targets)
            result['valid']=True
            scene=mobile.build_scene(targets,settings)
            sim_start=time.monotonic()
            metrics,trajectory=mobile.simulate(scene,skill)
            result.update(mobile_score(metrics))
            result.update(replay_exposure(scene,trajectory,metrics))
            result.update(metrics=metrics,simulation_wall_s=round(time.monotonic()-sim_start,4))
            # Same saved scene/plan replay proves repeatability; no second inference.
            replay,_=mobile.simulate(scene,skill)
            result['saved_plan_replay_identical']=replay==metrics
        except Exception as exc:
            # Provider errors are typed, sanitized by provider adapters; never serialize request objects.
            result['error_type']=type(exc).__name__
            result['error']=str(exc)[:240]
            result.setdefault('inference_latency_s',round(time.monotonic()-t0,4))
            if isinstance(getattr(exc,'metadata',None),dict):
                result['metadata']=exc.metadata
        result['total_wall_s']=round(time.monotonic()-t0,4)
        results.append(result)
        with (args.output/'results.jsonl').open('a') as stream:
            stream.write(json.dumps(result,allow_nan=False)+'\n')
        print(json.dumps({k:result.get(k) for k in ('case_id','split','provider','trial','valid','simulation_success','error_type')}),flush=True)
        return result

    async def campaign():
        weave=None
        links=[]
        if args.live and config.get('WANDB_API_KEY'):
            try:
                import weave as sdk
                config.init_weave()
                if config.TELEMETRY['weave']=='ok':
                    weave=sdk
            except Exception:
                pass
        for provider in args.providers if args.live else ['reference']:
            if provider!='reference' and not manifest['providers_configured'][provider]:
                links.append({'provider':provider,'status':'unavailable','reason':'Server credential absent; no fallback substituted'})
                continue
            for split,trials in [('development',1),('locked_test',2)]:
                subset=[r for r in rows if r['split']==split]
                if weave:
                    @weave.op()
                    def model(case,case_id,split):
                        previous=sum(r['provider']==provider and r['case_id']==case_id for r in results)
                        return predict(case,case_id,split,provider,previous)
                    @weave.op()
                    def score(output):
                        return {k:output.get(k,False) for k in ('valid','simulation_success','measurement_consistent','replay_exposure_consistent','saved_plan_replay_identical')}
                    dataset=weave.Dataset(name=f'scene2real_integration_v1_{split}',rows=[{'case':r['case'],'case_id':r['case_id'],'split':split} for r in subset])
                    ref=weave.publish(dataset)
                    ev=weave.Evaluation(name=f'scene2real_integration_v1_{provider}_{split}',dataset=dataset,scorers=[score],trials=trials)
                    summary,call=await ev.evaluate.call(ev,model)
                    links.append({'provider':provider,'split':split,'dataset_ref':str(ref),'url':call.ui_url,'summary':summary})
                    (args.output/'links.json').write_text(json.dumps(links,indent=2,default=str))
                else:
                    for r in subset:
                        for trial in range(trials):predict(r['case'],r['case_id'],split,provider,trial)
        (args.output/'links.json').write_text(json.dumps(links,indent=2,default=str))
    try:
        os.environ['WEAVE_PARALLELISM']='1'
        asyncio.run(campaign())
    finally:
        requests.post=original_post
    baseline_complete=sum(r['provider']=='astra' and r['split']=='locked_test' for r in results)==16
    summary=acceptance(results,baseline_complete)
    summary.update(requests=ledger,source_commit=revision,dataset_sha256=frozen['dataset_sha256'],
                   g1_physics_controls={'passed':sum(r['passed'] for r in live_controls),'count':len(live_controls),
                                        'provenance':'deterministic_physics_fixture; not model inference'},
                   counts={provider:{'attempts':sum(r['provider']==provider for r in results),
                                     'valid':sum(r['provider']==provider and r['valid'] for r in results),
                                     'success':sum(r['provider']==provider and r['simulation_success'] for r in results)}
                           for provider in ('reference','astra','wandb')})
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    (args.output/'request-ledger.json').write_text(json.dumps(ledger,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
