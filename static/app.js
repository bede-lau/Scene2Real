// Scene2Real workbench: plain ES module, no build step.
import { analysisReady, applyEdit, buildReport, fingerprint, renderIncidentReport, retainReport } from './incident_report.js';
const $ = (s, r = document) => r.querySelector(s);
const MAX_BYTES = 200 * 1024 * 1024;
const STAGES = ['Video', 'Cosmos', 'Confirm target', 'Instruction', 'Simulation', 'Metrics', 'IRS WORKSHEET'];
const PAGES = ['video', 'analysis', 'targets', 'instruction', 'simulation', 'metrics', 'report'];
const PAGE_DESCRIPTIONS = ['Choose up to three views of the same incident.', 'Analyse the footage and review what Cosmos observed.', 'Review sightings and confirm the fires to rehearse.', 'Generate and review the robot instruction and warehouse scene.', 'Run the recorded rehearsal, then explore the articulated G1 scene.', 'Review the measured results of your rehearsal.', 'Review and edit answers before printing.'];
const rootStyle = getComputedStyle(document.documentElement);
const ACCENT = rootStyle.getPropertyValue('--accent').trim() || '#66d9f2';
const ACCENT_2 = rootStyle.getPropertyValue('--accent-2').trim() || '#a99bff';
const ACCENT_INK = rootStyle.getPropertyValue('--accent-ink').trim() || '#091521';

const S = {
  run: null, clips: [], zones: {}, traj: null, page: Math.max(1, PAGES.indexOf(location.hash.slice(1)) + 1),
  restoring: !!new URLSearchParams(location.search).get('run') || location.hash.startsWith('#r_'),
  fireId: null, zone: null,
  busy: null,          // {section:Number}
  error: null,         // {message, retryable}
  last: null,          // async fn to retry
  uploadMsg: '', pending: [], view: 'V1', groups: [], excluded: {}, groupingKey: null,
  report: null,
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
const displayClipName = name => {
  let label = String(name ?? '').replace(/\bdemo(?=([ -])set[ -][12]\b)/gi, match => match[0] === 'D' ? 'Warehouse' : 'warehouse');
  if (/synthetic warehouse fire/i.test(label)) return 'Warehouse fire clip';
  return label
    .replace(/\s*[·,]?\s*synthetic API-generated CCTV\b/gi, '')
    .replace(/\bsynthetic\b|\bOpenAI\b/gi, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s*·\s*$/, '')
    .trim();
};
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
    throw { message: msg || `Request failed (${res.status})`, retryable: body.retryable ?? res.status >= 500, status: res.status };
  }
  return res.json();
}
const post = (p, body) => api(p, body === undefined ? { method: 'POST' } :
  { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

// Long model calls run on the server; every browser request stays short.
async function waitOperation(job) {
  const runId = job.run_id;
  let failures = 0;
  while (['pending', 'running'].includes(job.status)) {
    if (S.busy) { S.busy.startedAt = Date.parse(job.started_at || job.created_at) || Date.now(); renderOperationStatus(); }
    await new Promise(resolve => setTimeout(resolve, 1500));
    try { job = await api(`/api/runs/${runId}/operations/${job.id}`, { cache: 'no-store' }); failures = 0; }
    catch (error) {
      if (++failures >= 5 || error.status === 404) throw { message: 'Connection interrupted. The operation may still be running; retry to reconnect.', retryable: true };
    }
  }
  if (job.status === 'failed') throw { message: job.error?.detail || 'The operation failed.', retryable: job.error?.retryable ?? true };
  return job.result;
}
const runOperation = kind => post(`/api/runs/${id()}/operations`, { operation: kind }).then(waitOperation);

function pageURL(page) {
  const url = new URL(location.href);
  if (S.run?.run_id) url.searchParams.set('run', S.run.run_id);
  else url.searchParams.delete('run');
  url.hash = PAGES[page - 1];
  return url.pathname + url.search + url.hash;
}
let verifiedPrint = null;
let verifiedPrintExpiry = null;
function clearVerifiedPrint() {
  verifiedPrint = null;
  document.body.classList.remove('irs-print-verified');
  if (verifiedPrintExpiry) clearTimeout(verifiedPrintExpiry);
  verifiedPrintExpiry = null;
}
function printVerificationCurrent() {
  return !!(verifiedPrint && Date.now() < verifiedPrint.expires && S.page === 7 && !S.restoring &&
    S.report === verifiedPrint.snapshot && S.run?.run_id === verifiedPrint.runId &&
    fingerprint(S.run) === verifiedPrint.fingerprint);
}
addEventListener('beforeprint', () => {
  if (printVerificationCurrent()) document.body.classList.add('irs-print-verified');
  else clearVerifiedPrint();
});
addEventListener('afterprint', clearVerifiedPrint);

function setPage(page, { push = true, focus = true } = {}) {
  const nextPage = Math.max(1, Math.min(PAGES.length, page));
  if (nextPage !== S.page) clearVerifiedPrint();
  S.page = nextPage;
  if (push) history.pushState(null, '', pageURL(S.page));
  render();
  if (focus) { $('#h' + S.page).setAttribute('tabindex', '-1'); $('#h' + S.page).focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: 'instant' }); }
}
function renderOperationStatus() {
  const status = $('#operation-status'), kind = S.busy?.kind;
  status.hidden = !['analyse', 'scene', 'run'].includes(kind);
  if (status.hidden) return;
  $('#operation-title').textContent = ({ analyse: 'Analysing with Cosmos', scene: 'Generating the instruction and scene', run: 'Running the rehearsal' })[kind];
  const seconds = Math.max(0, Math.floor((Date.now() - (S.busy.startedAt || Date.now())) / 1000));
  $('#operation-detail').textContent = `${seconds}s elapsed · This can take a few minutes. You can refresh this page and reconnect to the same operation.`;
}
function renderPageNavigation() {
  const evidence = $('#video-evidence');
  const videoSlot = $(S.run && S.page === 2 ? '#analysis-video-slot' : S.run && S.page === 3 ? '#confirm-video-slot' : '#video-home');
  if (evidence.parentElement !== videoSlot) videoSlot.append(evidence);
  $('#page-kicker').textContent = `Step ${S.page} of ${PAGES.length}`;
  $('#page-description').textContent = PAGE_DESCRIPTIONS[S.page - 1];
  $('#page-position').textContent = `${S.page} / ${PAGES.length}`;
  $('#page-prev').hidden = S.page === 1;
  $('#page-prev').textContent = '← ' + STAGES[S.page - 2];
  const next = $('#page-next'); next.hidden = S.page === PAGES.length;
  next.textContent = 'Continue to ' + (STAGES[S.page] || 'Video') + ' →';
  const r = S.run;
  const ready = [!!r, !!r?.analysis, !!r?.confirmed_target, !!r?.instruction, !!r?.metrics, analysisReady(r)];
  next.disabled = !!S.busy || !ready[S.page - 1];
  const iframe = $('#g1-rehearsal');
  if (S.page === 5 && !S.restoring) {
    const target = r?.confirmed_targets?.[0] || r?.confirmed_target;
    const scenario = /left/.test(target?.zone) ? 'left' : /right/.test(target?.zone) ? 'right' : 'center';
    const seed = `${r?.run_id || 'preview'}:${scenario}`;
    if (iframe.dataset.seed !== seed) { iframe.dataset.seed = seed; iframe.src = iframe.dataset.src + '?scenario=' + scenario; }
  }
  iframe.contentWindow?.postMessage({ type: 'scene2real-page', active: S.page === 5 }, location.origin);
}

// ---------------- actions ----------------
const SECTION = { video: 1, analyse: 2, confirm: 3, scene: 4, run: 5, reset: 5 };

