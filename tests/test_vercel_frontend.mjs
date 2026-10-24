import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';

test('hosting gateway preserves assets and streams API data with a private server token', async () => {
  const secret = 'test-token-'.repeat(8);
  const seen = [];
  const upstream = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    seen.push({ url: req.url, headers: req.headers, body: Buffer.concat(chunks) });
    if (req.headers.range) {
      res.writeHead(206, { 'content-type': 'video/mp4', 'content-range': 'bytes 1-3/6', 'content-length': '3' }); res.end('bcd');
    } else { res.writeHead(200, { 'content-type': 'application/json' }); res.end('{"ok":true}'); }
  });
  upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
  const child = spawn(process.execPath, ['ops/vercel_frontend.mjs'], {
    cwd: new URL('..', import.meta.url),
    env: { ...process.env, PORT: '0', SCENE2REAL_BACKEND_URL: `http://127.0.0.1:${upstream.address().port}`, SCENE2REAL_SITE_TOKEN: secret },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    const output = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Gateway did not start')), 5000);
      child.stdout.once('data', data => { clearTimeout(timer); resolve(data.toString()); });
      child.once('exit', code => { clearTimeout(timer); reject(new Error(`Gateway exited ${code}`)); });
    });
    const base = `http://127.0.0.1:${output.match(/listening on (\d+)/)[1]}`;
    let response = await fetch(base + '/');
    const html = await response.text();
    assert.equal(response.status, 200);
    assert.match(html, /IRS WORKSHEET/i);
    assert.ok(!html.includes(secret));
    response = await fetch(base + '/incident_report.js');
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /javascript/);
    response = await fetch(base + '/index.html', { method: 'HEAD' });
    assert.equal(response.status, 200); assert.ok(Number(response.headers.get('content-length')) > 1000); assert.equal(await response.text(), '');
    for (const path of ['/%2e%2e%2fops/vercel_frontend.mjs', '/.env', '/bad%ZZ']) {
      response = await fetch(base + path); assert.equal(response.status, 404);
    }
    response = await fetch(base + '/index.html', { method: 'POST' }); assert.equal(response.status, 405);
    const payload = Buffer.from([0, 255, 13, 10, 128, 4]);
    response = await fetch(base + '/api/runs?check=1', { method: 'POST', headers: { authorization: 'untrusted-client-token', cookie: 'private-browser-cookie', 'content-type': 'application/octet-stream' }, body: payload });
    assert.equal(response.status, 200); assert.deepEqual(await response.json(), { ok: true });
    assert.equal(seen[0].url, '/api/runs?check=1');
    assert.equal(seen[0].headers.authorization, `Bearer ${secret}`);
    assert.equal(seen[0].headers.cookie, undefined);
    assert.deepEqual(seen[0].body, payload);
    response = await fetch(base + '/api/runs/test/video', { headers: { range: 'bytes=1-3' } });
    assert.equal(response.status, 206); assert.equal(response.headers.get('content-range'), 'bytes 1-3/6'); assert.equal(await response.text(), 'bcd');
    await new Promise(resolve => upstream.close(resolve));
    response = await fetch(base + '/api/health'); assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { detail: 'Backend unavailable' });
  } finally {
    child.kill('SIGTERM');
    await once(child, 'exit');
    upstream.close();
  }
});
