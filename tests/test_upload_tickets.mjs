import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createUploadTickets, MAX_UPLOAD_BYTES } from '../ops/upload_tickets.mjs';

test('upload grants expire, are single-use, origin-bound and bounded in number', () => {
  let clock = 1000;
  const tickets = createUploadTickets('https://backend.example', () => clock);
  assert.equal(tickets.issue('https://frontend.example/path'), null);
  assert.equal(tickets.issue('http://untrusted.example'), null);
  const grant = tickets.issue('https://frontend.example');
  assert.equal(grant.url, 'https://backend.example/api/runs');
  assert.equal(tickets.consume(grant.token, 'https://other.example'), false);
  assert.equal(tickets.consume(grant.token, 'https://frontend.example'), true);
  assert.equal(tickets.consume(grant.token, 'https://frontend.example'), false);
  const expired = tickets.issue('https://frontend.example');
  clock += 120001;
  assert.equal(tickets.consume(expired.token, 'https://frontend.example'), false);
  for (let i = 0; i < 128; i++) assert.ok(tickets.issue('https://frontend.example'));
  assert.equal(tickets.issue('https://frontend.example'), null);
  assert.equal(createUploadTickets().issue('https://frontend.example'), null);
});

test('direct uploads require an authenticated grant and cannot access other APIs', async t => {
  const secret = 'test-private-service-token-'.repeat(3), clientOrigin = 'https://workbench.example';
  const seen = [];
  const upstream = http.createServer(async (req, res) => {
    let size = 0;
    for await (const chunk of req) size += chunk.length;
    seen.push({ url: req.url, headers: req.headers, size });
    res.writeHead(200, { 'content-type': 'application/json' }).end('{"run_id":"test-run"}');
  });
  upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
  const reservation = http.createServer(); reservation.listen(0, '127.0.0.1'); await once(reservation, 'listening');
  const port = reservation.address().port; await new Promise(resolve => reservation.close(resolve));
  const child = spawn(process.execPath, ['ops/site_api_proxy.mjs'], {
    cwd: new URL('..', import.meta.url),
    env: { ...process.env, SCENE2REAL_PROXY_PORT: String(port), SCENE2REAL_SITE_TOKEN: secret,
      SCENE2REAL_PROXY_UPSTREAM: `http://127.0.0.1:${upstream.address().port}`, SCENE2REAL_PUBLIC_ORIGIN: 'https://backend.example' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  t.after(async () => { child.kill('SIGTERM'); await once(child, 'exit'); upstream.closeAllConnections(); upstream.close(); });
  await Promise.race([once(child.stdout, 'data'), once(child, 'exit').then(() => { throw new Error('Proxy failed'); })]);
  const base = `http://127.0.0.1:${port}`;
  const issue = () => fetch(base + '/api/upload-ticket', {
    method: 'POST', headers: { authorization: `Bearer ${secret}`, 'content-type': 'application/json' }, body: JSON.stringify({ origin: clientOrigin }),
  });
  assert.equal((await fetch(base + '/api/upload-ticket', { method: 'POST' })).status, 401);
  let response = await issue(); const grant = await response.json();
  assert.equal(response.status, 200); assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.ok(!JSON.stringify(grant).includes(secret));
  const headers = { origin: clientOrigin, 'x-scene2real-upload-ticket': grant.token, 'content-type': 'multipart/form-data; boundary=test' };
  response = await fetch(base + '/api/runs', { method: 'OPTIONS', headers: { origin: clientOrigin, 'access-control-request-method': 'POST', 'access-control-request-headers': 'x-scene2real-upload-ticket,content-type' } });
  assert.equal(response.status, 204); assert.equal(response.headers.get('access-control-allow-origin'), clientOrigin);
  assert.equal(response.headers.get('access-control-allow-credentials'), null);
  assert.equal((await fetch(base + '/api/runs', { method: 'POST', headers: { ...headers, origin: 'https://other.example' }, body: 'test' })).status, 401);
  assert.equal((await fetch(base + '/api/runs/private', { headers })).status, 401);
  assert.equal((await fetch(base + '/api/runs', { headers })).status, 401);
  const body = Buffer.alloc(6 * 1024 * 1024, 97);
  response = await fetch(base + '/api/runs', { method: 'POST', headers, body });
  assert.equal(response.status, 200); assert.equal(response.headers.get('access-control-allow-origin'), clientOrigin);
  assert.equal(seen.length, 1); assert.equal(seen[0].size, body.length);
  assert.equal(seen[0].headers.authorization, undefined); assert.equal(seen[0].headers['x-scene2real-upload-ticket'], undefined);
  assert.equal((await fetch(base + '/api/runs', { method: 'POST', headers, body: 'replay' })).status, 401);
  const second = await (await issue()).json();
  const tooLarge = await new Promise((resolve, reject) => {
    const req = http.request(base + '/api/runs', { method: 'POST', headers: { ...headers, 'x-scene2real-upload-ticket': second.token, 'content-length': MAX_UPLOAD_BYTES + 1 } }, res => { res.resume(); resolve(res.statusCode); });
    req.on('error', reject); req.end();
  });
  assert.equal(tooLarge, 413); assert.equal(seen.length, 1);
});