async function act(kind, fn) {
  if (S.busy || S.restoring) return;
  if (kind === 'analyse' || kind === 'confirm' || kind === 'reset') S.report = retainReport(S.report, S.run, kind);
  const startingPage = S.page;
  S.last = () => act(kind, fn);
  S.busy = { section: SECTION[kind], kind, startedAt: Date.now() };
  S.error = null;
  render();
  try {
    const run = await fn();
    setRun(run);
    if (run.state === 'completed') await loadTraj(kind === 'run');
    const nextPage = { video: 2, analyse: 3, confirm: 4 }[kind];
    if (nextPage && S.page === startingPage && !['failed', 'blocked', 'needs_review'].includes(run.state)) setPage(nextPage);
  } catch (e) {
    S.error = { message: e.message || String(e), retryable: !!e.retryable };
  } finally {
    S.busy = null;
    render();
  }
}
function setRun(run) {
  if (fingerprint(S.run) !== fingerprint(run)) clearVerifiedPrint();
  const prevId = S.run?.run_id;
  if (prevId && run.run_id !== prevId) S.report = null;
  const observationsChanged = run.run_id === prevId &&
    JSON.stringify(S.run?.observations) !== JSON.stringify(run.observations);
  S.run = run;
  if (run.run_id !== prevId) { S.traj = null; S.fireId = null; S.zone = null; S.view = 'V1'; S.groupingKey = null; sim.clear(); }
  else if (observationsChanged) S.zone = null;
  if (run.run_id) history.replaceState(null, '', pageURL(S.page));
  const fs = run.observations?.fire_sources || [];
  if (!fs.find(f => f.id === S.fireId)) {
    S.fireId = run.confirmed_target?.fire_id || fs[0]?.id || null;
    S.zone = null;
  }
  if (!S.zone) S.zone = run.confirmed_target?.zone || fs.find(f => f.id === S.fireId)?.suggested_zone || null;
  if (['scene_ready', 'confirmed', 'analysed', 'uploaded'].includes(run.state)) {
    if (run.state !== 'completed' && !run.metrics) { S.traj = null; sim.clear(); }
  }
}
async function loadTraj(autoplay) {
  S.traj = await api(`/api/runs/${S.run.run_id}/trajectory`);
  await sim.load(S.traj, autoplay);
}

function addFiles(files) {
  S.uploadMsg = '';
  for (const file of files) {
    if (!(file.type === 'video/mp4' || /\.mp4$/i.test(file.name))) { S.uploadMsg = 'Choose MP4 videos only.'; continue; }
    if (file.size > MAX_BYTES) { S.uploadMsg = `${file.name} exceeds the 200 MB limit.`; continue; }
    if (S.pending.length >= 3) { S.uploadMsg = 'Select up to three videos.'; break; }
    S.pending.push({ file, label: file.name });
  }
  render();
}
function loadSelected() {
  if (!S.pending.length || S.pending.length > 3) return;
  S.uploadMsg = '';
  const selected = [...S.pending];
  act('video', async () => {
    let destination = '/api/runs', ticket = null;
    if (selected.reduce((bytes, item) => bytes + (item.file?.size || 0), 0) > 3 * 1024 * 1024) {
      try {
        const grant = await post('/api/upload-ticket', { origin: location.origin });
        const url = new URL(grant.url);
        if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/api/runs' || url.search || url.hash) throw new Error('Invalid upload destination');
        destination = url.href; ticket = grant.token;
      } catch (error) { if (error.status !== 404) throw error; }
    }
    return new Promise((resolve, reject) => {
    const fd = new FormData();
    for (const item of selected.filter(x => x.file)) fd.append('files', item.file);
    const clipIds = selected.filter(x => x.clip_id).map(x => x.clip_id);
    if (clipIds.length) fd.append('clip_ids', JSON.stringify(clipIds));
    const x = new XMLHttpRequest();
    const wrap = $('#upload-wrap'), prog = $('#upload-prog'), lab = $('#upload-label');
    wrap.hidden = false; prog.value = 0; lab.textContent = 'Loading videos 0%';
    x.upload.onprogress = e => { if (e.lengthComputable) { const p = Math.round(e.loaded / e.total * 100); prog.value = p; lab.textContent = `Loading videos ${p}%`; } };
    x.onload = () => {
      wrap.hidden = true;
      let b = {}; try { b = JSON.parse(x.responseText); } catch { /* non-json */ }
      if (x.status >= 200 && x.status < 300) { S.pending = []; S.uploadMsg = ''; resolve(b); }
      else reject({ message: (typeof b.detail === 'string' ? b.detail : null) || `Load failed (${x.status})`, retryable: b.retryable ?? x.status >= 500 });
    };
    x.onerror = () => { wrap.hidden = true; reject({ message: 'Network error loading videos.', retryable: true }); };
    x.open('POST', destination);
    if (ticket) x.setRequestHeader('x-scene2real-upload-ticket', ticket);
    x.send(fd);
    });
  });
}
const id = () => S.run.run_id;
const doAnalyse = () => act('analyse', () => runOperation('analyse'));
const doConfirm = () => {
  const targets = S.groups.filter(g => g.members.length).map(g => ({ members: g.members, zone: g.zone, slot: Number(g.slot) }));
  const excluded = Object.entries(S.excluded).map(([id, reason]) => ({ id, reason: reason.trim() }));
  if (!targets.length || excluded.some(x => !x.reason)) { S.error = { message: 'Confirm at least one fire and give a reason for each excluded observation.', retryable: false }; render(); return; }
  act('confirm', () => post(`/api/runs/${id()}/confirm`, { targets, excluded }));
};
const doScene = () => act('scene', () => runOperation('scene'));
const doRun = () => act('run', () => runOperation('run'));
const doReset = () => act('reset', async () => { const r = await post(`/api/runs/${id()}/reset`); S.traj = null; sim.clear(); return r; });
const STAGE_RETRY = { analyse: doAnalyse, confirm: doConfirm, scene: doScene, plan: doScene, run: doRun, export: doRun };

// ---------------- derived state ----------------
function progress() {
  const r = S.run, st = r?.state;
  const reportCurrent = !!(S.report && r && fingerprint(r) === S.report.fingerprint);
  const done = [!!r, !!r?.analysis, !!r?.confirmed_target, !!r?.instruction, !!r?.metrics, !!r?.metrics, reportCurrent];
  let active = done.findIndex(d => !d); if (active < 0) active = PAGES.length - 1;
  const warn = st === 'needs_review' || st === 'blocked' || st === 'failed';
  return { done, active, warn };
}

// ---------------- render ----------------
const ICONS = {
  check: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4.5 10.5 3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  warn: '<svg class="ico" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.5 18 17H2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M10 8v4.2M10 14.4v.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  down: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v11m0 0-4-4m4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  ok: '<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="m11 18.5 5 5 9-10" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  bad: '<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="m12.5 12.5 11 11m0-11-11 11" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
  lock: '<svg viewBox="0 0 20 20" aria-hidden="true"><rect x="4.5" y="9" width="11" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M7 9V6.5a3 3 0 0 1 6 0V9" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
};
const icon = (name, cls = '') => { const s = document.createElement('span'); s.className = 'icw ' + cls; s.style.display = 'inline-flex'; s.innerHTML = ICONS[name]; return s; };
const STATE_LABEL = st => st.replace(/_/g, ' ');

