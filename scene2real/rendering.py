"""Render a recorded mobile trajectory to a real MP4 using MuJoCo and FFmpeg."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import mujoco
import numpy as np

from .ingest import media_tool


def export_video(scene, traj, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames, qposes = traj.get('frames', []), traj.get('qpos', [])
    fps = traj.get('fps')
    if not frames or len(frames) != len(qposes) or not isinstance(fps, (int, float)) or fps <= 0:
        raise ValueError('Recording requires aligned trajectory frames, qpos, and a positive frame rate')
    width, height = 960, 540
    temp_path = None
    renderer = proc = None
    try:
        model = mujoco.MjModel.from_xml_string(scene['mjcf'])
        data = mujoco.MjData(model)
        if any(len(q) != model.nq for q in qposes):
            raise ValueError('Recording joint positions do not match the scene')
        renderer = mujoco.Renderer(model, height=height, width=width)
        options = mujoco.MjvOption()
        options.geomgroup[3] = 1
        fd, temp_path = tempfile.mkstemp(prefix='.simulation-', suffix='.mp4', dir=str(destination.parent))
        os.close(fd)
        with tempfile.TemporaryFile() as errors:
            command = [media_tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y']
            threads = os.environ.get('SCENE2REAL_FFMPEG_THREADS')
            if threads is not None:
                count = int(threads)
                if not 1 <= count <= 64:
                    raise ValueError('SCENE2REAL_FFMPEG_THREADS must be between 1 and 64')
                command += ['-filter_threads', str(count), '-filter_complex_threads', str(count)]
            command += [
                    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps), '-i', '-',
                    '-an', '-c:v', 'libx264']
            if threads is not None:
                command += ['-threads', str(count)]
            command += ['-pix_fmt', 'yuv420p', '-movflags', '+faststart', temp_path]
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)

            def pipe_failure(exc):
                timed_out = False
                try:
                    code = proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    code = proc.wait()
                errors.seek(0)
                detail = errors.read().decode(errors='replace')[-1000:].strip()
                message = (f'FFmpeg did not exit after its input pipe closed; terminated (status {code})'
                           if timed_out else f'FFmpeg exited while receiving frames (status {code})')
                if detail:
                    message += f': {detail}'
                return RuntimeError(message)

            fires = traj.get('fx', {}).get('fires', [])
            events = traj.get('fx', {}).get('spray', [])
            fire_geoms = [(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'fire_' + f['id'] + suffix), f.get('suppressed_frame')) for f in fires for suffix in ('', '_tip')]
            stream_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'water_stream')
            fire_lookup = {f['id']: np.asarray(f['pos'], dtype=float) for f in fires}
            spray_on, target_id, event_idx = False, None, 0
            for index, qpos in enumerate(qposes):
                while event_idx < len(events) and events[event_idx]['frame'] <= index:
                    event = events[event_idx]; spray_on, target_id = bool(event['on']), event.get('target_id'); event_idx += 1
                data.qpos[:] = qpos
                mujoco.mj_forward(model, data)
                for geom, suppressed in fire_geoms:
                    if geom >= 0:
                        model.geom_rgba[geom, 3] = 0.0 if suppressed is not None and index >= suppressed else 1.0
                if stream_id >= 0:
                    model.geom_rgba[stream_id, 3] = .8 if spray_on and target_id in fire_lookup else 0.
                    if spray_on and target_id in fire_lookup:
                        noz = np.array(traj['fx']['nozzle'][index][:3])
                        length = float(np.linalg.norm(fire_lookup[target_id] - noz))
                        model.geom_size[stream_id, 1] = max(.01, length / 2)
                        model.geom_pos[stream_id, 0] = .5 + length / 2
                        mujoco.mj_forward(model, data)
                renderer.update_scene(data, camera='overview', scene_option=options)
                try:
                    proc.stdin.write(renderer.render().tobytes())
                except BrokenPipeError as exc:
                    raise pipe_failure(exc) from exc
            try:
                proc.stdin.close()
            except BrokenPipeError as exc:
                raise pipe_failure(exc) from exc
            code = proc.wait(timeout=120)
            if code:
                errors.seek(0)
                raise RuntimeError('FFmpeg encoding failed: ' + errors.read().decode(errors='replace')[-1000:])
        if not Path(temp_path).exists() or Path(temp_path).stat().st_size == 0:
            raise RuntimeError('FFmpeg produced an empty simulation video')
        os.replace(temp_path, destination)
        temp_path = None
        return {'path': str(destination), 'width': width, 'height': height, 'fps': fps,
                'duration_s': round(len(frames)/fps, 4), 'codec': 'h264', 'renderer': 'MuJoCo', 'frame_count': len(frames)}
    except Exception as exc:
        raise RuntimeError(f'Simulation video export failed: {exc}') from exc
    finally:
        if proc is not None and proc.poll() is None:
            try:
                if proc.stdin and not proc.stdin.closed:
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass
            finally:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                proc.wait()
        if renderer is not None:
            renderer.close()
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)
