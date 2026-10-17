"""Mode-specific G1 physics controls; fixture authorization is explicitly not inference."""
import time

import numpy as np


def run_controls():
    from scene2real.live import LiveSession
    results=[]
    for name in ('left','center','right','obscured','wrong','manual'):
        session=LiveSession(start_thread=False)
        try:
            session.set_scene({'scenario':name if name!='manual' else 'center'})
            pose='left' if name=='wrong' else 'center' if name in ('obscured','manual') else name
            session.control({'action':'pose','pose':pose})
            if name!='manual':
                # Test-only fixture state: cannot be invoked from an HTTP client.
                session.decision={'status':'ready'}
                session.lease_until=time.monotonic()+60
            session.step(2200)
            should_hit=name in ('left','center','right')
            exposure_agrees=abs(session.intensity-max(0,1-.24*session.metrics['hit_s']))<1e-6
            expected=(session.intensity<.8 and session.metrics['hit_s']>1) if should_hit else session.intensity==1
            finite=bool(np.all(np.isfinite(session.data.qpos)))
            limits=session.model.actuator_forcerange
            bounded=bool(np.all(session.data.actuator_force>=limits[:,0]-1e-6) and np.all(session.data.actuator_force<=limits[:,1]+1e-6))
            results.append({'case_id':'g1_'+name,'source_kind':'deterministic_physics_fixture',
                            'fresh_inference':False,'fixture_authorization':name!='manual',
                            'metric_contract':'live_g1_ray_intensity_proxy','intensity':session.intensity,
                            'metrics':session.metrics,'exposure_intensity_consistent':exposure_agrees,
                            'finite_qpos':finite,'actuator_force_within_limits':bounded,
                            'expected_outcome':expected,'passed':expected and exposure_agrees and finite and bounded})
        finally:
            session.closed=True
    return results