function render() {
  S.report = retainReport(S.report, S.run, null);
  const r = S.run, st = r?.state || 'idle', busy = !!S.busy || S.restoring;
  const { done, active, warn } = progress();

  $('#run-id').textContent = r ? r.run_id : 'no run';
  const sp = $('#run-state'); sp.textContent = S.restoring ? 'loading run' : busy ? 'working' : STATE_LABEL(st);
  sp.className = 'pill ' + (busy ? 'busy' : st === 'completed' ? (r?.metrics?.success === true ? 'ok' : r?.metrics?.success === false ? 'bad' : '') : (st === 'failed') ? 'bad' : (['needs_review', 'blocked'].includes(st) ? 'warn' : ''));
  sp.setAttribute('aria-live', 'polite');
  sp.dataset.state = st;

  // rail + section chrome
  const rail = $('#rail'); rail.replaceChildren();
  STAGES.forEach((name, i) => {
    const isActive = i + 1 === S.page;
    const isWorking = S.busy?.section === i + 1;
    const sub = isWorking ? 'working' : done[i] ? 'done' : i === active ? (warn ? STATE_LABEL(st) : 'next') : 'pending';
    const cls = [done[i] ? 'done' : '', isActive ? 'active' : '', i === active && warn ? 'warn' : ''].join(' ').trim();
    const n = h('span', { class: 'n' }); if (done[i]) n.innerHTML = ICONS.check; else n.textContent = String(i + 1);
    rail.append(h('li', { class: cls }, h('a', { href: pageURL(i + 1), 'aria-label': `${i + 1} ${name}, ${sub}`, 'aria-current': isActive ? 'page' : null, onclick: e => { if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); setPage(i + 1); } },
      n, h('span', { class: 't' }, name, h('small', {}, sub)))));
    const sec = $('#s' + (i + 1));
    sec.hidden = !isActive;
    sec.className = 'stage ' + cls;
    sec.querySelector('.status').textContent = done[i] ? 'done' : isActive ? (warn ? STATE_LABEL(st) : '') : '';
    const pr = sec.querySelector('.progress'); pr.hidden = S.busy?.section !== i + 1;
    sec.setAttribute('aria-busy', S.busy?.section === i + 1 ? 'true' : 'false');
  });

  // error
  // Confirm can show the inline warning only after analysis is available.
  const reviewErr = !S.error && !!r?.analysis && ['needs_review', 'blocked'].includes(st);
  const err = S.error || (r?.error && !reviewErr ? { message: `${r.error.stage}: ${r.error.message}`, retryable: r.error.retryable, stage: r.error.stage } : null);
  $('#err').hidden = !err;
  if (err) {
    $('#err-msg').textContent = err.message;
    const retry = S.error ? S.last : (STAGE_RETRY[r.error.stage] || null);
    const rb = $('#err-retry'); rb.hidden = !(err.retryable && retry); rb.disabled = busy; rb.onclick = () => retry && retry();
  }

  renderVideo(); renderCosmos(); renderConfirm(); renderInstruction(); renderSim(); renderMetrics(); renderReport();
  renderPageNavigation(); renderOperationStatus();
  drawOverlay();
}

function renderVideo() {
  const r = S.run, busy = !!S.busy || S.restoring;
  const box = $('#clips');
  box.replaceChildren(...S.clips.map(c => {
    const selected = S.pending.some(x => x.clip_id === c.clip_id);
    return h('label', { class: 'opt' }, h('input', { type: 'checkbox', checked: selected, disabled: busy, onchange: e => {
      S.uploadMsg = '';
      if (!e.target.checked) S.pending = S.pending.filter(x => x.clip_id !== c.clip_id);
      else if (S.pending.length < 3) S.pending.push({ clip_id: c.clip_id, label: c.label });
      else S.uploadMsg = 'Select up to three videos.';
      render();
    } }), h('span', { class: 'od' }, h('span', {}, displayClipName(c.label)), c.duration_s != null ? h('span', { class: 'small mono' }, `${Number(c.duration_s).toFixed(1)} s`) : null));
  }));
  if (!S.clips.length) box.append(h('span', { class: 'empty' }, 'No warehouse clips available'));
  const pending = $('#pending'); pending.replaceChildren(...S.pending.map((x, i) => h('div', { class: 'row selection' }, h('span', {}, `${i + 1}. ${displayClipName(x.label)}`), h('button', { type: 'button', class: 'btn small ghost', disabled: busy, 'aria-label': `Remove ${displayClipName(x.label)}`, onclick: () => { S.pending.splice(i, 1); render(); } }, 'Remove'))));
  $('#btn-load').disabled = busy || !S.pending.length;
  $('.btn.file').classList.toggle('disabled', busy); $('#file').disabled = busy;
  const m = $('#video-msg'); m.textContent = S.uploadMsg; m.classList.toggle('bad', !!S.uploadMsg);
  const wrap = $('#video-wrap'), v = $('#video'), refs = r?.video_refs?.length ? r.video_refs : r ? [{ view_id: 'V1', ...r.clip_ref }] : [];
  if (r) {
    if (!refs.some(x => x.view_id === S.view)) S.view = refs[0].view_id;
    const select = $('#view-select'); select.replaceChildren(...refs.map((x, i) => h('option', { value: x.view_id, selected: x.view_id === S.view }, `${x.view_id} · ${displayClipName(x.filename || x.clip_ref?.filename || `video ${i + 1}`)}`)));
    $('#view-field').hidden = refs.length < 2;
    const src = r.video_refs?.length ? `/api/runs/${r.run_id}/video/${encodeURIComponent(S.view)}` : `/api/runs/${r.run_id}/video`;
    wrap.hidden = false; $('#video-empty').hidden = true;
    if (v.dataset.src !== src) { v.dataset.src = src; v.src = src; }
  } else { wrap.hidden = true; $('#video-empty').hidden = false; $('#view-field').hidden = true; }
  const chips = $('#chips'); chips.replaceChildren();
  for (const f of activeFires()) for (const t of f.timestamps_s || [])
    chips.append(h('button', { type: 'button', class: 'chip', 'aria-label': `Seek to ${f.id} at ${Number(t).toFixed(1)} seconds`, onclick: () => { v.currentTime = t; v.pause(); v.scrollIntoView({ block: 'center' }); drawOverlay(); } }, h('b', {}, f.id), `${Number(t).toFixed(1)}s`));
  $('#chips-field').hidden = !chips.children.length;
}
function activeFires() {
  const aggregate = S.run?.observations?.fire_sources;
  if (aggregate) return aggregate.filter(f => !f.view_id || f.view_id === S.view);
  const views = S.run?.analysis?.views || [];
  const view = views.find(v => v.view_id === S.view);
  return (view?.observations?.fire_sources || []).map(f => ({ ...f, id: views.length > 1 ? `${S.view}:${f.id}` : f.id, view_id: S.view, source_id: f.id }));
}

