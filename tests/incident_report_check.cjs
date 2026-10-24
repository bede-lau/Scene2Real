// Focused contract checks against fixture data. Browser rendering and printed output
// are covered by tests/e2e/incident-report.spec.mjs.
const fs = require('fs');
const path = require('path');
const os = require('os');
const { pathToFileURL } = require('url');
const assert = require('assert/strict');

(async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'irs-report-module-'));
  try {
    // The app serves native ES modules while this repository has no package-wide
    // type=module. Copy only the report modules to an isolated .mjs test directory.
    const source = fs.readFileSync('static/incident_report.js', 'utf8')
      .replace(/(['"])\.\/irs_2012_worksheet\.js\1/g, '$1./irs_2012_worksheet.mjs$1');
    fs.writeFileSync(path.join(temp, 'incident_report.mjs'), source);
    fs.copyFileSync('static/irs_2012_worksheet.js', path.join(temp, 'irs_2012_worksheet.mjs'));
    const { IRS_2012_WORKSHEET } = await import(pathToFileURL(path.join(temp, 'irs_2012_worksheet.mjs')).href);
    const sourceInventory = JSON.parse(fs.readFileSync('.prd-to-production/fire-reporting/research/historical-worksheet-fields.json', 'utf8'));
    assert.deepEqual(IRS_2012_WORKSHEET, sourceInventory, 'the worksheet source matches the full reviewed source inventory');
    const { scrub, analysisReady, fingerprint, retainReport, buildReport, renderIncidentReport } = await import(pathToFileURL(path.join(temp, 'incident_report.mjs')).href);
    const load = id => JSON.parse(fs.readFileSync(`tests/fixtures/report_runs/${id}/run.json`, 'utf8'));
    const ok = load('r_report_ok');
    const fail = load('r_report_fail');
    const partial = load('r_report_partial');
    assert(analysisReady(ok));
    assert(analysisReady(fail));
    assert(analysisReady(partial));
    assert(!analysisReady(load('r_report_uploaded')));
    const snapshot = { fingerprint: fingerprint(ok), report: buildReport(ok, '2026-10-17T17:05:00Z') };
    assert(retainReport(snapshot, ok, null));
    for (const action of ['analyse', 'confirm', 'reset']) assert.equal(retainReport(snapshot, ok, action), null);
    assert.equal(retainReport(snapshot, fail, null), null, 'a different run invalidates the snapshot');
    for (const mutate of [
      run => { run.observations.fire_sources[0].description = 'a changed observation'; },
      run => { run.clip_ref.filename = 'other-camera.mp4'; },
      run => { run.video_refs[0].filename = 'other-view.mp4'; },
      run => { run.confirmed_target.zone = 'other'; },
      run => { run.excluded = [{ id: 'V1:A1', reason: 'reviewed' }]; },
      run => { run.model_id = 'a different model'; },
      run => { run.prompt_id = 'a different prompt'; },
      run => { run.analysis.views[0].analysis.model_id = 'a different view model'; },
      run => { run.analysis.views[0].analysis.spatial_review = { status: 'reviewed', model_id: 'grounding-model', prompt_id: 'grounding-prompt' }; },
      run => { run.analysis.spatial_review = { status: 'disabled', reason: 'unreviewed Cosmos observations' }; },
      run => { run.observations.fire_sources[0].bbox_provenance = { status: 'reviewed', model_id: 'grounding-model', prompt_id: 'grounding-prompt' }; },
    ]) {
      const changed = structuredClone(ok);
      mutate(changed);
      assert.notEqual(fingerprint(changed), fingerprint(ok), 'relevant source change changes the fingerprint');
      assert.equal(retainReport(snapshot, changed, null), null);
    }
    const before = JSON.stringify(snapshot.report);
    ok.observations.fire_sources[0].description = 'MUTATED_AFTER_SNAPSHOT';
    assert.equal(JSON.stringify(snapshot.report), before, 'report snapshot is independent of subsequent run mutation');
    assert(!JSON.stringify(snapshot.report).includes('MUTATED_AFTER_SNAPSHOT'));
    for (const secret of ['Bearer secret-token', 's3://private-bucket/clip', '/Users/someone/private.mp4', 'https://host/clip?X-Amz-Signature=sentinel']) {
      const value = scrub(secret) || '';
      assert(!value.includes('secret-token') && !value.includes('private-bucket') && !value.includes('/Users/') && !value.includes('sentinel'));
    }
    for (const pathValue of ['/mnt/data/private.mp4', '/srv/archive/private.mp4', '/Volumes/Drive/private.mp4', 'C:\\Users\\Fred\\private.mp4', '../private/private.mp4', '~/Documents/private/camera.mp4', 'file:///etc/private', '//fileserver/private/camera.mp4', 'config/team-28.config', '"/Users/Bede Lau/private.mp4"']) {
      const cleaned = scrub(pathValue) || '';
      assert(!cleaned.includes(pathValue) && !cleaned.includes('private') && !cleaned.includes('Bede Lau') && !cleaned.includes('team-28'), `local path leaked: ${pathValue}`);
    }
    assert.equal(scrub('Water flow 2 m/s; left/right racks'), 'Water flow 2 m/s; left/right racks', 'normal units and prose survive');
    const single = structuredClone(partial);
    delete single.analysis.views;
    single.analysis.spatial_review = { status:'disabled', reason:'Unreviewed Cosmos observations', raw_response:'PRIVATE_RAW' };
    const singleReport = buildReport(single);
    assert(JSON.stringify(singleReport).includes('Unreviewed Cosmos observations'), 'single-view review provenance is retained');
    assert(!JSON.stringify(singleReport).includes('PRIVATE_RAW'), 'raw provider output is not copied');
    const mixedCache = structuredClone(partial);
    delete mixedCache.analysis.cached;
    mixedCache.analysis.views = [{analysis:{cached:true}}, {analysis:{}}];
    assert.notEqual(buildReport(mixedCache).cache, 'Cached', 'unknown view is not reported as wholly cached');
    mixedCache.analysis.views[1].analysis.cached = true;
    assert.equal(buildReport(mixedCache).cache, 'Cached');
    const fresh = load('r_report_ok');
    const filled = buildReport(fresh, '2026-10-17T17:05:00Z').answers;
    const suggested = answers => Object.keys(answers).filter(id => answers[id].status === 'Suggested');
    assert.equal(Object.keys(filled).length, 158, 'every heading has an initial answer');
    assert(Object.values(filled).every(a => a.value.trim() && ['Suggested', 'Sample'].includes(a.status)));
    assert.deepEqual(suggested(filled), ['3.1']);
    assert.deepEqual(filled['3.1'], { value: 'Fire', status: 'Suggested', note: 'Run analysis · V1:A1' });
    assert.equal(filled['3.2'].status, 'Sample');
    const serialized = JSON.stringify(filled);
    assert.doesNotMatch(serialized, /V1:A2|V2:A1|same packaging|SpecialService|FalseAlarm|Not an FRS finding|Not operator-confirmed|Not an official classification|Vision draft|synthetic/i);
    for (const forbidden of ['r_report_ok', 'Walk the aisle', 'mobile_suppress_demo', 'right_rack', 'template-assumed', 'burning packaging beside the right rack']) assert.equal(serialized.includes(forbidden), false, forbidden);
    assert.equal(JSON.stringify(buildReport(structuredClone(fresh), '2026-10-17T17:05:00Z').answers), serialized);
    const failAnswers = buildReport(fail).answers;
    assert.deepEqual(failAnswers['3.1'], { value: 'Fire', status: 'Suggested', note: 'Run analysis · F1' });
    assert.equal(failAnswers['3.2'].status, 'Sample');
    assert.equal(failAnswers['4.2k'].status, 'Sample');
    assert.deepEqual(suggested(buildReport(partial).answers), [], 'smoke-only evidence leaves every answer as a sample');
    const dense = load('r_report_dense');
    const denseAnswers = buildReport(dense).answers;
    assert.deepEqual(suggested(denseAnswers), ['3.1'], 'a warehouse word inside a location phrase does not fill 3.2');
    assert.equal(JSON.stringify(denseAnswers).includes('position 12'), false, 'a 12-sighting run does not paste every excerpt');
    const excluded = structuredClone(fresh);
    excluded.excluded = [{ id: 'V1:A1', reason: 'operator removed' }, { id: 'V1:A2', reason: 'operator removed' }];
    assert.deepEqual(suggested(buildReport(excluded).answers), [], 'excluded flame observations do not fill 3.1');
    const oneExcluded = structuredClone(fresh);
    oneExcluded.excluded = [{ id: 'V1:A1', reason: 'operator removed' }];
    assert.equal(buildReport(oneExcluded).answers['3.1'].note, 'Run analysis · V1:A2');
    for (const description of ['no flames and not burning', 'possible flame', 'maybe burning', 'uncertain whether it is burning', 'smoke only at the door', 'Flames are not visible', 'Flames may be a reflection', 'burning is not observed', 'burnt residue beside the rack', 'burned residue on the pallet', 'charring along the beam', 'scorch marks on the beam']) {
      const changed = structuredClone(fresh);
      for (const source of changed.observations.fire_sources) {
        source.description = description;
        source.burning_object = description;
        source.smoke_description = description;
      }
      assert.equal(buildReport(changed).answers['3.1'].status, 'Sample', description);
    }
    const warehouse = structuredClone(partial);
    warehouse.observations.scene_description = 'The premises are a warehouse.';
    const warehouseAnswers = buildReport(warehouse).answers;
    assert.equal(warehouseAnswers['3.1'].status, 'Sample');
    assert.deepEqual(warehouseAnswers['3.2'], { value: 'Warehouse', status: 'Suggested', note: 'Run analysis · scene description' });
    for (const scene of ['This is not a warehouse.', 'possible warehouse', 'maybe a warehouse', 'warehouse cannot be confirmed']) {
      const changed = structuredClone(partial);
      changed.observations.scene_description = scene;
      assert.equal(buildReport(changed).answers['3.2'].status, 'Sample', scene);
    }
    const located = structuredClone(partial);
    located.observations.fire_sources[0].location_description = 'Warehouse aisle position 1, near shelving';
    assert.deepEqual(suggested(buildReport(located).answers), [], 'location text is not 3.2 or 4.2k');
    const hidden = structuredClone(fresh);
    hidden.observations.scene_description = null;
    hidden.observations.fire_sources = [{ id: 'V1:A1', description: 'flames in the warehouse', location_description: 'beside the right rack' }];
    hidden.confirmed_targets = [{ fire_id: 'T1', members: ['V1:A1'] }];
    hidden.excluded = [{ id: 'V1:A1', reason: 'out of frame' }];
    assert.deepEqual(suggested(buildReport(hidden).answers), []);
    function fakeDocument() {
      const make = tag => ({
        tag, className: '', attrs: {}, children: [], text: null,
        setAttribute(name, value) { this.attrs[name] = String(value); },
        get id() { return this.attrs.id || ''; }, set id(value) { this.attrs.id = value; },
        append(...nodes) { this.children.push(...nodes); },
        set textContent(value) { this.text = value == null ? '' : String(value); },
        get textContent() { return this.text != null ? this.text : this.children.map(child => child.textContent || '').join(''); },
      });
      return { createElement: tag => make(tag), createTextNode: text => ({ textContent: text, children: [], attrs: {}, className: '' }) };
    }
    function collect(node, out = []) {
      out.push(node);
      for (const child of node.children || []) collect(child, out);
      return out;
    }
    const rendered = renderIncidentReport(fakeDocument(), buildReport(fresh, '2026-10-17T17:05:00Z'));
    const nodes = collect(rendered);
    const text = rendered.textContent;
    assert.equal(rendered.attrs['aria-label'], 'IRS WORKSHEET');
    assert.equal(nodes.find(node => node.tag === 'h3').textContent, 'IRS WORKSHEET');
    assert.equal(nodes.some(node => String(node.className).includes('irs-evidence-annex') || String(node.className).includes('irs-observation')), false);
    assert.equal(text.includes('Video evidence'), false);
    assert.equal(text.includes('Historical reference worksheet — not current FaRDaP or a validated submission.'), false);
    assert.equal(text.includes('v1-0p'), false);
    assert.equal(text.includes('v1-0n'), false);
    assert.equal(text.includes('numbered question headings only'), false);
    assert.equal(text.includes('Vision draft'), false);
    assert.equal(/synthetic/i.test(text), false);
    assert.equal(text.includes('DEMO · SAMPLE CONTENT · NOT FOR INCIDENT SUBMISSION'), false);
    assert.equal(nodes.filter(node => node.attrs && node.attrs['data-question-id']).length, 158);
    assert.equal(nodes.filter(node => node.tag === 'textarea').length, 158, 'every answer box is editable');
    const answerBox = id => nodes.find(node => node.className === 'irs-answer' && node.attrs['aria-label'] === 'Answer ' + id);
    const answerValue = id => answerBox(id).children.find(node => node.tag === 'textarea').value;
    const answerStatus = id => answerBox(id).attrs['data-status'];
    assert.equal(answerValue('3.1'), 'Fire'); assert.equal(answerStatus('3.1'), 'Suggested');
    for (const id of ['1.1', '2.1', '3.2', '4.1', '4.2*', '4.2k', '4.3a/b', '5.1', '7.3', '8.1', '8.6', '8.14', '9.1']) { assert.ok(answerValue(id).trim(), id); assert.equal(answerStatus(id), 'Sample', id); }
    console.log('PASS: analysis eligibility, isolated snapshots, invalidation, suggested/sample answers and sensitive value redaction');
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
