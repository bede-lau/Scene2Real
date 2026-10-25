import test from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { MIN_VISIBLE_MS, createStartupGate, demoClipURL, preloadDemoClips, releaseClipURL, retainedClipCount, retainedClipURL } from '../static/startup.js';

const subtle = webcrypto.subtle;
const hex = buffer => Array.from(new Uint8Array(buffer), b => b.toString(16).padStart(2, '0')).join('');
const sha = async bytes => hex(await subtle.digest('SHA-256', bytes));
const mp4 = seed => { const b = new Uint8Array(64); b.set([0, 0, 0, 24, 0x66, 0x74, 0x79, 0x70], 0); b[20] = seed; return b; };
const clipsFor = async files => Promise.all(Object.entries(files).map(async ([clip_id, bytes]) => ({ clip_id, label: clip_id, filename: `${clip_id}.mp4`, duration_s: 5, media_sha256: await sha(bytes) })));
const response = (bytes, init = {}) => new Response(bytes, { status: 200, headers: { 'content-type': 'video/mp4', 'content-length': String(bytes.byteLength), ...init.headers }, ...init });

class FakeCache {
  constructor({ quota = Infinity } = {}) { this.store = new Map(); this.quota = quota; this.puts = 0; }
  async match(url) { const hit = this.store.get(url); return hit ? hit.clone() : undefined; }
  async put(url, res) { this.puts += 1; if (this.store.size >= this.quota) throw new DOMException('quota', 'QuotaExceededError'); this.store.set(url, res); }
  async delete(url) { return this.store.delete(typeof url === 'string' ? url : new URL(url.url).pathname); }
  async keys() { return [...this.store.keys()].map(url => new Request(new URL(url, 'http://local'))); }
}
const fakeCaches = cache => ({ open: async () => cache });

function server(files, { fail = () => null } = {}) {
  const log = [];
  return { log, async fetch(url, init = {}) {
    log.push({ url, method: init.method || 'GET' });
    const id = decodeURIComponent(url.match(/^\/api\/clips\/(.+)\/video$/)[1]);
    const forced = fail(id, log.filter(l => l.url === url).length);
    if (forced) return forced;
    const bytes = files[id];
    if (!bytes) return new Response('{"detail":"unknown"}', { status: 404, headers: { 'content-type': 'application/json' } });
    if (init.method === 'HEAD') return new Response(null, { status: 200, headers: { etag: `"${await sha(bytes)}"`, 'content-type': 'video/mp4' } });
    return response(bytes, { headers: { etag: `"${await sha(bytes)}"` } });
  } };
}

test('normal startup downloads every demo clip with bounded concurrency and reports real progress', async () => {
  const files = { a: mp4(1), b: mp4(2), c: mp4(3), d: mp4(4), e: mp4(5), f: mp4(6), g: mp4(7) };
  const clips = await clipsFor(files);
  let inflight = 0, peak = 0;
  const src = server(files);
  const fetch = async (...args) => { inflight += 1; peak = Math.max(peak, inflight); await new Promise(r => setTimeout(r, 5)); try { return await src.fetch(...args); } finally { inflight -= 1; } };
  const cache = new FakeCache();
  const progress = [];
  const results = await preloadDemoClips(clips, { fetch, caches: fakeCaches(cache), subtle, concurrency: 3, onProgress: p => progress.push(p.completed) });
  assert.equal(results.length, 7);
  assert.ok(results.every(r => !r.fromCache && r.persisted));
  assert.deepEqual(progress, [1, 2, 3, 4, 5, 6, 7]);
  assert.ok(peak <= 3 && peak >= 2, `concurrency bounded (peak ${peak})`);
  assert.equal(cache.store.size, 7);
  assert.ok([...cache.store.keys()].every(k => /^\/api\/clips\/[a-g]\/video$/.test(k)), 'only known demo assets are cached');
  assert.ok(retainedClipCount() >= 7);
});

test('warm cache reuses unchanged clips without downloading video bytes', async () => {
  const files = { a: mp4(11), b: mp4(12) };
  const clips = await clipsFor(files);
  const cache = new FakeCache();
  const first = server(files);
  await preloadDemoClips(clips, { fetch: first.fetch, caches: fakeCaches(cache), subtle });
  assert.equal(first.log.filter(l => l.method === 'GET').length, 2);
  const second = server(files);
  const results = await preloadDemoClips(clips, { fetch: second.fetch, caches: fakeCaches(cache), subtle });
  assert.deepEqual(second.log, [], 'no network requests when the catalogue digest matches the cached copy');
  assert.ok(results.every(r => r.fromCache));
});

