import subprocess

import pytest

from scene2real import ingest, mobile, rendering


@pytest.mark.parametrize('threads', [None, '1'])
def test_real_video_export_and_encoder_failure(tmp_path, monkeypatch, threads):
    if threads is None:
        monkeypatch.delenv('SCENE2REAL_FFMPEG_THREADS', raising=False)
    else:
        monkeypatch.setenv('SCENE2REAL_FFMPEG_THREADS', threads)
    settings = {'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':1.,'spray_profile':'water_demo','spray_duration_s':3.}
    scene = mobile.build_scene([{'fire_id':'T1','zone':'right_rack','slot':0}], settings)
    metrics, trajectory = mobile.simulate(scene, {'name':'mobile_suppress_demo','target_ids':['T1']})
    assert metrics['success']
    path = tmp_path / 'simulation.mp4'
    metadata = rendering.export_video(scene, trajectory, path)
    probe = ingest.probe(path)
    assert path.stat().st_size > 1000 and abs(probe['duration_s'] - metadata['duration_s']) < .1
    out = tmp_path / 'frame.png'
    subprocess.run([ingest.media_tool('ffmpeg'), '-v', 'error', '-y', '-i', str(path), '-frames:v', '1', str(out)], check=True)
    assert out.stat().st_size > 1000
    monkeypatch.setattr(rendering, 'media_tool', lambda _: '/nonexistent/ffmpeg')
    with pytest.raises(RuntimeError, match='Simulation video export failed'):
        rendering.export_video(scene, trajectory, tmp_path / 'failed.mp4')
    assert not (tmp_path / 'failed.mp4').exists()
