import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

// Stand-in for the mounted startup gate: records what boot() asks of the overlay.
function fakeStartup(revealed) {
  return {
    revealed, failures: [], steps: [], totals: [], reveals: 0, begun: 0,
    begin() { this.begun += 1; return undefined; },
    setTotal(total) { this.totals.push(total); }, announce() {}, step(label) { this.steps.push(label); },
    fail(message, retry) { this.failures.push({ message, retry }); },
    async reveal() { this.reveals += 1; this.revealed = true; },
  };
}

async function bootContext(startup, extra = {}) {
  const source = await readFile(new URL('../static/app.js', import.meta.url), 'utf8');
  const boot = source.slice(source.indexOf('(async function boot()'));
  const S = { clips: [], zones: {}, error: null, last: null, restoring: true };
  const context = {
    S, startup, location: { hash: '', search: '' }, URLSearchParams, render() {}, displayClipName: x => x, preloaded: [],
    async preloadDemoClips(clips, { onProgress }) { for (const clip of clips) { context.preloaded.push(clip.clip_id); onProgress({ clip, completed: 1, total: clips.length }); } return []; },
    ...extra,
  };
  await vm.runInNewContext(boot, context);
  return context;
}

test('retrying a failed initial load clears stale errors only when the new load succeeds', async () => {
  let unavailable = true;
  const startup = fakeStartup(false);
  const context = await bootContext(startup, {
    async api(path) {
      if (unavailable) throw { message: 'API origin unavailable', status: 502 };
      if (path === '/api/clips') return [{ clip_id: 'warehouse-test', label: 'Warehouse test' }];
      if (path === '/api/zones') return { left_rack: {} };
      throw new Error(`Unexpected request: ${path}`);
    },
  });
  const { S } = context;
  assert.equal(S.error.message, 'API origin unavailable');
  assert.equal(typeof S.last, 'function');
  assert.equal(startup.failures.length, 1, 'the startup overlay shows the failure');
  assert.equal(startup.failures[0].message, 'API origin unavailable');
  assert.equal(startup.failures[0].retry, S.last, 'the overlay retry is the same boot retry');
  assert.equal(startup.reveals, 0, 'a failed boot never reveals the workbench');
  await S.last();
  assert.equal(S.error.message, 'API origin unavailable', 'persistent failure stays visible');
  assert.equal(startup.failures.length, 2);
  assert.equal(startup.reveals, 0);
  unavailable = false;
  await S.last();
  assert.equal(S.error, null, 'a healthy retry removes the stale failure banner');
  assert.equal(S.last, null, 'successful startup does not retain an obsolete retry');
  assert.equal(S.clips[0].clip_id, 'warehouse-test');
  assert.ok(S.zones.left_rack);
  assert.deepEqual(context.preloaded, ['warehouse-test'], 'demo clips are buffered before reveal');
  assert.deepEqual(startup.totals.at(-1), 3, 'progress counts catalogue, zones and each clip');
  assert.deepEqual(startup.steps, ['clip catalogue', 'warehouse zones', 'Warehouse test']);
  assert.equal(startup.reveals, 1);
  assert.equal(startup.begun, 3, 'every gated attempt re-arms the watchdog');
});

test('a failed demo clip download keeps the overlay up with a retry instead of a falsely ready state', async () => {
  const startup = fakeStartup(false);
  let fail = true;
  const context = await bootContext(startup, {
    async api(path) { return path === '/api/clips' ? [{ clip_id: 'c1', label: 'Clip 1' }] : {}; },
    async preloadDemoClips() { if (fail) throw Object.assign(new Error('Clip 1: Incomplete video download'), { retryable: true }); return []; },
  });
  assert.equal(startup.reveals, 0);
  assert.equal(startup.failures[0].message, 'Clip 1: Incomplete video download');
  fail = false;
  await context.S.last();
  assert.equal(context.S.error, null);
  assert.equal(startup.reveals, 1);
});

