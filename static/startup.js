// Startup gate: holds a full-screen loader until the catalogue and bundled demo clips are usable.
// Pure helpers take their dependencies as arguments so they can be exercised without a browser.
const DEMO_CACHE = 'scene2real-demo-clips-v1';
const DIGEST_HEADER = 'x-scene2real-sha256';
export const MIN_VISIBLE_MS = 3000;
export const WATCHDOG_MS = 45000;
const FONT_SETTLE_MS = 1500;

export const demoClipURL = clipId => `/api/clips/${encodeURIComponent(clipId)}/video`;
const hex = buffer => Array.from(new Uint8Array(buffer), b => b.toString(16).padStart(2, '0')).join('');
const digestOf = async (bytes, subtle = globalThis.crypto?.subtle) => subtle ? hex(await subtle.digest('SHA-256', bytes)) : null;
const etagDigest = etag => (String(etag || '').match(/^(?:W\/)?"?([0-9a-f]{64})"?$/i) || [])[1]?.toLowerCase() || null;
const isMp4 = bytes => bytes.byteLength > 16 && String.fromCharCode(...new Uint8Array(bytes, 4, 4)) === 'ftyp';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const reject = (message, retryable = true) => Object.assign(new Error(message), { retryable });

// Demo bytes retained in memory for display; populated from the Cache API or the network.
const retained = new Map();      // sha256 -> Blob
const objectURLs = new Map();    // sha256 -> blob: URL currently handed to a <video>

async function openCache(caches = globalThis.caches) {
  if (!caches) return null;
  try { return await caches.open(DEMO_CACHE); } catch { return null; }
}

// Validate a response body as a complete MP4 and return {bytes, sha256}; throws when unusable.
async function readMp4(response, expectedSha, subtle) {
  if (response.status !== 200) throw reject(`Unexpected response (${response.status})`);
  const type = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
  if (type && type !== 'video/mp4') throw reject(`Unexpected media type ${type || 'unknown'}`);
  const bytes = await response.arrayBuffer();
  const declared = Number(response.headers.get('content-length'));
  if (!bytes.byteLength || (Number.isFinite(declared) && declared > 0 && declared !== bytes.byteLength)) throw reject('Incomplete video download');
  if (!isMp4(bytes)) throw reject('Downloaded file is not an MP4');
  const sha256 = await digestOf(bytes, subtle) || etagDigest(response.headers.get(DIGEST_HEADER) || response.headers.get('etag'));
  if (expectedSha && sha256 && sha256 !== expectedSha) throw reject('Demo clip changed on the server; retry to refresh it');
  return { bytes, sha256 };
}

async function cachedMatch(cache, url, expectedSha, fetchImpl, subtle) {
  if (!cache) return null;
  let hit;
  try { hit = await cache.match(url); } catch { return null; }
  if (!hit) return null;
  const stored = etagDigest(hit.headers.get(DIGEST_HEADER));
  let current = expectedSha;
  if (!current && fetchImpl) {
    try {
      const head = await fetchImpl(url, { method: 'HEAD', cache: 'no-store' });
      current = head.ok ? etagDigest(head.headers.get('etag')) : null;
    } catch { current = null; }
  }
  if (!stored || !current || stored !== current) { try { await cache.delete(url); } catch { /* best effort */ } return null; }
  try {
    const { bytes, sha256 } = await readMp4(hit, current, subtle);
    return { bytes, sha256: sha256 || stored, fromCache: true };
  } catch { try { await cache.delete(url); } catch { /* best effort */ } return null; }
}

async function store(cache, url, bytes, sha256, filename) {
  if (!cache) return false;
  try {
    await cache.put(url, new Response(bytes, { headers: {
      'content-type': 'video/mp4', 'content-length': String(bytes.byteLength), [DIGEST_HEADER]: sha256,
      etag: `"${sha256}"`, 'content-disposition': `inline; filename="${filename || 'clip.mp4'}"` } }));
    return true;
  } catch { return false; } // quota denied or storage unavailable: memory fallback only
}

