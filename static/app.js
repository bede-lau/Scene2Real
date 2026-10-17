// Scene2Real workbench: plain ES module, no build step.
const $ = (s, r = document) => r.querySelector(s);
const MAX_BYTES = 200 * 1024 * 1024;
const STAGES = ['Video', 'Cosmos', 'Confirm target', 'Instruction', 'Simulation', 'Metrics'];

const S = {
  run: null, clips: [], zones: {}, traj: null,
  fireId: null, zone: null,
  busy: null,          // {section:Number}
  error: null,         // {message, retryable}
  last: null,          // async fn to retry
  uploadMsg: '',
};

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, '');
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
const fmt = (v, d = 2, unit = '') => (v == null || Number.isNaN(v)) ? h('span', { class: 'unk' }, 'unknown') : `${Number(v).toFixed(d)}${unit}`;
const unk = (v, f = x => String(x)) => (v == null || (Array.isArray(v) && !v.length)) ? h('span', { class: 'unk' }, 'unknown') : f(v);
const bb = b => b ? `[${b.map(n => Number(n).toFixed(2)).join(', ')}]` : null;
const vec = v => v ? `(${v.map(n => Number(n).toFixed(2)).join(', ')}) m` : null;

// ---------------- API ----------------
async function api(path, opts = {}) {
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw { message: 'Network error: server unreachable.', retryable: true }; }
  if (!res.ok) {
    let body = {};
    try { body = await res.json(); } catch { /* non-json */ }
    let msg = body.detail;
    if (Array.isArray(msg)) msg = msg.map(d => d.msg || JSON.stringify(d)).join('; ');
    if (msg && typeof msg === 'object') msg = msg.message || JSON.stringify(msg);
    throw { message: msg || `Request failed (${res.status})`, retryable: body.retryable ?? res.status >= 500 };
  }
  return res.json();
}
const post = (p, body) => api(p, body === undefined ? { method: 'POST' } :
  { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

// ---------------- actions ----------------
const SECTION = { video: 1, analyse: 2, confirm: 3, scene: 5, run: 5, reset: 5 };

async function act(kind, fn) {
  S.last = () => act(kind, fn);
  S.busy = { section: SECTION[kind] };
  S.error = null;
  render();
  try {
    const run = await fn();
    setRun(run);
    if (run.state === 'completed') await loadTraj(kind === 'run');
  } catch (e) {
    S.error = { message: e.message || String(e), retryable: !!e.retryable };
  } finally {
    S.busy = null;
    render();
  }
}
function setRun(run) {
  const prevId = S.run?.run_id;
  S.run = run;
  if (run.run_id !== prevId) { S.traj = null; S.fireId = null; S.zone = null; sim.clear(); }
  if (run.run_id) history.replaceState(null, '', '#' + run.run_id);
  const fs = run.observations?.fire_sources || [];
  if (!fs.find(f => f.id === S.fireId)) S.fireId = run.confirmed_target?.fire_id || fs[0]?.id || null;
  if (!S.zone) S.zone = run.confirmed_target?.zone || fs.find(f => f.id === S.fireId)?.suggested_zone || null;
  if (['scene_ready', 'confirmed', 'analysed', 'uploaded'].includes(run.state)) {
    if (run.state !== 'completed' && !run.metrics) { S.traj = null; sim.clear(); }
  }
}
async function loadTraj(autoplay) {
  S.traj = await api(`/api/runs/${S.run.run_id}/trajectory`);
  await sim.load(S.traj, autoplay);
}

const startClip = id => act('video', () => post('/api/runs', { clip_id: id }));
function startUpload(file) {
  S.uploadMsg = '';
  if (!(file.type === 'video/mp4' || /\.mp4$/i.test(file.name))) { S.uploadMsg = 'Not an mp4 file. Choose a .mp4 video.'; return render(); }
  if (file.size > MAX_BYTES) { S.uploadMsg = `File is ${(file.size / 1048576).toFixed(0)} MB; limit is 200 MB.`; return render(); }
  act('video', () => new Promise((resolve, reject) => {
    const fd = new FormData(); fd.append('file', file);
    const x = new XMLHttpRequest();
    const wrap = $('#upload-wrap'), prog = $('#upload-prog'), lab = $('#upload-label');
    wrap.hidden = false; prog.value = 0; lab.textContent = `Uploading ${file.name} 0%`;
    x.upload.onprogress = e => { if (e.lengthComputable) { const p = Math.round(e.loaded / e.total * 100); prog.value = p; lab.textContent = `Uploading ${file.name} ${p}%`; } };
    x.onload = () => {
      wrap.hidden = true;
      let b = {}; try { b = JSON.parse(x.responseText); } catch { /* */ }
      if (x.status >= 200 && x.status < 300) resolve(b);
      else reject({ message: (typeof b.detail === 'string' ? b.detail : null) || `Upload failed (${x.status})`, retryable: b.retryable ?? x.status >= 500 });
    };
    x.onerror = () => { wrap.hidden = true; reject({ message: 'Network error during upload.', retryable: true }); };
    x.open('POST', '/api/runs'); x.send(fd);
  }));
}
const id = () => S.run.run_id;
const doAnalyse = () => act('analyse', () => post(`/api/runs/${id()}/analyse`));
const doConfirm = () => act('confirm', () => post(`/api/runs/${id()}/confirm`, { fire_id: S.fireId, zone: S.zone }));
const doScene = () => act('scene', () => post(`/api/runs/${id()}/scene`));
const doRun = () => act('run', () => post(`/api/runs/${id()}/run`));
const doReset = () => act('reset', async () => { const r = await post(`/api/runs/${id()}/reset`); S.traj = null; sim.clear(); return r; });
const STAGE_RETRY = { analyse: doAnalyse, confirm: doConfirm, scene: doScene, plan: doScene, run: doRun };

// ---------------- derived state ----------------
function progress() {
  const r = S.run, st = r?.state;
  const done = [!!r, !!r?.analysis, !!r?.confirmed_target, !!r?.instruction, !!r?.metrics, !!r?.metrics];
  let active = done.findIndex(d => !d); if (active < 0) active = 5;
  const warn = st === 'needs_review' || st === 'blocked' || st === 'failed';
  return { done, active, warn };
}

// ---------------- render ----------------
function render() {
  const r = S.run, st = r?.state || 'idle', busy = !!S.busy;
  const { done, active, warn } = progress();

  $('#run-id').textContent = r ? r.run_id : 'no run';
  const sp = $('#run-state'); sp.textContent = st.replace('_', ' ');
  sp.className = 'pill ' + (st === 'completed' ? 'ok' : (st === 'failed') ? 'bad' : (['needs_review', 'blocked'].includes(st) ? 'warn' : ''));

  // rail + section chrome
  const rail = $('#rail'); rail.replaceChildren();
  STAGES.forEach((name, i) => {
    const cls = done[i] ? 'done' : (i === active ? 'active' + (warn ? ' warn' : '') : '');
    rail.append(h('li', { class: cls }, h('a', { href: '#s' + (i + 1), 'aria-label': `${i + 1} ${name}`, 'aria-current': i === active ? 'step' : null },
      h('span', { class: 'n' }, done[i] ? '✓' : String(i + 1)), name)));
    const sec = $('#s' + (i + 1));
    const locked = i > active && !done[i];
    sec.className = 'stage ' + (done[i] ? 'done' : i === active ? 'active' + (warn ? ' warn' : '') : 'locked');
    sec.querySelector('.status').textContent = done[i] ? 'done' : i === active ? (warn ? st.replace('_', ' ') : 'active') : '';
    const pr = sec.querySelector('.progress'); pr.hidden = S.busy?.section !== i + 1;
    sec.setAttribute('aria-busy', S.busy?.section === i + 1 ? 'true' : 'false');
    if (locked) sec.classList.add('locked');
  });

  // error
  const err = S.error || (r?.error ? { message: `${r.error.stage}: ${r.error.message}`, retryable: r.error.retryable, stage: r.error.stage } : null);
  $('#err').hidden = !err;
  if (err) {
    $('#err-msg').textContent = err.message;
    const retry = S.error ? S.last : (STAGE_RETRY[r.error.stage] || null);
    const rb = $('#err-retry'); rb.hidden = !(err.retryable && retry); rb.disabled = busy; rb.onclick = () => retry && retry();
  }

  renderVideo(); renderCosmos(); renderConfirm(); renderInstruction(); renderSim(); renderMetrics();
  drawOverlay();
}

function renderVideo() {
  const r = S.run, busy = !!S.busy;
  const box = $('#clips');
  box.replaceChildren(...S.clips.map(c => h('button', { type: 'button', class: 'btn', disabled: busy, onclick: () => startClip(c.clip_id) },
    `${c.label}${c.duration_s != null ? ` · ${Number(c.duration_s).toFixed(1)}s` : ''}`)));
  $('.btn.file').classList.toggle('disabled', busy);
  $('#file').disabled = busy;
  const m = $('#video-msg'); m.textContent = S.uploadMsg; m.classList.toggle('bad', !!S.uploadMsg);
  const wrap = $('#video-wrap'), v = $('#video');
  if (r) {
    const src = `/api/runs/${r.run_id}/video`;
    wrap.hidden = false;
    if (v.dataset.rid !== r.run_id) { v.dataset.rid = r.run_id; v.src = src; }
  } else wrap.hidden = true;
  const chips = $('#chips'); chips.replaceChildren();
  for (const f of r?.observations?.fire_sources || [])
    for (const t of f.timestamps_s || [])
      chips.append(h('button', { type: 'button', class: 'chip', onclick: () => { v.currentTime = t; v.pause(); drawOverlay(); } }, `${f.id} · ${Number(t).toFixed(1)}s`));
}

function renderCosmos() {
  const r = S.run, busy = !!S.busy;
  $('#btn-analyse').disabled = busy || r?.state !== 'uploaded';
  const out = $('#cosmos-out'); out.replaceChildren();
  if (!r?.analysis) return;
  const a = r.analysis, o = r.observations;
  out.append(h('div', { class: 'body', style: 'padding:0' },
    h('dl', { class: 'kv' },
      h('dt', {}, 'Model'), h('dd', { class: 'mono' }, r.model_id || h('span', { class: 'unk' }, 'unknown')),
      h('dt', {}, 'Latency'), h('dd', { class: 'mono' }, fmt(a.latency_s, 1, ' s')),
      a.cached ? [h('dt', {}, 'Source'), h('dd', {}, h('span', { class: 'badge f' }, 'cached'))] : null),
    h('div', {}, h('div', { class: 'label', style: 'margin-bottom:6px' }, 'Cosmos response'), h('pre', { class: 'raw', tabindex: '0', 'aria-label': 'Raw Cosmos response' }, a.raw_text ?? '')),
    o ? h('details', {}, h('summary', {}, 'Validated observations (JSON)'), h('pre', { class: 'raw', tabindex: '0' }, JSON.stringify(o, null, 2))) : null,
    o ? firesTable(o) : null));
}
function firesTable(o) {
  const fs = o.fire_sources || [];
  const t = h('table', { class: 'fires' }, h('thead', {}, h('tr', {}, ...['ID', 'Timestamps', 'BBox (norm.)', 'Description'].map(x => h('th', {}, x)))),
    h('tbody', {}, fs.length ? fs.map(f => h('tr', {},
      h('td', {}, h('span', { class: 'fid' }, f.id)),
      h('td', { class: 'mono' }, unk(f.timestamps_s, a => a.map(x => Number(x).toFixed(1) + 's').join(', '))),
      h('td', { class: 'mono' }, unk(f.bbox_normalized, bb)),
      h('td', {}, unk(f.description)))) : h('tr', {}, h('td', { colspan: 4 }, 'No fire sources detected'))));
  return h('div', {},
    h('div', { class: 'label', style: 'margin-bottom:6px' }, 'Fire sources'),
    h('div', { class: 'tablewrap' }, t),
    h('dl', { class: 'kv', style: 'margin-top:12px' },
      h('dt', {}, 'Cause'), h('dd', {}, unk(o.cause)),
      h('dt', {}, 'Scale'), h('dd', {}, unk(o.scale)),
      h('dt', {}, 'Depth'), h('dd', { class: 'mono' }, unk(o.depth_m, d => `${d} m`)),
      h('dt', {}, 'Unknowns'), h('dd', { class: 'mono' }, unk(o.unknowns, u => u.join(', ')))));
}

function renderConfirm() {
  const r = S.run, busy = !!S.busy, out = $('#confirm-out'); out.replaceChildren();
  const st = r?.state;
  const fs = r?.observations?.fire_sources || [];
  if (!r?.analysis) { out.append(h('span', { class: 'unk' }, 'Awaiting analysis')); return; }
  const gated = st === 'needs_review' || st === 'blocked' || st === 'failed';
  if (gated) {
    const reason = r.error?.message || (st === 'needs_review' ? 'Observations need review before a target can be confirmed.' : 'Run is blocked.');
    out.append(h('div', { class: 'warnbox', role: 'status' }, `${st.replace('_', ' ')}: ${reason}`));
  }
  if (!fs.length) { out.append(h('span', { class: 'unk' }, 'No fire sources to confirm')); return; }
  const confirmed = !!r.confirmed_target;
  const canConfirm = !busy && st === 'analysed';
  const locked = !canConfirm;
  const cur = fs.find(f => f.id === S.fireId) || fs[0];
  const zoneKey = confirmed ? r.confirmed_target.zone : S.zone;
  const zone = S.zones[zoneKey];

  out.append(h('div', { role: 'radiogroup', 'aria-label': 'Fire source', class: 'body', style: 'padding:0' },
    ...fs.map(f => h('label', { class: 'opt' },
      h('input', { type: 'radio', name: 'fire', value: f.id, checked: f.id === cur.id, disabled: locked, onchange: () => { S.fireId = f.id; S.zone = f.suggested_zone || S.zone; renderConfirm(); } }),
      h('span', {}, h('span', { class: 'fid' }, f.id), ' ', f.description || h('span', { class: 'unk' }, 'unknown'))))));

  const sel = h('select', { id: 'zone', disabled: locked, 'aria-label': 'Zone', onchange: e => { S.zone = e.target.value; renderConfirm(); } },
    ...Object.entries(S.zones).map(([k, z]) => h('option', { value: k, selected: k === zoneKey }, `${z.label || k}${z.reachable === false ? ' (unreachable)' : ''}${k === cur.suggested_zone ? ' (suggested)' : ''}`)));
  out.append(h('div', { class: 'row' }, h('label', { for: 'zone', class: 'label' }, 'Zone'), sel,
    zone && zone.reachable === false ? h('span', { class: 'badge f' }, 'unreachable') : null,
    h('button', { type: 'button', class: 'btn primary', id: 'btn-confirm', disabled: locked || !S.zone, onclick: doConfirm }, 'Confirm target')));

  const ct = r.confirmed_target;
  out.append(h('div', { class: 'twocol' },
    h('div', { class: 'val img' }, h('span', { class: 'label' }, 'Image region · observed'),
      h('span', { class: 'mono' }, unk(ct ? ct.image_bbox_normalized : cur.bbox_normalized, bb)),
      h('span', { class: 'small', style: 'color:var(--mute)' }, 'normalized [x0, y0, x1, y1]')),
    h('div', { class: 'val metric' }, h('span', { class: 'label' }, 'Template position · assumed'),
      h('span', { class: 'mono' }, unk(ct ? ct.template_position_m : zone?.anchor, vec)),
      h('span', { class: 'small', style: 'color:var(--mute)' }, ct?.position_provenance || 'template-assumed (wh_aisle_v1 zone anchor)'))));
  if (confirmed) out.append(h('dl', { class: 'kv' }, h('dt', {}, 'Confirmed'), h('dd', { class: 'mono' }, `${ct.fire_id} → ${ct.zone}`)));
}

function renderInstruction() {
  const r = S.run, out = $('#instr-out'); out.replaceChildren();
  const ins = r?.instruction;
  if (!ins) { out.append(h('span', { class: 'unk' }, 'Not generated')); return; }
  const wb = ins.source === 'wandb';
  out.append(h('p', { class: 'instr' }, ins.text),
    h('div', { class: 'row' },
      h('span', { class: 'badge ' + (wb ? 'w' : 'f') }, wb ? `W&B · ${ins.model_id || 'unknown'}` : 'Deterministic fallback'),
      h('span', { class: 'mono small' }, `skill ${r.skill?.name ?? 'unknown'}`),
      h('span', { class: 'mono small' }, `target ${r.skill?.target_id ?? 'unknown'}`),
      ins.latency_s != null ? h('span', { class: 'mono small' }, `${Number(ins.latency_s).toFixed(1)} s`) : null));
}

function renderSim() {
  const r = S.run, busy = !!S.busy, st = r?.state;
  $('#btn-scene').disabled = busy || st !== 'confirmed';
  $('#btn-run').disabled = busy || st !== 'scene_ready';
  $('#btn-reset').disabled = busy || !['scene_ready', 'completed'].includes(st);
  $('#btn-replay').disabled = busy || !S.traj;
  sim.sync();
}

function renderMetrics() {
  const r = S.run, m = r?.metrics, out = $('#metrics-out'); out.replaceChildren();
  if (!m) { out.append(h('span', { class: 'unk' }, 'No run yet')); return; }
  const coll = m.unintended_collision_count ?? m.unintended_collisions?.length ?? 0;
  out.append(
    h('div', { class: 'row' }, h('span', { class: 'result ' + (m.success ? 'ok' : 'bad'), role: 'status' }, m.success ? 'SUCCESS' : 'FAIL'),
      m.rule ? h('span', { class: 'mono small', style: 'color:var(--mute)' }, m.rule) : null),
    h('div', { class: 'mgrid' },
      metric('Angle error · final', fmt(m.angle_error_deg_final, 1, '°')),
      metric('Angle error · min', fmt(m.angle_error_deg_min, 1, '°')),
      metric('Hold time', fmt(m.hold_s, 1, ' s')),
      metric('Duration', fmt(m.duration_s, 1, ' s')),
      metric('Unintended collisions', String(coll))),
    h('div', {}, h('div', { class: 'label', style: 'margin-bottom:6px' }, 'Angle error over time · 5° threshold'),
      h('canvas', { id: 'spark', class: 'spark', role: 'img', 'aria-label': 'Angle error over time' })),
    h('div', { class: 'tl' }, ...Object.entries(r.timings_s || {}).map(([k, v]) => h('div', {}, h('span', {}, k + ' '), h('b', {}, Number(v).toFixed(1) + ' s')))),
    h('div', { class: 'tl' }, ...['weave', 'vast'].map(k => {
      const v = r.telemetry?.[k] ?? 'unknown';
      return h('div', {}, h('span', {}, k + ' '), h('b', { class: v === 'ok' ? 'ok-t' : '' }, v));
    })));
  if (m.unintended_collisions?.length) out.append(h('div', { class: 'mono small' }, 'Collisions: ' + JSON.stringify(m.unintended_collisions)));
  drawSpark();
}
const metric = (l, v) => h('div', { class: 'm' }, h('span', { class: 'label' }, l), h('b', {}, v));

function drawSpark(frame) {
  const c = $('#spark'); if (!c) return;
  const data = S.traj?.angle_error_deg; const dpr = devicePixelRatio || 1;
  const w = c.clientWidth, hgt = c.clientHeight; c.width = w * dpr; c.height = hgt * dpr;
  const g = c.getContext('2d'); g.scale(dpr, dpr);
  const pad = { l: 34, r: 8, t: 8, b: 16 };
  if (!data?.length) { g.fillStyle = '#9aa4ae'; g.font = '12px IBM Plex Mono, monospace'; g.fillText('no trajectory', 10, 20); return; }
  const max = Math.max(10, ...data) * 1.05, W = w - pad.l - pad.r, H = hgt - pad.t - pad.b;
  const X = i => pad.l + (i / (data.length - 1)) * W, Y = v => pad.t + H - (v / max) * H;
  g.strokeStyle = '#2a3036'; g.fillStyle = '#9aa4ae'; g.font = '10px IBM Plex Mono, monospace'; g.lineWidth = 1;
  g.beginPath(); g.moveTo(pad.l, pad.t); g.lineTo(pad.l, pad.t + H); g.lineTo(pad.l + W, pad.t + H); g.stroke();
  g.fillText('0°', 8, pad.t + H); g.fillText(max.toFixed(0) + '°', 4, pad.t + 8);
  g.setLineDash([4, 4]); g.strokeStyle = '#2dd4bf'; g.beginPath(); g.moveTo(pad.l, Y(5)); g.lineTo(pad.l + W, Y(5)); g.stroke(); g.setLineDash([]);
  g.fillStyle = '#2dd4bf'; g.fillText('5°', pad.l + W - 16, Y(5) - 4);
  g.strokeStyle = '#ff6a1a'; g.lineWidth = 1.5; g.beginPath();
  data.forEach((v, i) => i ? g.lineTo(X(i), Y(v)) : g.moveTo(X(i), Y(v))); g.stroke();
  if (frame != null) { g.strokeStyle = '#e7eaed'; g.lineWidth = 1; g.beginPath(); g.moveTo(X(frame), pad.t); g.lineTo(X(frame), pad.t + H); g.stroke(); }
}

// ---------------- video overlay ----------------
function drawOverlay() {
  const v = $('#video'), c = $('#overlay');
  const w = v.clientWidth, hh = v.clientHeight; if (!w || !hh) return;
  const dpr = devicePixelRatio || 1;
  if (c.width !== w * dpr || c.height !== hh * dpr) { c.width = w * dpr; c.height = hh * dpr; c.style.width = w + 'px'; c.style.height = hh + 'px'; }
  const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, hh);
  const fs = S.run?.observations?.fire_sources; if (!fs) return;
  const t = v.currentTime;
  for (const f of fs) {
    if (!f.bbox_normalized) continue;
    const ts = f.timestamps_s;
    if (ts?.length && !ts.some(x => Math.abs(x - t) <= 1.0)) continue;
    const [x0, y0, x1, y1] = f.bbox_normalized;
    g.strokeStyle = '#ff6a1a'; g.lineWidth = 2; g.strokeRect(x0 * w, y0 * hh, (x1 - x0) * w, (y1 - y0) * hh);
    g.fillStyle = '#ff6a1a'; g.fillRect(x0 * w - 1, Math.max(0, y0 * hh - 18), 28, 18);
    g.fillStyle = '#1a0a00'; g.font = '500 11px IBM Plex Mono, monospace'; g.fillText(f.id, x0 * w + 4, Math.max(12, y0 * hh - 5));
  }
}
(function () {
  const v = $('#video');
  for (const ev of ['timeupdate', 'seeked', 'loadedmetadata', 'play', 'pause']) v.addEventListener(ev, drawOverlay);
  (function tick() { if (!v.paused) drawOverlay(); requestAnimationFrame(tick); })();
  addEventListener('resize', () => { drawOverlay(); drawSpark(sim.frame); });
})();

// ---------------- three.js simulation ----------------
const sim = {
  T: null, ready: null, traj: null, meshes: [], frame: 0, playing: false, lastT: 0, acc: 0,
  fires: [], particles: null, pv: null, plife: null, pn: 400, pi: 0, spray: [],
  loadFail: null,
  async init() {
    if (this.ready) return this.ready;
    this.ready = (async () => {
      const THREE = await import('three');
      const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
      this.T = THREE;
      const host = $('#sim');
      const r = this.renderer = new THREE.WebGLRenderer({ antialias: true });
      r.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
      host.append(r.domElement);
      const sc = this.scene = new THREE.Scene(); sc.background = new THREE.Color(0x0a0c0e);
      sc.add(new THREE.HemisphereLight(0xcfd8e3, 0x1a1d20, 1.0));
      const d = new THREE.DirectionalLight(0xffffff, 1.6); d.position.set(-3, -5, 8); sc.add(d);
      const cam = this.cam = new THREE.PerspectiveCamera(45, 1, 0.05, 200);
      cam.up.set(0, 0, 1); cam.position.set(-3.5, -6, 3.5);
      const oc = this.controls = new OrbitControls(cam, r.domElement);
      oc.target.set(3, 0, 1); oc.enableDamping = true; oc.update();
      const grid = new THREE.GridHelper(20, 20, 0x2a3036, 0x1b1f23); grid.rotation.x = Math.PI / 2; grid.position.set(3, 0, 0.002); sc.add(grid);
      // spray particles
      const n = this.pn, pos = new Float32Array(n * 3).fill(1e4);
      this.pv = new Float32Array(n * 3); this.plife = new Float32Array(n);
      const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      this.particles = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0x9fe8ff, size: 0.07, transparent: true, opacity: 0.85, depthWrite: false }));
      this.particles.frustumCulled = false; sc.add(this.particles);
      new ResizeObserver(() => this.resize()).observe(host); this.resize();
      this.loop = this.loop.bind(this); requestAnimationFrame(this.loop);
    })();
    return this.ready;
  },
  resize() {
    if (!this.renderer) return;
    const host = $('#sim'), w = host.clientWidth, hh = host.clientHeight; if (!w || !hh) return;
    this.renderer.setSize(w, hh); this.cam.aspect = w / hh; this.cam.updateProjectionMatrix();
  },
  clear() {
    this.traj = null; this.playing = false; this.frame = 0;
    if (this.scene) { for (const m of this.meshes) { this.scene.remove(m); m.geometry.dispose(); } this.meshes = []; for (const f of this.fires) this.scene.remove(f.group); this.fires = []; }
    const e = $('#sim-empty'); if (e) e.hidden = false;
    this.sync();
  },
  async load(traj, autoplay) {
    try { await this.init(); } catch (e) { $('#sim-empty').textContent = 'three.js failed to load (check network)'; return; }
    this.clear();
    const T = this.T; this.traj = traj; $('#sim-empty').hidden = true;
    for (const g of traj.geoms) {
      let geo; const s = g.size;
      switch (g.type) {
        case 'box': geo = new T.BoxGeometry(2 * s[0], 2 * s[1], 2 * s[2]); break;
        case 'sphere': geo = new T.SphereGeometry(s[0], 24, 16); break;
        case 'capsule': geo = new T.CapsuleGeometry(s[0], 2 * s[1], 6, 16); geo.rotateX(Math.PI / 2); break;
        case 'cylinder': geo = new T.CylinderGeometry(s[0], s[0], 2 * s[1], 24); geo.rotateX(Math.PI / 2); break;
        case 'plane': geo = new T.PlaneGeometry(2 * (s[0] > 0 ? s[0] : 30), 2 * (s[1] > 0 ? s[1] : 30)); break;
        default: geo = new T.BoxGeometry(0.1, 0.1, 0.1);
      }
      const [r, gg, b, a = 1] = g.rgba || [0.6, 0.6, 0.6, 1];
      const fire = g.group === 'fire';
      const mat = new T.MeshStandardMaterial({ color: new T.Color(r, gg, b), transparent: a < 1, opacity: a, roughness: 0.7, metalness: 0.1,
        emissive: fire ? new T.Color(1, 0.35, 0.05) : 0x000000, emissiveIntensity: fire ? 1.2 : 0, side: g.type === 'plane' ? T.DoubleSide : T.FrontSide });
      const mesh = new T.Mesh(geo, mat); mesh.matrixAutoUpdate = true; this.scene.add(mesh); this.meshes.push(mesh);
    }
    for (const f of traj.fx?.fires || []) {
      const grp = new T.Group(); grp.position.set(...f.pos);
      const mk = (rad, ht, col) => { const gm = new T.ConeGeometry(rad, ht, 16); gm.rotateX(Math.PI / 2); gm.translate(0, 0, ht / 2);
        return new T.Mesh(gm, new T.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 1.6, transparent: true, opacity: 0.9 })); };
      const outer = mk(0.32, 0.9, 0xff5a0a), inner = mk(0.17, 0.55, 0xffc23a);
      const light = new T.PointLight(0xff6a1a, 3, 6); light.position.z = 0.5;
      grp.add(outer, inner, light);
      if (f.target) { const ring = new T.Mesh(new T.RingGeometry(0.55, 0.62, 40), new T.MeshBasicMaterial({ color: 0xff6a1a, side: T.DoubleSide })); ring.position.z = 0.01; grp.add(ring); }
      this.scene.add(grp); this.fires.push({ group: grp, outer, inner, light, ph: Math.random() * 10 });
    }
    this.spray = [...(traj.fx?.spray || [])].sort((a, b) => a.frame - b.frame);
    this.plife.fill(0);
    this.setFrame(0);
    if (autoplay) this.play(); else this.sync();
  },
  setFrame(i) {
    if (!this.traj) return;
    const n = this.traj.frames.length; this.frame = Math.max(0, Math.min(n - 1, i));
    const fr = this.traj.frames[this.frame], T = this.T;
    for (let k = 0; k < this.meshes.length; k++) {
      const o = k * 7, m = this.meshes[k];
      m.position.set(fr[o], fr[o + 1], fr[o + 2]);
      m.quaternion.set(fr[o + 4], fr[o + 5], fr[o + 6], fr[o + 3]);
    }
    this.sync();
    drawSpark(this.frame);
  },
  sprayOn() { let on = false; for (const e of this.spray) { if (e.frame <= this.frame) on = e.on; else break; } return on; },
  play() { if (!this.traj) return; if (this.frame >= this.traj.frames.length - 1) this.frame = 0; this.playing = true; this.acc = this.frame; this.lastT = performance.now(); this.sync(); },
  pause() { this.playing = false; this.sync(); },
  replay() { if (!this.traj) return; this.frame = 0; this.play(); },
  sync() {
    const t = this.traj, sc = $('#scrub'), pb = $('#btn-play');
    if (!sc) return;
    const n = t ? t.frames.length : 0;
    sc.disabled = !t; pb.disabled = !t; sc.max = Math.max(0, n - 1);
    if (document.activeElement !== sc || this.playing) sc.value = this.frame;
    pb.textContent = this.playing ? 'Pause' : 'Play';
    const fps = t?.fps || 30;
    $('#sim-time').textContent = `${(this.frame / fps).toFixed(2)} / ${(Math.max(0, n - 1) / fps).toFixed(2)} s`;
  },
  loop(now) {
    requestAnimationFrame(this.loop);
    const dt = Math.min(0.05, (now - (this._p || now)) / 1000); this._p = now;
    if (this.playing && this.traj) {
      this.acc += (now - this.lastT) / 1000 * this.traj.fps; this.lastT = now;
      const last = this.traj.frames.length - 1;
      if (this.acc >= last) { this.setFrame(last); this.playing = false; this.sync(); } else this.setFrame(Math.floor(this.acc));
    }
    const time = now / 1000;
    for (const f of this.fires) {
      const k = 0.85 + 0.15 * Math.sin(time * 17 + f.ph) + 0.1 * Math.sin(time * 31 + f.ph * 2);
      f.outer.scale.set(1 + 0.08 * Math.sin(time * 23 + f.ph), 1 + 0.08 * Math.cos(time * 19), k);
      f.inner.scale.set(1, 1, 0.8 + 0.3 * Math.sin(time * 29 + f.ph));
      f.light.intensity = 2 + 2 * k;
    }
    this.stepParticles(dt);
    this.controls?.update();
    this.renderer?.render(this.scene, this.cam);
  },
  stepParticles(dt) {
    if (!this.particles) return;
    const pos = this.particles.geometry.attributes.position.array, v = this.pv, life = this.plife;
    if (this.playing && this.traj && this.sprayOn()) {
      const nz = this.traj.fx.nozzle?.[this.frame];
      if (nz) for (let e = 0; e < 8; e++) {
        const i = this.pi = (this.pi + 1) % this.pn, sp = 4 + Math.random() * 1.5;
        pos[i * 3] = nz[0]; pos[i * 3 + 1] = nz[1]; pos[i * 3 + 2] = nz[2];
        v[i * 3] = nz[3] * sp + (Math.random() - .5) * .5; v[i * 3 + 1] = nz[4] * sp + (Math.random() - .5) * .5; v[i * 3 + 2] = nz[5] * sp + (Math.random() - .5) * .5;
        life[i] = 0.7 + Math.random() * 0.3;
      }
    }
    for (let i = 0; i < this.pn; i++) {
      if (life[i] <= 0) { pos[i * 3 + 2] = 1e4; continue; }
      life[i] -= dt; v[i * 3 + 2] -= 4 * dt;
      pos[i * 3] += v[i * 3] * dt; pos[i * 3 + 1] += v[i * 3 + 1] * dt; pos[i * 3 + 2] += v[i * 3 + 2] * dt;
      if (pos[i * 3 + 2] < 0) life[i] = 0;
    }
    this.particles.geometry.attributes.position.needsUpdate = true;
  },
};

// ---------------- init ----------------
$('#file').addEventListener('change', e => { const f = e.target.files[0]; e.target.value = ''; if (f) startUpload(f); });
$('#btn-analyse').addEventListener('click', doAnalyse);
$('#btn-scene').addEventListener('click', doScene);
$('#btn-run').addEventListener('click', doRun);
$('#btn-reset').addEventListener('click', doReset);
$('#btn-replay').addEventListener('click', () => sim.replay());
$('#btn-play').addEventListener('click', () => sim.playing ? sim.pause() : sim.play());
$('#scrub').addEventListener('input', e => { sim.playing = false; sim.setFrame(+e.target.value); });

(async function boot() {
  render();
  try { [S.clips, S.zones] = await Promise.all([api('/api/clips'), api('/api/zones')]); }
  catch (e) { S.error = { message: e.message, retryable: true }; S.last = boot; }
  const rid = location.hash.slice(1);
  if (rid) {
    try { const r = await api('/api/runs/' + encodeURIComponent(rid)); setRun(r); if (r.metrics) await loadTraj(false); }
    catch { history.replaceState(null, '', location.pathname); }
  }
  render();
})();