test('after the workbench is revealed, boot retries use the in-workbench banner and never re-run the overlay', async () => {
  const startup = fakeStartup(true);
  let unavailable = true;
  const context = await bootContext(startup, {
    async api(path) {
      if (unavailable) throw { message: 'API origin unavailable', status: 502 };
      return path === '/api/clips' ? [{ clip_id: 'c1', label: 'Clip 1' }] : { left_rack: {} };
    },
    preloadDemoClips() { throw new Error('must not preload again after reveal'); },
  });
  assert.equal(startup.begun, 0);
  assert.equal(startup.failures.length, 0, 'overlay is not shown again');
  assert.equal(context.S.error.message, 'API origin unavailable');
  unavailable = false;
  await context.S.last();
  assert.equal(context.S.error, null);
  assert.equal(startup.reveals, 0);
  assert.equal(startup.begun, 0);
});

test('restoring a saved run waits for its GET/setRun before revealing, but not for a long-running operation', async () => {
  const startup = fakeStartup(false);
  let polls = 0;
  const seen = {};
  let releaseRun; const runLanded = new Promise(resolve => { releaseRun = resolve; });
  const booted = bootContext(startup, {
    location: { hash: '', search: '?run=r_1' },
    async api(path) {
      if (path === '/api/clips') return [];
      if (path === '/api/zones') return {};
      if (path === '/api/runs/r_1') { await runLanded; return { run_id: 'r_1', state: 'uploaded' }; }
      if (path === '/api/runs/r_1/operations') return { id: 'op', run_id: 'r_1', operation: 'analyse', status: 'running' };
      throw new Error(`Unexpected request: ${path}`);
    },
    setRun(run) { seen.run = run; seen.revealsAtSetRun = startup.reveals; },
    async loadTraj() {},
    async act(kind, fn) { seen.acted = kind; assert.equal(startup.reveals, 1, 'reveal was started before awaiting the operation'); await fn(); },
    async waitOperation() { polls += 1; },
    STAGE_RETRY: {},
  });
  await new Promise(r => setTimeout(r, 10));
  assert.equal(startup.reveals, 0, 'a slow saved-run fetch keeps the overlay up');
  assert.equal(seen.run, undefined);
  releaseRun();
  const context = await booted;
  assert.equal(context.S.error, null);
  assert.equal(seen.run.run_id, 'r_1');
  assert.equal(seen.revealsAtSetRun, 0, 'setRun happened before the reveal started');
  assert.deepEqual(startup.totals, [2, 3]);
  assert.deepEqual(startup.steps, ['clip catalogue', 'warehouse zones', 'saved run']);
  assert.equal(seen.acted, 'analyse');
  assert.equal(polls, 1);
  assert.equal(context.S.restoring, false);
});

test('a failed saved-run fetch reveals the workbench with the existing error banner instead of holding the overlay', async () => {
  const startup = fakeStartup(false);
  const context = await bootContext(startup, {
    location: { hash: '', search: '?run=r_missing' },
    async api(path) {
      if (path === '/api/clips') return [];
      if (path === '/api/zones') return {};
      throw Object.assign(new Error('run not found'), { status: 404 });
    },
    setRun() { assert.fail('setRun must not run for a missing run'); },
  });
  assert.equal(startup.failures.length, 0);
  assert.equal(startup.reveals, 1);
  assert.equal(context.S.error.message, 'run not found');
  assert.equal(typeof context.S.last, 'function');
});

test('demo clips are preloaded with display-normalised labels so error text never shows raw catalogue names', async () => {
  const startup = fakeStartup(false);
  const seen = [];
  const context = await bootContext(startup, {
    displayClipName: name => name.replace(/^Demo /, 'Warehouse ').replace(/ · Synthetic API-generated CCTV$/, ''),
    async api(path) { return path === '/api/clips' ? [{ clip_id: 'c1', label: 'Demo set 1 · West camera · Synthetic API-generated CCTV' }] : {}; },
    async preloadDemoClips(clips, { onProgress }) { for (const clip of clips) { seen.push(clip.label); onProgress({ clip, completed: 1, total: 1 }); } return []; },
  });
  assert.deepEqual(seen, ['Warehouse set 1 · West camera']);
  assert.deepEqual(startup.steps, ['clip catalogue', 'warehouse zones', 'Warehouse set 1 · West camera']);
  assert.equal(context.S.clips[0].label, 'Demo set 1 · West camera · Synthetic API-generated CCTV', 'the catalogue itself is untouched');
});
