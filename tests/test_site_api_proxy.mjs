import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import http from 'node:http';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import test from 'node:test';
import { gzipSync } from 'node:zlib';

const proxyPath = new URL('../ops/site_api_proxy.mjs', import.meta.url);

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}

async function unusedPort() {
  const server = http.createServer();
  const port = await listen(server);
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  return port;
}

async function waitForProxy(port, child) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`proxy exited with ${child.exitCode}`);
    try {
      return await fetch(`http://127.0.0.1:${port}/api/clips`);
    } catch {
      await delay(20);
    }
  }
  throw new Error('proxy did not start');
}

test('Site proxy requires the bearer token and forwards only authenticated API requests', async t => {
  const forwarded = [];
  const origin = http.createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    forwarded.push({
      method: request.method,
      url: request.url,
      authorization: request.headers.authorization,
      body: Buffer.concat(chunks).toString(),
    });
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({ ok: true, body: forwarded.at(-1).body }));
  });
  const originPort = await listen(origin);
  const proxyPort = await unusedPort();
  const secret = 'a'.repeat(64);
  const child = spawn(process.execPath, [proxyPath.pathname], {
    env: {
      ...process.env,
      SCENE2REAL_SITE_TOKEN: secret,
      SCENE2REAL_PROXY_UPSTREAM: `http://127.0.0.1:${originPort}`,
      SCENE2REAL_PROXY_PORT: String(proxyPort),
    },
    stdio: 'ignore',
  });
  t.after(async () => {
    child.kill('SIGTERM');
    await new Promise(resolve => child.once('exit', resolve));
    await new Promise(resolve => origin.close(resolve));
  });

  const unauthorized = await waitForProxy(proxyPort, child);
  assert.equal(unauthorized.status, 401);
  assert.equal(forwarded.length, 0);

  const nonApi = await fetch(`http://127.0.0.1:${proxyPort}/docs`, {
    headers: { authorization: `Bearer ${secret}` },
  });
  assert.equal(nonApi.status, 404);
  assert.equal(forwarded.length, 0);

  const absoluteTarget = await new Promise((resolve, reject) => {
    const request = http.request({
      hostname: '127.0.0.1',
      port: proxyPort,
      path: 'http://127.0.0.1:1/api/should-not-forward',
      headers: { authorization: `Bearer ${secret}` },
    }, resolve);
    request.once('error', reject);
    request.end();
  });
  assert.equal(absoluteTarget.statusCode, 400);
  assert.equal(forwarded.length, 0);

  const response = await fetch(`http://127.0.0.1:${proxyPort}/api/test`, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${secret}`,
      'content-type': 'text/plain',
    },
    body: 'preserve request body',
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true, body: 'preserve request body' });
  assert.deepEqual(forwarded, [{
    method: 'POST',
    url: '/api/test',
    authorization: undefined,
    body: 'preserve request body',
  }]);
});

test('Site proxy survives truncated responses and cancels disconnected clients', async t => {
  let originDisconnected;
  const disconnected = new Promise(resolve => { originDisconnected = resolve; });
  const origin = http.createServer((request, response) => {
    if (request.url === '/api/truncated') {
      response.writeHead(200, { 'content-length': '100' });
      response.write('partial');
      setTimeout(() => response.destroy(), 50);
    } else if (request.url === '/api/stream') {
      response.writeHead(200);
      response.write('first chunk');
      response.once('close', originDisconnected);
    } else {
      response.end('healthy');
    }
  });
  const originPort = await listen(origin);
  const proxyPort = await unusedPort();
  const secret = 'b'.repeat(64);
  const child = spawn(process.execPath, [proxyPath.pathname], {
    env: {
      ...process.env,
      SCENE2REAL_SITE_TOKEN: secret,
      SCENE2REAL_PROXY_UPSTREAM: `http://127.0.0.1:${originPort}`,
      SCENE2REAL_PROXY_PORT: String(proxyPort),
    },
    stdio: 'ignore',
  });
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill('SIGTERM');
      await once(child, 'exit');
    }
    origin.closeAllConnections();
    await new Promise(resolve => origin.close(resolve));
  });

  await waitForProxy(proxyPort, child);
  const headers = { authorization: `Bearer ${secret}` };
  const truncated = await fetch(`http://127.0.0.1:${proxyPort}/api/truncated`, { headers });
  await assert.rejects(truncated.text());
  const healthy = await fetch(`http://127.0.0.1:${proxyPort}/api/healthy`, { headers });
  assert.equal(await healthy.text(), 'healthy');

  await new Promise((resolve, reject) => {
    const request = http.get(`http://127.0.0.1:${proxyPort}/api/stream`, { headers }, response => {
      response.once('data', () => { response.destroy(); resolve(); });
    });
    request.once('error', reject);
  });
  await Promise.race([
    disconnected,
    delay(2000).then(() => { throw new Error('origin stream was not closed'); }),
  ]);
  const afterDisconnect = await fetch(`http://127.0.0.1:${proxyPort}/api/healthy`, { headers });
  assert.equal(await afterDisconnect.text(), 'healthy');
});