// Download the catalogue's demo clips with bounded concurrency. Resolves to an array of
// {clip_id, sha256, fromCache} after every clip is buffered locally, or throws the first failure.
// The first failure (or an external abort) cancels the whole attempt: in-flight transfers are
// aborted and anything they still deliver is discarded, so stale progress or results can never
// overwrite the reported error or leak into a later retry.
export async function preloadDemoClips(clips, { fetch: fetchImpl = globalThis.fetch, caches = globalThis.caches, subtle = globalThis.crypto?.subtle,
  concurrency = 3, attempts = 2, signal, onProgress = () => {} } = {}) {
  const attempt = new AbortController();
  let onCancel; const cancelledSignal = new Promise(resolve => { onCancel = resolve; });
  const cancel = () => { attempt.abort(); onCancel(); };
  if (signal?.aborted) cancel(); else signal?.addEventListener('abort', cancel, { once: true });
  const cancelled = () => attempt.signal.aborted;
  const checkpoint = () => { if (cancelled()) throw reject('Startup was cancelled'); };
  const cache = await openCache(caches);
  const queue = clips.map((clip, index) => ({ clip, index }));
  const results = new Array(clips.length);
  let completed = 0, failure = null;
  async function one({ clip, index }) {
    const url = demoClipURL(clip.clip_id);
    const expected = etagDigest(clip.media_sha256);
    checkpoint();
    let outcome = await cachedMatch(cache, url, expected, fetchImpl, subtle);
    checkpoint();
    for (let round = 1; !outcome; round += 1) {
      try {
        const response = await fetchImpl(url, { cache: 'no-store', signal: attempt.signal });
        checkpoint();
        const { bytes, sha256 } = await readMp4(response, expected, subtle);
        checkpoint();
        const digest = sha256 || expected;
        if (!digest) throw reject('Demo clip has no content digest');
        const persisted = await store(cache, url, bytes, digest, clip.filename);
        outcome = { bytes, sha256: digest, fromCache: false, persisted };
      } catch (error) {
        checkpoint();
        if (round >= attempts) throw reject(`${clip.label || clip.clip_id}: ${error.message || 'download failed'}`, true);
        await sleep(250 * round);
        checkpoint();
      }
    }
    checkpoint();
    retained.set(outcome.sha256, new Blob([outcome.bytes], { type: 'video/mp4' }));
    results[index] = { clip_id: clip.clip_id, sha256: outcome.sha256, fromCache: outcome.fromCache, persisted: outcome.persisted ?? true };
    completed += 1;
    onProgress({ completed, total: clips.length, clip });
  }
  const workers = Array.from({ length: Math.max(1, Math.min(concurrency, queue.length)) }, async () => {
    try { while (queue.length && !cancelled()) await one(queue.shift()); }
    catch (error) { if (!failure) failure = error; cancel(); }
  });
  // Settle as soon as every clip is ready or the attempt is cancelled; a lingering transfer that a
  // transport fails to abort is left to the checkpoints above, which discard whatever it delivers.
  try { await Promise.race([Promise.all(workers), cancelledSignal]); } finally { signal?.removeEventListener('abort', cancel); }
  if (failure) throw failure;
  if (cancelled()) throw reject('Startup was cancelled');
  if (cache) {
    const keep = new Set(clips.map(c => new URL(demoClipURL(c.clip_id), 'http://local').pathname));
    try { for (const request of await cache.keys()) if (!keep.has(new URL(request.url).pathname)) await cache.delete(request); } catch { /* best effort */ }
  }
  return results;
}

// Blob URL for a preloaded run reference; only when the stored digest matches downloaded bytes.
export function retainedClipURL(ref) {
  if (ref?.kind !== 'preloaded') return null;
  const sha256 = etagDigest(ref.sha256);
  const blob = sha256 && retained.get(sha256);
  if (!blob) return null;
  let url = objectURLs.get(sha256);
  if (!url) { url = URL.createObjectURL(blob); objectURLs.set(sha256, url); }
  return url;
}
export function releaseClipURL(url) {
  if (!url || !url.startsWith('blob:')) return;
  for (const [sha256, active] of objectURLs) if (active === url) { objectURLs.delete(sha256); URL.revokeObjectURL(url); }
}
export const retainedClipCount = () => retained.size;