function renderCosmos() {
  const r = S.run, busy = !!S.busy;
  $('#btn-analyse').disabled = busy || !['uploaded', 'analysed', 'needs_review'].includes(r?.state);
  $('#btn-analyse').textContent = r?.analysis ? 'Reanalyse' : 'Analyse';
  const facts = $('#cosmos-facts'); facts.replaceChildren();
  const out = $('#cosmos-out'); out.replaceChildren();
  if (!r?.analysis) { out.append(h('p', { class: 'empty' }, r ? 'Ready to analyse the loaded footage.' : 'Load a video on the Video page to begin analysis.')); return; }
  const a = r.analysis, o = r.observations;
  const view = a.views?.find(v => v.view_id === S.view);
  const selectedAnalysis = view ? view.analysis : a;
  const provenance = selectedAnalysis?.cached === true ? 'cached' : selectedAnalysis?.cached === false ? 'live' : 'unknown';
  const viewAnalyses = a.views?.map(v => v.analysis) || [];
  const incidentCache = viewAnalyses.length > 1 ? (viewAnalyses.some(v => v?.cached === true) ? 'some cached' : viewAnalyses.every(v => v?.cached === false) ? 'all live' : 'unknown') : null;
  // Older multi-view records timed only view processing, excluding association.
  const totalLabel = viewAnalyses.length > 1 && !Number.isFinite(r.timings_s?.analyse_views) ? 'View processing' : 'Analysis total';
  const totalTime = r.timings_s?.analyse;
  const reviewTime = selectedAnalysis?.spatial_review?.latency_s;
  facts.append(
    h('div', { class: 'fact' }, h('span', { class: 'label' }, 'Model'), h('b', {}, r.model_id || h('span', { class: 'unk' }, 'unknown'))),
    h('div', { class: 'fact' }, h('span', { class: 'label' }, view ? `Cosmos · ${S.view}` : 'Cosmos'), h('b', {}, fmt(selectedAnalysis?.latency_s, 1, ' s'))),
    ...(Number.isFinite(reviewTime) ? [h('div', { class: 'fact' }, h('span', { class: 'label' }, view ? `Astra review · ${S.view}` : 'Astra review'), h('b', {}, fmt(reviewTime, 1, ' s')))] : []),
    ...(Number.isFinite(totalTime) ? [h('div', { class: 'fact' }, h('span', { class: 'label' }, totalLabel), h('b', {}, fmt(totalTime, 1, ' s')))] : []),
    h('div', { class: 'fact' }, h('span', { class: 'label' }, view ? `${S.view} source` : 'Source'), h('b', {}, h('span', { class: 'badge f' }, provenance))),
    ...(incidentCache ? [h('div', { class: 'fact' }, h('span', { class: 'label' }, 'Incident source'), h('b', {}, incidentCache))] : []));
  const activeObs = view ? view.observations : o;
  out.append(h('div', { class: 'split wide' },
    h('div', { class: 'col-main' }, activeObs ? firesTable({ ...activeObs, fire_sources: activeFires() }) : h('span', { class: 'empty' }, 'No validated observations'),
      activeObs?.scene_description ? h('div', { class: 'panel' }, h('span', { class: 'label' }, `${S.view} scene`), activeObs.scene_description) : null),
    h('div', { class: 'col-side' },
      h('div', { class: 'field' }, h('span', { class: 'label', id: 'raw-label' }, view ? `${S.view} Cosmos response` : 'Cosmos response'),
        h('pre', { class: 'raw', tabindex: '0', 'aria-labelledby': 'raw-label' }, (view ? (view.analysis?.raw_text ?? (typeof view.error === 'string' ? view.error : view.error?.message) ?? '') : (a.raw_text ?? '')))),
      view?.analysis?.spatial_review ? h('details', {}, h('summary', {}, 'Astra spatial review and original Cosmos observations'), h('pre', { class: 'raw', tabindex: '0' }, JSON.stringify(view.analysis.spatial_review, null, 2))) : null,
      view?.error ? h('div', { class: 'warnbox', role: 'status' }, typeof view.error === 'string' ? view.error : JSON.stringify(view.error)) : null,
      a.views?.length > 1 ? h('details', {}, h('summary', {}, 'Incident aggregate response'), h('pre', { class: 'raw', tabindex: '0' }, a.raw_text ?? '')) : null,
      activeObs ? h('details', {}, h('summary', {}, 'Validated observations (JSON)'), h('pre', { class: 'raw', tabindex: '0', 'aria-label': 'Validated observations JSON' }, JSON.stringify(activeObs, null, 2))) : null)));
}
function firesTable(o) {
  const fs = o.fire_sources || [];
  const t = h('table', { class: 'fires' }, h('thead', {}, h('tr', {}, ...['ID', 'Seen at', 'BBox (norm.)', 'Description'].map(x => h('th', { scope: 'col' }, x)))),
    h('tbody', {}, fs.length ? fs.map(f => h('tr', {},
      h('td', { 'data-label': 'ID' }, h('span', { class: 'fid' }, f.id)),
      h('td', { class: 'mono', 'data-label': 'Seen at' }, unk(f.timestamps_s, a => a.map(x => Number(x).toFixed(1) + 's').join(' '))),
      h('td', { class: 'mono', 'data-label': 'BBox' }, unk(f.bbox_normalized, bb), h('div', { class: 'small' }, f.bbox_provenance?.source === 'openai' ? `Astra reviewed · ${f.bbox_provenance.model_id || 'unknown model'}${f.bbox_at_s != null ? ` · ${f.bbox_at_s}s` : ''}` : 'Cosmos observation')),
      h('td', { 'data-label': 'Description' }, unk(f.description)))) : h('tr', {}, h('td', { colspan: 4, class: 'empty' }, 'No fire sources detected'))));
  return h('div', { class: 'col-main' },
    h('div', { class: 'field' }, h('span', { class: 'label' }, 'Fire sources'), h('div', { class: 'tablewrap' }, t)));
}

function supportedAssociations(r) {
  const a = r?.analysis?.association;
  return a?.room_status === 'verified' && a?.status === 'proposed' && Array.isArray(a.candidates) ? a.candidates : [];
}

