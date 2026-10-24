// Focused checks for the editable IRS worksheet using small inline fixtures that follow
// the run schema in CONTRACT.md. Browser rendering and printed PDF output are covered by
// tests/e2e/incident-report.spec.mjs; this file needs no fixtures directory or inventory file.
const fs = require('fs');
const path = require('path');
const os = require('os');
const { pathToFileURL } = require('url');
const assert = require('assert/strict');

const REMOVED_COPY = [
  'Generate the IRS worksheet from this run.',
  'IRS worksheet. Any draft is machine-observed and unverified. Unsupported answers stay blank.',
  'Vision draft · unverified · Synthetic Scene2Real footage · V1:A1 · Yellow-orange flames rising from a low rectangular base on the left foreground floor.',
  'This worksheet reproduces the numbered question headings only. It does not reconstruct all subfields, options or validation rules.',
  'Generate the IRS worksheet from validated analysis. Unsupported answers stay blank.',
  'Vision draft',
  'Video evidence',
  'Historical reference worksheet — not current FaRDaP or a validated submission.',
  'DEMO · SAMPLE CONTENT · NOT FOR INCIDENT SUBMISSION',
  'Edits stay in this browser and are cleared when the run changes.',
];

function fixtureRun(overrides = {}) {
  const run = {
    run_id: 'r_inline_ok', created_at: '2026-10-17T09:42:00Z', state: 'analysed', error: null,
    clip_ref: { kind: 'preloaded', filename: 'left-camera.mp4', sha256: 'a'.repeat(64), duration_s: 12.0, local_path: 'runs/r_inline_ok/clip.mp4', s3_uri: null, label: 'local upload adapter (archived to VAST S3)', view_id: 'V1' },
    video_refs: [{ view_id: 'V1', kind: 'preloaded', filename: 'left-camera.mp4', sha256: 'a'.repeat(64), duration_s: 12.0, label: 'local upload adapter (archived to VAST S3)' }],
    model_id: 'nvidia/cosmos3-nano-reasoner', prompt_id: 'cosmos_fire_obs_v4',
    analysis: { cached: false, latency_s: 4.2, frames: [{ t_s: 0.0 }, { t_s: 2.0 }],
      spatial_review: { status: 'reviewed', source: 'astra', model_id: 'gpt-6-astra', prompt_id: 'astra_fire_grounding_v1', reason: null },
      views: [{ view_id: 'V1', state: 'analysed', analysis: { cached: false, model_id: 'nvidia/cosmos3-nano-reasoner', prompt_id: 'cosmos_fire_obs_v4', spatial_review: { status: 'reviewed', model_id: 'gpt-6-astra', prompt_id: 'astra_fire_grounding_v1' } } }] },
    observations: {
      fire_sources: [{ id: 'V1:A1', view_id: 'V1', timestamps_s: [2.0, 4.0], bbox_normalized: [0.12, 0.55, 0.3, 0.8], bbox_at_s: 2.0,
        description: 'Yellow-orange flames rising from a low rectangular base on the left foreground floor.',
        location_description: 'left foreground floor beside the rack', burning_object: 'cardboard packaging', smoke_description: 'light grey smoke drifting upward',
        nearby_objects: ['pallet', 'shelving'], suggested_zone: 'left_rack', bbox_provenance: { status: 'reviewed', model_id: 'gpt-6-astra', prompt_id: 'astra_fire_grounding_v1' } }],
      unknowns: ['cause', 'scale', 'depth'], cause: null, scale: null, depth_m: null, objects: [],
      scene_description: 'A warehouse aisle with pallet racking on both sides.',
    },
    excluded: [], confirmed_target: null, confirmed_targets: null, instruction: null, skill: null, metrics: null, timings_s: { analyse: 4.2 }, telemetry: { weave: 'skipped: test', vast: 'skipped: test' },
  };
  return Object.assign(run, overrides);
}

function fakeDocument() {
  const make = tag => ({
    tag, className: '', attrs: {}, children: [], text: null, listeners: {}, value: undefined, disabled: false,
    get id() { return this.attrs.id || ''; }, set id(v) { this.attrs.id = v; },
    setAttribute(name, value) { this.attrs[name] = String(value); },
    getAttribute(name) { return this.attrs[name] ?? null; },
    append(...nodes) { this.children.push(...nodes); },
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
    dispatch(type) { for (const fn of this.listeners[type] || []) fn({ target: this }); },
    set textContent(value) { this.text = value == null ? '' : String(value); this.children = []; },
    get textContent() { return this.text != null ? this.text : this.children.map(child => child.textContent || '').join(''); },
  });
  return { createElement: tag => make(tag), createTextNode: text => ({ textContent: String(text), children: [], attrs: {}, className: '' }) };
}
function collect(node, out = []) { out.push(node); for (const child of node.children || []) collect(child, out); return out; }