test('a changed clip (catalogue digest differs from the cached copy) is re-downloaded, and stale entries are evicted', async () => {
  const cache = new FakeCache();
  const oldFiles = { a: mp4(21), gone: mp4(22) };
  await preloadDemoClips(await clipsFor(oldFiles), { fetch: server(oldFiles).fetch, caches: fakeCaches(cache), subtle });
  const newFiles = { a: mp4(23) };
  const src = server(newFiles);
  const results = await preloadDemoClips(await clipsFor(newFiles), { fetch: src.fetch, caches: fakeCaches(cache), subtle });
  assert.equal(src.log.filter(l => l.url === demoClipURL('a') && l.method === 'GET').length, 1);
  assert.equal(results[0].fromCache, false);
  assert.equal(results[0].sha256, await sha(newFiles.a));
  assert.deepEqual([...cache.store.keys()], [demoClipURL('a')], 'the removed clip no longer occupies the demo cache');
});

test('without a catalogue digest the cached copy is validated against the server ETag via HEAD', async () => {
  const files = { a: mp4(31) };
  const cache = new FakeCache();
  const clips = (await clipsFor(files)).map(({ media_sha256, ...rest }) => rest);
  await preloadDemoClips(clips, { fetch: server(files).fetch, caches: fakeCaches(cache), subtle });
  const warm = server(files);
  await preloadDemoClips(clips, { fetch: warm.fetch, caches: fakeCaches(cache), subtle });
  assert.deepEqual(warm.log.map(l => l.method), ['HEAD']);
  const changed = server({ a: mp4(32) });
  await preloadDemoClips(clips, { fetch: changed.fetch, caches: fakeCaches(cache), subtle });
  assert.deepEqual(changed.log.map(l => l.method), ['HEAD', 'GET']);
});

test('storage quota denial falls back to memory and startup still succeeds', async () => {
  const files = { a: mp4(41), b: mp4(42) };
  const cache = new FakeCache({ quota: 1 });
  const results = await preloadDemoClips(await clipsFor(files), { fetch: server(files).fetch, caches: fakeCaches(cache), subtle, concurrency: 1 });
  assert.deepEqual(results.map(r => r.persisted), [true, false]);
  assert.ok(results.every(r => retainedClipURL({ kind: 'preloaded', sha256: r.sha256 })), 'both clips are playable from memory');
  const none = await preloadDemoClips(await clipsFor(files), { fetch: server(files).fetch, caches: undefined, subtle });
  assert.ok(none.every(r => !r.fromCache && !r.persisted));
});

test('error, non-MP4, empty and truncated responses never count as loaded', async () => {
  const files = { a: mp4(51) };
  const clips = await clipsFor(files);
  const cases = {
    'Unexpected response (502)': () => new Response('bad gateway', { status: 502 }),
    'Unexpected media type text/html': () => new Response('<html>', { status: 200, headers: { 'content-type': 'text/html' } }),
    'Incomplete video download': () => response(mp4(51).slice(0, 20), { headers: { 'content-length': '64' } }),
    'Downloaded file is not an MP4': () => response(new Uint8Array(64)),
  };
  for (const [message, make] of Object.entries(cases)) {
    const src = server(files, { fail: () => make() });
    await assert.rejects(preloadDemoClips(clips, { fetch: src.fetch, caches: fakeCaches(new FakeCache()), subtle, attempts: 1 }), err => err.message === `a: ${message}` && err.retryable);
  }
  const empty = server(files, { fail: () => new Response(new Uint8Array(0), { status: 200, headers: { 'content-type': 'video/mp4' } }) });
  await assert.rejects(preloadDemoClips(clips, { fetch: empty.fetch, caches: fakeCaches(new FakeCache()), subtle, attempts: 1 }), /Incomplete video download/);
  const cache = new FakeCache();
  const flaky = server(files, { fail: (id, n) => (n === 1 ? new Response('', { status: 503 }) : null) });
  const results = await preloadDemoClips(clips, { fetch: flaky.fetch, caches: fakeCaches(cache), subtle, attempts: 2 });
  assert.equal(results[0].fromCache, false);
  assert.equal(flaky.log.length, 2, 'one bounded retry');
  assert.equal(cache.store.size, 1, 'only the verified download is persisted');
});