function initGroups(r, fs) {
  const key = JSON.stringify([r.run_id, fs, r.analysis?.association]);
  if (S.groupingKey === key) return;
  S.groupingKey = key; S.groups = []; S.excluded = {};
  const remaining = new Set(fs.map(f => f.id));
  const proposals = supportedAssociations(r);
  const makeGroup = members => {
    const first = fs.find(f => f.id === members[0]);
    const zone = first?.suggested_zone && S.zones[first.suggested_zone]?.slots?.length ? first.suggested_zone : Object.keys(S.zones).find(k => S.zones[k].slots?.length);
    const used = new Set(S.groups.map(g => `${g.zone}:${g.slot}`));
    const free = Object.entries(S.zones).flatMap(([key, value]) => (value.slots || []).map((_, slot) => ({ zone: key, slot }))).find(x => !used.has(`${x.zone}:${x.slot}`));
    const slot = (S.zones[zone]?.slots || []).findIndex((_, n) => !used.has(`${zone}:${n}`));
    S.groups.push({ members, zone: slot >= 0 ? zone : (free?.zone || zone || ''), slot: slot >= 0 ? slot : (free?.slot || 0) });
    members.forEach(x => remaining.delete(x));
  };
  for (const proposal of proposals) {
    const members = proposal.members || [];
    const views = members.map(id => fs.find(f => f.id === id)?.view_id || 'V1');
    if (members.length > 1 && members.every(id => remaining.has(id)) && new Set(views).size === members.length) makeGroup([...members]);
  }
  for (const id of remaining) makeGroup([id]);
}
function renderConfirm() {
  const r = S.run, busy = !!S.busy, out = $('#confirm-out'); out.replaceChildren();
  const st = r?.state, fs = r?.observations?.fire_sources || [];
  if (!r?.analysis) { out.append(h('span', { class: 'empty' }, 'Awaiting analysis')); return; }
  if (['needs_review', 'blocked', 'failed'].includes(st)) {
    const reason = r.error?.message || 'Observations need review before confirmation.';
    const retry = r.error?.retryable ? STAGE_RETRY[r.error.stage] : null;
    out.append(h('div', { class: 'warnbox', role: 'status' }, icon('warn'), h('div', { class: 'wb-msg' }, h('b', {}, STATE_LABEL(st)), ' — ', reason), retry ? h('button', { type: 'button', class: 'btn small', disabled: busy, onclick: retry }, 'Retry') : null));
  }
  if (!fs.length) { out.append(h('span', { class: 'empty' }, 'No fire sources to confirm. Load another clip.')); return; }
  if (r.confirmed_target) {
    const targets = r.confirmed_targets?.length ? r.confirmed_targets : [r.confirmed_target];
    out.append(...targets.map(t => h('div', { class: 'panel' }, h('div', { class: 'confirmed' }, icon('check'), `${t.fire_id} → ${t.zone}${t.slot != null ? ` · slot ${t.slot + 1}` : ''}`), h('div', {}, `Evidence: ${(t.members || [t.fire_id]).join(', ')}`), h('div', {}, 'Template position · assumed: ', unk(t.template_position_m, vec)), h('span', { class: 'small mono' }, t.position_provenance || 'template-assumed'), t.association_provenance ? h('div', {}, 'Association: ', typeof t.association_provenance === 'string' ? t.association_provenance : JSON.stringify(t.association_provenance)) : null)));
    return;
  }
  initGroups(r, fs);
  const locked = busy || st !== 'analysed';
  const association = r.analysis.association;
  const associationError = r.analysis.association_error || association?.error;
  if (association && (association.room_status !== 'verified' || association.status === 'manual_review')) {
    const reasons = [...(association.uncertainties || []), ...(association.unmatched || []).map(x => `${x.id}: ${x.reason}`)];
    out.append(h('div', { class: 'warnbox', role: 'status' }, icon('warn'), h('div', { class: 'wb-msg' }, h('b', {}, 'Cross-camera identity unverified.'), ' Review and group sightings manually.',
      reasons.length ? h('ul', {}, ...reasons.map(x => h('li', {}, x))) : null,
      associationError ? h('details', {}, h('summary', {}, 'Matching error'), h('pre', { class: 'raw' }, typeof associationError === 'string' ? associationError : JSON.stringify(associationError, null, 2))) : null)));
  } else if (!association && associationError) {
    out.append(h('div', { class: 'warnbox', role: 'status' }, icon('warn'), h('div', { class: 'wb-msg' }, h('b', {}, 'Cross-camera identity unverified.'), ' Review and group sightings manually.', h('details', {}, h('summary', {}, 'Matching error'), h('pre', { class: 'raw' }, String(associationError))))));
  }
  for (const warning of r.observations?.evidence_warnings || []) {
    out.append(h('div', { class: 'warnbox', role: 'status' }, icon('warn'), h('div', { class: 'wb-msg' }, warning.message || 'Review possible duplicate sightings.', warning.members?.length ? ` (${warning.members.join(', ')})` : '')));
  }
  out.append(h('p', {}, 'Review and group sightings of the same physical fire before confirming. Groups are unconfirmed until submitted.'));
  const proposals = supportedAssociations(r);
  if (proposals.length) out.append(h('details', {}, h('summary', {}, 'Astra grouping proposals · unconfirmed'), h('ul', {}, ...proposals.map(p => h('li', {}, `${(p.members || []).join(' + ')}: ${p.reason || ''}`)))));
  if (association) out.append(h('details', {}, h('summary', {}, 'Astra cross-camera matching response'), h('pre', { class: 'raw', tabindex: '0' }, JSON.stringify(association, null, 2))));
  const list = h('div', { class: 'stack' });
  fs.forEach(f => {
    const groupIndex = S.groups.findIndex(g => g.members.includes(f.id));
    const value = groupIndex < 0 ? 'exclude' : String(groupIndex);
    const sel = h('select', { 'aria-label': `Physical fire group for ${f.id}`, disabled: locked, onchange: e => {
      S.groups.forEach(g => { g.members = g.members.filter(x => x !== f.id); });
      if (e.target.value === 'exclude') S.excluded[f.id] = '';
      else { delete S.excluded[f.id]; S.groups[Number(e.target.value)].members.push(f.id); }
      renderConfirm();
    } }, ...S.groups.map((g, i) => h('option', { value: String(i), selected: value === String(i) }, `Group ${i + 1}`)), h('option', { value: 'exclude', selected: value === 'exclude' }, 'Exclude'));
    const row = h('div', { class: 'panel' }, h('div', { class: 'row' }, h('span', { class: 'fid' }, f.id), h('span', {}, f.description || 'No description')), h('label', { class: 'field' }, h('span', { class: 'label' }, 'Physical fire group'), sel));
    if (value === 'exclude') row.append(h('label', { class: 'field' }, h('span', { class: 'label' }, 'Reason for exclusion'), h('input', { type: 'text', 'aria-label': `Reason for excluding ${f.id}`, value: S.excluded[f.id] || '', disabled: locked, oninput: e => { S.excluded[f.id] = e.target.value; } })));
    list.append(row);
  });
  out.append(list);
  out.append(h('button', { type: 'button', class: 'btn ghost small', disabled: locked || S.groups.length >= fs.length, onclick: () => { const zone = Object.keys(S.zones).find(k => S.zones[k].slots?.length) || ''; S.groups.push({ members: [], zone, slot: 0 }); renderConfirm(); } }, 'Add fire group'));
  S.groups.forEach((g, i) => {
    if (!g.members.length) return;
    const sameView = g.members.map(id => fs.find(f => f.id === id)?.view_id || 'V1');
    const valid = new Set(sameView).size === sameView.length;
    const zone = S.zones[g.zone];
    const zsel = h('select', { 'aria-label': `Zone for fire ${i + 1}`, disabled: locked, onchange: e => { g.zone = e.target.value; g.slot = 0; renderConfirm(); } }, ...Object.entries(S.zones).filter(([, z]) => z.slots?.length).map(([k, z]) => h('option', { value: k, selected: k === g.zone }, z.label || k)));
    const slots = zone?.slots || [];
    const slotSel = h('select', { 'aria-label': `Slot for fire ${i + 1}`, disabled: locked, onchange: e => { g.slot = Number(e.target.value); renderConfirm(); } }, ...slots.map((pos, n) => h('option', { value: n, selected: n === Number(g.slot) }, `Slot ${n + 1} · ${vec(pos)}`)));
    out.append(h('div', { class: 'panel' }, h('b', {}, `Unconfirmed group ${i + 1} · ${g.members.join(', ')}`), !valid ? h('span', { class: 'msg bad' }, 'Only one observation per video can be grouped together.') : null, h('div', { class: 'row' }, h('label', { class: 'field grow' }, h('span', { class: 'label' }, 'Zone'), zsel), h('label', { class: 'field grow' }, h('span', { class: 'label' }, 'Assumed template position'), slotSel))));
  });
  const groups = S.groups.filter(g => g.members.length);
  const invalid = groups.some(g => !g.zone || new Set(g.members.map(id => fs.find(f => f.id === id)?.view_id || 'V1')).size !== g.members.length) || new Set(groups.map(g => `${g.zone}:${g.slot}`)).size !== groups.length;
  if (invalid) out.append(h('span', { class: 'msg bad' }, 'Each fire needs a unique zone and slot, with at most one observation per video.'));
  out.append(h('button', { type: 'button', class: 'btn primary', id: 'btn-confirm', disabled: locked || !groups.length || invalid, onclick: doConfirm }, 'Confirm fires'));
}

function renderInstruction() {
  const r = S.run, out = $('#instr-out'); out.replaceChildren();
  const ins = r?.instruction;
  if (!ins) { out.append(h('p', { class: 'empty' }, r?.confirmed_target ? 'Generate the instruction to prepare the robot rehearsal.' : 'Confirm the fire targets before generating an instruction.')); return; }
  const wb = ins.source === 'wandb';
  const provenance = wb ? `W&B · ${ins.model_id || 'unknown'}` : null;
  out.append(h('div', { class: 'order' },
    h('p', { class: 'instr' }, ins.text),
    h('div', { class: 'metaline' },
      provenance ? h('span', { class: 'badge ' + (wb ? 'w' : 'f') }, provenance) : null,
      ins.source === 'fallback' && ins.fallback_reason ? h('span', {}, ins.fallback_reason) : null,
      ins.robot_reference ? h('span', {}, 'robot ', h('b', {}, typeof ins.robot_reference === 'string' ? ins.robot_reference : JSON.stringify(ins.robot_reference))) : null,
      h('span', {}, 'skill ', h('b', {}, r.skill?.name ?? 'unknown')),
      h('span', {}, 'target ', h('b', {}, r.skill?.target_ids?.join(', ') ?? r.skill?.target_id ?? 'unknown')),
      ins.latency_s != null ? h('span', {}, 'latency ', h('b', {}, `${Number(ins.latency_s).toFixed(1)} s`)) : null)));
}