(async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'irs-edit-module-'));
  try {
    const source = fs.readFileSync('static/incident_report.js', 'utf8').replace(/(['"])\.\/irs_2012_worksheet\.js\1/g, '$1./irs_2012_worksheet.mjs$1');
    fs.writeFileSync(path.join(temp, 'incident_report.mjs'), source);
    fs.copyFileSync('static/irs_2012_worksheet.js', path.join(temp, 'irs_2012_worksheet.mjs'));
    const { IRS_2012_WORKSHEET } = await import(pathToFileURL(path.join(temp, 'irs_2012_worksheet.mjs')).href);
    const mod = await import(pathToFileURL(path.join(temp, 'incident_report.mjs')).href);
    const { analysisReady, applyEdit, buildReport, effectiveAnswer, fingerprint, renderIncidentReport, retainReport, sanitizeEdit } = mod;
    const questions = IRS_2012_WORKSHEET.sections.flatMap(section => section.questions);
    assert.equal(questions.length, 158, 'the source module still lists 158 headings');

    // 1. Every existing answer box is populated with exactly one status.
    const run = fixtureRun();
    assert(analysisReady(run));
    const report = buildReport(run, '2026-10-17T17:05:00Z');
    assert.deepEqual(Object.keys(report.answers).sort(), questions.map(q => q.id).sort(), 'one answer per heading');
    const statuses = {};
    for (const q of questions) {
      const answer = report.answers[q.id];
      assert.equal(typeof answer.value, 'string'); assert(answer.value.trim(), `${q.id} has an initial value`);
      assert(['Suggested', 'Sample'].includes(answer.status), `${q.id} status is Suggested or Sample`);
      statuses[answer.status] = (statuses[answer.status] || 0) + 1;
    }
    assert.equal(statuses.Suggested, 2, 'only run-supported 3.1 and 3.2 are Suggested');
    assert.equal(statuses.Sample, 156);
    assert.deepEqual(report.answers['3.1'], { value: 'Fire', status: 'Suggested', note: 'Run analysis · V1:A1' });
    assert.deepEqual(report.answers['3.2'], { value: 'Warehouse', status: 'Suggested', note: 'Run analysis · scene description' });
    assert(report.observations === undefined, 'no video evidence annex is built into the snapshot');
    const values = new Set(Object.values(report.answers).map(a => a.value));
    assert(values.size >= 40, `sample values are a varied mix (${values.size} distinct values)`);
    assert.equal(JSON.stringify(buildReport(fixtureRun(), '2026-10-17T17:05:00Z').answers), JSON.stringify(report.answers), 'deterministic');
    assert(Object.isFrozen(report.answers) && Object.isFrozen(report.answers['1.1']), 'snapshot answers are immutable');
    const serialized = JSON.stringify(report.answers);
    for (const forbidden of ['synthetic', 'Synthetic', 'operator-entered', 'observed by operator', 'r_inline_ok', 'FaRDaP']) assert(!serialized.includes(forbidden), `snapshot must not contain "${forbidden}"`);
    assert(!/\b[A-Z]\d{2,3}\b/.test(serialized), 'no invented option codes');

    // 2. Suggested only when the run supports it.
    const smokeOnly = fixtureRun({ run_id: 'r_inline_smoke' });
    smokeOnly.observations = structuredClone(run.observations);
    smokeOnly.observations.fire_sources[0].description = 'smoke only at the door';
    smokeOnly.observations.fire_sources[0].burning_object = 'burnt residue';
    smokeOnly.observations.fire_sources[0].smoke_description = 'grey smoke';
    smokeOnly.observations.scene_description = 'warehouse cannot be confirmed';
    const smokeAnswers = buildReport(smokeOnly).answers;
    assert.equal(smokeAnswers['3.1'].status, 'Sample'); assert.equal(smokeAnswers['3.2'].status, 'Sample');
    assert.equal(Object.values(smokeAnswers).filter(a => a.status === 'Suggested').length, 0);
    const excludedRun = fixtureRun({ excluded: [{ id: 'V1:A1', reason: 'duplicate reflection' }] });
    assert.equal(buildReport(excludedRun).answers['3.1'].status, 'Sample', 'excluded observations do not drive Suggested');
    assert.equal(buildReport(excludedRun).answers['3.2'].status, 'Suggested', 'scene description is unaffected by sighting exclusion');
    const failedAnalyse = fixtureRun({ state: 'failed', error: { stage: 'analyse', message: 'upstream', retryable: true } });
    assert(!analysisReady(failedAnalyse)); assert(!analysisReady(fixtureRun({ state: 'uploaded', analysis: null })));

    // 3. Edits are sanitized, bound to the snapshot and reversible.
    const snapshot = { fingerprint: fingerprint(run), report, edits: {} };
    assert.deepEqual(effectiveAnswer(snapshot, '1.1'), report.answers['1.1']);
    assert.deepEqual(applyEdit(snapshot, '1.1', ' FRS/2026/000777 '), { value: 'FRS/2026/000777', status: 'Edited', note: null });
    assert.deepEqual(effectiveAnswer(snapshot, '1.1'), { value: 'FRS/2026/000777', status: 'Edited', note: null });
    assert.equal(report.answers['1.1'].value, 'DEMO-2026-000123', 'the immutable snapshot keeps its original value');
    assert.deepEqual(applyEdit(snapshot, '1.1', 'DEMO-2026-000123'), report.answers['1.1'], 'restoring the original text restores its status');
    assert(!Object.prototype.hasOwnProperty.call(snapshot.edits, '1.1'));
    assert.deepEqual(applyEdit(snapshot, '3.1', ''), { value: '', status: 'Edited', note: null }, 'an operator can clear a Suggested value');
    assert.equal(applyEdit(snapshot, 'not-a-question', 'x'), null);
    assert.equal(sanitizeEdit(null), ''); assert.equal(sanitizeEdit('   '), '');
    assert.equal(sanitizeEdit('Line one\r\nLine\u0000 two\u001b'), 'Line one\nLine two');
    assert.equal(sanitizeEdit('x'.repeat(5000)).length, 2000, 'edits are length-capped');
    for (const secret of ['Bearer secret-token', 's3://private-bucket/clip', '/Users/someone/private.mp4', 'https://host/clip?X-Amz-Signature=sentinel', 'api_key=abc123', 'C:\\Users\\Fred\\private.mp4', 'config/team-28.config']) {
      const cleaned = applyEdit(snapshot, '4.2k', 'Note ' + secret).value;
      for (const leak of ['secret-token', 'private-bucket', '/Users/', 'sentinel', 'abc123', 'Fred', 'team-28']) assert(!cleaned.includes(leak), `${secret} leaked as ${cleaned}`);
      assert(cleaned.includes('[redacted]'));
    }
    assert.equal(applyEdit(snapshot, '4.2k', 'Water flow 2 m/s; left/right racks').value, 'Water flow 2 m/s; left/right racks');
    assert.equal(applyEdit(snapshot, '4.2k', '<img src=x onerror=alert(1)>').value, '<img src=x onerror=alert(1)>', 'markup is kept as inert text and rendered via textContent');

    // 4. Stale edits are cleared with the snapshot after invalidating transitions.
    assert.equal(retainReport(snapshot, run, null), snapshot);
    for (const action of ['analyse', 'confirm', 'reset']) assert.equal(retainReport(snapshot, run, action), null, action + ' clears the worksheet and its edits');
    assert.equal(retainReport(snapshot, fixtureRun({ run_id: 'r_inline_other' }), null), null, 'a run change clears the worksheet and its edits');
    for (const mutate of [
      r => { r.state = 'scene_ready'; },
      r => { r.observations.fire_sources[0].description = 'a changed observation'; },
      r => { r.confirmed_targets = [{ target_id: 'T1', members: ['V1:A1'], zone: 'left_rack' }]; },
      r => { r.excluded = [{ id: 'V1:A1', reason: 'reviewed' }]; },
      r => { r.metrics = { success: true }; },
    ]) {
      const changed = fixtureRun(); changed.observations = structuredClone(run.observations); mutate(changed);
      assert.notEqual(fingerprint(changed), fingerprint(run));
      assert.equal(retainReport(snapshot, changed, null), null);
    }
    assert(Object.keys(snapshot.edits).length > 0, 'edits existed before invalidation');
    const fresh = { fingerprint: fingerprint(run), report: buildReport(run, '2026-10-17T17:06:00Z'), edits: {} };
    assert.deepEqual(effectiveAnswer(fresh, '1.1'), report.answers['1.1'], 'a regenerated worksheet starts without edits');

    // 5. Rendering: every box is an editable, labelled control; edits reach the print layer; copy is correct.
    const doc = fakeDocument();
    const edits = {};
    const rendered = renderIncidentReport(doc, report, { edits, onEdit: (id, value) => applyEdit({ report, edits }, id, value) });
    const nodes = collect(rendered);
    const text = rendered.textContent;
    assert.equal(rendered.attrs['aria-label'], 'IRS WORKSHEET');
    assert.equal(nodes.find(node => node.tag === 'h3').textContent, 'IRS WORKSHEET');
    assert.equal(nodes.filter(node => node.attrs['data-question-id']).length, 158);
    const inputs = nodes.filter(node => node.tag === 'textarea');
    assert.equal(inputs.length, 158, 'every answer box is a textarea');
    const ids = new Set();
    for (const input of inputs) {
      assert(input.id && !ids.has(input.id), 'unique id for keyboard/label association'); ids.add(input.id);
      assert.match(input.attrs['aria-label'], /^Answer /);
      assert(nodes.some(node => node.tag === 'label' && node.attrs.for === input.id), `label targets ${input.id}`);
      assert.equal(input.attrs['aria-describedby'], undefined, 'no answer-status tag is attached to the control');
      assert(input.value.trim(), 'textarea is pre-filled');
      assert.equal(input.attrs.tabindex, undefined, 'natively focusable');
    }
    const answers = nodes.filter(node => node.className === 'irs-answer');
    assert.equal(answers.length, 158);
    assert.equal(nodes.filter(node => node.className === 'irs-answer-status').length, 0, 'no per-answer status pill is rendered');
    assert.equal(answers.filter(a => a.attrs['data-status'] === 'Suggested').length, 2, 'status is kept on data-status');
    assert.equal(answers.filter(a => a.attrs['data-status'] === 'Sample').length, 156);
    const chrome = a => a.children.filter(child => child.tag !== 'textarea' && child.className !== 'irs-answer-print').map(child => child.textContent).join(' ');
    for (const a of answers) assert(!/\b(?:Suggested|Sample|Edited)\b/.test(chrome(a)), `answer ${a.attrs['aria-label']} shows no status text`);
    assert.equal(nodes.filter(node => /irs-legend|irs-answer-note/.test(node.className)).length, 0, 'status keys and source notes are absent from the worksheet UI');
    assert(!/Supported by this run|Illustrative placeholder|Changed in this preview|Run analysis/i.test(text), 'answer status and source explanations are absent from visible copy');
    assert.equal(nodes.filter(node => /irs-demo-banner|irs-demo-footer/.test(node.className)).length, 0, 'demo banner is omitted from preview and print');
    assert(!text.includes('DEMO · SAMPLE CONTENT · NOT FOR INCIDENT SUBMISSION'));
    assert(text.includes('Department for Communities and Local Government'), 'historical IRS attribution retained');
    for (const copy of REMOVED_COPY) assert(!text.includes(copy), `removed copy still rendered: ${copy}`);
    assert(!/synthetic/i.test(text), 'the word synthetic does not appear in UI copy');
    assert(!text.includes('v1-0p') && !text.includes('v1-0n'));
    assert.equal(nodes.filter(node => /irs-evidence-annex|irs-observation/.test(node.className)).length, 0, 'no video evidence section');
    const box = id => nodes.find(node => node.className === 'irs-answer' && node.attrs['aria-label'] === 'Answer ' + id);
    const input31 = box('3.1').children.find(n => n.tag === 'textarea');
    const print31 = box('3.1').children.find(n => n.className === 'irs-answer-print');
    const status31 = () => box('3.1').attrs['data-status'];
    assert.equal(print31.textContent, 'Fire'); assert.equal(status31(), 'Suggested'); assert.equal(input31.attrs['data-status'], 'Suggested');
    input31.value = 'Fire /Users/someone/private.mp4'; input31.dispatch('input');
    assert.equal(print31.textContent, 'Fire [redacted]', 'edited value reaches the print layer sanitized');
    assert.equal(status31(), 'Edited'); assert.equal(input31.attrs['data-status'], 'Edited'); assert.equal(input31.attrs['aria-describedby'], undefined);
    assert.equal(edits['3.1'], 'Fire [redacted]');
    input31.dispatch('change');
    assert.equal(input31.value, 'Fire [redacted]', 'the control shows the sanitized text after commit');
    input31.value = 'Fire'; input31.dispatch('input');
    assert.equal(status31(), 'Suggested'); assert(!('3.1' in edits));
    const reRendered = renderIncidentReport(fakeDocument(), report, { edits: { '2.1': '17 Oct 2026, 09:40' } });
    const re = collect(reRendered);
    const box21 = re.find(node => node.className === 'irs-answer' && node.attrs['aria-label'] === 'Answer 2.1');
    assert.equal(box21.children.find(n => n.tag === 'textarea').value, '17 Oct 2026, 09:40', 'existing edits survive a re-render of the same snapshot');
    assert.equal(box21.attrs['data-status'], 'Edited');
    assert(!re.some(node => node.className === 'irs-answer-status'));

    // 6. Removed copy and required copy in the shipped frontend sources.
    const appSource = fs.readFileSync('static/app.js', 'utf8');
    const html = fs.readFileSync('static/index.html', 'utf8');
    const css = fs.readFileSync('static/styles.css', 'utf8');
    for (const copy of REMOVED_COPY) assert(!appSource.includes(copy) && !source.includes(copy) && !html.includes(copy), `removed copy still in sources: ${copy}`);
    assert(appSource.includes("'Review and edit answers before printing.'"), 'new page description');
    assert(/\bIRS WORKSHEET\b/.test(html) && !/IRS Worksheet|Irs Worksheet/.test(html + appSource + source), 'title is exactly IRS WORKSHEET');
    assert(/'IRS WORKSHEET'\]/.test(appSource), 'stage label is IRS WORKSHEET');
    const uiString = /(['"`])(?:(?!\1)[^\\\n]|\\.)*synthetic(?:(?!\1)[^\\\n]|\\.)*\1/i;
    assert(!uiString.test(source) && !uiString.test(appSource.slice(appSource.indexOf('function renderReport'), appSource.indexOf('function drawSpark'))) && !uiString.test(html.slice(html.indexOf('id="s7"'))), 'no synthetic in worksheet UI strings');
    assert(/\.irs-answer-input\{display:none!important\}/.test(css) && /\.irs-answer-print\{display:block!important/.test(css), 'print swaps controls for printed values');
    assert(!/\.irs-answer-status\b/.test(css), 'no pill styling remains');
    assert(/\.irs-answer\[data-status="Suggested"\]/.test(css) && /\.irs-answer\[data-status="Sample"\]/.test(css), 'suggested and sample boxes are distinguished by subtle styling');
    assert(/\.irs-answer-input:focus-visible/.test(css) && /\.irs-answer-input:hover/.test(css), 'focus and hover states are styled');
    assert(/\.irs-answer-input\{[^}]*border-radius:10px/.test(css) && /\.irs-answer-input\{[^}]*padding:9px 12px/.test(css) && /\.irs-answer-input\{[^}]*font:500 14px\/1\.5/.test(css), 'answer controls use rounded corners, comfortable padding and legible type');
    assert(/\.irs-answer-print\{display:block!important;[^}]*border-radius:1\.5mm/.test(css) && /\.irs-answer\[data-status="Suggested"\] \.irs-answer-print/.test(css), 'printed answers keep a clean bordered box with the subtle status styling');
    assert(!/\.irs-legend|\.irs-answer-note/.test(css), 'no answer status key or source-note styling remains');
    assert(!/\.irs-demo-banner|\.irs-demo-footer/.test(css), 'demo banner has no preview or print styling');
    assert(!appSource.includes('Edits stay in this browser and are cleared when the run changes.'), 'run-change note is removed from the worksheet controls');
    assert(!/#video-evidence|video-evidence/.test(html.slice(html.indexOf('id="s7"'), html.indexOf('</section>', html.indexOf('id="s7"')))), 'no video evidence section inside the worksheet page');
    console.log('PASS: 158 editable populated boxes, Suggested/Sample mix, sanitized edits in print, stale edit clearing, removed copy, title and no video evidence section');
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