test('digest mismatch never substitutes wrong footage', async () => {
  const served = { a: mp4(61) };
  const clips = await clipsFor({ a: mp4(62) });
  const cache = new FakeCache();
  await assert.rejects(preloadDemoClips(clips, { fetch: server(served).fetch, caches: fakeCaches(cache), subtle, attempts: 1 }), /Demo clip changed on the server/);
  assert.equal(cache.store.size, 0);
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: clips[0].media_sha256 }), null, 'the expected digest has no bytes');
  await preloadDemoClips(await clipsFor(served), { fetch: server(served).fetch, caches: fakeCaches(cache), subtle });
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: clips[0].media_sha256 }), null, 'a run ref with a different sha256 does not get the downloaded bytes');
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: 'not-a-digest' }), null);
});

test('only preloaded refs with a matching sha256 reuse a Blob URL; uploads keep streaming', async () => {
  const files = { a: mp4(71) };
  const [clip] = await clipsFor(files);
  const cache = new FakeCache();
  await preloadDemoClips([clip], { fetch: server(files).fetch, caches: fakeCaches(cache), subtle });
  const url = retainedClipURL({ kind: 'preloaded', sha256: clip.media_sha256 });
  assert.match(url, /^blob:/);
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: clip.media_sha256 }), url, 'the same Blob URL is reused while retained');
  assert.equal(retainedClipURL({ kind: 'upload', sha256: clip.media_sha256 }), null, 'uploaded footage is never served from the demo cache');
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: 'f'.repeat(64) }), null);
  assert.equal(retainedClipURL(undefined), null);
  assert.deepEqual([...cache.store.keys()], [demoClipURL('a')], 'uploads are not written to the cache');
  releaseClipURL(url);
  assert.notEqual(retainedClipURL({ kind: 'preloaded', sha256: clip.media_sha256 }), url, 'a released URL is not handed out again');
  releaseClipURL('/api/runs/r_1/video'); // streaming URLs are ignored
  releaseClipURL(url); // double release is safe
});

function fakeView() {
  const view = { detail: '', progress: null, error: null, retry: null, left: false, leaves: 0,
    setDetail(t) { view.detail = t; }, setProgress(v, m) { view.progress = [v, m]; }, clearError() { view.error = null; view.retry = null; },
    showError(message, retry) { view.error = message; view.detail = message; view.retry = retry; }, async leave() { view.leaves += 1; view.left = true; } };
  return view;
}
function clock() {
  let t = 0; const timers = new Map(); let id = 0;
  return { now: () => t, setTimer(fn, ms) { timers.set(++id, { at: t + ms, fn }); return id; }, clearTimer(i) { timers.delete(i); },
    async advance(ms) { const until = t + ms; for (;;) { const next = [...timers.entries()].filter(([, x]) => x.at <= until).sort((a, b) => a[1].at - b[1].at)[0]; if (!next) break; t = next[1].at; timers.delete(next[0]); next[1].fn(); await Promise.resolve(); } t = until; await new Promise(r => setImmediate(r)); } };
}

test('the minimum hold keeps the overlay for 3 s even when everything is ready instantly', async () => {
  const c = clock(), view = fakeView();
  const gate = createStartupGate(view, { now: c.now, setTimer: c.setTimer, clearTimer: c.clearTimer, startedAt: 0 });
  assert.equal(MIN_VISIBLE_MS, 3000);
  gate.begin(); gate.setTotal(2); gate.step('clip catalogue'); gate.step('warehouse zones');
  assert.deepEqual(view.progress, [2, 2]);
  assert.equal(view.detail, '2 of 2 ready · warehouse zones');
  const done = gate.reveal();
  await c.advance(2999);
  assert.equal(view.left, false, 'ready early still holds until 3000 ms');
  await c.advance(1);
  await done;
  assert.equal(view.left, true); assert.equal(view.detail, 'Workbench ready'); assert.equal(gate.revealed, true);
  assert.equal(gate.begin(), null, 'after reveal the gate never re-arms for route changes');
  gate.fail('late', () => {}); assert.equal(view.error, null, 'late failures do not resurrect the overlay');
});