function renderSim() {
  const r = S.run, busy = !!S.busy, st = r?.state;
  $('#btn-scene').disabled = busy || st !== 'confirmed';
  $('#btn-run').disabled = busy || st !== 'scene_ready';
  const canReset = ['scene_ready', 'completed'].includes(st) || (st === 'failed' && ['run', 'export'].includes(r?.error?.stage) && !!r?.skill);
  $('#btn-reset').disabled = busy || !canReset;
  $('#btn-replay').disabled = busy || !S.traj;
  const se = $('#sim-empty');
  if (se && !S.traj) se.textContent = S.busy?.kind === 'scene' ? (r?.response_mode === 'mobile' ? 'Generating scene with Astra…' : 'Generating scene…') : S.busy?.kind === 'run' ? 'Simulating…' : st === 'scene_ready' ? 'Scene ready · press Run' : 'No trajectory';
  sim.sync();
}

function renderMetrics() {
  const r = S.run, m = r?.metrics, out = $('#metrics-out'); out.replaceChildren();
  if (!m) { out.append(h('span', { class: 'empty' }, 'No run yet')); return; }
  const coll = m.unintended_collision_count ?? m.unintended_collisions?.length ?? 0;
  const fin = m.angle_error_deg_final;
  const verdict = m.success === true ? 'PASS' : m.success === false ? 'FAIL' : 'UNKNOWN';
  out.append(
    h('div', { class: 'verdict ' + (m.success === true ? 'ok' : 'bad'), role: 'status' },
      h('span', { class: 'word' }, icon(m.success === true ? 'ok' : 'bad'), verdict),
      null),
    h('div', { class: 'mstrip' },
      ...(m.target_count != null ? [metric('Fires suppressed', `${m.suppressed_count ?? 'unknown'} / ${m.target_count}`)] : []),
      ...(m.distance_travelled_m != null ? [metric('Distance travelled', fmt(m.distance_travelled_m, 1, ' m'))] : []),
      metric('Angle error · final', fmt(fin, 1, '°')),
      metric('Angle error · min', fmt(m.angle_error_deg_min, 1, '°')),
      metric('Hold time', fmt(m.hold_s, 1, ' s')),
      metric('Duration', fmt(m.duration_s, 1, ' s')),
      metric('Collisions', String(coll))),
    h('div', { class: 'chartwrap' },
      h('div', { class: 'legend' }, h('span', { class: 'label' }, 'Angle error over time')),
      h('canvas', { id: 'spark', class: 'spark', role: 'img', 'aria-label': `Angle error over time; final ${fin != null ? Number(fin).toFixed(1) + '°' : 'unknown'}` })),
    h('div', { class: 'readouts' },
      h('div', { class: 'field' }, h('span', { class: 'label' }, 'Stage timings'),
        h('div', { class: 'tl' }, ...Object.entries(r.timings_s || {}).map(([k, v]) => h('div', {}, h('span', {}, k), h('b', {}, Number(v).toFixed(1) + ' s')))))));
  if (m.targets?.length) {
    const headers = ['Fire', 'Suppressed', 'Valid exposure', 'Suppressed at'];
    const qa = h('table', { class: 'fires' },
      h('thead', {}, h('tr', {}, ...headers.map(x => h('th', { scope: 'col' }, x)))),
      h('tbody', {}, ...m.targets.map(t => h('tr', {},
        h('td', { 'data-label': 'Fire' }, t.target_id),
        h('td', { 'data-label': 'Suppressed' }, t.suppressed ? 'Yes' : 'No'),
        h('td', { 'data-label': 'Valid exposure' }, fmt(t.best_valid_exposure_s, 1, ' s')),
        h('td', { 'data-label': 'Suppressed at' }, fmt(t.suppressed_at_s, 1, ' s'))))));
    out.append(h('div', { class: 'field' }, h('span', { class: 'label' }, 'Per-fire QA'), h('div', { class: 'tablewrap' }, qa)));
  }
  if (m.unintended_collisions?.length) out.append(h('pre', { class: 'raw' }, 'Collisions: ' + JSON.stringify(m.unintended_collisions)));
  drawSpark();
}
const metric = (l, v, cls = '') => h('div', { class: 'm' }, h('span', { class: 'label' }, l), h('b', { class: cls }, v));

let renderedReport = null;
function renderReport() {
  S.report = retainReport(S.report, S.run, null);
  const ready = analysisReady(S.run);
  const btn = $('#btn-report'), print = $('#btn-print'), note = $('#report-note'), out = $('#report-out');
  if (!btn) return;
  btn.disabled = !!S.busy || S.restoring || !ready;
  print.hidden = !S.report;
  print.disabled = !!S.busy || S.restoring || !S.report;
  if (!S.run) note.textContent = 'Load a run before generating a worksheet.';
  else if (!ready) note.textContent = 'Generate is available after validated analysis.';
  else if (!S.report) note.textContent = 'Generate a worksheet for this run.';
  else note.textContent = '';
  note.hidden = !!S.report || !note.textContent;
  if (renderedReport !== S.report) {
    renderedReport = S.report;
    out.replaceChildren();
    if (S.report) out.append(renderIncidentReport(document, S.report.report, { edits: S.report.edits, onEdit: (id, value) => S.report === renderedReport ? applyEdit(S.report, id, value) : null }));
  }
  if (S.report) for (const input of out.querySelectorAll('.irs-answer-input')) input.disabled = !!S.busy || S.restoring;
}
async function doReport() {
  if (S.busy || S.restoring || !S.run || !analysisReady(S.run)) return;
  clearVerifiedPrint();
  const starting = S.run.run_id, initialFingerprint = fingerprint(S.run);
  const request = { section: 7, kind: 'report', startedAt: Date.now() };
  S.busy = request;
  S.error = null;
  render();
  try {
    const run = await api('/api/runs/' + encodeURIComponent(starting), { cache: 'no-store' });
    if (S.busy !== request || S.restoring || !S.run || S.run.run_id !== starting || fingerprint(S.run) !== initialFingerprint) return;
    if (run.run_id !== starting || !analysisReady(run)) {
      S.report = null;
      S.error = { message: 'The run changed. Refresh and generate the worksheet again.', retryable: true };
      return;
    }
    setRun(run);
    S.report = { fingerprint: fingerprint(run), report: buildReport(run, new Date().toISOString()), edits: {} };
  } catch (e) {
    if (S.busy === request && S.run?.run_id === starting && fingerprint(S.run) === initialFingerprint) {
      S.report = null;
      S.error = { message: 'Unable to generate worksheet. Retry: ' + (e.message || String(e)), retryable: true };
    }
  } finally {
    if (S.busy === request) { S.busy = null; render(); }
  }
}
async function printReport() {
  if (S.busy || S.restoring || !S.report || !S.run || S.page !== 7) return;
  const snapshot = S.report, starting = S.run.run_id, initialFingerprint = fingerprint(S.run);
  if (snapshot.report.runId !== starting || snapshot.fingerprint !== initialFingerprint) {
    S.report = null; S.error = {message:'The run changed. Generate the worksheet again before printing.', retryable:true}; render(); return;
  }
  const request = {section:7, kind:'report-print', startedAt:Date.now()};
  S.busy = request; S.error = null; render();
  try {
    const fresh = await api('/api/runs/' + encodeURIComponent(starting), {cache:'no-store'});
    if (S.busy !== request || S.restoring || S.page !== 7 || S.report !== snapshot || S.run?.run_id !== starting || fingerprint(S.run) !== initialFingerprint) return;
    if (fresh.run_id !== starting || fingerprint(fresh) !== snapshot.fingerprint || !analysisReady(fresh)) {
      S.report = null; S.error = {message:'The run changed. Generate the worksheet again before printing.', retryable:true}; return;
    }
    clearVerifiedPrint();
    verifiedPrint = { snapshot, runId: starting, fingerprint: initialFingerprint, expires: Date.now() + 15000 };
    document.body.classList.add('irs-print-verified');
    verifiedPrintExpiry = setTimeout(clearVerifiedPrint, 15000);
    window.print();
  } catch (e) {
    if (S.busy === request && S.report === snapshot && S.run?.run_id === starting && fingerprint(S.run) === initialFingerprint) {
      S.report = null; S.error = {message:'Could not verify the current run. Generate the worksheet again and retry printing.', retryable:true};
    }
  } finally {
    if (S.busy === request) { S.busy = null; render(); }
  }
}

