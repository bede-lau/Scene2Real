import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

test('retrying a failed initial load clears stale errors only when the new load succeeds', async () => {
  const source = await readFile(new URL('../static/app.js', import.meta.url), 'utf8');
  const boot = source.slice(source.indexOf('(async function boot()'));
  const S = { clips: [], zones: {}, error: null, last: null, restoring: false };
  let unavailable = true;
  const context = {
    S, location: { hash: '', search: '' }, URLSearchParams, render() {},
    async api(path) {
      if (unavailable) throw { message: 'API origin unavailable', status: 502 };
      if (path === '/api/clips') return [{ clip_id: 'warehouse-test' }];
      if (path === '/api/zones') return { left_rack: {} };
      throw new Error(`Unexpected request: ${path}`);
    },
  };
  await vm.runInNewContext(boot, context);
  assert.equal(S.error.message, 'API origin unavailable');
  assert.equal(typeof S.last, 'function');
  await S.last();
  assert.equal(S.error.message, 'API origin unavailable', 'persistent failure stays visible');
  unavailable = false;
  await S.last();
  assert.equal(S.error, null, 'a healthy retry removes the stale failure banner');
  assert.equal(S.last, null, 'successful startup does not retain an obsolete retry');
  assert.equal(S.clips[0].clip_id, 'warehouse-test');
  assert.ok(S.zones.left_rack);
});