test('slow downloads keep the app hidden past the minimum timer; the watchdog makes a stall actionable', async () => {
  const c = clock(), view = fakeView();
  const gate = createStartupGate(view, { now: c.now, setTimer: c.setTimer, clearTimer: c.clearTimer, startedAt: 0, watchdogMs: 45000 });
  let retries = 0;
  const signal = gate.begin(() => { retries += 1; });
  assert.ok(signal && !signal.aborted);
  await c.advance(10000);
  assert.equal(view.left, false, 'no reveal without readiness even long after 3 s');
  assert.equal(view.error, null);
  await c.advance(35000);
  assert.ok(signal.aborted, 'in-flight downloads are cancelled by the watchdog');
  assert.match(view.error, /longer than 45 seconds/);
  assert.equal(typeof view.retry, 'function');
  view.retry(); assert.equal(retries, 1);
  const again = gate.begin(() => {});
  assert.equal(view.error, null, 'retry clears the stale error'); assert.ok(again && !again.aborted);
  gate.reveal(); await c.advance(0); await c.advance(1);
  assert.equal(view.left, true, 'readiness after the minimum hold reveals immediately');
  await c.advance(60000);
  assert.equal(view.error, null, 'the cleared watchdog never fires after reveal');
});

test('font readiness is awaited but bounded', async () => {
  const c = clock(), view = fakeView();
  const neverFonts = new Promise(() => {});
  const gate = createStartupGate(view, { now: c.now, setTimer: c.setTimer, clearTimer: c.clearTimer, startedAt: 0, fontsReady: neverFonts, fontSettleMs: 4000 });
  gate.begin(); const done = gate.reveal();
  await c.advance(3000); assert.equal(view.left, false, 'still waiting on fonts past the minimum hold');
  await c.advance(1000); await done; assert.equal(view.left, true, 'font wait is capped at the settle budget');
  const view2 = fakeView(); const c2 = clock();
  const gate2 = createStartupGate(view2, { now: c2.now, setTimer: c2.setTimer, clearTimer: c2.clearTimer, startedAt: 0, fontsReady: Promise.reject(new Error('fonts')), fontSettleMs: 1500 });
  gate2.begin(); const done2 = gate2.reveal(); await c2.advance(3000); await done2; assert.equal(view2.left, true, 'a rejected fonts promise does not block');
  assert.equal(view2.leaves, 1); gate2.reveal(); assert.equal(view2.leaves, 1, 'reveal is idempotent');
});