function drawSpark(frame) {
  const c = $('#spark'); if (!c) return;
  const data = S.traj?.angle_error_deg; const dpr = devicePixelRatio || 1;
  const w = c.clientWidth, hgt = c.clientHeight; c.width = w * dpr; c.height = hgt * dpr;
  const g = c.getContext('2d'); g.scale(dpr, dpr);
  const pad = { l: 40, r: 12, t: 12, b: 22 };
  if (!data?.length) { g.fillStyle = '#93a1b0'; g.font = '12px IBM Plex Mono, monospace'; g.fillText('no trajectory', 12, 22); return; }
  const fps = S.traj.fps || 30;
  const max = Math.max(10, ...data) * 1.08, W = w - pad.l - pad.r, H = hgt - pad.t - pad.b;
  const X = i => pad.l + (i / (data.length - 1)) * W, Y = v => pad.t + H - (v / max) * H;
  g.font = '11px IBM Plex Mono, monospace'; g.lineWidth = 1;
  // gridlines
  g.strokeStyle = '#1e2630'; g.fillStyle = '#93a1b0';
  const step = max > 60 ? 20 : max > 30 ? 10 : 5;
  for (let v = 0; v <= max; v += step) { g.beginPath(); g.moveTo(pad.l, Y(v)); g.lineTo(pad.l + W, Y(v)); g.stroke(); g.textAlign = 'right'; g.fillText(v + '°', pad.l - 6, Y(v) + 4); }
  g.textAlign = 'left'; g.fillText('0 s', pad.l, hgt - 6); g.textAlign = 'right'; g.fillText(((data.length - 1) / fps).toFixed(1) + ' s', pad.l + W, hgt - 6); g.textAlign = 'left';
  // area + line
  const fade = g.createLinearGradient(0, pad.t, 0, pad.t + H); fade.addColorStop(0, `${ACCENT}47`); fade.addColorStop(1, `${ACCENT}00`);
  const grad = g.createLinearGradient(pad.l, 0, pad.l + W, 0); grad.addColorStop(0, ACCENT); grad.addColorStop(1, ACCENT_2);
  g.beginPath(); data.forEach((v, i) => i ? g.lineTo(X(i), Y(v)) : g.moveTo(X(i), Y(v))); g.lineTo(X(data.length - 1), pad.t + H); g.lineTo(X(0), pad.t + H); g.closePath(); g.fillStyle = fade; g.fill();
  g.strokeStyle = grad; g.lineWidth = 2; g.lineJoin = 'round'; g.beginPath();
  data.forEach((v, i) => i ? g.lineTo(X(i), Y(v)) : g.moveTo(X(i), Y(v))); g.stroke();
  if (frame != null) {
    const x = X(frame); g.strokeStyle = '#e8edf2'; g.lineWidth = 1; g.beginPath(); g.moveTo(x, pad.t); g.lineTo(x, pad.t + H); g.stroke();
    g.fillStyle = '#e8edf2'; g.beginPath(); g.arc(x, Y(data[frame] ?? 0), 3.5, 0, 7); g.fill();
  }
}

// ---------------- video overlay ----------------
function boxAtTime(f, time, sampleTimes) {
  if (!Array.isArray(f.bbox_by_frame)) return f.bbox_normalized || null;
  const times = (sampleTimes || []).filter(Number.isFinite);
  if (!times.length) return null;
  const nearest = times.reduce((best, t) => Math.abs(t - time) < Math.abs(best - time) ? t : best);
  const frame = f.bbox_by_frame.find(x => Number.isFinite(x.t_s) && Math.abs(x.t_s - nearest) < 0.001 && Array.isArray(x.bbox_normalized) && x.bbox_normalized.length === 4);
  return frame?.bbox_normalized || null;
}
function drawOverlay() {
  const v = $('#video'), c = $('#overlay');
  const w = v.clientWidth, hh = v.clientHeight; if (!w || !hh) return;
  const dpr = devicePixelRatio || 1;
  if (c.width !== w * dpr || c.height !== hh * dpr) { c.width = w * dpr; c.height = hh * dpr; c.style.width = w + 'px'; c.style.height = hh + 'px'; }
  const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, hh);
  const refs = S.run?.video_refs?.length ? S.run.video_refs : [S.run?.clip_ref];
  const activeRef = refs.find(x => x?.view_id === S.view) || refs[0];
  if (/synthetic/i.test(`${activeRef?.filename || ''} ${activeRef?.label || ''}`) && v.readyState >= 2 && v.videoWidth && v.videoHeight) {
    const scaleX = w / v.videoWidth, scaleY = hh / v.videoHeight;
    g.fillStyle = '#0a0d11'; g.fillRect(0, 0, 240 * scaleX, 44 * scaleY);
  }
  const fs = activeFires(); if (!fs.length) return;
  const t = v.currentTime;
  const view = S.run?.analysis?.views?.find(x => x.view_id === S.view);
  const sampleTimes = view?.analysis?.spatial_review?.frame_times_s;
  for (const f of fs) {
    const box = boxAtTime(f, t, sampleTimes);
    if (!box) continue;
    const ts = f.timestamps_s;
    if (!Array.isArray(f.bbox_by_frame) && ts?.length && !ts.some(x => Math.abs(x - t) <= 1.0)) continue;
    const [x0, y0, x1, y1] = box;
    const x = x0 * w, y = y0 * hh, boxWidth = (x1 - x0) * w;
    const accentLine = g.createLinearGradient(x, y, x + boxWidth, y + (y1 - y0) * hh);
    accentLine.addColorStop(0, ACCENT); accentLine.addColorStop(1, ACCENT_2);
    g.strokeStyle = accentLine; g.lineWidth = 2; g.strokeRect(x, y, boxWidth, (y1 - y0) * hh);
    g.font = '500 11px IBM Plex Mono, monospace';
    const labelWidth = Math.max(28, g.measureText(f.id).width + 8);
    g.fillStyle = ACCENT; g.fillRect(x - 1, Math.max(0, y - 18), labelWidth, 18);
    g.fillStyle = ACCENT_INK; g.fillText(f.id, x + 4, Math.max(12, y - 5));
  }
}
(function () {
  const v = $('#video');
  for (const ev of ['timeupdate', 'seeked', 'loadedmetadata', 'loadeddata', 'play', 'pause']) v.addEventListener(ev, drawOverlay);
  (function tick() { if (!v.paused) drawOverlay(); requestAnimationFrame(tick); })();
  addEventListener('resize', () => { drawOverlay(); drawSpark(sim.frame); });
})();

// Water follows the same recorded nozzle ray and target range used by the simulator.
function waterParticle(nz, target, index) {
  const axisLength = Math.hypot(nz[3], nz[4], nz[5]);
  if (!axisLength) return null;
  const axis = nz.slice(3, 6).map(x => x / axisLength);
  const range = target ? Math.hypot(target[0] - nz[0], target[1] - nz[1], target[2] - nz[2]) : 4.05;
  const sideways = Math.hypot(axis[0], axis[1]);
  const perpendicular = sideways > 1e-8 ? [-axis[1] / sideways, axis[0] / sideways, 0] : [1, 0, 0];
  const t = (index % 40) / 39;
  // Taper the small deterministic spread at both ends, keeping every particle within range.
  const spread = (((index * 37) % 101) / 100 - 0.5) * Math.min(0.04, range * 0.1) * t * (1 - t);
  return axis.map((v, n) => nz[n] + v * range * t + perpendicular[n] * spread);
}

