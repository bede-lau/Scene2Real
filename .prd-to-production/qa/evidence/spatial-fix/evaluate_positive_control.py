import json, math
from pathlib import Path
out=Path('output/spatial-fix/positive-e2e'); d=json.loads((out/'analysis.json').read_text()); truth=json.loads((out/'fixture_truth.json').read_text()); order=json.loads((out/'qa-order.json').read_text())['upload_order_fixture_ids']
# This evaluation reads QA-only geometry AFTER inference. It cannot repair or modify predictions.
report={'scope':truth['scope'],'evaluated_after_inference':True,'threshold_normalized':0.08,'views':[],'groups':[],'pass':False}
lookup={}; ok=d.get('state')=='analysed'; all_ids=set()
for k,view in enumerate(d['analysis']['views']):
 vid=view['view_id']; refs=truth['videos'][order[k]-1]['reference_centers_xy']; t=view['analysis']['frames'][len(view['analysis']['frames'])//2]['t_s']; entries=[]; assigned=[]
 for f in view['observations']['fire_sources']:
  fid=vid+':'+f['id']; all_ids.add(fid)
  boxes=[b['bbox_normalized'] for b in f.get('bbox_by_frame',[]) if b['t_s']==t]
  if len(boxes)!=1:
   entries.append({'id':fid,'error':'No unique box for selected frame'}); ok=False; continue
  x1,y1,x2,y2=boxes[0]; center=[(x1+x2)/2,(y1+y2)/2]
  ds=[math.dist(center,p) for p in refs]; site=min(range(len(ds)),key=ds.__getitem__); lookup[fid]=site; assigned.append(site)
  entries.append({'id':fid,'evaluated_center':center,'nearest_reference_site':site+1,'error_normalized':round(ds[site],4)})
  if ds[site]>.08:ok=False
 if sorted(assigned)!=list(range(len(refs))):ok=False
 report['views'].append({'view_id':vid,'selected_timestamp_s':t,'entries':entries,'all_reference_sites_unique':sorted(assigned)==list(range(len(refs)))})
association=d['analysis']['association']; candidates=association.get('candidates',[]); used=set()
for c in candidates:
 members=c['members']; sites=[lookup.get(i) for i in members]; good=len(members)==3 and None not in sites and len(set(sites))==1 and not used.intersection(members)
 if not good:ok=False
 used.update(members);report['groups'].append({'members':members,'reference_sites':[None if s is None else s+1 for s in sites],'pass':good,'geometry_checks':c.get('geometry_checks')})
if len(candidates)!=4 or used!=all_ids:ok=False
report['association_status']=association['status'];report['room_status']=association['room_status'];report['association_uncertainties']=association['uncertainties'];report['association_error']=association['error'];report['pass']=ok
(out/'evaluation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); print('positive control', 'PASS' if ok else 'FAIL')
