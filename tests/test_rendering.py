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


def test_export_reports_early_ffmpeg_exit_and_cleans_temp_file(tmp_path, monkeypatch):
    settings = {'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':1.,'spray_profile':'water_demo','spray_duration_s':3.}
    scene = mobile.build_scene([{'fire_id':'T1','zone':'right_rack','slot':0}], settings)
    _, trajectory = mobile.simulate(scene, {'name':'mobile_suppress_demo','target_ids':['T1']})
    encoder = tmp_path / 'failed-ffmpeg'
    encoder.write_text('#!/bin/sh\necho "encoder rejected input" >&2\nexit 1\n')
    encoder.chmod(0o755)
    monkeypatch.setattr(rendering, 'media_tool', lambda _: str(encoder))
    destination = tmp_path / 'simulation.mp4'

    with pytest.raises(RuntimeError, match=r'FFmpeg exited while receiving frames \(status 1\): encoder rejected input'):
        rendering.export_video(scene, trajectory, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob('.simulation-*.mp4'))


def test_export_reports_broken_pipe_on_stdin_close(tmp_path, monkeypatch):
    settings = {'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':1.,'spray_profile':'water_demo','spray_duration_s':3.}
    scene = mobile.build_scene([{'fire_id':'T1','zone':'right_rack','slot':0}], settings)
    _, trajectory = mobile.simulate(scene, {'name':'mobile_suppress_demo','target_ids':['T1']})

    class BrokenClosePipe:
        closed = False

        def write(self, frame):
            return len(frame)

        def close(self):
            self.closed = True
            raise BrokenPipeError('flush failed')

    class FailedEncoder:
        def __init__(self):
            self.stdin = BrokenClosePipe()
            self.returncode = None

        def wait(self, timeout=None):
            self.returncode = 1
            return self.returncode

        def poll(self):
            return self.returncode

    def start_encoder(command, stdin, stderr):
        stderr.write(b'encoder failed while flushing')
        return FailedEncoder()

    monkeypatch.setattr(rendering.subprocess, 'Popen', start_encoder)
    destination = tmp_path / 'simulation.mp4'

    with pytest.raises(RuntimeError, match=r'FFmpeg exited while receiving frames \(status 1\): encoder failed while flushing'):
        rendering.export_video(scene, trajectory, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob('.simulation-*.mp4'))


def test_export_kills_and_reaps_encoder_when_pipe_diagnosis_times_out(tmp_path, monkeypatch):
    settings = {'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':1.,'spray_profile':'water_demo','spray_duration_s':3.}
    scene = mobile.build_scene([{'fire_id':'T1','zone':'right_rack','slot':0}], settings)
    _, trajectory = mobile.simulate(scene, {'name':'mobile_suppress_demo','target_ids':['T1']})

    class BrokenClosePipe:
        closed = False

        def write(self, frame):
            return len(frame)

        def close(self):
            self.closed = True
            raise BrokenPipeError('flush failed')

    class HungEncoder:
        def __init__(self):
            self.stdin = BrokenClosePipe()
            self.returncode = None
            self.killed = False
            self.wait_calls = 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            if timeout is not None:
                raise subprocess.TimeoutExpired('ffmpeg', timeout)
            assert self.killed
            self.returncode = -9
            return self.returncode

        def kill(self):
            self.killed = True

        def poll(self):
            return self.returncode

    encoder = HungEncoder()

    def start_encoder(command, stdin, stderr):
        stderr.write(b'encoder hung')
        return encoder

    monkeypatch.setattr(rendering.subprocess, 'Popen', start_encoder)
    destination = tmp_path / 'simulation.mp4'

    with pytest.raises(RuntimeError, match=r'did not exit after its input pipe closed; terminated \(status -9\): encoder hung'):
        rendering.export_video(scene, trajectory, destination)

    assert encoder.killed and encoder.wait_calls == 2
    assert not destination.exists()
    assert not list(tmp_path.glob('.simulation-*.mp4'))


def test_cleanup_close_error_does_not_mask_original_failure(tmp_path, monkeypatch):
    settings = {'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':1.,'spray_profile':'water_demo','spray_duration_s':3.}
    scene = mobile.build_scene([{'fire_id':'T1','zone':'right_rack','slot':0}], settings)
    _, trajectory = mobile.simulate(scene, {'name':'mobile_suppress_demo','target_ids':['T1']})

    class FailingPipe:
        closed = False

        def write(self, frame):
            raise ValueError('original frame failure')

        def close(self):
            self.closed = True
            raise BrokenPipeError('cleanup close failure')

    class RunningEncoder:
        def __init__(self):
            self.stdin = FailingPipe()
            self.returncode = None
            self.killed = False
            self.reaped = False

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

        def wait(self, timeout=None):
            self.reaped = True
            return self.returncode

    encoder = RunningEncoder()
    monkeypatch.setattr(rendering.subprocess, 'Popen', lambda *args, **kwargs: encoder)
    destination = tmp_path / 'simulation.mp4'

    with pytest.raises(RuntimeError, match='Simulation video export failed: original frame failure'):
        rendering.export_video(scene, trajectory, destination)

    assert encoder.killed and encoder.reaped
    assert not destination.exists()
    assert not list(tmp_path.glob('.simulation-*.mp4'))