// ---------------- three.js simulation ----------------
const sim = {
  T: null, ready: null, traj: null, meshes: [], frame: 0, playing: false, lastT: 0, acc: 0,
  fires: [], particles: null, pv: null, plife: null, pn: 400, pi: 0, spray: [], speed: 1,
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
      const sc = this.scene = new THREE.Scene(); sc.background = new THREE.Color(0x0a0d11);
      sc.add(new THREE.HemisphereLight(0xcfd8e3, 0x1a1d20, 1.0));
      const d = new THREE.DirectionalLight(0xffffff, 1.6); d.position.set(-3, -5, 8); sc.add(d);
      const cam = this.cam = new THREE.PerspectiveCamera(45, 1, 0.05, 200);
      cam.up.set(0, 0, 1); cam.position.set(-3.5, -6, 3.5);
      const oc = this.controls = new OrbitControls(cam, r.domElement);
      oc.target.set(3, 0, 1); oc.enableDamping = true; oc.update();
      const grid = new THREE.GridHelper(20, 20, 0x2a3440, 0x161c24); grid.rotation.x = Math.PI / 2; grid.position.set(3, 0, 0.002); sc.add(grid);
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
    this.traj = null; this.playing = false; this.frame = 0; this.spray = [];
    if (this.particles) { this.particles.geometry.attributes.position.array.fill(1e4); this.particles.geometry.attributes.position.needsUpdate = true; }
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
      const mesh = new T.Mesh(geo, mat); mesh.matrixAutoUpdate = true;
      if (traj.version === 'mobile_v1' && fire) mesh.visible = false;
      this.scene.add(mesh); this.meshes.push(mesh);
    }
    for (const f of traj.fx?.fires || []) {
      const grp = new T.Group(); grp.position.set(...f.pos);
      const mk = (rad, ht, col) => { const gm = new T.ConeGeometry(rad, ht, 16); gm.rotateX(Math.PI / 2); gm.translate(0, 0, ht / 2);
        return new T.Mesh(gm, new T.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 1.6, transparent: true, opacity: 0.9 })); };
      const outer = mk(0.32, 0.9, 0xff5a0a), inner = mk(0.17, 0.55, 0xffc23a);
      const light = new T.PointLight(0xff6a1a, 3, 6); light.position.z = 0.5;
      grp.add(outer, inner, light);
      if (f.target) { const ring = new T.Mesh(new T.RingGeometry(0.55, 0.62, 40), new T.MeshBasicMaterial({ color: 0xff6a1a, side: T.DoubleSide })); ring.position.z = 0.01; grp.add(ring); }
      this.scene.add(grp); this.fires.push({ group: grp, outer, inner, light, ph: this.fires.length * 2.1, suppressedFrame: f.suppressed_frame });
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
    for (const f of this.fires) f.group.visible = f.suppressedFrame == null || this.frame < f.suppressedFrame;
    this.updateSpray();
    this.sync();
    drawSpark(this.frame);
  },
  sprayEvent() { let event = null; for (const e of this.spray) { if (e.frame <= this.frame) event = e; else break; } return event; },
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
      this.acc += (now - this.lastT) / 1000 * this.traj.fps * this.speed; this.lastT = now;
      const last = this.traj.frames.length - 1;
      if (this.acc >= last) { this.setFrame(last); this.playing = false; this.sync(); } else this.setFrame(Math.floor(this.acc));
    }
    const time = this.traj ? this.frame / (this.traj.fps || 30) : 0;
    for (const f of this.fires) {
      const k = 0.85 + 0.15 * Math.sin(time * 17 + f.ph) + 0.1 * Math.sin(time * 31 + f.ph * 2);
      f.outer.scale.set(1 + 0.08 * Math.sin(time * 23 + f.ph), 1 + 0.08 * Math.cos(time * 19), k);
      f.inner.scale.set(1, 1, 0.8 + 0.3 * Math.sin(time * 29 + f.ph));
      f.light.intensity = 2 + 2 * k;
    }
    // Spray is reconstructed from the recorded frame, including when paused or scrubbed.
    this.controls?.update();
    this.renderer?.render(this.scene, this.cam);
  },
  updateSpray() {
    if (!this.particles) return;
    const pos = this.particles.geometry.attributes.position.array;
    pos.fill(1e4);
    const nz = this.traj?.fx?.nozzle?.[this.frame], event = this.sprayEvent();
    const target = this.traj?.fx?.fires?.find(f => f.id === event?.target_id)?.pos || null;
    if (nz && event?.on) for (let i = 0; i < this.pn; i++) {
      const point = waterParticle(nz, target, i);
      if (point) pos.set(point, i * 3);
    }
    this.particles.geometry.attributes.position.needsUpdate = true;

  },
};

// ---------------- init ----------------
$('.skip').addEventListener('click', event => { event.preventDefault(); $('#main').focus(); });
$('#file').addEventListener('change', e => { const files = Array.from(e.target.files); e.target.value = ''; addFiles(files); });
$('#btn-load').addEventListener('click', loadSelected);
$('#view-select').addEventListener('change', e => { S.view = e.target.value; render(); });
$('#sim-speed').addEventListener('change', e => { sim.speed = Number(e.target.value); });
$('#btn-analyse').addEventListener('click', doAnalyse);
$('#btn-scene').addEventListener('click', doScene);
$('#btn-run').addEventListener('click', doRun);
$('#btn-reset').addEventListener('click', doReset);
$('#btn-replay').addEventListener('click', () => sim.replay());
$('#btn-play').addEventListener('click', () => sim.playing ? sim.pause() : sim.play());
$('#scrub').addEventListener('input', e => { sim.playing = false; sim.setFrame(+e.target.value); });
$('#page-prev').addEventListener('click', () => setPage(S.page - 1));
$('#page-next').addEventListener('click', () => setPage(S.page + 1));
$('#btn-report').addEventListener('click', doReport);
$('#btn-print').addEventListener('click', printReport);
$('#g1-rehearsal').addEventListener('load', () => renderPageNavigation());
addEventListener('message', event => {
  const frame = $('#g1-rehearsal');
  if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.type !== 'scene2real-rehearsal-resize') return;
  const height = Number(event.data.height);
  if (Number.isFinite(height)) frame.style.height = Math.min(2000, Math.max(400, height)) + 'px';
});
function routeChanged() {
  const run = new URLSearchParams(location.search).get('run');
  if (run !== (S.run?.run_id || null)) { location.reload(); return; }
  setPage(Math.max(1, PAGES.indexOf(location.hash.slice(1)) + 1), { push: false });
}
addEventListener('popstate', routeChanged);
addEventListener('hashchange', routeChanged);

(async function boot() {
  const hash = location.hash.slice(1);
  const legacyRun = hash.startsWith('r_') ? hash : null;
  const rid = new URLSearchParams(location.search).get('run') || legacyRun;
  render();
  try { [S.clips, S.zones] = await Promise.all([api('/api/clips'), api('/api/zones')]); }
  catch (e) { S.error = { message: e.message, retryable: true }; S.last = boot; }
  if (rid) {
    try {
      const r = await api('/api/runs/' + encodeURIComponent(rid));
      if (legacyRun) S.page = ({ uploaded: 2, analysed: 3, confirmed: 4, scene_ready: 5, completed: 5 })[r.state] || 2;
      setRun(r);
      S.restoring = false;
      if (r.metrics) await loadTraj(false);
      const job = await api(`/api/runs/${rid}/operations`, { cache: 'no-store' }).catch(error => { if (error.status !== 404) throw error; return null; });
      if (job && ['pending', 'running'].includes(job.status)) await act(job.operation, () => waitOperation(job));
      else if (job?.status === 'failed' && !r.error) { S.error = { message: job.error?.detail || 'The previous operation failed.', retryable: job.error?.retryable }; S.last = STAGE_RETRY[job.operation]; }
    }
    catch (error) { S.error = { message: error.message || 'Could not restore this run.', retryable: true }; S.last = boot; }
  }
  S.restoring = false;
  render();
})();