// Regression: a failed worker cancels the attempt; a delayed sibling transfer that lands afterwards
// (even from a server that ignores the abort) must not report progress, retain bytes or count as a result.
test('a failed worker aborts the attempt and a delayed sibling completion is discarded', async () => {
  const files = { good: mp4(201), bad: mp4(202), slow: mp4(203) };
  const clips = await clipsFor(files);
  const before = retainedClipCount();
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: await sha(files.slow) }), null, 'precondition: slow bytes not retained yet');
  let releaseSlow; const slowLanded = new Promise(resolve => { releaseSlow = resolve; });
  const slowBytes = files.slow;
  const seen = [];
  const log = [];
  const fetchImpl = async (url, init = {}) => {
    const id = decodeURIComponent(url.match(/^\/api\/clips\/(.+)\/video$/)[1]);
    log.push({ id, method: init.method || 'GET', signal: init.signal });
    if (init.method === 'HEAD') return new Response(null, { status: 200, headers: { etag: `"${await sha(files[id])}"`, 'content-type': 'video/mp4' } });
    if (id === 'bad') return new Response('nope', { status: 500, headers: { 'content-type': 'text/plain' } });
    if (id === 'slow') { await slowLanded; return response(slowBytes, { headers: { etag: `"${await sha(slowBytes)}"` } }); }
    return response(files[id], { headers: { etag: `"${await sha(files[id])}"` } });
  };
  const cache = new FakeCache();
  const progress = [];
  const run = preloadDemoClips(clips, { fetch: fetchImpl, caches: fakeCaches(cache), subtle, concurrency: 3, attempts: 1, onProgress: p => progress.push(p.clip.clip_id) });
  // `bad` fails immediately while `slow` is still in flight.
  const error = await run.then(() => null, e => e);
  assert.ok(error, 'the attempt rejected');
  assert.match(error.message, /^bad: Unexpected response \(500\)/);
  const slowFetch = log.find(l => l.id === 'slow' && l.method === 'GET');
  assert.ok(slowFetch?.signal?.aborted, 'the in-flight sibling transfer was aborted with the attempt');
  seen.push(...progress);
  // The server ignores the abort and delivers valid bytes late: nothing may change.
  releaseSlow(); await new Promise(r => setTimeout(r, 20));
  assert.deepEqual(progress, seen, 'no progress callback after the failure');
  assert.ok(!progress.includes('slow'), 'the late completion never reported progress');
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: await sha(slowBytes) }), null, 'late bytes were not retained');
  assert.equal(cache.store.has(demoClipURL('slow')), false, 'late bytes were not cached');
  assert.ok(retainedClipCount() <= before + 1, 'only transfers that finished before the failure were retained');
  // Cache API reads do not obey AbortSignal: a cache hit that resolves after the failure is discarded too.
  let releaseHit; const hitLanded = new Promise(resolve => { releaseHit = resolve; });
  const lateCache = new FakeCache();
  await lateCache.put(demoClipURL('slow'), response(slowBytes, { headers: { 'x-scene2real-sha256': await sha(slowBytes) } }));
  const realMatch = lateCache.match.bind(lateCache);
  lateCache.match = async url => { if (url === demoClipURL('slow')) await hitLanded; return realMatch(url); };
  const progress2 = [];
  const failing = async (url, init = {}) => (url === demoClipURL('bad') ? new Response('nope', { status: 500 }) : fetchImpl(url, init));
  const error2 = await preloadDemoClips(clips, { fetch: failing, caches: fakeCaches(lateCache), subtle, concurrency: 3, attempts: 1, onProgress: p => progress2.push(p.clip.clip_id) }).then(() => null, e => e);
  assert.match(error2.message, /^bad: /, 'rejected promptly while the cache read was still pending');
  const retainedBefore = retainedClipCount();
  releaseHit(); await new Promise(r => setTimeout(r, 20));
  assert.ok(!progress2.includes('slow'), 'a late cache hit never reports progress');
  assert.equal(retainedClipCount(), retainedBefore, 'a late cache hit is not retained');
  assert.equal(retainedClipURL({ kind: 'preloaded', sha256: await sha(slowBytes) }), null);
  // An already-aborted signal cancels before any network or cache read.
  const ac = new AbortController(); ac.abort();
  const log2 = [];
  await assert.rejects(preloadDemoClips(clips, { fetch: async (url) => { log2.push(url); return response(mp4(1)); }, caches: fakeCaches(new FakeCache()), subtle, signal: ac.signal }), /cancelled/);
  assert.equal(log2.length, 0);
});

test('the gate keeps a reported error visible and only the newest attempt may progress or reveal', async () => {
  const c = clock(), view = fakeView();
  const gate = createStartupGate(view, { now: c.now, setTimer: c.setTimer, clearTimer: c.clearTimer, startedAt: 0 });
  const first = gate.begin(() => {});
  gate.setTotal(3, first); gate.step('clip catalogue', first);
  gate.fail('Clip 2: Incomplete video download', () => {}, first);
  assert.ok(first.aborted, 'failing aborts the attempt');
  gate.step('late clip', first); gate.announce('still going', first);
  assert.equal(view.detail, 'Clip 2: Incomplete video download', 'late progress never overwrites the error');
  assert.equal(await gate.reveal(first), undefined); await c.advance(5000);
  assert.equal(view.left, false, 'a failed attempt cannot reveal');
  // Retry: the old attempt is superseded; only the new token is honoured.
  const second = gate.begin(() => {});
  assert.equal(view.error, null); assert.notEqual(second, first); assert.ok(!second.aborted);
  gate.setTotal(2, second); gate.step('clip catalogue', second);
  gate.step('stale from attempt one', first); gate.fail('stale failure', () => {}, first);
  assert.equal(view.detail, '1 of 2 ready · clip catalogue'); assert.equal(view.error, null);
  await gate.reveal(first); await c.advance(5000);
  assert.equal(view.left, false, 'an old completion cannot reveal the new attempt');
  gate.step('warehouse zones', second);
  const done = gate.reveal(second); await c.advance(1); await done;
  assert.equal(view.left, true); assert.equal(gate.revealed, true);
});
