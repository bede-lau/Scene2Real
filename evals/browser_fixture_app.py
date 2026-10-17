"""Test-only app: mocked service boundaries, actual ingest/validation/MuJoCo/export.

Never use as the application entrypoint. Start explicitly on a separate loopback
port: python -m uvicorn evals.browser_fixture_app:app --host 127.0.0.1 --port 8096
"""
import json
from scene2real import config, cosmos, matching, planner, records, yolo, pipeline
from .runner import reference

config.spatial_review_enabled=lambda:False
config.init_weave=lambda:'skipped: explicit mocked browser fixture'
cosmos.MODEL_ID='mocked-browser-fixture'
cosmos.PROMPT_ID='fixture-not-inference'
original_event=pipeline._event
def mocked_event(run,stage,**kwargs):
    kwargs['provenance']='mocked'
    return original_event(run,stage,**kwargs)
pipeline._event=mocked_event
records.archive=lambda *a,**kw:None
yolo.detect=lambda *a,**kw:([],'mocked browser fixture')


def analyse(frames,duration,sha,allow_empty=False):
    times=[f['t_s'] for f in frames]
    raw={'scene_description':'MOCKED SERVICE BOUNDARY: warehouse browser fixture',
         'fire_sources':[{'id':'F1','timestamps_s':times,'bbox_2d':[150,300,300,650],
                          'description':'MOCKED visible flames at packaging'},
                         {'id':'F2','timestamps_s':times,'bbox_2d':[650,250,800,600],
                          'description':'MOCKED reflection requiring reasoned exclusion'}],
         'cause':None,'scale':None,'depth_m':None,'unknowns':['depth','cause','scale']}
    obs=cosmos.validate(raw,duration,allow_empty=allow_empty)
    obs['objects']=[]
    return {'raw_text':json.dumps(raw),'cached':False,'mocked':True,'frames':[{'t_s':t} for t in times],
            'latency_s':0,'model_id':'mocked-browser-fixture'},obs


cosmos.analyse=analyse
cosmos.propose_associations=lambda *a,**kw:{'status':'manual_review','candidates':[],'error':None,'provenance':'mocked'}
matching.propose=lambda *a,**kw:{'room_status':'unverified','status':'manual_review','candidates':[],
                               'unmatched':[],'uncertainties':['MOCKED: operator grouping required'],
                               'error':None,'model_id':None,'provenance':'mocked'}


def plan(targets,evidence):
    raw=reference(targets)
    text,skill,settings=planner.validate_mobile_payload(raw,targets)
    return {'text':text,'source':'mocked','provider':'mocked','model_id':'mocked-browser-fixture',
            'prompt_id':'fixture-not-inference','raw_plan':raw,'latency_s':0,'cached':False},skill,settings


planner.make_mobile_plan=plan
from scene2real.app import app  # noqa: E402