test('Unauthenticated health probe reports the origin state and supports HEAD', async t => {
  let status = 200;
  const origin = http.createServer((request, response) => {
    assert.equal(request.url, '/api/health');
    response.writeHead(status);
    response.end('{"status":"ok"}');
  });
  const originPort = await listen(origin);
  const proxyPort = await unusedPort();
  const child = spawn(process.execPath, [proxyPath.pathname], {
    env: {
      ...process.env,
      SCENE2REAL_SITE_TOKEN: 'c'.repeat(64),
      SCENE2REAL_PROXY_UPSTREAM: `http://127.0.0.1:${originPort}`,
      SCENE2REAL_PROXY_PORT: String(proxyPort),
      SCENE2REAL_PROXY_HOST: '0.0.0.0',
    },
    stdio: 'ignore',
  });
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill('SIGTERM');
      await once(child, 'exit');
    }
    origin.closeAllConnections();
    if (origin.listening) await new Promise(resolve => origin.close(resolve));
  });

  await waitForProxy(proxyPort, child);
  const url = `http://127.0.0.1:${proxyPort}/healthz`;
  const healthy = await fetch(url);
  assert.equal(healthy.status, 200);
  assert.deepEqual(await healthy.json(), { status: 'ok' });
  const head = await fetch(url, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
  assert.equal((await fetch(url, { method: 'POST' })).status, 405);
  status = 500;
  assert.equal((await fetch(url)).status, 503);
  origin.closeAllConnections();
  await new Promise(resolve => origin.close(resolve));
  assert.equal((await fetch(url)).status, 503);
});

test('Proxy forwards correctly if an origin sends compressed content anyway', async t => {
  const origin = http.createServer((request, response) => {
    assert.equal(request.headers['accept-encoding'], 'identity');
    const body = gzipSync('complete response');
    response.writeHead(200, { 'content-encoding': 'gzip', 'content-length': body.length });
    response.end(body);
  });
  const originPort = await listen(origin);
  const proxyPort = await unusedPort();
  const secret = 'd'.repeat(64);
  const child = spawn(process.execPath, [proxyPath.pathname], {
    env: {
      ...process.env,
      SCENE2REAL_SITE_TOKEN: secret,
      SCENE2REAL_PROXY_UPSTREAM: `http://127.0.0.1:${originPort}`,
      SCENE2REAL_PROXY_PORT: String(proxyPort),
    },
    stdio: 'ignore',
  });
  t.after(async () => {
    child.kill('SIGTERM');
    await once(child, 'exit');
    origin.closeAllConnections();
    await new Promise(resolve => origin.close(resolve));
  });
  await waitForProxy(proxyPort, child);
  const result = await fetch(`http://127.0.0.1:${proxyPort}/api/compressed`, {
    headers: { authorization: `Bearer ${secret}` },
  });
  assert.equal(result.headers.get('content-encoding'), null);
  assert.equal(result.headers.get('content-length'), null);
  assert.equal(await result.text(), 'complete response');
});