// Startup controller: minimum visible time plus real readiness, finite watchdog, retry.
// begin() returns the attempt's AbortSignal; passing it back as `token` to the other methods makes
// calls from a superseded attempt (an earlier boot that was retried or timed out) no-ops.
export function createStartupGate(view, { minVisibleMs = MIN_VISIBLE_MS, watchdogMs = WATCHDOG_MS, now = () => performance.now(), startedAt = null,
  setTimer = (fn, ms) => setTimeout(fn, ms), clearTimer = id => clearTimeout(id), reducedMotion = false, fontsReady = null, fontSettleMs = FONT_SETTLE_MS } = {}) {
  const current = token => token === undefined || token === gate.signal;
  const gate = {
    state: 'loading', revealed: false, startedAt: startedAt ?? now(), progress: { completed: 0, total: 0 }, controller: null, signal: null, watchdog: null, revealing: null,
    announce(detail, token) { if (gate.state === 'loading' && current(token)) view.setDetail(detail); },
    setTotal(total, token) {
      if (gate.state !== 'loading' || !current(token)) return;
      gate.progress = { completed: 0, total }; view.setProgress(0, total);
    },
    step(label, token) {
      if (gate.state !== 'loading' || !current(token)) return; // never overwrite a reported failure
      gate.progress.completed += 1;
      view.setProgress(gate.progress.completed, gate.progress.total);
      view.setDetail(`${gate.progress.completed} of ${gate.progress.total} ready · ${label}`);
    },
    begin(onTimeout) {
      if (gate.revealed) return null;
      gate.state = 'loading';
      view.clearError();
      gate.controller?.abort();
      gate.controller = typeof AbortController === 'function' ? new AbortController() : null;
      gate.signal = gate.controller?.signal ?? null;
      if (gate.watchdog) clearTimer(gate.watchdog);
      const signal = gate.signal;
      gate.watchdog = setTimer(() => {
        if (gate.state !== 'loading' || !current(signal)) return;
        gate.controller?.abort();
        gate.fail(`Startup took longer than ${Math.round(watchdogMs / 1000)} seconds. Check the connection and retry.`, onTimeout, signal);
      }, watchdogMs);
      return signal;
    },
    fail(message, retry, token) {
      if (gate.revealed || gate.state === 'ready' || !current(token)) return;
      gate.state = 'error';
      gate.controller?.abort();
      if (gate.watchdog) { clearTimer(gate.watchdog); gate.watchdog = null; }
      view.showError(message, retry ? () => { gate.lastRetry = retry; retry(); } : null);
    },
    // Resolves once the minimum time has elapsed and the overlay has left; never before readiness,
    // and never for an attempt that has since failed or been superseded by a retry.
    async reveal(token) {
      if (gate.revealing) return gate.revealing;
      if (gate.state !== 'loading' || !current(token)) return;
      gate.revealing = (async () => {
        gate.state = 'ready';
        if (gate.watchdog) { clearTimer(gate.watchdog); gate.watchdog = null; }
        if (fontsReady) await Promise.race([fontsReady.catch(() => {}), new Promise(resolve => setTimer(resolve, fontSettleMs))]);
        const remaining = gate.startedAt + minVisibleMs - now();
        if (remaining > 0) await new Promise(resolve => setTimer(resolve, remaining));
        view.setDetail('Workbench ready');
        await view.leave(reducedMotion);
        gate.revealed = true;
      })();
      return gate.revealing;
    },
  };
  return gate;
}

// Binds the controller to the loader markup in index.html.
export function mountStartupGate(doc = document, options = {}) {
  const root = doc.getElementById('startup-loader');
  const app = doc.querySelector('.app');
  const detail = doc.getElementById('startup-detail'), progress = doc.getElementById('startup-progress'), retry = doc.getElementById('startup-retry');
  const main = doc.getElementById('main');
  const boot = globalThis.__scene2realStartup;
  boot?.alive?.();
  const reducedMotion = !!globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const view = {
    setDetail(text) { if (detail) detail.textContent = text; },
    setProgress(value, max) {
      if (!progress) return;
      const total = Math.max(1, max), done = Math.min(value, total);
      progress.hidden = false;
      progress.setAttribute('aria-valuemax', String(total)); progress.setAttribute('aria-valuenow', String(done));
      progress.firstElementChild?.style.setProperty('--p', String(done / total));
    },
    clearError() { root?.classList.remove('has-error'); if (retry) { retry.hidden = true; retry.onclick = null; } root?.setAttribute('aria-busy', 'true'); },
    showError(message, onRetry) {
      root?.classList.add('has-error'); root?.setAttribute('aria-busy', 'false');
      if (detail) detail.textContent = message;
      if (retry) { retry.hidden = !onRetry; retry.onclick = onRetry; if (onRetry) retry.focus(); }
    },
    // Fades the overlay out and removes it (which also stops the decorative animation).
    leave(instant) {
      return new Promise(resolve => {
        if (!root) return resolve();
        root.setAttribute('aria-busy', 'false');
        if (app) { app.inert = false; app.removeAttribute('inert'); app.removeAttribute('aria-hidden'); }
        doc.documentElement.dataset.startup = 'ready';
        const finish = () => { const refocus = root.contains(doc.activeElement); root.remove(); if (refocus) main?.focus({ preventScroll: true }); resolve(); };
        if (instant) return finish();
        root.classList.add('is-leaving');
        let done = false; const once = () => { if (!done) { done = true; finish(); } };
        root.addEventListener('transitionend', once, { once: true });
        setTimeout(once, 500);
      });
    },
  };
  const fontsReady = doc.fonts?.ready || null;
  return createStartupGate(view, { reducedMotion, fontsReady, startedAt: Number.isFinite(boot?.armed) ? boot.armed : null, ...options });
}
